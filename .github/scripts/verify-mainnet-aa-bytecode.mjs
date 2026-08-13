#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import http from 'node:http';
import https from 'node:https';
import { join } from 'node:path';

const RPC_ATTEMPTS = 3;
const CONNECT_TIMEOUT_MS = 10_000;
const REQUEST_TIMEOUT_MS = 20_000;

function fail(message) {
  throw new Error(message);
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

function contractOutput(compilerOutput, target) {
  const compilerErrors = (compilerOutput.errors || []).filter((error) => error.severity === 'error');
  if (compilerErrors.length > 0) {
    fail(`${target.key}: compiler error: ${compilerErrors.map((error) => error.formattedMessage || error.message).join('\n')}`);
  }
  const output = compilerOutput.contracts?.[target.sourcePath]?.[target.contractName];
  if (!output) {
    fail(`${target.key}: missing compiler output for ${target.sourcePath}:${target.contractName}`);
  }
  return output;
}

function flattenImmutableRanges(immutableReferences) {
  if (!immutableReferences || typeof immutableReferences !== 'object' || Array.isArray(immutableReferences)) {
    fail('immutable references must be an object');
  }
  const ranges = [];
  for (const entries of Object.values(immutableReferences)) {
    if (!Array.isArray(entries)) {
      fail('immutable reference entries must be arrays');
    }
    for (const range of entries) {
      if (!Number.isSafeInteger(range?.start) || range.start < 0 || !Number.isSafeInteger(range?.length) || range.length <= 0) {
        fail('immutable range must contain nonnegative integer start and positive integer length');
      }
      ranges.push({ start: range.start, length: range.length });
    }
  }
  return ranges.sort((left, right) => left.start - right.start);
}

function maskRanges(bytecode, ranges) {
  const hex = bytecode.slice(2);
  const byteLength = hex.length / 2;
  const bytes = Buffer.from(hex, 'hex');
  let previousEnd = 0;
  for (const range of ranges) {
    const end = range.start + range.length;
    if (range.start < previousEnd) {
      fail('immutable ranges overlap');
    }
    if (end > byteLength) {
      fail('immutable range exceeds deployed bytecode');
    }
    bytes.fill(0, range.start, end);
    previousEnd = end;
  }
  return `0x${bytes.toString('hex')}`;
}

function sha256LowercaseHexString(bytecode) {
  return createHash('sha256').update(bytecode.toLowerCase(), 'utf8').digest('hex');
}

function rpcRequest(rpcUrl, payload) {
  const url = new URL(rpcUrl);
  const transport = url.protocol === 'https:' ? https : http;
  const body = JSON.stringify(payload);
  return new Promise((resolve, reject) => {
    const request = transport.request(
      url,
      {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'content-length': Buffer.byteLength(body),
        },
      },
      (response) => {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(chunk));
        response.on('end', () => {
          const responseBody = Buffer.concat(chunks).toString('utf8');
          if (response.statusCode < 200 || response.statusCode >= 300) {
            reject(new Error(`RPC HTTP ${response.statusCode}: ${responseBody}`));
            return;
          }
          try {
            resolve(JSON.parse(responseBody));
          } catch (error) {
            reject(new Error(`RPC returned invalid JSON: ${error.message}`));
          }
        });
      },
    );
    const connectTimer = setTimeout(() => request.destroy(new Error('RPC connect timeout')), CONNECT_TIMEOUT_MS);
    request.on('socket', (socket) => {
      const connected = () => clearTimeout(connectTimer);
      if (socket.connecting) {
        socket.once(url.protocol === 'https:' ? 'secureConnect' : 'connect', connected);
      } else {
        connected();
      }
    });
    request.setTimeout(REQUEST_TIMEOUT_MS, () => request.destroy(new Error('RPC request timeout')));
    request.on('error', (error) => {
      clearTimeout(connectTimer);
      reject(error);
    });
    request.end(body);
  });
}

let rpcId = 0;
async function rpcCall(rpcUrl, method, params) {
  let lastError;
  for (let attempt = 1; attempt <= RPC_ATTEMPTS; attempt += 1) {
    try {
      const response = await rpcRequest(rpcUrl, { jsonrpc: '2.0', id: ++rpcId, method, params });
      if (response.error) {
        fail(`RPC ${method} failed: ${JSON.stringify(response.error)}`);
      }
      if (!Object.hasOwn(response, 'result')) {
        fail(`RPC ${method} response is missing result`);
      }
      return response.result;
    } catch (error) {
      lastError = error;
      if (attempt < RPC_ATTEMPTS) {
        await new Promise((resolve) => setTimeout(resolve, 100 * attempt));
      }
    }
  }
  fail(`RPC ${method} failed after ${RPC_ATTEMPTS} attempts: ${lastError.message}`);
}

function normalizeBytecode(value, label) {
  if (typeof value !== 'string') {
    fail(`${label} must be a hex string`);
  }
  const normalized = value.toLowerCase().startsWith('0x') ? value.toLowerCase() : `0x${value.toLowerCase()}`;
  if (!/^0x[0-9a-f]+$/.test(normalized) || normalized.length % 2 !== 0) {
    fail(`${label} must be nonempty, even-length hex bytecode`);
  }
  return normalized;
}

function hasLinkReferences(linkReferences) {
  return Object.values(linkReferences || {}).some((libraries) =>
    Object.values(libraries || {}).some((references) => Array.isArray(references) && references.length > 0),
  );
}

async function verifyTarget({ artifactDirectory, rpcUrl, target }) {
  const compilerOutput = await readJson(join(artifactDirectory, target.compilerOutputFile));
  const output = contractOutput(compilerOutput, target);
  const deployed = output.evm?.deployedBytecode;
  if (!deployed) {
    fail(`${target.key}: missing deployed bytecode output`);
  }
  if (hasLinkReferences(deployed.linkReferences)) {
    fail(`${target.key}: compiler output contains unresolved library link references`);
  }
  if (typeof deployed.object === 'string' && deployed.object.includes('__$')) {
    fail(`${target.key}: compiler output contains unresolved library placeholders`);
  }
  const compiledCode = normalizeBytecode(deployed.object, `${target.key} compiled bytecode`);
  const immutableRanges = flattenImmutableRanges(deployed.immutableReferences || {});
  const liveCode = normalizeBytecode(await rpcCall(rpcUrl, 'eth_getCode', [target.address, 'latest']), `${target.key} live bytecode`);
  if (liveCode.length !== compiledCode.length) {
    fail(`${target.key}: live and compiled bytecode lengths differ`);
  }
  const liveHash = sha256LowercaseHexString(liveCode);
  if (liveHash !== target.expectedCodeSha256) {
    fail(`${target.key}: live bytecode hash ${liveHash} does not match ${target.expectedCodeSha256}`);
  }
  if (maskRanges(liveCode, immutableRanges) !== maskRanges(compiledCode, immutableRanges)) {
    fail(`${target.key}: live bytecode differs from compiler output outside immutable ranges`);
  }

  for (const check of target.rpcChecks || []) {
    const selector = output.evm?.methodIdentifiers?.[check.signature];
    if (typeof selector !== 'string' || !/^[0-9a-fA-F]{8}$/.test(selector)) {
      fail(`${target.key}: missing selector for ${check.signature}`);
    }
    const result = await rpcCall(rpcUrl, 'eth_call', [{ to: target.address, data: `0x${selector}` }, 'latest']);
    if (typeof result !== 'string' || !/^0x[0-9a-fA-F]{64}$/.test(result)) {
      fail(`${target.key}: ${check.signature} must return exactly one ABI word`);
    }
    const actualAddress = `0x${result.slice(-40)}`.toLowerCase();
    if (actualAddress !== check.expectedAddress.toLowerCase()) {
      fail(`${target.key}: ${check.signature} returned ${actualAddress}, expected ${check.expectedAddress}`);
    }
  }
  console.log(`${target.key}: compiler bytecode and Mainnet runtime match`);
}

async function main() {
  const [artifactDirectory, rpcUrl] = process.argv.slice(2);
  if (!artifactDirectory || !rpcUrl) {
    fail('usage: verify-mainnet-aa-bytecode.mjs <verification-artifact-directory> <rpc-url>');
  }
  const manifest = await readJson(join(artifactDirectory, 'verification-manifest.json'));
  if (manifest.version !== 2 || manifest.chainId !== 7979 || !Array.isArray(manifest.contracts) || manifest.contracts.length === 0) {
    fail('invalid Mainnet AA verification manifest');
  }
  for (const target of manifest.contracts) {
    await verifyTarget({ artifactDirectory, rpcUrl, target });
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});

export { contractOutput, flattenImmutableRanges, maskRanges, rpcCall, sha256LowercaseHexString, verifyTarget };

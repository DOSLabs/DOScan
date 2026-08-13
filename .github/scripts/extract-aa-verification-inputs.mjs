#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';

const COMPILER_VERSION = 'v0.8.28+commit.7893614a';
const SOLC_LONG_VERSION = COMPILER_VERSION.slice(1);
const EVM_VERSION = 'cancun';
const OPTIMIZER_RUNS = 1_000_000;
const ENTRY_POINT_ADDRESS = '0x4337084D9E255Ff0702461CF8895CE9E3b5Ff108';
const FACTORY_ADDRESS = '0xe908bff16d2a2ee257873708dbec8029ee9cd2cc';
const FACTORY_CONSTRUCTOR_ARGS =
  '0000000000000000000000004337084d9e255ff0702461cf8895ce9e3b5ff108';

const targets = [
  {
    key: 'entry-point',
    address: ENTRY_POINT_ADDRESS,
    contractName: 'EntryPoint',
    sourcePath: 'contracts/core/EntryPoint.sol',
    standardInputFile: 'entry-point.standard-input.json',
    licenseType: 'gnu_gpl_v3',
    spdxLicense: 'GPL-3.0',
    constructorArgs: '',
  },
  {
    key: 'simple-account-factory',
    address: FACTORY_ADDRESS,
    contractName: 'SimpleAccountFactory',
    sourcePath: 'contracts/accounts/SimpleAccountFactory.sol',
    standardInputFile: 'simple-account-factory.standard-input.json',
    licenseType: 'mit',
    spdxLicense: 'MIT',
    constructorArgs: FACTORY_CONSTRUCTOR_ARGS,
  },
];

function fail(message) {
  throw new Error(message);
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

function validateBuildInfo(buildInfo, target) {
  if (buildInfo.solcLongVersion !== SOLC_LONG_VERSION) {
    fail(
      `${target.contractName} compiler must be ${SOLC_LONG_VERSION}, got ${buildInfo.solcLongVersion}`,
    );
  }

  const input = buildInfo.input;
  const settings = input?.settings;
  if (input?.language !== 'Solidity') {
    fail(`${target.contractName} build language must be Solidity`);
  }
  if (settings?.evmVersion !== EVM_VERSION) {
    fail(`${target.contractName} EVM version must be ${EVM_VERSION}`);
  }
  if (settings?.optimizer?.enabled !== true || settings?.optimizer?.runs !== OPTIMIZER_RUNS) {
    fail(`${target.contractName} optimizer must be enabled with ${OPTIMIZER_RUNS} runs`);
  }
  if (settings?.viaIR !== true) {
    fail(`${target.contractName} build must use viaIR`);
  }
  const primarySource = input?.sources?.[target.sourcePath]?.content;
  if (typeof primarySource !== 'string') {
    fail(`${target.contractName} standard input is missing ${target.sourcePath}`);
  }
  if (!primarySource.includes(`SPDX-License-Identifier: ${target.spdxLicense}`)) {
    fail(`${target.contractName} source must declare SPDX license ${target.spdxLicense}`);
  }
  if (buildInfo.output?.contracts?.[target.sourcePath]?.[target.contractName] == null) {
    fail(`${target.contractName} is missing from compiler output`);
  }

  return input;
}

async function extractTarget(checkout, outputDirectory, target) {
  const debugPath = join(
    checkout,
    'artifacts',
    target.sourcePath,
    `${target.contractName}.dbg.json`,
  );
  const debugArtifact = await readJson(debugPath);
  if (typeof debugArtifact.buildInfo !== 'string' || debugArtifact.buildInfo.length === 0) {
    fail(`${target.contractName} debug artifact does not reference build-info`);
  }

  const buildInfoPath = resolve(dirname(debugPath), debugArtifact.buildInfo);
  const buildInfo = await readJson(buildInfoPath);
  const standardInput = validateBuildInfo(buildInfo, target);
  await writeFile(
    join(outputDirectory, target.standardInputFile),
    `${JSON.stringify(standardInput, null, 2)}\n`,
    'utf8',
  );
}

async function main() {
  const [, , checkoutArgument, outputArgument] = process.argv;
  if (!checkoutArgument || !outputArgument) {
    fail('usage: extract-aa-verification-inputs.mjs <account-abstraction-checkout> <output-directory>');
  }

  const checkout = resolve(checkoutArgument);
  const outputDirectory = resolve(outputArgument);
  await mkdir(outputDirectory, { recursive: true });

  for (const target of targets) {
    await extractTarget(checkout, outputDirectory, target);
  }

  const manifest = {
    version: 1,
    compilerVersion: COMPILER_VERSION,
    evmVersion: EVM_VERSION,
    optimizer: { enabled: true, runs: OPTIMIZER_RUNS },
    viaIR: true,
    contracts: targets,
  };
  await writeFile(
    join(outputDirectory, 'manifest.json'),
    `${JSON.stringify(manifest, null, 2)}\n`,
    'utf8',
  );
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

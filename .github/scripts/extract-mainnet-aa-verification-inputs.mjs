#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, posix, relative, resolve } from 'node:path';

const CHAIN_ID = 7979;
const ENTRY_POINT_ADDRESS = '0x0000000071727De22E5E9d8BAf0edAc6f37da032';
const KERNEL_ADDRESS = '0xd6CEDDe84be40893d153Be9d467CD6aD37875b28';
const KERNEL_FACTORY_ADDRESS = '0x2577507b78c2008Ff367261CB6285d44ba5eF2E9';
const ECDSA_VALIDATOR_ADDRESS = '0x845ADb2C711129d4f3966735eD98a9F09fC4cE57';
const FACTORY_STAKER_ADDRESS = '0xd703aaE79538628d27099B8c4f621bE4CCd142d5';

const OUTPUT_SELECTION = [
  'abi',
  'evm.deployedBytecode.object',
  'evm.deployedBytecode.immutableReferences',
  'evm.deployedBytecode.linkReferences',
  'evm.methodIdentifiers',
];

const targets = [
  {
    key: 'entry-point',
    address: ENTRY_POINT_ADDRESS,
    contractName: 'EntryPoint',
    sourcePath: 'contracts/core/EntryPoint.sol',
    diskSourcePath: 'contracts/core/EntryPoint.sol',
    standardInputFile: 'entry-point.standard-input.json',
    compilerOutputFile: 'entry-point.compiler-output.json',
    compilerPackage: 'solc-0.8.23',
    compilerVersion: 'v0.8.23+commit.f704f362',
    evmVersion: 'paris',
    optimizer: { enabled: true, runs: 1_000_000 },
    viaIR: true,
    metadata: { bytecodeHash: 'ipfs' },
    licenseType: 'gnu_gpl_v3',
    spdxLicense: 'GPL-3.0',
    constructorArgs: '',
    expectedCodeSha256: '4dcad467095cd9af58006b270475ac7591c6946bca08552f6789727097b51eae',
    rpcChecks: [],
    sourceFamily: 'account-abstraction',
  },
  {
    key: 'kernel',
    address: KERNEL_ADDRESS,
    contractName: 'Kernel',
    sourcePath: 'src/Kernel.sol',
    diskSourcePath: 'src/Kernel.sol',
    standardInputFile: 'kernel.standard-input.json',
    compilerOutputFile: 'kernel.compiler-output.json',
    compilerPackage: 'solc-0.8.28',
    compilerVersion: 'v0.8.28+commit.7893614a',
    evmVersion: 'prague',
    optimizer: { enabled: true, runs: 200 },
    viaIR: true,
    metadata: { appendCBOR: false, bytecodeHash: 'none' },
    licenseType: 'mit',
    spdxLicense: 'MIT',
    constructorArgs: '0000000000000000000000000000000071727de22e5e9d8baf0edac6f37da032',
    expectedCodeSha256: 'd13e7ff2bc90271659100c83f49ee6250555bbf26ed35c2315f243c6849a2127',
    rpcChecks: [{ signature: 'entrypoint()', expectedAddress: ENTRY_POINT_ADDRESS }],
    sourceFamily: 'kernel',
    soladySourcePrefix: 'lib/solady/src',
  },
  {
    key: 'kernel-factory',
    address: KERNEL_FACTORY_ADDRESS,
    contractName: 'KernelFactory',
    sourcePath: 'dependencies/kernel-v3.3/src/factory/KernelFactory.sol',
    diskSourcePath: 'src/factory/KernelFactory.sol',
    standardInputFile: 'kernel-factory.standard-input.json',
    compilerOutputFile: 'kernel-factory.compiler-output.json',
    compilerPackage: 'solc-0.8.28',
    compilerVersion: 'v0.8.28+commit.7893614a',
    evmVersion: 'prague',
    optimizer: { enabled: true, runs: 200 },
    viaIR: true,
    metadata: { appendCBOR: false, bytecodeHash: 'none' },
    licenseType: 'mit',
    spdxLicense: 'MIT',
    constructorArgs: '000000000000000000000000d6cedde84be40893d153be9d467cd6ad37875b28',
    expectedCodeSha256: '56443d7d18bfd62d5d69b04fc8207e439bf904166335dd7159e0eeef1cba2367',
    rpcChecks: [{ signature: 'implementation()', expectedAddress: KERNEL_ADDRESS }],
    sourceFamily: 'kernel',
    soladySourcePrefix: 'dependencies/solady-0.1.26/src',
  },
  {
    key: 'ecdsa-validator',
    address: ECDSA_VALIDATOR_ADDRESS,
    contractName: 'ECDSAValidator',
    sourcePath: 'src/validator/ECDSAValidator.sol',
    diskSourcePath: 'src/validator/ECDSAValidator.sol',
    standardInputFile: 'ecdsa-validator.standard-input.json',
    compilerOutputFile: 'ecdsa-validator.compiler-output.json',
    compilerPackage: 'solc-0.8.25',
    compilerVersion: 'v0.8.25+commit.b61c2a91',
    evmVersion: 'paris',
    optimizer: { enabled: true, runs: 200 },
    viaIR: true,
    metadata: { appendCBOR: false, bytecodeHash: 'none' },
    licenseType: 'mit',
    spdxLicense: 'MIT',
    constructorArgs: '',
    expectedCodeSha256: 'be711f07f49e57bf56c512b6f32f7c77d9ec1881c4051ed33a45cfad8c7a8b8e',
    rpcChecks: [],
    sourceFamily: 'kernel',
    soladySourcePrefix: 'lib/solady/src',
  },
  {
    key: 'factory-staker',
    address: FACTORY_STAKER_ADDRESS,
    contractName: 'FactoryStaker',
    sourcePath: 'src/factory/FactoryStaker.sol',
    diskSourcePath: 'src/factory/FactoryStaker.sol',
    standardInputFile: 'factory-staker.standard-input.json',
    compilerOutputFile: 'factory-staker.compiler-output.json',
    compilerPackage: 'solc-0.8.24',
    compilerVersion: 'v0.8.24+commit.e11b9ed9',
    evmVersion: 'paris',
    optimizer: { enabled: true, runs: 200 },
    viaIR: false,
    metadata: { appendCBOR: false, bytecodeHash: 'none' },
    licenseType: 'mit',
    spdxLicense: 'MIT',
    constructorArgs: '',
    expectedCodeSha256: 'f91091bf1260892a4d0b834494489fea55be2f2f968ad6b1abc1410531f2a2a1',
    rpcChecks: [],
    sourceFamily: 'kernel',
    soladySourcePrefix: 'lib/solady/src',
  },
];

function fail(message) {
  throw new Error(message);
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

function isInside(root, candidate) {
  const child = relative(root, candidate);
  return child === '' || (!child.startsWith('..') && !isAbsolute(child));
}

function validatePrimarySource(content, target) {
  if (!content.includes(`SPDX-License-Identifier: ${target.spdxLicense}`)) {
    fail(`${target.contractName} source must declare SPDX license ${target.spdxLicense}`);
  }
  if (!new RegExp(`\\b(?:abstract\\s+)?contract\\s+${target.contractName}\\b`).test(content)) {
    fail(`${target.contractName} is missing from ${target.sourcePath}`);
  }
}

function validateEntryPointBuildInfo(buildInfo, target) {
  const expectedLongVersion = target.compilerVersion.slice(1);
  if (buildInfo.solcLongVersion !== expectedLongVersion) {
    fail(`${target.contractName} compiler must be ${expectedLongVersion}`);
  }
  const input = buildInfo.input;
  const settings = input?.settings;
  if (input?.language !== 'Solidity') {
    fail(`${target.contractName} build language must be Solidity`);
  }
  if (settings?.evmVersion !== target.evmVersion) {
    fail(`${target.contractName} EVM version must be ${target.evmVersion}`);
  }
  if (
    settings?.optimizer?.enabled !== target.optimizer.enabled ||
    settings?.optimizer?.runs !== target.optimizer.runs
  ) {
    fail(`${target.contractName} optimizer settings are not canonical`);
  }
  if (settings?.viaIR !== true) {
    fail(`${target.contractName} build must use viaIR`);
  }
  if (settings?.metadata?.bytecodeHash !== 'ipfs') {
    fail(`${target.contractName} metadata bytecode hash must be ipfs`);
  }
  const primarySource = input?.sources?.[target.sourcePath]?.content;
  if (typeof primarySource !== 'string') {
    fail(`${target.contractName} standard input is missing ${target.sourcePath}`);
  }
  validatePrimarySource(primarySource, target);
  if (buildInfo.output?.contracts?.[target.sourcePath]?.[target.contractName] == null) {
    fail(`${target.contractName} is missing from compiler output`);
  }
  return structuredClone(input);
}

function importedPaths(content) {
  const paths = [];
  const expressions = [
    /import\s*["']([^"']+)["']\s*;/g,
    /import\s+[^;]*?\s+from\s*["']([^"']+)["']\s*;/g,
  ];
  for (const expression of expressions) {
    for (const match of content.matchAll(expression)) {
      paths.push(match[1]);
    }
  }
  return paths;
}

function resolveImport({ importerUnit, importerDiskPath, importPath, kernelCheckout, target }) {
  if (importPath.startsWith('.')) {
    const sourceUnit = posix.normalize(posix.join(posix.dirname(importerUnit), importPath));
    if (sourceUnit === '..' || sourceUnit.startsWith('../')) {
      fail(`Import escapes source-unit root: ${importPath}`);
    }
    return {
      sourceUnit,
      diskPath: resolve(dirname(importerDiskPath), importPath),
    };
  }

  if (importPath.startsWith('solady/')) {
    const suffix = importPath.slice('solady/'.length);
    return {
      sourceUnit: posix.join(target.soladySourcePrefix, suffix),
      diskPath: resolve(kernelCheckout, 'lib', 'solady', 'src', ...suffix.split('/')),
    };
  }

  fail(`Unsupported Kernel import: ${importPath}`);
}

async function collectKernelSources({ kernelCheckout, target }) {
  const root = resolve(kernelCheckout);
  const pending = [{
    sourceUnit: target.sourcePath,
    diskPath: resolve(root, ...target.diskSourcePath.split('/')),
  }];
  const sources = {};

  while (pending.length > 0) {
    const current = pending.pop();
    if (sources[current.sourceUnit] != null) {
      continue;
    }
    if (!isInside(root, current.diskPath)) {
      fail(`Kernel source escapes checkout: ${current.diskPath}`);
    }

    let content;
    try {
      content = await readFile(current.diskPath, 'utf8');
    } catch {
      fail(`Missing Kernel source ${current.sourceUnit} at ${current.diskPath}`);
    }
    sources[current.sourceUnit] = { content };

    for (const importPath of importedPaths(content)) {
      pending.push(resolveImport({
        importerUnit: current.sourceUnit,
        importerDiskPath: current.diskPath,
        importPath,
        kernelCheckout: root,
        target,
      }));
    }
  }

  return sources;
}

function canonicalOutputSelection() {
  return { '*': { '*': OUTPUT_SELECTION } };
}

async function entryPointInput(aaCheckout, target) {
  const debugPath = resolve(
    aaCheckout,
    'artifacts',
    'contracts',
    'core',
    'EntryPoint.sol',
    'EntryPoint.dbg.json',
  );
  const debugArtifact = await readJson(debugPath);
  if (typeof debugArtifact.buildInfo !== 'string' || debugArtifact.buildInfo.length === 0) {
    fail('EntryPoint debug artifact does not reference build-info');
  }
  const buildInfo = await readJson(resolve(dirname(debugPath), debugArtifact.buildInfo));
  const input = validateEntryPointBuildInfo(buildInfo, target);
  input.settings.outputSelection = canonicalOutputSelection();
  return input;
}

async function kernelInput(kernelCheckout, target) {
  const sources = await collectKernelSources({ kernelCheckout, target });
  const primarySource = sources[target.sourcePath]?.content;
  if (typeof primarySource !== 'string') {
    fail(`${target.contractName} standard input is missing ${target.sourcePath}`);
  }
  validatePrimarySource(primarySource, target);

  const settings = {
    evmVersion: target.evmVersion,
    optimizer: target.optimizer,
    metadata: target.metadata,
    remappings: [`solady/=${target.soladySourcePrefix}/`],
    outputSelection: canonicalOutputSelection(),
  };
  if (target.viaIR) {
    settings.viaIR = true;
  }
  return { language: 'Solidity', sources, settings };
}

function publicTarget(target) {
  const { diskSourcePath: _diskSourcePath, sourceFamily: _sourceFamily, soladySourcePrefix: _soladySourcePrefix, ...manifestTarget } = target;
  return manifestTarget;
}

async function main() {
  const [, , aaArgument, kernelArgument, outputArgument] = process.argv;
  if (!aaArgument || !kernelArgument || !outputArgument) {
    fail(
      'usage: extract-mainnet-aa-verification-inputs.mjs <account-abstraction-checkout> <kernel-checkout> <output-directory>',
    );
  }

  const aaCheckout = resolve(aaArgument);
  const kernelCheckout = resolve(kernelArgument);
  const outputDirectory = resolve(outputArgument);
  await mkdir(outputDirectory, { recursive: true });

  for (const target of targets) {
    const input = target.sourceFamily === 'account-abstraction'
      ? await entryPointInput(aaCheckout, target)
      : await kernelInput(kernelCheckout, target);
    await writeFile(
      join(outputDirectory, target.standardInputFile),
      `${JSON.stringify(input, null, 2)}\n`,
      'utf8',
    );
  }

  const manifest = {
    version: 2,
    chainId: CHAIN_ID,
    contracts: targets.map(publicTarget),
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

# Mainnet Account Abstraction Source Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproducibly compile, bytecode-gate, verify, and publicly validate the five DOS ID Wallet Account Abstraction contracts on DOScan Mainnet.

**Architecture:** GitHub Actions checks out three immutable official source commits and builds five contract-specific standard JSON inputs before obtaining GCP credentials. A local bytecode gate proves the generated compiler outputs correspond to the immutable Mainnet code, then a standalone remote verifier runs after `DEPLOYMENT_STARTED=0` and requires the expected Blockscout match mode plus exact metadata under one global deadline. A separate Playwright spec validates all five public contract pages and `/ops` after deployment.

**Tech Stack:** GitHub Actions YAML, Node.js ESM, npm lockfiles, Yarn 1, Hardhat build-info, Solidity standard JSON, Bash, Python `unittest`, Blockscout API v2, JSON-RPC, `curl`, `jq`, Playwright.

## Global Constraints

- Modify only the DOScan repository. DOS-Chain and DOS-Me remain read-only references.
- Do not redeploy, upgrade, transfer ownership of, or fund any contract.
- Verify exactly five Mainnet contracts and do not add `SimpleAccountFactory`.
- Pin `eth-infinitism/account-abstraction` to `7af70c8993a6f42973f520ae0752386a5032abe7`.
- Pin `zerodevapp/kernel` to `cd697c7e21715d015e0643af22310a99aa17433b` and its Solady submodule to `3f2f5345261904463f5429c9031c3d2185c0f4fe`.
- Pin the ECDSAValidator and FactoryStaker deployment source to Kernel commit `8f7fd9946b9d351bb5be0428bf34c87bad7ed6c9` and its Solady submodule to `9deb9ed36a27261a8745db5b7cd7f4cdc3b1cd4e`.
- Install dependencies, run upstream compile code, assemble inputs, compile standard JSON, and pass the bytecode gate before Google authentication.
- Use one global 300-second source-verification deadline for all five contracts.
- Start source verification only after runtime acceptance passes and `DEPLOYMENT_STARTED=0` is set.
- A source-verification failure must fail the workflow without triggering database, IPFS, or container rollback.
- Never write directly to the Blockscout database to repair verification metadata.
- Do not archive or log private keys, paymaster credentials, API tokens, or GCP credentials.
- Keep the existing Testnet v0.8 extractor and verifier behavior unchanged.
- Expected SHA-256 values are hashes of the lowercase `0x`-prefixed runtime bytecode string encoded as UTF-8:
  - EntryPoint: `4dcad467095cd9af58006b270475ac7591c6946bca08552f6789727097b51eae`
  - Kernel: `d13e7ff2bc90271659100c83f49ee6250555bbf26ed35c2315f243c6849a2127`
  - KernelFactory: `56443d7d18bfd62d5d69b04fc8207e439bf904166335dd7159e0eeef1cba2367`
  - ECDSAValidator: `be711f07f49e57bf56c512b6f32f7c77d9ec1881c4051ed33a45cfad8c7a8b8e`
  - FactoryStaker: `f91091bf1260892a4d0b834494489fea55be2f2f968ad6b1abc1410531f2a2a1`

## File Structure

- `.github/scripts/mainnet-aa-solc/package.json`: exact npm aliases for Solidity 0.8.23, 0.8.24, 0.8.25, and 0.8.28.
- `.github/scripts/mainnet-aa-solc/package-lock.json`: integrity-pinned compiler dependency graph used by `npm ci --ignore-scripts`.
- `.github/scripts/extract-mainnet-aa-verification-inputs.mjs`: source-unit collection, per-contract standard-input generation, and manifest generation.
- `.github/scripts/verify-mainnet-aa-bytecode.mjs`: compiler-output validation, immutable-aware bytecode comparison, pinned live-code hashes, and immutable getter checks.
- `.github/scripts/prepare-mainnet-aa-verification.sh`: isolated pre-auth checkout, dependency, compile, extraction, and bytecode-gate orchestration shared by CI and local validation.
- `.github/scripts/verify-mainnet-aa-sources.sh`: idempotent exact Blockscout verification state machine for manifest version 2.
- `.github/scripts/mainnet-aa-source-ui.spec.mjs`: public Browser UAT for five contract pages and `/ops`.
- `.github/scripts/tests/test_extract_mainnet_aa_verification_inputs.py`: synthetic source-tree and manifest tests.
- `.github/scripts/tests/test_verify_mainnet_aa_bytecode.py`: fake JSON-RPC behavioral tests for code and immutable gates.
- `.github/scripts/tests/test_verify_mainnet_aa_sources.py`: fake Blockscout behavioral tests for exact verification and the shared deadline.
- `.github/scripts/tests/test_validate_mainnet_bens.py`: workflow ordering, archive, rollback boundary, and Playwright wiring regression tests.
- `.github/workflows/deploy-config.yml`: immutable source preparation, pre-auth bytecode gate, archive wiring, post-runtime verification, and public UAT.

---

### Task 1: Generate the five deterministic standard inputs

**Files:**

- Create: `.github/scripts/mainnet-aa-solc/package.json`
- Create: `.github/scripts/mainnet-aa-solc/package-lock.json`
- Create: `.github/scripts/extract-mainnet-aa-verification-inputs.mjs`
- Create: `.github/scripts/tests/test_extract_mainnet_aa_verification_inputs.py`

**Interfaces:**

- Consumes: `node extract-mainnet-aa-verification-inputs.mjs <account-abstraction-checkout> <kernel-checkout> <ecdsa-kernel-checkout> <output-directory>`.
- Produces: `manifest.json`, five `*.standard-input.json` files, and manifest fields used by Tasks 2 and 3.
- Produces manifest version 2 with this per-contract shape:

```json
{
  "key": "kernel",
  "address": "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28",
  "contractName": "Kernel",
  "sourcePath": "src/Kernel.sol",
  "standardInputFile": "kernel.standard-input.json",
  "compilerOutputFile": "kernel.compiler-output.json",
  "compilerPackage": "solc-0.8.28",
  "compilerVersion": "v0.8.28+commit.7893614a",
  "evmVersion": "prague",
  "optimizer": { "enabled": true, "runs": 200 },
  "viaIR": true,
  "licenseType": "mit",
  "spdxLicense": "MIT",
  "constructorArgs": "0000000000000000000000000000000071727de22e5e9d8baf0edac6f37da032",
  "expectedCodeSha256": "d13e7ff2bc90271659100c83f49ee6250555bbf26ed35c2315f243c6849a2127",
  "rpcChecks": [{ "signature": "entrypoint()", "expectedAddress": "0x0000000071727De22E5E9d8BAf0edAc6f37da032" }]
}
```

- The complete target catalog is:

| Key | Address | Contract | Source path | Compiler | EVM | Runs | viaIR | Metadata | Constructor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `entry-point` | `0x0000000071727De22E5E9d8BAf0edAc6f37da032` | `EntryPoint` | `contracts/core/EntryPoint.sol` | `v0.8.23+commit.f704f362` | `paris` | 1,000,000 | true | `bytecodeHash=ipfs` | empty |
| `kernel` | `0xd6CEDDe84be40893d153Be9d467CD6aD37875b28` | `Kernel` | `src/Kernel.sol` | `v0.8.28+commit.7893614a` | `prague` | 200 | true | `appendCBOR=false`, `bytecodeHash=none` | EntryPoint address |
| `kernel-factory` | `0x2577507b78c2008Ff367261CB6285d44ba5eF2E9` | `KernelFactory` | `dependencies/kernel-v3.3/src/factory/KernelFactory.sol` | `v0.8.28+commit.7893614a` | `prague` | 200 | true | `appendCBOR=false`, `bytecodeHash=none` | Kernel address |
| `ecdsa-validator` | `0x845ADb2C711129d4f3966735eD98a9F09fC4cE57` | `ECDSAValidator` | `src/validator/ECDSAValidator.sol` | `v0.8.25+commit.b61c2a91` | `paris` | 200 | true | `appendCBOR=false`, `bytecodeHash=none` | empty |
| `factory-staker` | `0xd703aaE79538628d27099B8c4f621bE4CCd142d5` | `FactoryStaker` | `src/factory/FactoryStaker.sol` | `v0.8.24+commit.e11b9ed9` | `paris` | 200 | omitted | `appendCBOR=false`, `bytecodeHash=none` | owner `0x9775137314fE595c943712B0b336327dfa80aE8A` |

- [ ] **Step 1: Write the compiler toolchain package manifest**

```json
{
  "name": "doscan-mainnet-aa-solc",
  "private": true,
  "version": "1.0.0",
  "dependencies": {
    "solc-0.8.23": "npm:solc@0.8.23-fixed",
    "solc-0.8.24": "npm:solc@0.8.24",
    "solc-0.8.25": "npm:solc@0.8.25",
    "solc-0.8.28": "npm:solc@0.8.28"
  }
}
```

- [ ] **Step 2: Generate and inspect the lockfile without running lifecycle scripts**

Run:

```bash
npm install --prefix .github/scripts/mainnet-aa-solc --package-lock-only --ignore-scripts
npm ci --prefix .github/scripts/mainnet-aa-solc --ignore-scripts
```

Expected: both commands exit 0 and `package-lock.json` contains all four alias names with integrity hashes.

- [ ] **Step 3: Write failing extractor tests**

Create synthetic Account Abstraction Hardhat build-info and a synthetic Kernel checkout with local and `solady/` imports. Assert:

```python
self.assertEqual(2, manifest["version"])
self.assertEqual(7979, manifest["chainId"])
self.assertEqual(
    ["entry-point", "kernel", "kernel-factory", "ecdsa-validator", "factory-staker"],
    [contract["key"] for contract in manifest["contracts"]],
)
self.assertEqual(
    "dependencies/kernel-v3.3/src/factory/KernelFactory.sol",
    contracts["kernel-factory"]["sourcePath"],
)
self.assertNotIn("viaIR", factory_staker_input["settings"])
self.assertEqual(
    {"appendCBOR": False, "bytecodeHash": "none"},
    kernel_input["settings"]["metadata"],
)
```

Also mutate compiler version, optimizer runs, EVM, SPDX, missing import, unexpected source root, and source content. Each mutation must exit nonzero without leaving a complete manifest.

- [ ] **Step 4: Run the focused test and confirm the red state**

Run:

```bash
python -m unittest .github.scripts.tests.test_extract_mainnet_aa_verification_inputs -v
```

Expected: FAIL because the extractor does not exist.

- [ ] **Step 5: Implement deterministic source collection**

Use these exact interfaces:

```js
async function collectSources({ sourceUnit, diskPath, remappings })
function resolveImport({ importerUnit, importerDiskPath, importPath, remappings })
function validateSettings(input, target)
async function writeTargetInput({ aaCheckout, kernelCheckout, outputDirectory, target })
```

`collectSources` must parse both `import "path";` and `import {...} from "path";`, recurse with a visited source-unit set, reject paths outside the two checkouts and the pinned Solady checkout, and never perform network access. Relative imports preserve the parent source-unit directory. `solady/` resolves to `<kernel-checkout>/lib/solady/src/` while the KernelFactory source-unit key uses `dependencies/solady-0.1.26/src/`.

Read EntryPoint's exact standard input from its Hardhat debug artifact and build-info. Rebuild the four Kernel inputs from the pinned checkout with the catalog settings. Require the primary SPDX declaration and require every input's `outputSelection` to include:

```json
{
  "*": {
    "*": [
      "abi",
      "evm.deployedBytecode.object",
      "evm.deployedBytecode.immutableReferences",
      "evm.deployedBytecode.linkReferences",
      "evm.methodIdentifiers"
    ]
  }
}
```

- [ ] **Step 6: Run extractor tests and compiler syntax checks**

Run:

```bash
node --check .github/scripts/extract-mainnet-aa-verification-inputs.mjs
python -m unittest .github.scripts.tests.test_extract_mainnet_aa_verification_inputs -v
```

Expected: PASS.

- [ ] **Step 7: Commit the deterministic input generator**

```bash
git add .github/scripts/mainnet-aa-solc .github/scripts/extract-mainnet-aa-verification-inputs.mjs .github/scripts/tests/test_extract_mainnet_aa_verification_inputs.py
git commit -m "Build immutable Mainnet AA verification inputs"
```

---

### Task 2: Fail closed on compiler output and Mainnet bytecode drift

**Files:**

- Create: `.github/scripts/verify-mainnet-aa-bytecode.mjs`
- Create: `.github/scripts/tests/test_verify_mainnet_aa_bytecode.py`

**Interfaces:**

- Consumes: `node verify-mainnet-aa-bytecode.mjs <verification-artifact-directory> <rpc-url>`.
- Consumes each target's `compilerOutputFile` generated by the corresponding `solc.js --standard-json` invocation.
- Produces exit 0 only when compiler output, runtime code hash, immutable-aware bytecode, and declared immutable getters all match.

- [ ] **Step 1: Write a fake JSON-RPC behavioral test**

The local `ThreadingHTTPServer` must record `eth_getCode` and `eth_call`. Cover:

```python
def test_accepts_exact_code_and_immutable_getters(self): ...
def test_rejects_live_code_hash_mismatch(self): ...
def test_rejects_non_immutable_byte_mismatch(self): ...
def test_rejects_wrong_immutable_getter(self): ...
def test_rejects_unresolved_library_link(self): ...
def test_rejects_compiler_error_or_missing_contract(self): ...
def test_retries_transient_rpc_failure_with_a_finite_limit(self): ...
```

The synthetic compiler output must include one immutable range and `methodIdentifiers` for `entrypoint()` or `implementation()`.

- [ ] **Step 2: Run the bytecode test and confirm the red state**

Run:

```bash
python -m unittest .github.scripts.tests.test_verify_mainnet_aa_bytecode -v
```

Expected: FAIL because the bytecode verifier does not exist.

- [ ] **Step 3: Implement strict compiler-output validation**

Use these interfaces:

```js
function contractOutput(compilerOutput, target)
function flattenImmutableRanges(immutableReferences)
function maskRanges(bytecode, ranges)
function sha256LowercaseHexString(bytecode)
async function rpcCall(rpcUrl, method, params)
async function verifyTarget({ artifactDirectory, rpcUrl, target })
```

Reject any compiler error with `severity === "error"`, missing contract output, empty deployed bytecode, nonempty link references, unresolved `__$...$__` placeholders, unexpected bytecode length, malformed immutable ranges, or overlapping/out-of-bounds ranges.

Require the lowercase live `eth_getCode` string hash to equal `expectedCodeSha256`. Then mask only compiler-declared immutable ranges in both compiled and live bytecode and require exact equality outside those ranges.

- [ ] **Step 4: Implement immutable getter checks**

For every `rpcChecks` entry, read the selector from `evm.methodIdentifiers[signature]`, call the contract with that selector, require exactly one ABI word, and require its low 20 bytes to equal `expectedAddress`.

The catalog must require:

```json
{"signature":"entrypoint()","expectedAddress":"0x0000000071727De22E5E9d8BAf0edAc6f37da032"}
```

for Kernel and:

```json
{"signature":"implementation()","expectedAddress":"0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"}
```

for KernelFactory. Other targets use an empty `rpcChecks` list because their full pinned code hashes still apply.

Use three RPC attempts, a 10-second connect timeout, a 20-second request timeout, and no unbounded retry loop.

- [ ] **Step 5: Run focused bytecode tests**

Run:

```bash
node --check .github/scripts/verify-mainnet-aa-bytecode.mjs
python -m unittest .github.scripts.tests.test_verify_mainnet_aa_bytecode -v
```

Expected: PASS.

- [ ] **Step 6: Commit the bytecode gate**

```bash
git add .github/scripts/verify-mainnet-aa-bytecode.mjs .github/scripts/tests/test_verify_mainnet_aa_bytecode.py
git commit -m "Gate Mainnet AA compiler bytecode"
```

---

### Task 3: Verify five contracts idempotently through Blockscout

**Files:**

- Create: `.github/scripts/verify-mainnet-aa-sources.sh`
- Create: `.github/scripts/tests/test_verify_mainnet_aa_sources.py`

**Interfaces:**

- Consumes: `/bin/sh verify-mainnet-aa-sources.sh <verification-artifact-directory>`.
- Environment: `DOSCAN_MAINNET_AA_API_BASE_URL`, `DOSCAN_MAINNET_AA_API_HOST_HEADER`, `DOSCAN_MAINNET_AA_MAX_SECONDS`, `DOSCAN_MAINNET_AA_POLL_ATTEMPTS`, bounded curl settings, and test-only clock/curl overrides.
- Produces exit 0 only after all five manifest entries report their expected Blockscout match mode and exact metadata.

- [ ] **Step 1: Build a five-contract fake Blockscout server**

Copy the behavioral server pattern from `test_verify_testnet_aa_sources.py`, but define exact responses from each manifest contract instead of global compiler settings. Add tests for:

```python
def test_five_exact_contracts_are_not_submitted(self): ...
def test_submits_each_unverified_contract_with_its_own_profile(self): ...
def test_already_verified_race_requires_exact_get(self): ...
def test_rejects_wrong_metadata_for_each_profile_field(self): ...
def test_rejects_unexpected_match_or_twin_verification(self): ...
def test_one_global_deadline_covers_all_five_contracts(self): ...
def test_rejects_noncanonical_manifest_before_http(self): ...
def test_rejects_missing_or_renamed_standard_input(self): ...
```

Assert FactoryStaker POST uses contract name `src/factory/FactoryStaker.sol:FactoryStaker`, not `MetaFactory`.

- [ ] **Step 2: Run the verifier test and confirm the red state**

Run:

```bash
python -m unittest .github.scripts.tests.test_verify_mainnet_aa_sources -v
```

Expected: FAIL because the Mainnet verifier does not exist.

- [ ] **Step 3: Implement manifest version 2 validation**

Validate exact chain ID 7979, exactly five ordered targets, addresses, file names, compiler profiles, SPDX values, constructor arguments, source paths, code hashes, and getter expectations before the first HTTP request. Reject directory separators, `..`, hidden names, missing files, extra targets, and duplicate addresses.

- [ ] **Step 4: Implement per-contract exact metadata predicates**

The classifier must normalize the optional compiler `v` prefix and constructor `0x` prefix, then require:

```jq
.is_verified == true and
(if $target.verificationMatch == "full" then .is_fully_verified == true and .is_partially_verified == false
 else .is_fully_verified == false and .is_partially_verified == true end) and
.verified_twin_address_hash == null and
.name == $expected_name and
.file_path == $expected_source_path and
.optimization_enabled == true and
.optimization_runs == $expected_runs and
.evm_version == $expected_evm and
.license_type == $expected_license and
((.constructor_args // "") | normalize_hex) == ($expected_constructor | normalize_hex)
```

Require `compiler_settings.viaIR == true` for the four IR targets. For FactoryStaker require `(.compiler_settings.viaIR // false) == false`. Require Kernel-family `metadata.appendCBOR == false` and `metadata.bytecodeHash == "none"`; require EntryPoint `metadata.bytecodeHash == "ipfs"`.

- [ ] **Step 5: Implement bounded idempotent submission and polling**

Reuse the safe multipart fields from the Testnet verifier, but send each target's compiler, source path, name, constructor, license, and input file. Create `verification_deadline` once before the loop over five contracts and pass it into every `verify_contract` call.

Treat `Already verified` as a race signal only. GET again and accept only exact metadata. A verified but inexact contract fails immediately and is never resubmitted.

- [ ] **Step 6: Run shell and behavioral validation**

Run:

```bash
bash -n .github/scripts/verify-mainnet-aa-sources.sh
python -m unittest .github.scripts.tests.test_verify_mainnet_aa_sources -v
```

Expected: PASS.

- [ ] **Step 7: Commit the Mainnet source verifier**

```bash
git add .github/scripts/verify-mainnet-aa-sources.sh .github/scripts/tests/test_verify_mainnet_aa_sources.py
git commit -m "Verify Mainnet AA sources exactly"
```

---

### Task 4: Wire the pre-auth build and post-runtime verification into Mainnet deploy

**Files:**

- Create: `.github/scripts/prepare-mainnet-aa-verification.sh`
- Modify: `.github/workflows/deploy-config.yml:4-32`
- Modify: `.github/workflows/deploy-config.yml:64-145`
- Modify: `.github/workflows/deploy-config.yml:145-184`
- Modify: `.github/workflows/deploy-config.yml:620-705`
- Modify: `.github/scripts/tests/test_validate_mainnet_bens.py:140-190`

**Interfaces:**

- Consumes Task 1's source generator and Task 2's bytecode verifier.
- Consumes: `prepare-mainnet-aa-verification.sh <aa-repository> <aa-ref> <kernel-repository> <kernel-ref> <solady-ref> <ecdsa-kernel-ref> <ecdsa-solady-ref> <output-directory> <rpc-url>`.
- Packages `${RUNNER_TEMP}/mainnet-aa-verification` as `mainnet-aa-verification` in `/tmp/doscan-config.tgz`.
- Invokes Task 3's verifier through the local Caddy origin after `DEPLOYMENT_STARTED=0`.

- [ ] **Step 1: Write failing workflow regression assertions**

Extend `test_mainnet_workflow_consumes_the_canonical_manifest` and add focused tests that parse the Mainnet job and preparation script. Assert:

```python
self.assertLess(prepare_index, google_auth_index)
self.assertLess(bytecode_gate_index, google_auth_index)
self.assertLess(deployment_stopped_index, source_verify_index)
self.assertIn("mainnet-aa-verification", package_step)
self.assertIn("verify-mainnet-aa-sources.sh", package_step)
self.assertNotIn("verify-mainnet-aa-sources.sh", testnet_job)
```

Also assert the exact two repository SHAs, exact Solady SHA, all four compiler aliases, five expected output files, and a bounded public RPC URL. Assert the remote source verifier appears after the last rollback-sensitive runtime gate and before external metadata checks.

- [ ] **Step 2: Run the Mainnet regression and confirm the red state**

Run:

```bash
python -m unittest .github.scripts.tests.test_validate_mainnet_bens -v
```

Expected: FAIL because Mainnet has no AA source preparation or verification wiring.

- [ ] **Step 3: Add Mainnet-only immutable source constants**

Add job-level environment variables:

```yaml
env:
  AA_V07_SOURCE_REPOSITORY: https://github.com/eth-infinitism/account-abstraction.git
  AA_V07_SOURCE_REF: 7af70c8993a6f42973f520ae0752386a5032abe7
  KERNEL_SOURCE_REPOSITORY: https://github.com/zerodevapp/kernel.git
  KERNEL_SOURCE_REF: cd697c7e21715d015e0643af22310a99aa17433b
  KERNEL_SOLADY_REF: 3f2f5345261904463f5429c9031c3d2185c0f4fe
```

Do not move these into global workflow env because Testnet uses a different Account Abstraction release.

- [ ] **Step 4: Add the pre-auth preparation step**

Implement `prepare-mainnet-aa-verification.sh` with `set -eu`, exactly nine required arguments, private `mktemp -d` checkouts, and an `EXIT HUP INT TERM` cleanup trap. Place `Prepare immutable Mainnet Account Abstraction verification inputs` after Caddy validation and before `Authenticate to Google Cloud`; the workflow step calls the script with the seven pinned provenance variables, `${RUNNER_TEMP}/mainnet-aa-verification`, and `https://main.doschain.com/`.

The preparation script must:

1. Create clean runner-temp checkouts.
2. Fetch and detach exactly both full SHAs.
3. Initialize only `lib/solady` and require its HEAD to equal `KERNEL_SOLADY_REF`.
4. Install Yarn 1.22.22, run `yarn install --frozen-lockfile --non-interactive`, and compile Account Abstraction v0.7.
5. Run `npm ci --prefix .github/scripts/mainnet-aa-solc --ignore-scripts`.
6. Run the Task 1 extractor.
7. Compile each standard input with its manifest-selected `compilerPackage`:

```bash
compiler_js="${GITHUB_WORKSPACE}/.github/scripts/mainnet-aa-solc/node_modules/${compiler_package}/solc.js"
node "${compiler_js}" --standard-json \
  < "${output}/${standard_input_file}" \
  > "${output}/${compiler_output_file}"
```

8. Run `verify-mainnet-aa-bytecode.mjs` against `https://main.doschain.com/`.
9. Require all five standard inputs, all five compiler outputs, and `manifest.json` to be nonempty.

- [ ] **Step 5: Package only public verification artifacts**

Add these archive members:

```text
.github/scripts/verify-mainnet-aa-sources.sh
-C ${RUNNER_TEMP} mainnet-aa-verification
```

Keep the existing `umask 077` and NFT media credential cleanup. The compiler toolchain and upstream checkouts are not shipped to the VM.

- [ ] **Step 6: Run source verification outside rollback scope**

Immediately after the existing Mainnet line that sets `DEPLOYMENT_STARTED=0`, invoke:

```sh
/bin/sh "${SRC}/.github/scripts/verify-mainnet-aa-sources.sh" \
  "${SRC}/mainnet-aa-verification"
```

Do not add the verifier to `TOUCHED_SERVICES`, `bens_rollback`, or database restore paths.

- [ ] **Step 7: Run workflow regressions and syntax checks**

Run:

```bash
python -m unittest .github.scripts.tests.test_validate_mainnet_bens -v
python -c "import pathlib,yaml; yaml.safe_load(pathlib.Path('.github/workflows/deploy-config.yml').read_text())"
actionlint .github/workflows/deploy-config.yml
```

Extract both remote `gcloud --command` payloads with the existing test helpers and require `bash -n` exit 0.

Also run:

```bash
bash -n .github/scripts/prepare-mainnet-aa-verification.sh
```

- [ ] **Step 8: Commit Mainnet workflow wiring**

```bash
git add .github/scripts/prepare-mainnet-aa-verification.sh .github/workflows/deploy-config.yml .github/scripts/tests/test_validate_mainnet_bens.py
git commit -m "Wire Mainnet AA source verification"
```

---

### Task 5: Add public Browser UAT for five sources and `/ops`

**Files:**

- Create: `.github/scripts/mainnet-aa-source-ui.spec.mjs`
- Modify: `.github/workflows/deploy-config.yml:708-720`
- Modify: `.github/scripts/tests/test_validate_mainnet_bens.py:180-215`

**Interfaces:**

- Consumes: `DOSCAN_MAINNET_URL=https://doscan.io/`.
- Produces: Playwright success only when the API and visible UI agree on all five exact contracts and `/ops` still exposes EntryPoint v0.7 operations.

- [ ] **Step 1: Write failing static workflow and spec assertions**

Require the workflow to copy and run both `mainnet-bens-ui.spec.mjs` and `mainnet-aa-source-ui.spec.mjs` in the same pinned Playwright installation. Assert the new spec contains all five addresses, the EntryPoint v0.7 address on `/ops`, `response?.ok()`, visible locators, and the exact two-marker Cloudflare skip predicate.

- [ ] **Step 2: Run the Mainnet regression and confirm the red state**

Run:

```bash
python -m unittest .github.scripts.tests.test_validate_mainnet_bens -v
```

Expected: FAIL because the new Playwright spec is absent.

- [ ] **Step 3: Implement the public contract-page acceptance helper**

Use this target shape:

```js
const targets = [
  {
    address: "0x0000000071727De22E5E9d8BAf0edAc6f37da032",
    name: "EntryPoint",
    compiler: "v0.8.23+commit.f704f362",
    sourcePath: "contracts/core/EntryPoint.sol",
  }
];
```

Include all five targets. For each target:

1. Fetch `/api/v2/smart-contracts/${address}` and require HTTP 200.
2. Require the expected Blockscout match mode, exact name, compiler normalization, source path, optimizer settings, EVM, license, and constructor arguments. EntryPoint requires full match; the four no-CBOR Kernel contracts require partial match after the pre-auth bytecode gate proves exact runtime equality.
3. Navigate to `/address/${address}?tab=contract`.
4. Require the contract name and the visible expected verification signal.
5. Reject visible `Oops! Something went wrong` text.

Retry only the initial landing readiness six times with 5-second delays. Skip only when both the exact title `Just a moment...` and URL token `__cf_chl_rt_tk=` are present.

- [ ] **Step 4: Add the `/ops` regression**

Navigate to `/ops`, require a successful Account Abstraction API response, require at least one visible operation row, and require the visible EntryPoint address or its shortened checksum text to resolve to `0x0000000071727De22E5E9d8BAf0edAc6f37da032`. Do not accept a static page title as evidence.

- [ ] **Step 5: Run Node syntax and workflow regressions**

Run:

```bash
node --check .github/scripts/mainnet-aa-source-ui.spec.mjs
python -m unittest .github.scripts.tests.test_validate_mainnet_bens -v
```

Expected: PASS.

- [ ] **Step 6: Commit public UAT**

```bash
git add .github/scripts/mainnet-aa-source-ui.spec.mjs .github/workflows/deploy-config.yml .github/scripts/tests/test_validate_mainnet_bens.py
git commit -m "Test Mainnet AA source verification UI"
```

---

### Task 6: Full validation, independent review, merge, deployment, and live UAT

**Files:**

- Review: complete diff against `origin/main`
- Verify: all files created or modified in Tasks 1 through 5

**Interfaces:**

- Consumes all previous task outputs.
- Produces a reviewed and merged PR, a terminally successful Mainnet workflow, and live Browser evidence.

- [ ] **Step 1: Prove the new test suite passes**

Run:

```bash
python -m unittest .github.scripts.tests.test_extract_mainnet_aa_verification_inputs -v
python -m unittest .github.scripts.tests.test_verify_mainnet_aa_bytecode -v
python -m unittest .github.scripts.tests.test_verify_mainnet_aa_sources -v
python -m unittest .github.scripts.tests.test_validate_mainnet_bens -v
```

Expected: all tests pass.

- [ ] **Step 2: Prove existing Testnet behavior did not regress**

Run:

```bash
python -m unittest .github.scripts.tests.test_extract_aa_verification_inputs -v
python -m unittest .github.scripts.tests.test_verify_testnet_aa_sources -v
python scripts/validate-testnet-bens.py
```

Expected: all tests and validator pass without changing Testnet target metadata.

- [ ] **Step 3: Run repository quality gates**

Run:

```bash
node --check .github/scripts/extract-mainnet-aa-verification-inputs.mjs
node --check .github/scripts/verify-mainnet-aa-bytecode.mjs
node --check .github/scripts/mainnet-aa-source-ui.spec.mjs
bash -n .github/scripts/verify-mainnet-aa-sources.sh
bash -n .github/scripts/prepare-mainnet-aa-verification.sh
python -c "import pathlib,yaml; yaml.safe_load(pathlib.Path('.github/workflows/deploy-config.yml').read_text())"
actionlint .github/workflows/deploy-config.yml
git diff --check origin/main...HEAD
git status --short
```

Expected: every command exits 0 and the worktree contains only the intended task files.

- [ ] **Step 4: Rebuild real upstream inputs from clean checkouts**

Run the shared preparation script from a clean temporary output directory:

```bash
output="$(mktemp -d)"
trap 'rm -rf "${output}"' EXIT
.github/scripts/prepare-mainnet-aa-verification.sh \
  https://github.com/eth-infinitism/account-abstraction.git \
  7af70c8993a6f42973f520ae0752386a5032abe7 \
  https://github.com/zerodevapp/kernel.git \
  cd697c7e21715d015e0643af22310a99aa17433b \
  3f2f5345261904463f5429c9031c3d2185c0f4fe \
  8f7fd9946b9d351bb5be0428bf34c87bad7ed6c9 \
  9deb9ed36a27261a8745db5b7cd7f4cdc3b1cd4e \
  "${output}" \
  https://main.doschain.com/
```

Expected: exit 0, all five compilers report the exact long version, all five code hashes match the global constraints, Kernel returns the v0.7 EntryPoint from `entrypoint()`, and KernelFactory returns the pinned Kernel from `implementation()`.

- [ ] **Step 5: Request independent review on the exact head**

Use `superpowers:requesting-code-review`. The reviewer must inspect provenance, compiler settings, source-unit mapping, immutable masking, code hashes, deadline behavior, credential ordering, rollback boundary, archive cleanup, shell quoting, and Browser acceptance. Fix every Critical, Important, and Minor finding and request re-review on the new exact SHA.

- [ ] **Step 6: Publish and merge**

Push `codex/mainnet-aa-source-verification`, open a ready PR, wait for all required CI and CodeQL checks, and merge only after the independent reviewer approves the exact head.

- [ ] **Step 7: Observe Mainnet deployment to terminal success**

Verify the merged `Deploy Config` Mainnet job completes. Record evidence that input preparation and bytecode gating ran before GCP auth, runtime deployment passed, `DEPLOYMENT_STARTED=0` preceded source verification, and all five exact confirmations appeared.

- [ ] **Step 8: Run live Browser UAT after deployment**

Using Browser, open each public contract page and `/ops`. Confirm the exact contract name, compiler, source path, expected full or partial match state, and expected v0.7 EntryPoint operation data. Treat CI Playwright and live Browser inspection as separate evidence.

# Testnet Account Abstraction Source Verification Implementation Plan

> **For Codex:** Execute this plan task by task with test-driven development. Do not deploy until an independent reviewer approves the exact PR head.

**Goal:** Make the Testnet deployment workflow reproducibly verify the official ERC-4337 v0.8 EntryPoint and SimpleAccountFactory sources, then fail closed on incorrect Blockscout metadata without rolling back a healthy database.

**Architecture:** GitHub Actions fetches the immutable `eth-infinitism/account-abstraction` v0.8.0 commit, installs its locked dependencies, compiles it, and extracts the exact Hardhat standard JSON input for each target contract into the deployment archive. A standalone shell verifier runs on the Testnet VM after all rollback-sensitive health checks, uses the local Caddy origin to avoid CDN caching, submits only contracts that are not already exact, and polls with a bounded deadline until Blockscout reports exact full verification metadata.

**Tech Stack:** GitHub Actions YAML, Bash, Node.js ESM, Python `unittest`, Hardhat build-info, Blockscout API v2, `curl`, `jq`.

---

## Task 1: Specify the verification artifact extractor

**Files:**

- Create: `.github/scripts/extract-aa-verification-inputs.mjs`
- Create: `.github/scripts/tests/test_extract_aa_verification_inputs.py`

**Steps:**

1. Write failing tests with synthetic Hardhat artifact and build-info fixtures.
2. Require exact source paths, contract names, and SPDX licenses for EntryPoint and SimpleAccountFactory.
3. Require Solidity `0.8.28`, Cancun, optimizer enabled with 1,000,000 runs, and `viaIR=true`.
4. Require each compiler output to contain the named contract.
5. Write one standard input JSON per contract plus a manifest containing addresses, expected metadata, and the factory constructor arguments.
6. Run the focused test and confirm it passes.

## Task 2: Specify the idempotent Blockscout verifier

**Files:**

- Create: `.github/scripts/verify-testnet-aa-sources.sh`
- Create: `.github/scripts/tests/test_verify_testnet_aa_sources.py`

**Steps:**

1. Start with behavioral tests backed by a local `ThreadingHTTPServer`.
2. Cover already exact contracts and assert no verification POST occurs.
3. Cover submit and delayed success, including transient GET failures.
4. Cover partial verification, wrong compiler, EVM, optimizer, source path, name, and constructor arguments.
5. Cover malformed JSON, missing required fields, rejected POST, a valid `Already verified` race, and bounded timeout.
6. Implement `curl` timeouts, one global polling deadline, retry interval overrides for tests, and exact `jq` predicates including license.
7. Submit multipart standard input through the standard Blockscout API v2 route.
8. Run the focused test and confirm it passes.

## Task 3: Wire immutable source preparation into Testnet deployment

**Files:**

- Modify: `.github/workflows/deploy-config.yml`
- Modify: `.github/scripts/tests/test_validate_testnet_bens.py`

**Steps:**

1. Add failing workflow regression assertions for the exact upstream repository, commit, compiler artifact preparation, archive entries, remote invocation, and ordering after `DEPLOYMENT_STARTED=0`.
2. Add pinned job environment constants for the upstream repository and peeled v0.8.0 commit.
3. Before GCP authentication, fetch the commit into `${RUNNER_TEMP}`, verify exact HEAD, run `yarn install --frozen-lockfile`, and compile.
4. Call the extractor to produce immutable verification artifacts.
5. Include the extractor output and verifier script in the Testnet archive.
6. Run the verifier through local Caddy only after setting `DEPLOYMENT_STARTED=0`.
7. Keep Mainnet and Beta jobs unchanged.
8. Run focused workflow regression tests.

## Task 4: Validate failure semantics and repository quality

**Files:**

- Modify if required: `.github/scripts/tests/test_validate_testnet_bens.py`

**Steps:**

1. Prove a verification failure exits the remote deploy command after rollback has been disabled.
2. Prove all attempts are bounded by connect, transfer, and total polling limits.
3. Run all `.github/scripts/tests` tests.
4. Run `python scripts/validate-testnet-bens.py`.
5. Run YAML parse, `actionlint`, Bash syntax, Node syntax, and `git diff --check`.
6. Confirm the worktree contains only intended files.

## Task 5: Review, publish, deploy, and UAT

**Files:**

- Review the complete diff against `origin/main`.

**Steps:**

1. Commit the implementation in intentional units.
2. Request an independent reviewer on the exact branch head.
3. Fix every Critical, Important, and Minor finding, then request re-review.
4. Push the branch, create a PR, wait for required CI, and merge it.
5. Observe the Testnet deployment workflow to terminal success.
6. Verify both live contract pages with Browser, including exact match, compiler, EVM, optimizer runs, source path, and factory constructor.
7. Verify `/ops` and Account Abstraction status remain healthy.

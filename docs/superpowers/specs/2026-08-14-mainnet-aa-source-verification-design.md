# Mainnet Account Abstraction Source Verification Design

**Date:** 2026-08-14

**Status:** Approved

**Repository:** DOScan

**Network:** DOS Chain Mainnet, chain ID 7979

## 1. Decision

DOScan will deterministically reconstruct Solidity standard JSON inputs from pinned official upstream repositories and verify the five production contracts that make up the DOS ID wallet Account Abstraction stack.

The verification gate will be part of the existing Mainnet deployment workflow. It will run only after runtime deployment and semantic health checks have succeeded and after `DEPLOYMENT_STARTED=0`, so a source-verification failure reports a failed workflow without rolling back a healthy runtime.

This change does not redeploy contracts, change wallet behavior, modify Blockscout core, or depend on another explorer at deployment time.

## 2. Scope

### In scope

| Role | Address | Expected contract name |
| --- | --- | --- |
| EntryPoint v0.7 | `0x0000000071727De22E5E9d8BAf0edAc6f37da032` | `EntryPoint` |
| Kernel v3.3 implementation | `0xd6CEDDe84be40893d153Be9d467CD6aD37875b28` | `Kernel` |
| KernelFactory v3.3 | `0x2577507b78c2008Ff367261CB6285d44ba5eF2E9` | `KernelFactory` |
| ECDSA validator | `0x845ADb2C711129d4f3966735eD98a9F09fC4cE57` | `ECDSAValidator` |
| MetaFactory deployment | `0xd703aaE79538628d27099B8c4f621bE4CCd142d5` | `FactoryStaker` |

The last address is called MetaFactory by the wallet stack, but its Solidity contract name is `FactoryStaker`. Verification must use the Solidity name.

### Out of scope

- No contract deployment, upgrade, ownership change, or fund transfer.
- No verification of `SimpleAccountFactory`.
- No migration to EntryPoint v0.8 or later.
- No Blockscout Backend, Frontend, or smart-contract-verifier core changes.
- No DOS-Chain or DOS-Me repository changes.
- No direct database correction when Blockscout metadata is wrong.

## 3. Considered approaches

### Chosen: reconstruct from pinned official upstream repositories

The workflow checks out immutable upstream commits, installs their locked dependencies, compiles with exact per-contract settings, and extracts deterministic standard JSON inputs.

Benefits:

- Official source provenance is explicit and reproducible.
- DOScan does not vendor a large third-party source snapshot.
- Deployment does not trust a live third-party explorer.
- A source or compiler drift fails before production credentials are issued.

### Rejected: vendor generated standard inputs in DOScan

This removes build work from CI but duplicates third-party source artifacts and makes provenance updates easier to miss.

### Rejected: fetch verified inputs from Ethereum Blockscout during deployment

This is compact, but Mainnet deployment would depend on an external explorer's availability and mutable response format.

## 4. Immutable source provenance

| Family | Official repository | Ref | Pinned commit |
| --- | --- | --- | --- |
| EntryPoint v0.7 | `eth-infinitism/account-abstraction` | `v0.7.0` | `7af70c8993a6f42973f520ae0752386a5032abe7` |
| Kernel v3.3 stack | `zerodevapp/kernel` | `v3.3` | `cd697c7e21715d015e0643af22310a99aa17433b` |

The Kernel pin supplies `Kernel`, `KernelFactory`, `ECDSAValidator`, and `FactoryStaker`. Every checkout must resolve to the full expected SHA. Generated inputs are deployment artifacts only and must not contain credentials.

## 5. Exact compilation profiles

Each contract has its own canonical compilation profile. The implementation must not apply one repository-wide compiler configuration to all Kernel contracts.

| Contract | Source path | Compiler | Optimizer | EVM | IR | Metadata | License | Constructor data |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EntryPoint | `contracts/core/EntryPoint.sol` | `v0.8.23+commit.f704f362` | enabled, 1,000,000 runs | `paris` | `true` | IPFS bytecode hash | `gnu_gpl_v3` | none |
| Kernel | `src/Kernel.sol` | `v0.8.28+commit.7893614a` | enabled, 200 runs | `prague` | `true` | no CBOR, no bytecode hash | `mit` | EntryPoint v0.7 address |
| KernelFactory | `dependencies/kernel-v3.3/src/factory/KernelFactory.sol` | `v0.8.28+commit.7893614a` | enabled, 200 runs | `prague` | `true` | no CBOR, no bytecode hash | `mit` | Kernel implementation address |
| ECDSAValidator | `src/validator/ECDSAValidator.sol` | `v0.8.25+commit.b61c2a91` | enabled, 200 runs | `paris` | `true` | no CBOR, no bytecode hash | `mit` | none |
| FactoryStaker | `src/factory/FactoryStaker.sol` | `v0.8.24+commit.e11b9ed9` | enabled, 200 runs | `paris` | omitted, equivalent to `false` | no CBOR, no bytecode hash | `mit` | none |

Compiler versions are normalized to a canonical `vX.Y.Z+commit...` form when comparing Blockscout metadata.

Kernel contains immutable data tied to EntryPoint and chain-specific deployment behavior. The bytecode preflight must compile for DOS Chain Mainnet with the exact constructor arguments and compare `eth_getCode` against the compiler's deployed bytecode using the emitted immutable-reference ranges. It must not compare Kernel blindly against Ethereum bytecode.

All other contracts must also pass an exact deployed-bytecode comparison before any production mutation. Any unresolved library link, immutable range, constructor mismatch, or metadata mismatch fails closed.

## 6. Workflow architecture and ordering

```text
checkout pinned upstream sources
  -> install locked toolchains and dependencies
  -> compile five exact profiles
  -> extract standard JSON inputs and verification manifest
  -> compare generated deployed bytecode with canonical Mainnet code
  -> package immutable artifacts
  -> authenticate to Google Cloud
  -> run the existing Mainnet deployment and semantic gates
  -> set DEPLOYMENT_STARTED=0
  -> verify five sources through the internal Blockscout API
  -> run public Browser UAT
```

The source preparation, dependency installation, compilation, extraction, and local bytecode checks must run before Google authentication. Upstream lifecycle scripts therefore cannot access production cloud credentials. The generator preserves the canonical source-unit names expected by Blockscout, including the `dependencies/kernel-v3.3/` prefix used by KernelFactory.

The remote verification script uses the internal canonical Blockscout API to avoid CDN caching while exercising the same deployed verifier service. The public explorer is checked afterward by Browser UAT.

## 7. Verification state machine

One global deadline of 300 seconds is created before processing the first contract. The same deadline applies to all five contracts and every poll. It must never reset per contract.

For each contract:

1. GET current smart-contract metadata.
2. If every required field is exact, skip POST.
3. If the contract is unverified, POST its standard JSON input and exact constructor arguments.
4. Poll until the contract is exact or the shared deadline expires.
5. If POST reports `Already verified`, GET again and accept only exact metadata.
6. If Blockscout reports a verified contract with wrong metadata, fail immediately.

Required exact metadata includes full verification, contract name, source path, compiler, optimizer state and runs, EVM version, license, constructor arguments, and the absence of partial verification.

The script must use bounded connection and transfer timeouts. Invalid JSON, missing required fields, HTTP failures that outlive the shared deadline, partial verification, or contradictory metadata fail closed.

## 8. Failure and rollback semantics

- Source preparation or bytecode mismatch occurs before Google authentication and before production mutation.
- Runtime deployment preserves its existing backup, rollback, and semantic verification behavior.
- Source verification begins only after runtime success and `DEPLOYMENT_STARTED=0`.
- A source-verification failure fails the workflow but does not trigger a database, IPFS, or container rollback.
- Temporary source artifacts are removed on success and failure.
- The verifier never writes directly to the Blockscout database and never tries to repair wrong verified metadata automatically.

## 9. Test strategy

Behavioral tests must cover real request parsing and state transitions, not only string assertions.

Required cases:

- Pinned commits resolve exactly and all five standard inputs are deterministic.
- All five compiled deployed bytecodes match Mainnet, including immutable-aware Kernel matching.
- A bytecode mismatch fails before Google authentication and before mutation.
- Five already-exact contracts produce no POST requests.
- An unverified contract submits once and polls to exact metadata.
- An `Already verified` race succeeds only after an exact GET.
- A verified contract with wrong compiler, optimizer, EVM, path, name, license, or constructor arguments fails immediately.
- Partial verification fails.
- Two or more pending contracts share one global 300-second deadline.
- Network and malformed-JSON failures are bounded.
- Source verification is ordered after `DEPLOYMENT_STARTED=0` and cannot invoke runtime rollback.

Existing Mainnet deployment, shell syntax, workflow validation, actionlint, Compose rendering, and diff checks must continue to pass.

## 10. Security properties

- Upstream code is pinned by full commit SHA and built before cloud credentials exist.
- Package managers use lockfiles and pinned tool versions.
- Verification artifacts contain source inputs and public contract metadata only.
- No private key, API token, paymaster credential, wallet secret, or GCP credential is logged or archived.
- Deployment has no runtime dependency on Ethereum Blockscout or another third-party explorer.
- Every remote call and poll has a finite wall-clock bound.

## 11. Acceptance criteria

- An independent reviewer reports no Critical, Important, or Minor finding.
- The PR is merged by the agent after approval and all required CI checks pass.
- The Mainnet deployment workflow completes successfully.
- DOScan Mainnet shows full exact source verification for all five contract pages.
- Browser UAT confirms each contract page exposes the expected name, compiler, source, and verified state.
- Browser UAT confirms `/ops` remains healthy and still reports the production EntryPoint v0.7 operations.

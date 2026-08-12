# ENSv2 BENS Testnet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy DOS ENSv2 on Testnet 3939 and integrate `.dos` names into DOScan through an official BENS runtime and a DOS-owned custom subgraph.

**Architecture:** DOS-Names-Contracts owns the contracts, deployment manifest, and ENSv2-to-BENS subgraph. DOScan pins an exact DOS Names revision and owns only the official runtime services, protocol config, same-origin proxy, standard Blockscout env, deployment automation, and runtime verification.

**Tech Stack:** Solidity, Foundry, The Graph AssemblyScript mappings, Matchstick, graph-node, PostgreSQL, IPFS Kubo, Blockscout BENS, Docker Compose, GitHub Actions, Caddy, Python validation, Playwright.

## Global Constraints

- Testnet chain ID is `3939` and the canonical public RPC is `https://test.doschain.com`.
- Mainnet remains unchanged.
- The custom subgraph source lives only in `DOS-Names-Contracts/subgraph/dos-names`.
- DOScan runs pinned official images and upstream Blockscout env variables only.
- No registration, purchase, renewal, or management UI is added.
- No secret is committed or printed.
- DOS-Chain is read-only.

---

### Task 1: Establish the DOS Names Subgraph Package

**Files:**
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/package.json`
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/schema.graphql`
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/subgraph.template.yaml`
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/abis/*.json`
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/src/*.ts`
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/tests/*.test.ts`

**Interfaces:**
- Consumes: ENSv2 events from `PermissionedRegistry`, `DOSRegistrar`, and `PermissionedResolver`.
- Produces: BENS v1.7.3-compatible graph-node entities and a renderable Testnet subgraph manifest.

- [ ] **Step 1: Copy the existing adapter tests into the DOS-owned package before the mappings.**
- [ ] **Step 2: Run `npm ci && npm test` and record the expected failure caused by missing DOS-owned mappings.**
- [ ] **Step 3: Add the schema, minimal event ABIs, mappings, templates, and package scripts.**
- [ ] **Step 4: Run `npm run codegen`, `npm test`, and `npm run build`; require zero failures.**
- [ ] **Step 5: Compare the schema fields used by the adapter against Blockscout BENS tag `bens/v1.7.3`.**

### Task 2: Render and Validate the Concrete Subgraph Manifest

**Files:**
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/scripts/render-manifest.mjs`
- Create: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/subgraph/dos-names/tests/render-manifest.test.mjs`
- Modify: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/.github/workflows/main.yml`

**Interfaces:**
- Consumes: the committed DOS Testnet deployment manifest and `subgraph.template.yaml`.
- Produces: `subgraph.yaml` with concrete checksummed addresses and deployment start block.

- [ ] **Step 1: Write tests that reject missing addresses, zero addresses, invalid chain IDs, and missing deployment blocks.**
- [ ] **Step 2: Run the render tests and verify they fail because the renderer is absent.**
- [ ] **Step 3: Implement the renderer and validate every required deployment key.**
- [ ] **Step 4: Add CI steps for clean install, renderer tests, graph code generation, Matchstick tests, and graph build.**
- [ ] **Step 5: Run the full subgraph validation locally.**

### Task 3: Keep DOScan Runtime-Only

**Files:**
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/docker-compose/docker-compose-testnet.yml`
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/docker-compose/Caddyfile-gcp-testnet`
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/docker-compose/envs/common-blockscout-testnet.env`
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/docker-compose/envs/common-frontend-testnet.env`
- Create: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/docker-compose/bens/config.template.json`
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/scripts/render-testnet-bens.py`
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/scripts/validate-testnet-bens.py`
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/.github/workflows/deploy-config.yml`
- Modify: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/.github/workflows/dependency-build.yml`
- Delete: `D:/Projects/DOScan/.codex/worktrees/ensv2-bens-testnet/docker-compose/bens/dos-names`

**Interfaces:**
- Consumes: an exact merged DOS Names subgraph commit and the Testnet secrets env.
- Produces: a deployable official BENS stack and same-origin Blockscout integration.

- [ ] **Step 1: Add or update Python tests that fail when custom mapping source is tracked by DOScan, images are unpinned, the subgraph revision is not immutable, or a database password is hardcoded.**
- [ ] **Step 2: Run the focused Python tests and verify the new assertions fail.**
- [ ] **Step 3: Remove the custom mapping copy and make CI fetch the exact DOS Names commit.**
- [ ] **Step 4: Supply the BENS database password only through `DOSCAN_BENS_DB_PASSWORD` in the existing secrets env.**
- [ ] **Step 5: Validate Compose, Caddy, env parity, workflow YAML, BENS protocol config, and rollback paths.**

### Task 4: Deploy and Verify ENSv2 Contracts

**Files:**
- Existing entrypoint: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/contracts/script/foundry/DeployDOSTestnet.s.sol`
- Create after successful broadcast: `D:/Projects/DOS-Names-Contracts/.codex/worktrees/ensv2-bens-subgraph/contracts/deployments/dos-testnet-3939.json`

**Interfaces:**
- Consumes: Wallet 99999 private key through the designated 1Password item, verified chain 3939 RPC, funded deployer, and verified final owner.
- Produces: live contracts, broadcast evidence, and the committed deployment manifest.

- [ ] **Step 1: Verify chain ID, Blockchain ID, latest block, deployer address, deployer nonce, deployer balance, final owner, and absence of an existing ENSv2 deployment.**
- [ ] **Step 2: Run the Foundry deployment simulation without printing the key and verify the estimated gas fits the funded balance.**
- [ ] **Step 3: Broadcast once from the exact verified deployer.**
- [ ] **Step 4: Extract addresses and deployment block from broadcast output into the canonical manifest.**
- [ ] **Step 5: Verify bytecode, ownership handoff, required roles, deployer role revocation, and WDOS behavior on the live chain.**

### Task 5: Deploy BENS and Prove the User Flow

**Files:**
- Runtime artifact: `/opt/doscan-testnet/bens`
- Runtime env: `/opt/doscan-testnet/envs`
- Runtime Caddy config: `/opt/doscan-testnet/Caddyfile`

**Interfaces:**
- Consumes: merged DOS Names and DOScan commits plus the live ENSv2 deployment manifest.
- Produces: healthy BENS APIs and visible `.dos` behavior in Testnet DOScan.

- [ ] **Step 1: Deploy graph-node, PostgreSQL, IPFS, and the rendered subgraph before enabling BENS.**
- [ ] **Step 2: Confirm graph-node indexing status has no deterministic error and has reached the deployment block.**
- [ ] **Step 3: Start BENS, verify health, and verify `dos-names` from `/name-service/api/v1/protocols`.**
- [ ] **Step 4: Register one Testnet-only verification name using the existing contract flow, then verify search and address lookup through BENS.**
- [ ] **Step 5: Deploy the standard Backend and Frontend env, then verify the same name in DOScan with Playwright.**

### Task 6: Independent Review and Promotion

**Files:**
- Review the complete diffs in both worktrees.

**Interfaces:**
- Consumes: verified commits from Tasks 1 through 5.
- Produces: reviewer-approved PRs, merged branches, and final remote/runtime evidence.

- [ ] **Step 1: Run all repository-specific tests, lint, builds, Compose validation, and deployment validators fresh.**
- [ ] **Step 2: Dispatch independent code review for DOS Names and DOScan.**
- [ ] **Step 3: Fix all Critical and Important findings and request re-review.**
- [ ] **Step 4: Create or update one PR per repository, wait for required CI, and merge after approval.**
- [ ] **Step 5: Verify merged SHAs, deployed runtime image digests, BENS health, API behavior, and Playwright evidence.**

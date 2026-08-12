# ENSv2 BENS Testnet Design

**Status:** Approved by JOY on 2026-08-12

## Goal

Deploy the DOS ENSv2 contracts to DOS Chain Testnet 3939 and expose `.dos` display, search, forward resolution, and address lookup in DOScan through the official Blockscout BENS service.

## Scope

- Deploy a fresh DOS ENSv2 stack on Testnet 3939.
- Keep the custom ENSv2-to-BENS indexing adapter in `DOS-Names-Contracts` next to the contracts and deployment manifest it indexes.
- Run only pinned official BENS, graph-node, PostgreSQL, IPFS, and Node images from DOScan.
- Enable only upstream Blockscout Backend and Frontend environment variables.
- Proxy BENS through the Testnet explorer origin.
- Leave Mainnet unchanged.
- Do not add registration, purchase, renewal, or management UI.

## Repository Boundaries

### DOS-Names-Contracts

Owns:

- ENSv2 contracts and the existing `DeployDOSTestnet.s.sol` deployment entrypoint.
- The committed Testnet deployment manifest produced after broadcast.
- `subgraph/dos-names`, including event ABIs, BENS-compatible schema, mappings, tests, manifest template, and render validation.
- CI that proves subgraph tests, code generation, and build succeed.

### DOScan

Owns:

- Pinned official runtime images and Compose wiring.
- BENS protocol configuration for chain 3939.
- Caddy same-origin routing.
- Standard Backend and Frontend environment variables.
- Deployment automation that fetches an exact DOS Names subgraph commit and deploys it to graph-node.
- Runtime health and API verification.

DOScan must not contain a maintained copy of the custom mapping source.

### DOS-Chain

Read-only reference for Testnet topology and ownership. This task does not modify DOS-Chain.

## Data Flow

`ENSv2 contracts -> DOS ENSv2 subgraph -> graph-node/PostgreSQL -> BENS API -> DOScan Backend/Frontend`

The adapter translates hierarchical ENSv2 registry and resolver events into the stable BENS ENS-like `Domain`, `Registration`, `Resolver`, and event entities. A token-to-domain mapping preserves the relationship because ENSv2 token IDs are not ENS namehashes.

## Deployment Artifact Contract

1. DOS Names deploys contracts with the dedicated Testnet deployer `0x99999e454138f6be73e2be82c890bc5765749999`.
2. Final protocol ownership is handed to `0x310Bc061214ee89aF5CfB28a6ebF96c5436fa3CD` unless a newer verified ownership record explicitly replaces it.
3. DOS Names records deployment block and contract addresses in a committed Testnet manifest.
4. The subgraph render command consumes that manifest and produces a concrete graph-node manifest.
5. DOScan pins the exact merged DOS Names commit and fetches only `subgraph/dos-names` during validation and deployment.

No private key, database password, or token may be committed or printed.

## Runtime Topology

- `bens-db`: official PostgreSQL image, internal volume, password supplied through the existing Testnet secrets environment.
- `bens-ipfs`: official Kubo image, internal volume.
- `bens-graph-node`: official graph-node image connected to the canonical Testnet RPC.
- `bens-deployer`: official Node image used only as a one-shot subgraph build and deployment job.
- `bens`: official Blockscout BENS image connected to the graph-node PostgreSQL database.
- `caddy`: proxies `/name-service/*` to BENS and strips the prefix.

No BENS, graph-node admin, PostgreSQL, or IPFS port is publicly exposed.

## Blockscout Configuration

Backend:

```env
MICROSERVICE_BENS_ENABLED=true
MICROSERVICE_BENS_URL=http://bens:8050/
MICROSERVICE_BENS_PROTOCOLS=dos-names
```

Frontend:

```env
NEXT_PUBLIC_NAME_SERVICE_API_HOST=https://test.doscan.io/name-service
NEXT_PUBLIC_NAME_SERVICE_PROTOCOLS=['dos-names']
```

## BENS Protocol Configuration

- Network ID: `3939`
- Protocol ID: `dos-names`
- TLD: `dos`
- Address resolution technique: `all_domains`
- Offchain resolution: disabled for this phase

ENSv2 does not provide the ENSv1 reverse registry assumed by `reverse_registry`. Address lookup therefore uses indexed domains with a current resolved address.

## Failure Handling

- Contract deployment fails closed when the chain ID, signer address, balance, owner, or RPC differs from the verified preflight.
- Subgraph deployment fails when the deployment manifest is absent, an address has no bytecode, code generation fails, the mapping build fails, or graph-node is not ready.
- DOScan deployment restores the previous Compose, env, Caddy, BENS config, and subgraph runtime bundle if health checks fail.
- Mainnet files and services are outside the deployment target.

## Verification Gates

- DOS Names contract tests and subgraph tests pass.
- Subgraph code generation and build pass from a clean install.
- All deployed contract addresses have bytecode.
- Handoff roles and ownership match the final owner, while the deployer no longer retains privileged roles covered by the deployment script.
- Graph-node indexes through the deployment block without deterministic errors.
- BENS health reports serving.
- `/name-service/api/v1/protocols` exposes `dos-names`.
- A real `.dos` test name is indexed, searchable, resolves to its address, and appears in DOScan.
- Playwright verifies the deployed Testnet UI after rollout.


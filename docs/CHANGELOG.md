# DOScan Changelog

All notable changes to DOScan (DOS Chain Block Explorer) are documented in this file.

---

## [2026-08-04] - Production Documentation and Runtime Baseline

### Deployed

- Mainnet and Testnet run Frontend `2.10.0` and custom Backend `v11.2.4.+commit.2d53484e` on GCP.
- Both production Compose files pin `ghcr.io/dos/doscan:11.2.4.commit.2d53484e@sha256:370eb1e8360ca86dfca3e13f9ffd0cb34e3d90be51cfbaf3abc91416994dc32e`.
- Mainnet runs on `doscan-mainnet` in `asia-southeast1-b`.
- Testnet runs on `dos-testnet-r0` in `asia-southeast1-a`.
- Beta runs as an isolated Compose stack on the Mainnet GCP VM. Its application state is separate from Mainnet, while it uses the local Mainnet archive RPC.

### Added

- Enabled the Blockscout Metadata Service in the backend and exposed it through same-origin Caddy proxies on Mainnet and Testnet.
- Enabled official BENS and Graph Node services on Testnet for the custom DOS Names ENSv2 subgraph and `.dos` protocol.
- Enabled NFT Media Handler with GCS storage and separate `mainnet/nft-media` and `testnet/nft-media` prefixes.
- Deployed Interchain Indexer v1.6.0 on Mainnet for DOS Chain and Avalanche C-Chain messages.
- Documented the current GCP deployment, edge routing, service layout, data isolation, and CI/CD flow.

### Changed

- Updated the production frontend to `2.10.0`.
- Updated the backend baseline to Blockscout `11.2.4`; the current tree retains the behavior introduced by custom commit `86fd0dd5`.
- Replaced stale Azure and local WSL2 architecture guidance with the active GCP topology.
- Corrected feature status: the admin panel remains disabled; BENS is enabled on Testnet and disabled on Mainnet, while Metadata Service is enabled.

### Fixed

- Commit `86fd0dd5` omits a missing original thumbnail for NFT videos instead of returning an invalid original-thumbnail value.
- Restored the direct `xav` dependency removed during the v11.2.4 sync and verified `Image.Video` against the exact published production digest.
- Production validation now checks backend health, version, Metadata proxy behavior, and environment-specific service routes.

### Verified

- Mainnet and Testnet `/api/v2/stats` returned HTTP 200.
- Mainnet and Testnet `/api/v2/config/backend-version` returned `v11.2.4.+commit.2d53484e`.
- Docker inspection showed both backend containers running and healthy on the pinned custom image.
- Mainnet and Testnet Metadata proxy probes returned HTTP 200 with an `addresses` object.
- Deploy Config run `30926419497` completed successfully for Mainnet and Testnet.

---

## [2026-02-01] - Testnet Feature Expansion

### Added

#### Frontend Features
- **User Operations Page** (`/ops`) - ERC-4337 Account Abstraction support
  - Integrated with `user-ops-indexer` microservice
  - API endpoint: `https://test-ops.doscan.io`

- **Homepage Stats Widget** - Display key blockchain metrics on homepage
  - `total_blocks`, `average_block_time`, `total_txs`, `wallet_addresses`, `gas_tracker`

- **Get Gas Button** - Link to DOS Faucet for testnet tokens
  - URL: `https://faucet.doschain.com?address={address}`

#### Backend Features
- **Account Abstraction Microservice** - Backend support for ERC-4337
  - `MICROSERVICE_ACCOUNT_ABSTRACTION_ENABLED=true`
  - URL: `http://host.docker.internal:8090/`

- **Admin Panel** - Backend administration interface
  - `ADMIN_PANEL_ENABLED=true`

- **GraphQL API** - GraphQL endpoint for queries
  - `API_GRAPHQL_ENABLED=true`

- **Sourcify Integration** - Alternative contract verification
  - `SOURCIFY_INTEGRATION_ENABLED=true`
  - Server: `https://sourcify.dev/server`

#### Infrastructure
- **test-stats.doscan.io** - Dedicated stats API for testnet
  - Port: 8052
  - Container: `test-stats`
  - Database: testnet blockscout DB (port 7432)

- **test-ops.doscan.io** - User Ops API endpoint
  - Port: 8090
  - Container: `user-ops-indexer`

### Changed
- Updated `NEXT_PUBLIC_STATS_API_HOST` from `stats-beta.doscan.io` to `test-stats.doscan.io`
- Added `ops` route to nginx frontend regex for proper routing

### Fixed
- Fixed User Ops page 404 error by adding route to nginx config
- Fixed frontend env syntax error for `NEXT_PUBLIC_HOMEPAGE_STATS`

---

## [2026-01-31] - User Ops Indexer Deployment

### Added
- Deployed `user-ops-indexer` container for ERC-4337 support
- Created nginx config for `test-ops.doscan.io`
- Added CORS headers for cross-origin API access

### Configuration
```yaml
USER_OPS_INDEXER__INDEXER__RPC_URL: http://10.0.0.4:9650/ext/bc/.../rpc
USER_OPS_INDEXER__INDEXER__ENTRYPOINTS__V08: "true"
USER_OPS_INDEXER__INDEXER__ENTRYPOINTS__V08_ENTRY_POINT: "0x433709009B8330FDa32311DF1C2AFA402eD8D009"
USER_OPS_INDEXER__DATABASE__CONNECT__URL: postgresql://postgres:@host.docker.internal:7432/blockscout
```

---

## [2026-01-30] - Testnet Explorer Launch

### Added
- Full Blockscout deployment for DOS Chain Testnet
- Frontend v2.6.0 (latest)
- Backend v9.0.2

### Services Deployed
- Frontend (`ghcr.io/blockscout/frontend:latest`)
- Backend (`blockscout/blockscout:latest`)
- PostgreSQL 15
- Redis
- Smart Contract Verifier
- Visualizer (Sol2UML)
- Sig Provider

### Domains Configured
- `test.doscan.io` - Main explorer
- `test-api.doscan.io` - API endpoint
- `viz-beta.doscan.io` - Visualizer
- `stats-beta.doscan.io` - Stats (legacy)

---

## [2026-01-23] - Initial Setup

### Added
- Initial DOScan project structure
- Docker Compose configuration for testnet
- Environment variable templates

### Network Configuration
- Chain ID: 3939
- RPC: `https://test.doschain.com`
- Blockchain ID: `e4PHth8utBAPorg4sFRTaWmDfUWf9X8nAECczGx1BJVmYBv3A`

---

## Current Follow-up

### Product prerequisites

- [ ] Add a Validators view only after an Avalanche L1-compatible implementation exists.
- [ ] Enable user accounts only after a supported identity and email stack is selected.
- [ ] Enable CSV export only after the export service and anti-abuse configuration are deployed.
- [ ] Register DEX pools only after official or verified DOSwap Factory and Pair contracts with liquidity are available.
- [ ] Enable BENS on Mainnet only after the Testnet DOS Name Service rollout passes acceptance checks.

### Operations

- [ ] Keep production image pins immutable by tag and digest.
- [ ] Keep automated database backup and restore validation documented and tested.
- [ ] Keep public, container, and deployment-workflow evidence aligned when changing runtime status documentation.

---

## Version History

| Date | Frontend | Backend | Notes |
|------|----------|---------|-------|
| 2026-08-04 | 2.10.0 | 11.2.4 + `2d53484e` | Current GCP production baseline; NFT video decoding restored and verified |
| 2026-02-01 | latest | latest | Feature expansion |
| 2026-01-30 | v2.6.0 | v9.0.2 | Initial testnet launch |

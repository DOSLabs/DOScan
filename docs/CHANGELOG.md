# DOScan Changelog

All notable changes to DOScan (DOS Chain Block Explorer) are documented in this file.

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

## Pending / Roadmap

### Mainnet Deployment
- [ ] Deploy to mainnet (Chain ID: 7979)
- [ ] Configure `doscan.io` domain
- [ ] Set up production database

### Features to Enable
- [ ] Validators List (requires custom implementation for Avalanche L1)
- [ ] My Account full integration with Auth0
- [ ] Export to CSV feature
- [ ] Public tag submission

### Infrastructure
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure automated backups
- [ ] Set up CI/CD pipeline

---

## Version History

| Date | Frontend | Backend | Notes |
|------|----------|---------|-------|
| 2026-02-01 | latest | latest | Feature expansion |
| 2026-01-30 | v2.6.0 | v9.0.2 | Initial testnet launch |

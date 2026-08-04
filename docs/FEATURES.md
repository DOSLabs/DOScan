# DOScan Feature Status

This document records the deployed feature baseline for DOScan Mainnet and Testnet.

**Last verified:** 2026-08-04

## Runtime Baseline

| Environment | Explorer | Chain ID | Frontend | Backend | Runtime status |
|---|---|---:|---|---|---|
| Mainnet | `https://doscan.io` | 7979 | `2.10.0` | `v11.2.3.+commit.86fd0dd5` | HTTP 200, backend healthy |
| Testnet | `https://test.doscan.io` | 3939 | `2.10.0` | `v11.2.3.+commit.86fd0dd5` | HTTP 200, backend healthy |

Both production environments pin the custom backend image below:

```text
ghcr.io/dos/doscan:11.2.3.commit.86fd0dd5@sha256:423bab078a679d3290cc6e276774a8ed201686636933e0d066ce9859270f700d
```

Commit `86fd0dd5` fixes NFT video media processing so a missing original thumbnail is omitted instead of emitting an invalid value.

## Backend Features

### APIs and Access

| Feature | Configuration | Mainnet | Testnet | Notes |
|---|---|---|---|---|
| API v2 | Default Blockscout API | Enabled | Enabled | `/api/v2/stats` and `/api/v2/config/backend-version` return HTTP 200 |
| API v1 read methods | `API_V1_READ_METHODS_DISABLED=false` | Enabled | Enabled | Shared base configuration |
| API v1 write methods | `API_V1_WRITE_METHODS_DISABLED=false` | Enabled | Enabled | Shared base configuration |
| GraphQL API | `API_GRAPHQL_ENABLED=true` | Enabled | Enabled | Shared base configuration |
| Public metrics | `/public-metrics` route | Enabled | Enabled | Checked by the deployment workflow |
| Admin panel | `ADMIN_PANEL_ENABLED=false` | Disabled | Disabled | Deliberately not exposed in production |
| Proxy-aware API rate limiting | `API_RATE_LIMIT_IS_BLOCKSCOUT_BEHIND_PROXY=true` | Enabled | Enabled | Uses Cloudflare and forwarded client IP headers |

### Indexing

| Feature | Mainnet | Testnet | Notes |
|---|---|---|---|
| Blocks and transactions | Enabled | Enabled | Core Blockscout indexer |
| Internal transactions | Enabled | Disabled | Testnet RPC does not expose the required debug tracing interface |
| Pending transactions | Enabled | Disabled | Testnet RPC does not expose `txpool_content` |
| Cataloged token updater | Enabled | Enabled | `INDEXER_DISABLE_CATALOGED_TOKEN_UPDATER_FETCHER=false` |
| Token instance metadata processing | Enabled | Enabled | Includes retry, refetch, sanitization, and NFT media integration |
| Market data | Disabled | Disabled | `DISABLE_MARKET=true`; DOS is not sourced from a configured market provider |

### Backend Integrations and Services

| Service or integration | Mainnet | Testnet | Runtime path |
|---|---|---|---|
| Smart Contract Verifier | Enabled | Enabled | `smart-contract-verifier:8050` |
| Sol2UML Visualizer | Enabled | Enabled | `visualizer:8050` |
| Signature Provider | Enabled | Enabled | `sig-provider:8050` |
| Account Abstraction | Enabled | Enabled | `user-ops-indexer:8050`, EntryPoint v0.6, v0.7, and v0.8 |
| Stats service | Enabled | Enabled | Separate Stats database in each environment |
| Metadata Service | Enabled | Enabled | Backend integration plus same-origin Caddy proxy |
| Sourcify | Enabled | Enabled | `https://sourcify.dev/server` |
| Decode non-contract calls | Enabled | Enabled | `DECODE_NOT_A_CONTRACT_CALLS=true` |
| Interchain Indexer | Enabled | Not deployed | Mainnet indexes Avalanche C-Chain and DOS Chain cross-chain messages |

### NFT Media Handler

| Capability | Mainnet | Testnet | Notes |
|---|---|---|---|
| Media handler | Enabled | Enabled | Runs inside the custom Blockscout backend |
| Backfill | Enabled | Enabled | `NFT_MEDIA_HANDLER_BACKFILL_ENABLED=true` |
| Object storage | `gs://doscan/mainnet/nft-media` | `gs://doscan/testnet/nft-media` | Separate prefixes in the shared public GCS bucket |
| Generated assets | Original plus 60, 250, and 500 px thumbnails | Original plus 60, 250, and 500 px thumbnails | Video records omit a missing original thumbnail after `86fd0dd5` |

See [NFT Media Handler](NFT-MEDIA-HANDLER.md) for implementation and operational details.

## Frontend Features Backed by Production Services

| Feature | Mainnet | Testnet | Notes |
|---|---|---|---|
| Advanced filter | Enabled | Enabled | Shared frontend configuration |
| Gas tracker | Enabled | Enabled | Included in homepage stats |
| User Operations | Enabled | Enabled | Backed by the local Account Abstraction service |
| DEX Pools UI | Enabled | Enabled | A truthful empty state is expected until official or verified Factory and Pair contracts are recorded |
| Hot Contracts | Enabled | Enabled | Results depend on sufficient chain history |
| Metadata address tags | Enabled | Enabled | Uses `/metadata-api` on the same explorer origin |
| Contract Info proxy | Enabled | Enabled | Proxied through each explorer origin |
| Cross-chain transactions | Enabled | Disabled | Mainnet only, backed by Interchain Indexer v1.6.0 |
| Marketplace | Enabled | Enabled | Uses checked-in DOS configuration URLs |
| Wallet helpers | Enabled | Enabled | MetaMask, Rabby, Coinbase Wallet, and TokenPocket |

The detailed frontend environment audit is maintained in [Frontend Environment Audit](reports/doscan-frontend-env-audit.vi.html).

## Deliberately Disabled or Blocked Features

| Feature | Status | Reason or prerequisite |
|---|---|---|
| BENS / name service | Disabled | No DOS or `.dos` BENS protocol is configured for chain 7979 or 3939 |
| Multichain Search | Disabled | No dedicated Multichain Search service is deployed |
| User accounts and Auth0 | Disabled | Requires a supported identity and email stack |
| CSV export | Disabled | Requires the export service and anti-abuse configuration |
| Transaction interpretation provider | Disabled | No approved provider and credential are configured |
| Validators list | Disabled | The upstream UI does not provide the required Avalanche L1 integration |
| Beacon, rollup, blob, Celo, Stylus, and SUAVE features | Not applicable | These chain-specific features do not match DOS Chain |

## Operational Evidence

The 2026-08-04 verification used all of the following evidence layers:

1. Checked-in Compose image pins and environment overrides.
2. GCP instance inventory for `doscan-mainnet` and `dos-testnet-r0`.
3. Docker runtime inspection showing both backend containers healthy on the pinned custom image.
4. HTTP 200 responses from Mainnet and Testnet Stats, backend version, frontend config, and Metadata proxy endpoints.
5. Git history confirming that `86fd0dd5` is the NFT video original-thumbnail fix.
6. [Deploy Config run 30878181874](https://github.com/DOS/DOScan/actions/runs/30878181874), which completed successfully for Mainnet and Testnet on the current production head.

Configuration in Git describes the intended deployment. Live HTTP and container checks confirm the running deployment. Neither evidence layer should be used alone when updating this document.

## References

- [DOScan Architecture](DOScan-ARCHITECTURE.md)
- [Frontend Environment Audit](reports/doscan-frontend-env-audit.vi.html)
- [NFT Media Handler](NFT-MEDIA-HANDLER.md)
- [Blockscout backend environment variables](https://docs.blockscout.com/setup/env-variables/backend-env-variables)

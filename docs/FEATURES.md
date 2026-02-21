# DOScan Features Summary

Tổng hợp các tính năng Blockscout đã bật/chưa bật cho DOS Chain Testnet.

**Last Updated:** 2026-02-02

---

## Frontend Features

### App Configuration
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| App Protocol | `NEXT_PUBLIC_APP_PROTOCOL` | ✅ `https` | |
| App Host | `NEXT_PUBLIC_APP_HOST` | ✅ `test.doscan.io` | |
| App Environment | `NEXT_PUBLIC_APP_ENV` | ✅ `production` | |

### Blockchain Parameters
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| Network Name | `NEXT_PUBLIC_NETWORK_NAME` | ✅ `DOS Chain Testnet` | |
| Network ID | `NEXT_PUBLIC_NETWORK_ID` | ✅ `3939` | |
| Network RPC | `NEXT_PUBLIC_NETWORK_RPC_URL` | ✅ `https://test.doschain.com` | |
| Currency Symbol | `NEXT_PUBLIC_NETWORK_CURRENCY_SYMBOL` | ✅ `DOS` | |
| Testnet Indicator | `NEXT_PUBLIC_IS_TESTNET` | ✅ `true` | |
| Token Standard | `NEXT_PUBLIC_NETWORK_TOKEN_STANDARD_NAME` | ✅ `ERC` | |
| Multiple Gas Currencies | `NEXT_PUBLIC_NETWORK_MULTIPLE_GAS_CURRENCIES` | ❌ | Not needed |

### UI - Homepage
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| Homepage Charts | `NEXT_PUBLIC_HOMEPAGE_CHARTS` | ✅ `['daily_txs']` | |
| Homepage Stats | `NEXT_PUBLIC_HOMEPAGE_STATS` | ✅ 5 widgets | total_blocks, avg_block_time, total_txs, wallet_addresses, gas_tracker |
| Hero Plate Background | `NEXT_PUBLIC_HOMEPAGE_PLATE_BACKGROUND` | ✅ Custom gradient | |
| Hero Banner | `NEXT_PUBLIC_HOMEPAGE_HERO_BANNER_CONFIG` | ❌ | Optional |

### UI - Branding
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| Network Logo | `NEXT_PUBLIC_NETWORK_LOGO` | ✅ Custom | |
| Network Logo Dark | `NEXT_PUBLIC_NETWORK_LOGO_DARK` | ✅ Custom | |
| Network Icon | `NEXT_PUBLIC_NETWORK_ICON` | ✅ Custom | |
| Favicon | `FAVICON_MASTER_URL` | ✅ Custom | |
| Footer Links | `NEXT_PUBLIC_FOOTER_LINKS` | ✅ Custom JSON | |
| Featured Networks | `NEXT_PUBLIC_FEATURED_NETWORKS` | ✅ Custom JSON | |

### UI - Views
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| SolidityScan | `NEXT_PUBLIC_VIEWS_CONTRACT_SOLIDITYSCAN_ENABLED` | ✅ Enabled | Security scoring |
| Token Scam Toggle | `NEXT_PUBLIC_VIEWS_TOKEN_SCAM_TOGGLE_ENABLED` | ✅ Enabled | |
| NFT Marketplaces | `NEXT_PUBLIC_VIEWS_NFT_MARKETPLACES` | ✅ OverMint | |
| Contract IDEs | `NEXT_PUBLIC_CONTRACT_CODE_IDES` | ✅ Remix IDE | |
| Network Explorers | `NEXT_PUBLIC_NETWORK_EXPLORERS` | ✅ Configured | |

### Core Features
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| Gas Tracker | `NEXT_PUBLIC_GAS_TRACKER_ENABLED` | ✅ Enabled | |
| Advanced Filter | `NEXT_PUBLIC_ADVANCED_FILTER_ENABLED` | ✅ Enabled | |
| API Documentation | `NEXT_PUBLIC_API_DOCS_TABS` | ✅ rest, eth_rpc, graphql | |

### Account & Auth
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| My Account | `NEXT_PUBLIC_IS_ACCOUNT_SUPPORTED` | ✅ Enabled | |
| Auth0 Integration | `NEXT_PUBLIC_AUTH0_CLIENT_ID` | ✅ Configured | Deprecated but working |
| Address Verification | `NEXT_PUBLIC_CONTRACT_INFO_API_HOST` | ✅ Blockscout service | |

### Blockchain Interaction
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| WalletConnect | `NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID` | ✅ Configured | |
| Web3 Wallets | `NEXT_PUBLIC_WEB3_WALLETS` | ✅ 6 wallets | metamask, rabby, coinbase, trust, okx, token_pocket |
| Add Token to Wallet | `NEXT_PUBLIC_WEB3_DISABLE_ADD_TOKEN_TO_WALLET` | ✅ Enabled | |
| Transaction Interpretation | `NEXT_PUBLIC_TRANSACTION_INTERPRETATION_PROVIDER` | ✅ Blockscout | |

### Microservice Integrations
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| User Operations (ERC-4337) | `NEXT_PUBLIC_HAS_USER_OPS` | ✅ Enabled | `https://test-ops.doscan.io` |
| Blockchain Statistics | `NEXT_PUBLIC_STATS_API_HOST` | ✅ Enabled | `https://test-stats.doscan.io` |
| Sol2UML Visualizer | `NEXT_PUBLIC_VISUALIZE_API_HOST` | ✅ Enabled | `https://viz-beta.doscan.io` |
| Name Service | `NEXT_PUBLIC_NAME_SERVICE_API_HOST` | ✅ Blockscout BENS | |

### Marketplace
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| DApp Marketplace | `NEXT_PUBLIC_MARKETPLACE_ENABLED` | ✅ Enabled | |
| Marketplace Config | `NEXT_PUBLIC_MARKETPLACE_CONFIG_URL` | ✅ Custom JSON | |
| Submit Form | `NEXT_PUBLIC_MARKETPLACE_SUBMIT_FORM` | ✅ Google Form | |
| Categories | `NEXT_PUBLIC_MARKETPLACE_CATEGORIES_URL` | ✅ Custom JSON | |

### Additional Features
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| DEX Pools | `NEXT_PUBLIC_DEX_POOLS_ENABLED` | ✅ Enabled | |
| Hot Contracts | `NEXT_PUBLIC_HOT_CONTRACTS_ENABLED` | ✅ Enabled | |
| Bridged Tokens | `NEXT_PUBLIC_BRIDGED_TOKENS_CHAINS` | ✅ Ethereum | |
| Get Gas Button | `NEXT_PUBLIC_GAS_REFUEL_PROVIDER_CONFIG` | ✅ DOS Faucet | |
| Google Analytics | `NEXT_PUBLIC_GOOGLE_ANALYTICS_PROPERTY_ID` | ✅ Configured | |

### Features NOT Enabled (Optional)
| Feature | Env Variable | Reason |
|---------|--------------|--------|
| Beacon Chain | `NEXT_PUBLIC_HAS_BEACON_CHAIN` | Not applicable (not Ethereum) |
| Rollup Features | `NEXT_PUBLIC_ROLLUP_TYPE` | Not a rollup |
| Data Availability | `NEXT_PUBLIC_DATA_AVAILABILITY_ENABLED` | No EIP-4844 blobs |
| Validators List | `NEXT_PUBLIC_VALIDATORS_CHAIN_TYPE` | Avalanche L1 uses PoA |
| SUAVE Chain | `NEXT_PUBLIC_IS_SUAVE_CHAIN` | Not SUAVE |
| Celo Features | `NEXT_PUBLIC_CELO_ENABLED` | Not Celo |
| Banner Ads | `NEXT_PUBLIC_AD_BANNER_PROVIDER` | Disabled (none) |
| Text Ads | `NEXT_PUBLIC_AD_TEXT_PROVIDER` | Disabled (none) |
| Mixpanel | `NEXT_PUBLIC_MIXPANEL_PROJECT_TOKEN` | Optional analytics |
| GrowthBook | `NEXT_PUBLIC_GROWTH_BOOK_CLIENT_KEY` | Optional A/B testing |
| MetaSuites | `NEXT_PUBLIC_METASUITES_ENABLED` | Optional extension |
| Multichain Balance | `NEXT_PUBLIC_MULTICHAIN_BALANCE_PROVIDER_CONFIG` | Future feature |
| DeFi Dropdown | `NEXT_PUBLIC_DEFI_DROPDOWN_ITEMS` | No DeFi apps yet |
| CSV Export | Requires reCAPTCHA | Not configured |

---

## Backend Features

### Core Services
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| API v2 | `API_V2_ENABLED` | ✅ Default | |
| API v1 Read | `API_V1_READ_METHODS_DISABLED` | ✅ Enabled | |
| API v1 Write | `API_V1_WRITE_METHODS_DISABLED` | ✅ Enabled | |
| GraphQL API | `API_GRAPHQL_ENABLED` | ✅ Enabled | |
| Admin Panel | `ADMIN_PANEL_ENABLED` | ✅ Enabled | |

### Indexer Settings
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| Internal Transactions | `INDEXER_DISABLE_INTERNAL_TRANSACTIONS_FETCHER` | ✅ Enabled (false) | |
| Pending Transactions | `INDEXER_DISABLE_PENDING_TRANSACTIONS_FETCHER` | ✅ Enabled (false) | |
| Token Instance Fetchers | Various | ✅ Enabled | realtime, retry, sanitize |
| Block Reward Fetcher | `INDEXER_DISABLE_BLOCK_REWARD_FETCHER` | ✅ Default | |

### Microservices
| Service | Env Variables | Status | URL |
|---------|---------------|--------|-----|
| Smart Contract Verifier | `MICROSERVICE_SC_VERIFIER_*` | ✅ Enabled | eth-bytecode-db.services.blockscout.com |
| Visualizer (Sol2UML) | `MICROSERVICE_VISUALIZE_SOL2UML_*` | ✅ Enabled | http://visualizer:8050/ |
| Sig Provider | `MICROSERVICE_SIG_PROVIDER_*` | ✅ Enabled | http://sig-provider:8050/ |
| Account Abstraction | `MICROSERVICE_ACCOUNT_ABSTRACTION_*` | ✅ Enabled | http://host.docker.internal:8090/ |

### External Integrations
| Feature | Env Variable | Status | Notes |
|---------|--------------|--------|-------|
| Sourcify | `SOURCIFY_INTEGRATION_ENABLED` | ✅ Enabled | sourcify.dev |
| Decode Non-Contract Calls | `DECODE_NOT_A_CONTRACT_CALLS` | ✅ Enabled | |

### Features NOT Enabled (Optional)
| Feature | Env Variable | Reason |
|---------|--------------|--------|
| BENS (ENS) | `MICROSERVICE_BENS_*` | No ENS on DOS Chain |
| Multichain Search | `MICROSERVICE_MULTICHAIN_SEARCH_*` | Single chain |
| Metadata Service | `MICROSERVICE_METADATA_*` | Optional |
| Noves.fi | `NOVES_FI_*` | Optional tx interpretation |
| Tenderly | `SHOW_TENDERLY_LINK` | Optional debugging |
| Datadog | `DATADOG_*` | Optional monitoring |
| MUD Framework | `MUD_*` | Not using MUD |
| Stylus Verifier | `MICROSERVICE_STYLUS_VERIFIER_URL` | Not Arbitrum |
| Xname | `XNAME_*` | Optional humanity score |

---

## Summary Statistics

### Frontend
| Category | Enabled | Available | Percentage |
|----------|---------|-----------|------------|
| Core Config | 8/8 | 8 | 100% |
| UI/Branding | 12/15 | 15 | 80% |
| Core Features | 6/6 | 6 | 100% |
| Microservice APIs | 4/4 | 4 | 100% |
| Marketplace | 4/4 | 4 | 100% |
| Analytics | 1/4 | 4 | 25% |
| Optional/Chain-specific | 3/15 | 15 | 20% |
| **Total Essential** | **38/42** | **42** | **90%** |

### Backend
| Category | Enabled | Available | Percentage |
|----------|---------|-----------|------------|
| Core APIs | 4/4 | 4 | 100% |
| Indexers | 4/4 | 4 | 100% |
| Microservices | 4/8 | 8 | 50% |
| External Integrations | 2/6 | 6 | 33% |
| **Total Essential** | **14/16** | **16** | **88%** |

---

## Recommendations

### High Priority (Should Enable)
1. **CSV Export** - Requires reCAPTCHA setup
2. **Public Tag Submission** - Requires Metadata Service

### Medium Priority (Nice to Have)
1. **Mixpanel Analytics** - Better user tracking
2. **Multichain Balance** - When supporting multiple chains
3. **DeFi Dropdown** - When DeFi apps launch

### Low Priority (Optional)
1. **MetaSuites Extension** - Browser extension support
2. **GrowthBook** - A/B testing
3. **Noves.fi** - Enhanced tx interpretation

---

## References

- [Frontend ENV Docs](https://docs.blockscout.com/setup/env-variables/frontend-common-envs/envs)
- [Backend ENV Docs](https://docs.blockscout.com/setup/env-variables/backend-env-variables)
- [Backend Integrations](https://docs.blockscout.com/setup/env-variables/backend-envs-integrations)

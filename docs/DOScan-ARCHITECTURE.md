# DOScan Architecture

## Overview

DOScan is the blockchain explorer for DOS Chain, built on [Blockscout](https://github.com/blockscout/blockscout). This document describes the architecture for both Testnet and Mainnet deployments.

---

## Environments

| Environment | Domain | Chain ID | VM | Status |
|-------------|--------|----------|----|--------|
| Testnet | test.doscan.io | 3939 | `dev` (20.198.249.62) | Active |
| Mainnet | doscan.io | 7979 | `archive` (20.195.24.239) | Active (indexing) |

---

## Mainnet Architecture

### Server: Azure VM `archive` (METADOS Resource Group)

- **IP:** 20.195.24.239
- **OS:** Ubuntu
- **Access:** SSH `JOY@20.195.24.239`
- **Compose Path:** `/home/JOY/doscan/`
- **AvalancheGo Data:** `/home/JOY/.avalanchego/`

### Architecture Diagram

```
                         ┌─────────────┐
                         │ CLOUDFLARE   │
                         │ (DNS + CDN) │
                         └──────┬──────┘
                                │
           ┌────────────────────┼─────────────────────┐
           │                    │                      │
           ▼                    ▼                      ▼
    doscan.io            api.doscan.io          stats.doscan.io
    www.doscan.io                               viz.doscan.io
           │                    │                      │
           └────────────────────┼──────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Caddy (Reverse Proxy + Cloudflare Origin SSL)              │
│  Certs: /home/JOY/doscan/certs/ (Cloudflare Origin Certificate)            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  doscan.io/www ────────┬──► :3000 Frontend (Next.js)       [default]       │
│                         ├──► :4000 Backend   /api/* /socket/* /auth/*       │
│                         └──► :8050 Visualizer  /visualize/*                │
│                                                                             │
│  api.doscan.io ────────────► :4000 Backend (all paths)                     │
│                                                                             │
│  stats.doscan.io ──────────► :8050 Stats Service (CORS: doscan.io)         │
│                                                                             │
│  viz.doscan.io ────────────► :8050 Visualizer (CORS: doscan.io)            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                   Docker Compose (`~/doscan/compose.yml`)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  backend ──────── doscan-backend:latest (custom Blockscout build)          │
│    └── RPC: http://host.docker.internal:9650/ext/bc/22v7AG7.../rpc        │
│                                                                             │
│  frontend ─────── doscan-frontend:latest (custom Blockscout build)         │
│                                                                             │
│  db ───────────── PostgreSQL 15 (127.0.0.1:7432 → 5432)                   │
│  redis-db ─────── Redis Alpine (6379)                                      │
│                                                                             │
│  stats ────────── ghcr.io/blockscout/stats:latest (127.0.0.1:8052)        │
│  smart-contract-verifier ── ghcr.io/blockscout/smart-contract-verifier     │
│  visualizer ────────────── ghcr.io/blockscout/visualizer                   │
│  sig-provider ──────────── ghcr.io/blockscout/sig-provider                 │
│  caddy ─────────────────── caddy:latest (80, 443)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                  AvalancheGo (Native Systemd — NOT Docker)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Binary: /usr/local/bin/avalanchego (v1.14.1, built-in subnet-evm)        │
│  Service: systemctl start|stop avalanchego                                 │
│  Port 9650 (127.0.0.1) ── RPC for Blockscout (via host.docker.internal)  │
│  Port 9651 (public)    ── P2P                                              │
│  Mode: Archive (pruning-enabled: false)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **NOTE:** AvalancheGo runs as **native systemd service**, NOT in Docker Compose.
> Blockscout backend connects via `host.docker.internal:9650` to reach the host's RPC.

### RPC Connection

- **Backend RPC:** `http://host.docker.internal:9650/ext/bc/22v7AG7h6qaVxd4bLvAsSsg2LZ4RCn5iVYgFn7a2Fj1LCuYwjv/rpc` (local native archive node via Docker bridge)
- **Public RPC:** `https://main.doschain.com` (via Cloudflare → gw `20.6.91.153` nginx → r0/r1 internal `10.0.0.15`/`10.0.0.17`)
- **Archive RPC:** `https://main2.doschain.com` (via Cloudflare → gw `20.6.91.153` nginx → archive1 internal `10.0.0.26`)
- **Chain ID:** 7979
- **Blockchain ID:** `22v7AG7h6qaVxd4bLvAsSsg2LZ4RCn5iVYgFn7a2Fj1LCuYwjv`

> **IMPORTANT:** Backend MUST use local avago RPC, NOT main.doschain.com.
> Doscan generates ~2M requests/day which will overload r0 and get rate-limited by Cloudflare.

### Compose File Structure

```
/home/JOY/doscan/
├── compose.yml                    # Main docker compose (source: docker-compose/docker-compose-mainnet.yml)
├── Caddyfile                      # Caddy reverse proxy config (source: docker-compose/Caddyfile-mainnet)
├── certs/                         # Cloudflare Origin SSL certificates (NOT in repo)
│   ├── origin.pem                 # Certificate
│   └── origin-key.pem            # Private key
├── envs/
│   ├── common-blockscout.env      # Backend config (RPC URLs, chain settings, SECRET_KEY_BASE)
│   ├── common-frontend.env        # Frontend config (UI settings, stats/viz API hosts)
│   ├── common-smart-contract-verifier.env
│   └── common-visualizer.env
└── frontend-override.env
```

### Key Backend Config (`envs/common-blockscout.env`)

```env
ETHEREUM_JSONRPC_VARIANT=geth
ETHEREUM_JSONRPC_HTTP_URL=http://host.docker.internal:9650/ext/bc/22v7AG7h6qaVxd4bLvAsSsg2LZ4RCn5iVYgFn7a2Fj1LCuYwjv/rpc
ETHEREUM_JSONRPC_TRACE_URL=http://host.docker.internal:9650/ext/bc/22v7AG7h6qaVxd4bLvAsSsg2LZ4RCn5iVYgFn7a2Fj1LCuYwjv/rpc
ETHEREUM_JSONRPC_WS_URL=ws://host.docker.internal:9650/ext/bc/22v7AG7h6qaVxd4bLvAsSsg2LZ4RCn5iVYgFn7a2Fj1LCuYwjv/ws
CHAIN_ID=7979
NETWORK=DOS Chain
SUBNETWORK=Mainnet
```

> Backend uses `host.docker.internal` to reach the native AvalancheGo running on the host (port 9650 bound to 127.0.0.1).

### Caddy Domains & Routing

| Domain | Backend | CORS |
|--------|---------|------|
| `doscan.io`, `www.doscan.io` | Frontend (:3000) default, Backend (:4000) for `/api/*`, `/socket/*`, `/auth/*`, `/sitemap.xml`, `/metrics`; Visualizer (:8050) for `/visualize/*` | — |
| `api.doscan.io` | Backend (:4000) all paths | — |
| `stats.doscan.io` | Stats (:8050) | `https://doscan.io` |
| `viz.doscan.io` | Visualizer (:8050) | `https://doscan.io` |

All domains use Cloudflare Origin SSL certificates (`/etc/caddy/certs/origin.pem`).

### AvalancheGo Archive Node Config

AvalancheGo runs as **native systemd** on the host (NOT Docker):

```bash
# Binary: /usr/local/bin/avalanchego (v1.14.1, built-in subnet-evm — no plugin file needed)
sudo systemctl status avalanchego
```

```
/home/JOY/.avalanchego/
├── configs/
│   └── chains/
│       └── 22v7AG7h6qaVxd4bLvAsSsg2LZ4RCn5iVYgFn7a2Fj1LCuYwjv/
│           ├── config.json        # pruning-enabled: false (archive mode), full debug APIs
│           └── upgrade.json       # Warp activation + stateUpgrades (~26KB)
├── staking/
├── plugins/                       # Legacy plugin file (not used by v1.14.1+)
└── db/
```

Track subnet: `nQCwF6V9y8VFjvMuPeQVWWYn6ba75518Dpf6ZMWZNb3NyTA94`

### Deployment

**CI/CD:** GitHub Actions workflow `.github/workflows/deploy-config.yml`

- **Auto deploy:** Push to `main` branch (changes in `docker-compose/**`)
- **Manual deploy:** Workflow dispatch → choose mainnet / testnet / both

**Flow:** GitHub Actions → SCP configs to VM → SSH apply + restart services

**GitHub Environments & Secrets:**

| Environment | Secret | Variables |
|---|---|---|
| `mainnet` | `SSH_PRIVATE_KEY` | `MAINNET_HOST`=20.195.24.239, `SSH_USER`=JOY |
| `testnet` | `SSH_PRIVATE_KEY` | `TESTNET_HOST`=20.198.249.62, `SSH_USER`=JOY |

> **Note:** `SECRET_KEY_BASE` in `common-blockscout.env` is redacted to `CHANGE_ME` in repo.
> Real value is kept on the VM. Deploy workflow skips copying blockscout env if it contains placeholder.

**Manual commands:**

```bash
# SSH to archive VM
ssh -i ~/.ssh/Ed25519 JOY@20.195.24.239

# Restart backend
cd ~/doscan && sudo docker compose restart backend

# Recreate backend (after env changes)
cd ~/doscan && sudo docker compose up -d --no-deps --force-recreate backend

# View backend logs
docker logs backend --tail 100 -f

# Restart all services
cd ~/doscan && sudo docker compose restart

# Check avago sync status (native process)
curl -s -X POST --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  -H 'content-type:application/json' http://localhost:9650/ext/bc/22v7AG7h6qaVxd4bLvAsSsg2LZ4RCn5iVYgFn7a2Fj1LCuYwjv/rpc
```

---

## Testnet Architecture

### Server: Azure VM `dev` (METADOS Resource Group)

- **IP:** 20.198.249.62
- **OS:** Ubuntu
- **Services Path:** `/home/ubuntu/services/DOScan/docker-compose/`

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NGINX (Reverse Proxy)                          │
│  SSL: /etc/nginx/ssls/doscan.com_cert.pem                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  test.doscan.io ──────────┬──► :3000 Frontend (Next.js)                     │
│                           └──► :4000 Backend (Elixir)                       │
│                                                                             │
│  test-api.doscan.io ─────────► :4000 Backend API                            │
│                                                                             │
│  test-stats.doscan.io ───────► :8052 Stats Service                          │
│                                                                             │
│  test-ops.doscan.io ─────────► :8090 User Ops Indexer (ERC-4337)            │
│                                                                             │
│  viz-beta.doscan.io ─────────► :8051 Visualizer (Sol2UML)                   │
│                                                                             │
│  stats-beta.doscan.io ───────► :8050 Stats Service (legacy)                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### RPC Connection (Testnet)

- **Internal:** `http://10.0.0.4:9650/ext/bc/e4PHth8utBAPorg4sFRTaWmDfUWf9X8nAECczGx1BJVmYBv3A/rpc`
- **Public:** `https://test.doschain.com`
- **Chain ID:** 3939
- **Blockchain ID:** `e4PHth8utBAPorg4sFRTaWmDfUWf9X8nAECczGx1BJVmYBv3A`

### Deployment Commands (Testnet)

```bash
# Restart backend
az vm run-command invoke --resource-group METADOS --name dev \
  --command-id RunShellScript --scripts "docker restart backend"

# Restart frontend
az vm run-command invoke --resource-group METADOS --name dev \
  --command-id RunShellScript --scripts "docker restart frontend"

# View logs
az vm run-command invoke --resource-group METADOS --name dev \
  --command-id RunShellScript --scripts "docker logs backend --tail 100"

# Reload Nginx
az vm run-command invoke --resource-group METADOS --name dev \
  --command-id RunShellScript --scripts "nginx -t && systemctl reload nginx"
```

---

## Services (Shared across environments)

### Core Services

| Service | Container | Port | Image |
|---------|-----------|------|-------|
| Frontend | `frontend` | 3000 | `doscan-frontend:latest` (mainnet) / `ghcr.io/blockscout/frontend:latest` (testnet) |
| Backend | `backend` | 4000 | `doscan-backend:latest` (mainnet) / `blockscout/blockscout:latest` (testnet) |
| Database | `db` | 7432 | `postgres:15` |
| Redis | `redis-db` | 6379 | `redis:alpine` |

### Microservices

| Service | Container | Port | Image | Purpose |
|---------|-----------|------|-------|---------|
| Smart Contract Verifier | `smart-contract-verifier` | 8043 | `ghcr.io/blockscout/smart-contract-verifier:latest` | Verify Solidity/Vyper contracts |
| Visualizer | `visualizer` | 8044 (mainnet) / 8051 (testnet) | `ghcr.io/blockscout/visualizer:latest` | Sol2UML diagrams |
| Sig Provider | `sig-provider` | 8045 | `ghcr.io/blockscout/sig-provider:latest` | Method signatures |
| User Ops Indexer | `user-ops-indexer` | 8090 | `ghcr.io/blockscout/user-ops-indexer:latest` | ERC-4337 indexing (testnet only) |
| Stats | `stats` | 8052 | `ghcr.io/blockscout/stats:latest` | Blockchain statistics (mainnet + testnet) |

---

## Database Schema

### Main Database (PostgreSQL)

- **Host:** db container
- **Port:** 5432 (internal), 7432 (external)
- **Database:** `blockscout`
- **User:** `postgres`
- **Auth:** Trust (no password)

### Tables (Key)

- `blocks` - Block data
- `transactions` - Transaction data
- `addresses` - Address data
- `tokens` - Token contracts
- `user_operations` - ERC-4337 user ops (managed by user-ops-indexer)

---

## Features Enabled

### Frontend Features

| Feature | Env Variable | Status |
|---------|--------------|--------|
| User Operations (ERC-4337) | `NEXT_PUBLIC_HAS_USER_OPS=true` | Enabled |
| Gas Tracker | `NEXT_PUBLIC_GAS_TRACKER_ENABLED=true` | Enabled |
| Advanced Filter | `NEXT_PUBLIC_ADVANCED_FILTER_ENABLED=true` | Enabled |
| Marketplace | `NEXT_PUBLIC_MARKETPLACE_ENABLED=true` | Enabled |
| My Account | `NEXT_PUBLIC_IS_ACCOUNT_SUPPORTED=true` | Enabled |
| DEX Pools | `NEXT_PUBLIC_DEX_POOLS_ENABLED=true` | Enabled |
| Hot Contracts | `NEXT_PUBLIC_HOT_CONTRACTS_ENABLED=true` | Enabled |
| Stats API | `NEXT_PUBLIC_STATS_API_HOST` | Enabled |
| Visualizer | `NEXT_PUBLIC_VISUALIZE_API_HOST` | Enabled |
| Homepage Stats | `NEXT_PUBLIC_HOMEPAGE_STATS` | Enabled |
| Get Gas Button | `NEXT_PUBLIC_GAS_REFUEL_PROVIDER_CONFIG` | Enabled |

### Backend Features

| Feature | Env Variable | Status |
|---------|--------------|--------|
| Account Abstraction | `MICROSERVICE_ACCOUNT_ABSTRACTION_ENABLED=true` | Enabled |
| Smart Contract Verifier | `MICROSERVICE_SC_VERIFIER_ENABLED=true` | Enabled |
| Visualizer | `MICROSERVICE_VISUALIZE_SOL2UML_ENABLED=true` | Enabled |
| Sig Provider | `MICROSERVICE_SIG_PROVIDER_ENABLED=true` | Enabled |
| Admin Panel | `ADMIN_PANEL_ENABLED=true` | Enabled |
| GraphQL API | `API_GRAPHQL_ENABLED=true` | Enabled |
| Sourcify | `SOURCIFY_INTEGRATION_ENABLED=true` | Enabled |
| Internal Txs | `INDEXER_DISABLE_INTERNAL_TRANSACTIONS_FETCHER=false` | Enabled |
| Pending Txs | `INDEXER_DISABLE_PENDING_TRANSACTIONS_FETCHER=false` | Enabled |

---

## Nginx Configuration (Testnet)

### Route Mapping (test.doscan.io)

```nginx
# Frontend routes (proxy to :3000)
location ~ ^/(_next|node-api|apps|account|accounts|favicon|static|
              auth/profile|auth/unverified-email|txs|tx|blocks|block|
              login|address|stats|search-results|token|tokens|visualize|
              api-docs|csv-export|verified-contracts|graphiql|withdrawals|
              ops|assets|envs.js|sprite.svg|icons) {
    proxy_pass http://127.0.0.1:3000;
}

# API routes (proxy to :4000)
location / {
    proxy_pass http://127.0.0.1:4000;
}
```

### CORS Configuration

All API subdomains have CORS headers:
```nginx
add_header 'Access-Control-Allow-Origin' '*' always;
add_header 'Access-Control-Allow-Methods' 'PUT, GET, POST, OPTIONS, DELETE, PATCH' always;
add_header 'Access-Control-Allow-Headers' 'Accept,Authorization,Cache-Control,Content-Type,...' always;
```

---

## ERC-4337 (Account Abstraction) - Testnet

### EntryPoint Contract

- **Address:** `0x433709009B8330FDa32311DF1C2AFA402eD8D009`
- **Version:** v0.9 (compatible with v0.8 format)

### User Ops Indexer Config

```yaml
USER_OPS_INDEXER__INDEXER__ENTRYPOINTS__V08: "true"
USER_OPS_INDEXER__INDEXER__ENTRYPOINTS__V08_ENTRY_POINT: "0x433709009B8330FDa32311DF1C2AFA402eD8D009"
USER_OPS_INDEXER__INDEXER__ENTRYPOINTS__V06: "false"
USER_OPS_INDEXER__INDEXER__ENTRYPOINTS__V07: "false"
```

---

## Network Routing

### Mainnet (doscan.io)

```
User Browser
    │ HTTPS
    ▼
Cloudflare (CDN + DNS)
    │ Origin SSL
    ▼
archive VM (20.195.24.239)
    │
    ├── :443 → Caddy container → route by domain:
    │       ├── doscan.io     → frontend :3000 / backend :4000 / visualizer :8050
    │       ├── api.doscan.io → backend :4000
    │       ├── stats.doscan.io → stats :8050
    │       └── viz.doscan.io   → visualizer :8050
    │
    └── :9650 → AvalancheGo (native systemd, 127.0.0.1 only)
            └── Blockscout backend connects via host.docker.internal:9650
```

### Public RPC Routing (main.doschain.com / main2.doschain.com)

```
User / DApp
    │ HTTPS
    ▼
Cloudflare (DNS)
    │
    ├── main.doschain.com  → gw VM (20.6.91.153) nginx
    │       └── upstream: r0 (10.0.0.15:9650) + r1 (10.0.0.17:9650)
    │           └── proxy_pass → /ext/bc/22v7AG7h.../rpc
    │
    └── main2.doschain.com → gw VM (20.6.91.153) nginx
            └── upstream: archive (10.0.0.26:9650)
                └── proxy_pass → /ext/bc/22v7AG7h.../rpc
```

> **Note:** `main.doschain.com` and `main2.doschain.com` both route through the **gw** VM nginx.
> Users call `/` (root path) — nginx appends the full blockchain RPC path internally.

### ICM Relayer (archive VM)

```
archive VM
    └── Docker container `relayer` (avaplatform/icm-relayer:v1.7.5)
        ├── DOS Chain RPC: http://10.0.0.15:9650/ext/bc/22v7AG7h.../rpc (r0 internal)
        ├── C-Chain RPC:   http://10.0.0.15:9650/ext/bc/C/rpc (r0 internal)
        ├── P-Chain API:   http://10.0.0.15:9650 (r0 internal)
        └── Wallet: 0xEb9C076528BE1278C69C6b21E3cC0AB8f8809E2F
```

---

## Lessons Learned

### 2026-02-16: Doscan overloading RPC node

**Problem:** Doscan backend pointed to `main.doschain.com` (Cloudflare → gateway → r0).
~2M requests/day caused:
1. Cloudflare rate limiting
2. r0 overloaded with `eth_call` for historical states (missing trie nodes due to pruning)
3. r0 unable to sync new blocks → all transactions stuck

**Solution:** Moved doscan backend RPC to local archive avago node (`http://avago:9650/...`).
Backend and avago are in the same docker network, no external traffic needed.

---

## Related Documentation

- [Blockscout Docs](https://docs.blockscout.com/)
- [Frontend ENV Variables](https://docs.blockscout.com/setup/env-variables/frontend-common-envs)
- [Backend ENV Variables](https://docs.blockscout.com/setup/env-variables)
- [User Ops Indexer](https://github.com/blockscout/blockscout-rs/tree/main/user-ops-indexer)

# DOScan Architecture

## Overview

DOScan is the Blockscout-based explorer for DOS Chain. Mainnet, Testnet, and Beta run on Google Cloud Platform in project `dos--ai`.

**Last verified:** 2026-08-04

This document describes the current GCP runtime. Retired Azure and local WSL2 deployments are not part of the active architecture.

## Deployed Environments

| Environment | Public origin | Chain ID | GCP host | Zone | Deployment path |
|---|---|---:|---|---|---|
| Mainnet | `https://doscan.io` | 7979 | `doscan-mainnet` | `asia-southeast1-b` | `/opt/doscan-l1` |
| Testnet | `https://test.doscan.io` | 3939 | `dos-testnet-r0` | `asia-southeast1-a` | `/opt/doscan-testnet` |
| Beta | `https://beta.doscan.io` | 7979 | `doscan-mainnet` | `asia-southeast1-b` | `/opt/doscan-beta` |

Mainnet and Testnet are production environments. Beta is an isolated validation stack that indexes Mainnet through the local archive RPC on `doscan-mainnet`.

## Runtime Versions

| Component | Production version |
|---|---|
| Frontend | `metados/blockscout-frontend:2.10.0@sha256:4125d49b1658ba95b81075cabbc07120bebd90be95df49440aff5fa0e7e95eed` |
| Backend | `ghcr.io/dos/doscan:11.2.3.commit.86fd0dd5@sha256:423bab078a679d3290cc6e276774a8ed201686636933e0d066ce9859270f700d` |
| Interchain Indexer | `v1.6.0`, Mainnet only |

Commit `86fd0dd5` is a DOS custom patch for NFT video media records. It omits an original thumbnail when no original thumbnail exists.

## Request Topology

### Mainnet

```text
Browser or API client
        |
        v
Cloudflare DNS, CDN, and TLS proxy
        |
        v
Public edge Caddy on doscan-mainnet (:80/:443)
        |
        +-> doscan.io -----------> Mainnet origin Caddy
        |                              +-> Frontend :3000
        |                              +-> Backend :4000
        |                              +-> Stats :8050
        |                              +-> Visualizer :8050
        |                              +-> Interchain Indexer :8050
        |                              +-> external Metadata and Contract Info proxies
        |
        +-> api.doscan.io -------> Backend :4000
        +-> stats.doscan.io -----> Stats :8050
        +-> viz.doscan.io -------> Visualizer :8050
        +-> beta.doscan.io ------> Beta origin Caddy
```

The public edge stack is stored in `/opt/doscan`. Its `caddy` container joins the external Mainnet and Beta Docker networks and routes public traffic to the correct internal service.

### Testnet

```text
Browser or API client
        |
        v
Cloudflare Tunnel
        |
        v
Testnet origin Caddy on 127.0.0.1:13080
        +-> Frontend :3000
        +-> Backend :4000
        +-> Stats :8050
        +-> Visualizer :8050
        +-> external Metadata and Contract Info proxies
```

The Testnet VM runs separate Cloudflare tunnel containers for the explorer and DOS Testnet services. The DOScan Compose origin remains bound to loopback.

## Compose Service Layout

### Shared Mainnet and Testnet Services

| Service | Purpose | Data or dependency |
|---|---|---|
| `backend` | Combined Blockscout API and indexer | PostgreSQL, Redis, archive RPC |
| `frontend` | Blockscout Next.js UI | Backend and proxied microservices |
| `db` | Environment-local PostgreSQL | Persistent Compose volume |
| `redis-db` | Blockscout cache and queue state | Persistent Compose volume |
| `smart-contract-verifier` | Solidity and Vyper verification | Called by backend |
| `visualizer` | Sol2UML contract visualization | Called by backend and Caddy |
| `sig-provider` | Function and event signatures | Called by backend |
| `user-ops-indexer` | ERC-4337 operations | Environment-local Blockscout database |
| `stats` | Charts and aggregate statistics | Separate Stats database plus Blockscout database |
| `caddy` | Environment origin routing | Loopback-bound origin port |

Mainnet additionally runs `interchain-indexer`, which indexes DOS Chain and Avalanche C-Chain cross-chain messages into a separate database on the Mainnet PostgreSQL service.

### Beta Isolation

Beta has its own Compose project, Docker network, PostgreSQL volume, Redis volume, backend, frontend, and microservice containers. It shares only these host-level resources with Mainnet:

- The archive RPC exposed by the `avago` container on `doscan-mainnet`.
- Shared base environment files under `/opt/doscan/envs`.
- The public edge Caddy that routes `beta.doscan.io` to the Beta origin.

Beta does not share the Mainnet Blockscout database.

## Chain and RPC Connections

| Environment | Backend RPC | Blockchain ID | Fetcher constraints |
|---|---|---|---|
| Mainnet | `http://host.docker.internal:9650/ext/bc/2ewKoUrSjnviEgGmeTiELHBmNjxVTVczBPowST471rYUZvA9bk/rpc` | `2ewKoUrSjnviEgGmeTiELHBmNjxVTVczBPowST471rYUZvA9bk` | Pending and internal transaction fetchers enabled |
| Testnet | `http://10.148.0.7:9650/ext/bc/2EhCz8u48mSCUzxEEGsqY7d1PnqUKkc2B1zkTQaJxbT99wshkJ/rpc` | `2EhCz8u48mSCUzxEEGsqY7d1PnqUKkc2B1zkTQaJxbT99wshkJ` | Pending and internal transaction fetchers disabled because the RPC lacks `txpool_content` and debug tracing |
| Beta | Mainnet host archive RPC | Mainnet blockchain ID | Lower indexing concurrency than Mainnet |

The archive nodes run in Docker containers outside the DOScan Compose projects. The explorer must use the local archive RPC instead of sending indexing traffic through public Cloudflare endpoints.

Mainnet public RPC routing is handled by the edge Caddy:

- `main.doschain.com` routes to the ICM node.
- `main2.doschain.com` and `main3.doschain.com` route to the local Mainnet archive node.

Testnet Caddy exposes an internal loopback RPC origin on port 8545 for its Cloudflare tunnel.

## Backend Integrations

### Metadata Service

The backend enables Blockscout Metadata Service:

```env
MICROSERVICE_METADATA_URL=https://metadata.services.blockscout.com/
MICROSERVICE_METADATA_ENABLED=true
MICROSERVICE_METADATA_PROXY_REQUESTS_TIMEOUT=30s
```

Browsers do not call the external service directly. Each environment exposes a same-origin `/metadata-api` route through Caddy. Caddy strips the prefix and removes `Cookie` and `Authorization` before forwarding the request.

| Environment | Browser endpoint |
|---|---|
| Mainnet | `https://doscan.io/metadata-api` |
| Testnet | `https://test.doscan.io/metadata-api` |

BENS is not configured. There is no DOS or `.dos` BENS protocol for the deployed chain IDs, so name-service UI and backend integration remain disabled.

### NFT Media Handler

NFT Media Handler runs inside the custom backend on Mainnet and Testnet:

```env
NFT_MEDIA_HANDLER_ENABLED=true
NFT_MEDIA_HANDLER_REMOTE_DISPATCHER_NODE_MODE_ENABLED=false
NFT_MEDIA_HANDLER_AWS_BUCKET_HOST=storage.googleapis.com
NFT_MEDIA_HANDLER_AWS_BUCKET_NAME=doscan
NFT_MEDIA_HANDLER_AWS_PUBLIC_BUCKET_URL=https://storage.googleapis.com/doscan
NFT_MEDIA_HANDLER_BACKFILL_ENABLED=true
```

Mainnet writes to `mainnet/nft-media`; Testnet writes to `testnet/nft-media`. HMAC credentials come from GCP Secret Manager during deployment and are not stored in the repository.

See [NFT Media Handler](NFT-MEDIA-HANDLER.md) for the processing model and validation procedures.

### Other Services

- Smart Contract Verifier, Visualizer, Signature Provider, Account Abstraction, and Stats run locally in each production Compose project.
- Sourcify is enabled as an external verification source.
- Contract Info is proxied through the explorer origin for browser compatibility.
- Interchain Indexer is deployed only on Mainnet.
- Multichain Search, transaction interpretation providers, and BENS are not deployed.

## Routing Rules

The environment origin Caddy uses ordered path routing:

| Path | Destination |
|---|---|
| `/api/v1/counters`, `/api/v1/lines`, `/api/v1/pages/main` | Stats |
| Mainnet `/api/v1/interchain/*` and interchain status/stat paths | Interchain Indexer |
| `/api/v1/chains/*` | Contract Info proxy |
| Metadata API paths and `/metadata-api/*` | Metadata Service proxy |
| `/api/*`, `/socket/*`, `/auth/*`, `/metrics`, `/public-metrics` | Backend |
| `/stats-api/*` | Stats |
| `/visualize/*` | Visualizer |
| All other paths | Frontend |

## Configuration Model

Backend and frontend configuration use a base plus environment override pattern:

```text
docker-compose/envs/
  common-blockscout.env
  common-blockscout-mainnet.env
  common-blockscout-testnet.env
  common-blockscout-beta.env
  common-frontend.env
  common-frontend-scan.env
  common-frontend-testnet.env
  common-frontend-beta.env
```

Compose loads the shared base first and the environment override last. Empty values are real overrides, not equivalent to an unset variable. The deployment workflow runs `scripts/validate-blockscout-env-parity.py` before applying Mainnet or Testnet configuration.

Production secrets are stored on the VM or read from GCP Secret Manager. Repository environment files must contain only non-secret configuration or explicit placeholders.

## Deployment Flow

`.github/workflows/deploy-config.yml` is the deployment source of truth.

```text
Push to main or manual dispatch
        |
        v
Validate env parity and Caddy configuration
        |
        v
Authenticate to GCP with Workload Identity Federation
        |
        v
Read NFT media HMAC credentials from Secret Manager
        |
        v
Upload a configuration archive through IAP
        |
        v
Back up current runtime configuration
        |
        v
Apply Compose and Caddy changes
        |
        v
Run container, API, metadata, RPC, and public health checks
        |
        +-> success: retain new configuration
        +-> failure: restore the backed-up configuration and verify rollback health
```

Mainnet changes also manage the public edge Caddy. Testnet deployment is independent and targets `dos-testnet-r0`. Beta is deployed manually to the isolated stack on `doscan-mainnet`.

External failures such as Metadata Service, GCS, Cloudflare, or public RPC outages must not trigger a destructive database restore. Deployment gates distinguish local stack health from external dependency health.

## Production Verification

The following checks passed on 2026-08-04:

| Check | Mainnet | Testnet |
|---|---|---|
| GCP VM state | `RUNNING` | `RUNNING` |
| Backend container | `running`, `healthy` | `running`, `healthy` |
| Frontend container | `running`, `healthy` | `running`, `healthy` |
| Backend version endpoint | `v11.2.3.+commit.86fd0dd5` | `v11.2.3.+commit.86fd0dd5` |
| Stats API | HTTP 200 | HTTP 200 |
| Frontend runtime config | HTTP 200 | HTTP 200 |
| Metadata same-origin proxy | HTTP 200 with `addresses` | HTTP 200 with `addresses` |

The current production head also passed [Deploy Config run 30878181874](https://github.com/DOS/DOScan/actions/runs/30878181874) for both environments.

Runtime verification must check both the configured image reference and the live container. A healthy container alone does not prove that the expected custom build is running.

## Sources of Truth

Use these files for the current deployment:

- `docker-compose/docker-compose-mainnet.yml`
- `docker-compose/docker-compose-testnet.yml`
- `docker-compose/docker-compose-beta.yml`
- `docker-compose/docker-compose-gcp-edge.yml`
- `docker-compose/Caddyfile-gcp-mainnet`
- `docker-compose/Caddyfile-gcp-testnet`
- `docker-compose/Caddyfile-gcp-edge`
- `docker-compose/envs/common-blockscout*.env`
- `.github/workflows/deploy-config.yml`
- `scripts/apply-beta-on-mainnet-vm.sh`

For status reporting, combine checked-in configuration, workflow results, GCP inventory, live container inspection, and public endpoint probes.

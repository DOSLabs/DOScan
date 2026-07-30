# DOScan Beta on the Mainnet GCP VM

`beta.doscan.io` runs on the `doscan-mainnet` VM in `asia-southeast1-b`.

## Isolation boundary

- Beta shares the host AvalancheGo archive RPC for chain ID 7979.
- Beta runs as the dedicated `doscan-beta` Docker Compose project.
- PostgreSQL, Redis, Caddy data, and Caddy config use beta-owned volumes.
- The production Blockscout database and beta Blockscout database are separate.
- Beta Caddy binds only to `127.0.0.1:14080`.
- The VM edge Caddy terminates TLS and proxies `beta.doscan.io` to that loopback port.
- NFT media processing is disabled in beta to avoid duplicate production bucket work.

## Deployment

The `deploy-beta` job in `.github/workflows/deploy-config.yml` runs on a GitHub-hosted runner. It authenticates with GCP Workload Identity Federation, uploads the checked-in configuration through IAP, and applies it under `/opt/doscan-beta`.

The deployment verifies:

- Docker Compose configuration
- Beta Caddy configuration
- Local explorer statistics and public metrics endpoints
- Shared AvalancheGo RPC chain ID
- Runtime frontend host and API configuration
- Public `https://beta.doscan.io/api/v2/stats`

Secrets are not stored in the beta compose file. The deployment reads the VM-managed Blockscout secret env file under `/opt/doscan/envs`.

The deployment stops only confirmed orphan containers from the retired `/opt/doscan` explorer stack. It does not stop the edge Caddy container and does not delete legacy volumes.

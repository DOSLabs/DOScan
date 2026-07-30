#!/usr/bin/env bash
set -euo pipefail

src="${1:?source directory is required}"
deploy_id="${2:?deployment id is required}"
beta_path="/opt/doscan-beta"
shared_env_path="/opt/doscan/envs"
blockscout_secrets="${shared_env_path}/common-blockscout-secrets.env"
backup="${beta_path}/backups/github-${deploy_id}"

test -s "${blockscout_secrets}"
test -s "${shared_env_path}/common-frontend.env"
test -s "${shared_env_path}/common-smart-contract-verifier.env"
test -s "${shared_env_path}/common-visualizer.env"

mkdir -p "${backup}" "${beta_path}/envs"
cp -a "${beta_path}/compose.yml" "${backup}/compose.yml" 2>/dev/null || true
cp -a "${beta_path}/Caddyfile-beta" "${backup}/Caddyfile-beta" 2>/dev/null || true
cp -a "${beta_path}/envs" "${backup}/envs" 2>/dev/null || true

install -m 0644 "${src}/docker-compose/docker-compose-beta.yml" "${beta_path}/compose.yml"
install -m 0644 "${src}/docker-compose/Caddyfile-beta" "${beta_path}/Caddyfile-beta"
install -m 0644 "${src}/docker-compose/envs/common-blockscout.env" "${beta_path}/envs/common-blockscout.env"
install -m 0644 "${src}/docker-compose/envs/common-blockscout-beta.env" "${beta_path}/envs/common-blockscout-beta.env"
install -m 0644 "${src}/docker-compose/envs/common-frontend-beta.env" "${beta_path}/envs/common-frontend-beta.env"

cd "${beta_path}"
export DOSCAN_BLOCKSCOUT_SECRETS_ENV="${blockscout_secrets}"
export DOSCAN_BASE_ENV_DIR="${shared_env_path}"

docker network inspect doscan-beta >/dev/null 2>&1 || docker network create doscan-beta >/dev/null
docker compose config -q
docker compose pull

# These containers are confirmed orphans from the retired /opt/doscan explorer stack.
# Keep the edge Caddy container running and preserve all legacy volumes.
for legacy_container in \
  frontend backend redis-db db user-ops-indexer stats \
  smart-contract-verifier visualizer sig-provider; do
  if [ "$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "${legacy_container}" 2>/dev/null || true)" = "doscan" ]; then
    docker stop "${legacy_container}" >/dev/null
  fi
done

docker compose up -d --remove-orphans

for attempt in $(seq 1 72); do
  if curl -fsS http://127.0.0.1:14080/api/v2/stats >/dev/null &&
     curl -fsS http://127.0.0.1:14080/public-metrics >/dev/null &&
     curl -fsS http://127.0.0.1:14080/api/v1/lines >/dev/null &&
     curl -fsS http://127.0.0.1:14080/api/v2/proxy/account-abstraction/status >/dev/null; then
    break
  fi
  if [ "${attempt}" -eq 72 ]; then
    echo "DOScan beta did not become healthy in time" >&2
    docker compose ps
    exit 1
  fi
  sleep 5
done

for service_url in \
  http://smart-contract-verifier:8050/health \
  http://visualizer:8050/health \
  http://sig-provider:8050/health; do
  docker compose exec -T backend curl -fsS "${service_url}" >/dev/null
done

running_services="$(docker compose ps --status running --services)"
for required_service in \
  redis-db db backend frontend smart-contract-verifier visualizer \
  sig-provider user-ops-indexer stats caddy; do
  if ! grep -qx "${required_service}" <<<"${running_services}"; then
    echo "Required beta service is not running: ${required_service}" >&2
    docker compose ps
    exit 1
  fi
done

rpc_body='{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
rpc_response="$(curl -fsS -H 'Content-Type: application/json' --data "${rpc_body}" \
  http://127.0.0.1:9650/ext/bc/2ewKoUrSjnviEgGmeTiELHBmNjxVTVczBPowST471rYUZvA9bk/rpc)"
grep -q '"result":"0x1f2b"' <<<"${rpc_response}"

frontend_env="$(docker compose exec -T frontend curl -fsS http://localhost:3000/assets/envs.js)"
grep -Fq 'NEXT_PUBLIC_APP_HOST: "beta.doscan.io"' <<<"${frontend_env}"
grep -Fq 'NEXT_PUBLIC_API_HOST: "beta.doscan.io"' <<<"${frontend_env}"
grep -Fq 'NEXT_PUBLIC_STATS_API_BASE_PATH: "/stats-api"' <<<"${frontend_env}"

docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile
docker compose ps
echo "GCP beta deployment completed"

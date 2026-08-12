#!/usr/bin/env bash

# Source this file from the Mainnet deployment shell after setting SRC, BACKUP,
# L1_PATH, SHARED_ENV_PATH, BLOCKSCOUT_SECRETS, and DEPLOY_ID.

BENS_SECRETS_ENV="${L1_PATH}/envs/bens-secrets.env"
BENS_DB_VOLUME="doscan-l1_bens_postgres_data"
BENS_IPFS_VOLUME="doscan-l1_bens_ipfs_data"
BENS_STATE_EXISTED=0
BENS_PREPARED=0
BENS_BACKUP_COMPLETE=0
BENS_KUBO_IMAGE="ipfs/kubo:v0.43.0@sha256:63f5502f7a01b82a675e45bae81b2f5dfa90248ec4a86cd0a58c218347e1f2d2"

bens_compose() {
  sudo env \
    DOSCAN_BLOCKSCOUT_SECRETS_ENV="${BLOCKSCOUT_SECRETS}" \
    DOSCAN_BENS_SECRETS_ENV="${BENS_SECRETS_ENV}" \
    DOSCAN_BASE_ENV_DIR="${SHARED_ENV_PATH}" \
    BENS_SUBGRAPH_VERSION="${BENS_SUBGRAPH_VERSION:-mainnet}" \
    docker compose "$@"
}

bens_rpc_request() {
  local method="$1"
  local params="$2"
  curl --fail --silent --show-error --max-time 30 \
    -H "Content-Type: application/json" \
    --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"${method}\",\"params\":${params}}" \
    "http://127.0.0.1:9650/ext/bc/2ewKoUrSjnviEgGmeTiELHBmNjxVTVczBPowST471rYUZvA9bk/rpc"
}

bens_prepare_secret() {
  local key_count password_count password secrets_tmp canonical_tmp
  key_count="$(sudo grep -Ec '^DOSCAN_BENS_DB_PASSWORD=' "${BLOCKSCOUT_SECRETS}" || true)"
  password_count="$(sudo grep -Ec '^DOSCAN_BENS_DB_PASSWORD=[0-9a-f]{64}$' "${BLOCKSCOUT_SECRETS}" || true)"
  if [ "${key_count}" -eq 0 ]; then
    password="$(openssl rand -hex 32)"
    canonical_tmp="$(mktemp /tmp/doscan-mainnet-secrets.XXXXXX)"
    sudo cat "${BLOCKSCOUT_SECRETS}" > "${canonical_tmp}"
    printf 'DOSCAN_BENS_DB_PASSWORD=%s\n' "${password}" >> "${canonical_tmp}"
    sudo install -m 0600 "${canonical_tmp}" "${BLOCKSCOUT_SECRETS}"
    rm -f "${canonical_tmp}"
  elif [ "${key_count}" -ne 1 ] || [ "${password_count}" -ne 1 ]; then
    echo "Mainnet canonical BENS database password is missing, duplicated, or invalid" >&2
    return 1
  fi

  password="$(sudo awk -F= '$1 == "DOSCAN_BENS_DB_PASSWORD" { print $2 }' "${BLOCKSCOUT_SECRETS}")"
  [[ "${password}" =~ ^[0-9a-f]{64}$ ]]
  secrets_tmp="$(mktemp /tmp/doscan-mainnet-bens-secrets.XXXXXX)"
  printf \
    'POSTGRES_PASSWORD=%s\npostgres_pass=%s\nBENS__DATABASE__CONNECT__URL=postgresql://graph-node:%s@bens-db:5432/graph-node\n' \
    "${password}" "${password}" "${password}" > "${secrets_tmp}"
  sudo install -m 0600 "${secrets_tmp}" "${BENS_SECRETS_ENV}"
  rm -f "${secrets_tmp}"
  unset password
}

bens_validate_manifest_and_chain() {
  local deployment chain_id genesis_hash address code
  deployment="${SRC}/docker-compose/bens/deployment.json"
  jq -e \
    '.environment == "dos-mainnet" and .chainId == 7979 and
     .deploymentBlock == 117 and .finalDeploymentBlock == 162 and
     .smokeName == "bens-smoke.dos" and
     .smokeResolvedAddress == "0x99999e454138f6be73E2bE82c890bc5765749999" and
     .contracts.wrappedDOS == "0x1111111111111111111111111111111111111111"' \
    "${deployment}" >/dev/null

  chain_id="$(bens_rpc_request eth_chainId '[]' | jq -er .result)"
  [ "${chain_id}" = "0x1f2b" ]
  genesis_hash="$(bens_rpc_request eth_getBlockByNumber '["0x0",false]' | jq -er '.result.hash | ascii_downcase')"
  [ "${genesis_hash}" = "0x3b5fbd6089c79e21843f16384316ad75de4951f8bb2d0f26e3ce12e984e2e82b" ]

  while read -r address; do
    code="$(bens_rpc_request eth_getCode "[\"${address}\",\"latest\"]" | jq -er .result)"
    if [ "${code}" = "0x" ] || [ "${code}" = "0x0" ]; then
      echo "Mainnet ENSv2 contract has no bytecode: ${address}" >&2
      return 1
    fi
  done < <(jq -r '.contracts | to_entries[] | select(.key != "wrappedDOS") | .value' "${deployment}")
}

bens_require_current_services() {
  local service services
  services="$(bens_compose config --services)"
  for service in bens-db bens-ipfs bens-graph-node bens; do
    if ! grep -Fx "${service}" <<<"${services}" >/dev/null; then
      echo "Mainnet BENS volume exists but current Compose lacks ${service}" >&2
      return 1
    fi
  done
}

bens_prepare() {
  local db_exists ipfs_exists
  bens_validate_manifest_and_chain
  bens_prepare_secret

  db_exists="$(sudo docker volume inspect "${BENS_DB_VOLUME}" >/dev/null 2>&1 && echo 1 || echo 0)"
  ipfs_exists="$(sudo docker volume inspect "${BENS_IPFS_VOLUME}" >/dev/null 2>&1 && echo 1 || echo 0)"
  if [ "${db_exists}" != "${ipfs_exists}" ]; then
    echo "Mainnet BENS volumes are incomplete; refusing deployment" >&2
    return 1
  fi

  if sudo test -d "${L1_PATH}/bens"; then
    sudo cp -a "${L1_PATH}/bens" "${BACKUP}/bens"
    sudo touch "${BACKUP}/bens-existed"
  fi

  if [ "${db_exists}" -eq 1 ]; then
    bens_require_current_services
    BENS_STATE_EXISTED=1
    BENS_PREPARED=1
    bens_capture_prior_state
    bens_compose stop bens bens-graph-node
    bens_compose exec -T bens-db pg_dump -U graph-node -Fc graph-node |
      sudo tee "${BACKUP}/bens-graph-node.dump" >/dev/null
    bens_compose stop bens-db bens-ipfs
    sudo docker run --rm \
      -v "${BENS_IPFS_VOLUME}:/data/ipfs:ro" \
      -v "${BACKUP}:/backup" \
      --entrypoint /bin/sh \
      "${BENS_KUBO_IMAGE}" \
      -ec "tar -C /data/ipfs -czf /backup/bens-ipfs.tgz ."
    sudo test -s "${BACKUP}/bens-graph-node.dump"
    sudo test -s "${BACKUP}/bens-ipfs.tgz"
    sudo docker run --rm \
      -v "${BACKUP}:/backup:ro" \
      --entrypoint /bin/sh \
      "postgres:16.10@sha256:21f6013073bc6b92830a2129570e2f5ec42a6c734b5a985a41e83aa58f54c3c1" \
      -ec 'pg_restore --list /backup/bens-graph-node.dump >/dev/null'
    sudo docker run --rm \
      -v "${BACKUP}:/backup:ro" \
      --entrypoint /bin/sh \
      "${BENS_KUBO_IMAGE}" \
      -ec 'tar -tzf /backup/bens-ipfs.tgz >/dev/null'
    BENS_BACKUP_COMPLETE=1
    sudo touch "${BACKUP}/bens-state-existed"
  else
    BENS_PREPARED=1
  fi
}

bens_query_meta() {
  bens_compose exec -T backend curl -fsS \
    -H 'Content-Type: application/json' \
    --data '{"query":"{ _meta { deployment block { number } hasIndexingErrors } }"}' \
    http://bens-graph-node:8000/subgraphs/name/dos-names
}

bens_capture_prior_state() {
  local deployment meta smoke_name smoke_address domain reverse search state_tmp
  deployment="${L1_PATH}/bens/deployment.json"
  sudo jq -e \
    '.chainId == 7979 and (.finalDeploymentBlock | type == "number") and
     (.smokeName | type == "string") and (.smokeResolvedAddress | type == "string")' \
    "${deployment}" >/dev/null
  smoke_name="$(sudo jq -er .smokeName "${deployment}")"
  smoke_address="$(sudo jq -er .smokeResolvedAddress "${deployment}")"
  meta="$(bens_query_meta)"
  jq -e \
    '.errors == null and (.data._meta.deployment | type == "string") and
     .data._meta.hasIndexingErrors == false and
     (.data._meta.block.number | tonumber) >= 0' <<<"${meta}" >/dev/null
  domain="$(bens_compose exec -T backend curl -fsS "http://bens:8050/api/v1/7979/domains/${smoke_name}")"
  reverse="$(bens_compose exec -T backend curl -fsS "http://bens:8050/api/v1/7979/addresses/${smoke_address}?protocol_id=dos-names")"
  search="$(bens_compose exec -T backend curl -fsS "http://backend:4000/api/v2/search?q=${smoke_name}")"
  jq -e --arg name "${smoke_name}" --arg address "${smoke_address}" \
    '.name == $name and (.resolved_address.hash | ascii_downcase) == ($address | ascii_downcase)' \
    <<<"${domain}" >/dev/null
  jq -e --arg name "${smoke_name}" '.domain.name == $name' <<<"${reverse}" >/dev/null
  jq -e --arg name "${smoke_name}" --arg address "${smoke_address}" \
    'any(.items[]?; .type == "ens_domain" and (.name // .ens_info.name) == $name and
     (.address_hash | ascii_downcase) == ($address | ascii_downcase))' <<<"${search}" >/dev/null
  state_tmp="$(mktemp /tmp/doscan-mainnet-bens-state.XXXXXX)"
  jq -n \
    --arg deployment "$(jq -er .data._meta.deployment <<<"${meta}")" \
    --argjson block "$(jq -er '.data._meta.block.number | tonumber' <<<"${meta}")" \
    --arg smokeName "${smoke_name}" --arg smokeAddress "${smoke_address}" \
    '{deployment: $deployment, block: $block, smokeName: $smokeName, smokeAddress: $smokeAddress}' \
    > "${state_tmp}"
  sudo install -m 0600 "${state_tmp}" "${BACKUP}/bens-prior-state.json"
  rm -f "${state_tmp}"
}

bens_verify_restored_state() {
  local prior expected_cid expected_block smoke_name smoke_address meta domain reverse search
  prior="${BACKUP}/bens-prior-state.json"
  sudo jq -e \
    '(.deployment | type == "string") and (.block | type == "number") and
     (.smokeName | type == "string") and (.smokeAddress | type == "string")' \
    "${prior}" >/dev/null
  expected_cid="$(sudo jq -er .deployment "${prior}")"
  expected_block="$(sudo jq -er .block "${prior}")"
  smoke_name="$(sudo jq -er .smokeName "${prior}")"
  smoke_address="$(sudo jq -er .smokeAddress "${prior}")"
  for attempt in $(seq 1 60); do
    meta="$(bens_query_meta 2>/dev/null || true)"
    domain="$(bens_compose exec -T backend curl -fsS "http://bens:8050/api/v1/7979/domains/${smoke_name}" 2>/dev/null || true)"
    reverse="$(bens_compose exec -T backend curl -fsS "http://bens:8050/api/v1/7979/addresses/${smoke_address}?protocol_id=dos-names" 2>/dev/null || true)"
    search="$(bens_compose exec -T backend curl -fsS "http://backend:4000/api/v2/search?q=${smoke_name}" 2>/dev/null || true)"
    if jq -e --arg cid "${expected_cid}" --argjson block "${expected_block}" \
         '.errors == null and .data._meta.deployment == $cid and
          .data._meta.hasIndexingErrors == false and
          (.data._meta.block.number | tonumber) >= $block' <<<"${meta}" >/dev/null 2>&1 &&
       jq -e --arg name "${smoke_name}" --arg address "${smoke_address}" \
         '.name == $name and (.resolved_address.hash | ascii_downcase) == ($address | ascii_downcase)' \
         <<<"${domain}" >/dev/null 2>&1 &&
       jq -e --arg name "${smoke_name}" '.domain.name == $name' <<<"${reverse}" >/dev/null 2>&1 &&
       jq -e --arg name "${smoke_name}" --arg address "${smoke_address}" \
         'any(.items[]?; .type == "ens_domain" and (.name // .ens_info.name) == $name and
          (.address_hash | ascii_downcase) == ($address | ascii_downcase))' \
         <<<"${search}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  echo "Mainnet restored BENS state failed exact deployment and lookup checks" >&2
  return 1
}

bens_wait_healthy() {
  for attempt in $(seq 1 60); do
    if bens_compose exec -T backend curl -fsS http://bens:8050/health | grep -q '"SERVING"'; then
      return 0
    fi
    if [ "${attempt}" -eq 60 ]; then
      echo "Mainnet BENS did not become healthy" >&2
      return 1
    fi
    sleep 5
  done
}

bens_wait_graph_admin() {
  for attempt in $(seq 1 60); do
    if bens_compose exec -T backend curl --silent --show-error \
      --connect-timeout 10 --max-time 20 --output /dev/null \
      http://bens-graph-node:8020/; then
      return 0
    fi
    if [ "${attempt}" -eq 60 ]; then
      echo "Mainnet BENS Graph Node did not become ready" >&2
      return 1
    fi
    sleep 5
  done
}

bens_wait_restored_core_http() {
  for attempt in $(seq 1 24); do
    if curl --fail --silent --show-error --connect-timeout 10 --max-time 20 \
         http://127.0.0.1:13080/api/v2/stats >/dev/null &&
       curl --fail --silent --show-error --connect-timeout 10 --max-time 20 \
         http://127.0.0.1:13080/public-metrics >/dev/null; then
      return 0
    fi
    sleep 5
  done
  echo "Mainnet restored core HTTP endpoints did not become ready" >&2
  return 1
}

bens_deploy() {
  local deploy_output subgraph_ipfs_hash meta domain reverse
  cd "${L1_PATH}"
  bens_compose pull bens-db bens-ipfs bens-graph-node bens bens-deployer
  bens_compose up -d bens-db bens-ipfs bens-graph-node
  bens_wait_graph_admin

  deploy_output="$(BENS_SUBGRAPH_VERSION="github-${DEPLOY_ID}" bens_compose --profile bens-deploy run --rm bens-deployer 2>&1)"
  printf '%s\n' "${deploy_output}"
  subgraph_ipfs_hash="$(grep -Eo '(Build completed|Subgraph IPFS hash): Qm[1-9A-HJ-NP-Za-km-z]{44}' <<<"${deploy_output}" | grep -Eo 'Qm[1-9A-HJ-NP-Za-km-z]{44}' | tail -n 1)"
  [ -n "${subgraph_ipfs_hash}" ]

  FINAL_DEPLOYMENT_BLOCK="$(jq -er .finalDeploymentBlock "${L1_PATH}/bens/deployment.json")"
  SMOKE_NAME="$(jq -er .smokeName "${L1_PATH}/bens/deployment.json")"
  SMOKE_RESOLVED_ADDRESS="$(jq -er .smokeResolvedAddress "${L1_PATH}/bens/deployment.json")"
  for attempt in $(seq 1 60); do
    meta="$(bens_query_meta 2>/dev/null || true)"
    if jq -e --arg cid "${subgraph_ipfs_hash}" --argjson final "${FINAL_DEPLOYMENT_BLOCK}" \
      '.errors == null and .data._meta.deployment == $cid and
       .data._meta.hasIndexingErrors == false and
       (.data._meta.block.number | tonumber) >= $final' <<<"${meta}" >/dev/null 2>&1; then
      break
    fi
    if [ "${attempt}" -eq 60 ]; then
      echo "Mainnet DOS Names subgraph did not reach the exact deployment and final block" >&2
      return 1
    fi
    sleep 5
  done

  bens_compose up -d bens
  bens_wait_healthy

  domain="$(bens_compose exec -T backend curl -fsS "http://bens:8050/api/v1/7979/domains/${SMOKE_NAME}")"
  jq -e --arg name "${SMOKE_NAME}" --arg address "${SMOKE_RESOLVED_ADDRESS}" \
    '.name == $name and (.resolved_address.hash | ascii_downcase) == ($address | ascii_downcase)' \
    <<<"${domain}" >/dev/null
  reverse="$(bens_compose exec -T backend curl -fsS "http://bens:8050/api/v1/7979/addresses/${SMOKE_RESOLVED_ADDRESS}?protocol_id=dos-names")"
  jq -e --arg name "${SMOKE_NAME}" '.domain.name == $name' <<<"${reverse}" >/dev/null
}

bens_rollback() {
  local restore_rc=0 service
  if [ "${BENS_PREPARED}" -ne 1 ]; then
    return 0
  fi
  set +e
  cd "${L1_PATH}"
  for service in bens bens-graph-node bens-ipfs bens-db; do
    bens_compose rm -sf "${service}" >/dev/null 2>&1 || restore_rc=1
    if [ -n "$(bens_compose ps -aq "${service}" 2>/dev/null)" ]; then
      restore_rc=1
    fi
  done
  if [ "${restore_rc}" -ne 0 ]; then
    echo "Mainnet BENS rollback could not remove the new runtime containers" >&2
    return 1
  fi

  if sudo test -f "${BACKUP}/bens-existed"; then
    sudo rm -rf "${L1_PATH}/bens" || restore_rc=1
    sudo cp -a "${BACKUP}/bens" "${L1_PATH}/bens" || restore_rc=1
  else
    sudo rm -rf "${L1_PATH}/bens" || restore_rc=1
  fi

  sudo cp -a "${BACKUP}/compose.yml" "${L1_PATH}/compose.yml" || restore_rc=1
  if [ "${BENS_STATE_EXISTED}" -eq 1 ]; then
    if [ "${BENS_BACKUP_COMPLETE}" -ne 1 ]; then
      bens_compose up -d bens-db bens-ipfs bens-graph-node bens || restore_rc=1
      bens_wait_healthy || restore_rc=1
      bens_verify_restored_state || restore_rc=1
      return "${restore_rc}"
    fi
    if ! sudo test -s "${BACKUP}/bens-graph-node.dump" ||
       ! sudo test -s "${BACKUP}/bens-ipfs.tgz"; then
      echo "Mainnet BENS backup is incomplete; refusing destructive restore" >&2
      return 1
    fi
    bens_compose up -d bens-db || restore_rc=1
    for attempt in $(seq 1 30); do
      if bens_compose exec -T bens-db pg_isready -U graph-node -d graph-node; then
        break
      fi
      [ "${attempt}" -eq 30 ] && restore_rc=1
      sleep 2
    done
    bens_compose exec -T bens-db dropdb --force -U graph-node graph-node || restore_rc=1
    bens_compose exec -T bens-db createdb -U graph-node graph-node || restore_rc=1
    sudo cat "${BACKUP}/bens-graph-node.dump" |
      bens_compose exec -T bens-db pg_restore -U graph-node -d graph-node --clean --if-exists || restore_rc=1
    bens_compose stop bens-db || restore_rc=1
    sudo docker run --rm \
      -v "${BENS_IPFS_VOLUME}:/data/ipfs" \
      -v "${BACKUP}:/backup:ro" \
      --entrypoint /bin/sh \
      "${BENS_KUBO_IMAGE}" \
      -ec 'find /data/ipfs -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; tar -C /data/ipfs -xzf /backup/bens-ipfs.tgz' || restore_rc=1
    bens_compose up -d bens-db bens-ipfs bens-graph-node bens || restore_rc=1
    bens_wait_healthy || restore_rc=1
    bens_verify_restored_state || restore_rc=1
  else
    for volume in "${BENS_DB_VOLUME}" "${BENS_IPFS_VOLUME}"; do
      if sudo docker volume inspect "${volume}" >/dev/null 2>&1; then
        sudo docker volume rm "${volume}" >/dev/null || restore_rc=1
      fi
      if sudo docker volume inspect "${volume}" >/dev/null 2>&1; then
        restore_rc=1
      fi
    done
    sudo rm -f "${BENS_SECRETS_ENV}" || restore_rc=1
  fi
  return "${restore_rc}"
}

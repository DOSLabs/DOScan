#!/bin/sh

set -eu

GRAPH_ADMIN_URL="${DOSCAN_GRAPH_ADMIN_URL:-http://bens-graph-node:8020}"
GRAPH_QUERY_URL="${DOSCAN_GRAPH_QUERY_URL:-http://bens-graph-node:8000/subgraphs/name/dos-names}"
GRAPH_IPFS_URL="${DOSCAN_GRAPH_IPFS_URL:-http://bens-ipfs:5001}"
READINESS_ATTEMPTS="${DOSCAN_SUBGRAPH_READINESS_ATTEMPTS:-6}"
RETRY_DELAY_SECONDS="${DOSCAN_SUBGRAPH_RETRY_DELAY_SECONDS:-5}"
SOURCE_DIR="${DOSCAN_SUBGRAPH_SOURCE_DIR:-/source}"
WORK_DIR="${DOSCAN_SUBGRAPH_WORK_DIR:-/work}"
deploy_log="${DOSCAN_SUBGRAPH_DEPLOY_LOG:-/tmp/dos-names-deploy.log}"

run_graph_cli() {
  if [ -n "${DOSCAN_GRAPH_CLI_RUNNER:-}" ]; then
    "${DOSCAN_GRAPH_CLI_RUNNER}" "$@"
  else
    node node_modules/@graphprotocol/graph-cli/bin/run "$@"
  fi
}

run_npm() {
  if [ -n "${DOSCAN_NPM_RUNNER:-}" ]; then
    "${DOSCAN_NPM_RUNNER}" "$@"
  else
    npm "$@"
  fi
}

subgraph_ready() {
  node -e 'const expectedDeployment = process.argv[1]; const queryUrl = process.argv[2]; fetch(queryUrl, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({query: "{ _meta { deployment hasIndexingErrors } }"})}).then(async (response) => { const body = await response.json(); if (!response.ok || body.errors || !body.data || !body.data._meta || body.data._meta.deployment !== expectedDeployment || body.data._meta.hasIndexingErrors !== false) process.exit(1); }).catch(() => process.exit(1));' \
    "${subgraph_ipfs_hash}" "${GRAPH_QUERY_URL}"
}

wait_for_subgraph() {
  readiness_attempt=1
  while [ "${readiness_attempt}" -le "${READINESS_ATTEMPTS}" ]; do
    if subgraph_ready; then
      return 0
    fi
    sleep "${RETRY_DELAY_SECONDS}"
    readiness_attempt=$((readiness_attempt + 1))
  done
  return 1
}

mkdir -p "${WORK_DIR}"
cp -a "${SOURCE_DIR}/." "${WORK_DIR}/"
cd "${WORK_DIR}"
run_npm ci
run_graph_cli codegen --output-dir src/types/
run_graph_cli build
run_graph_cli create dos-names --node "${GRAPH_ADMIN_URL}" || true

set +e
run_graph_cli deploy dos-names \
  --ipfs "${GRAPH_IPFS_URL}" \
  --node "${GRAPH_ADMIN_URL}" \
  --version-label "${BENS_SUBGRAPH_VERSION:-testnet}" \
  >"${deploy_log}" 2>&1
deploy_rc="${?}"
set -e
cat "${deploy_log}"

subgraph_ipfs_hash="$(grep -Eo '(Build completed|Subgraph IPFS hash): Qm[1-9A-HJ-NP-Za-km-z]{44}' "${deploy_log}" | grep -Eo 'Qm[1-9A-HJ-NP-Za-km-z]{44}' | tail -n 1)"
if [ -z "${subgraph_ipfs_hash}" ]; then
  echo "Graph CLI did not report the uploaded subgraph IPFS hash" >&2
  exit 1
fi

subgraph_deployed=0
if wait_for_subgraph; then
  subgraph_deployed=1
else
  echo "Initial Graph deploy exited ${deploy_rc} without an active subgraph; retrying the uploaded IPFS hash" >&2
  for deploy_attempt in 2 3; do
    set +e
    run_graph_cli deploy dos-names \
      --ipfs "${GRAPH_IPFS_URL}" \
      --ipfs-hash "${subgraph_ipfs_hash}" \
      --node "${GRAPH_ADMIN_URL}" \
      --version-label "${BENS_SUBGRAPH_VERSION:-testnet}" \
      >"${deploy_log}" 2>&1
    deploy_rc="${?}"
    set -e
    cat "${deploy_log}"
    if wait_for_subgraph; then
      subgraph_deployed=1
      break
    fi
    echo "Graph deploy attempt ${deploy_attempt} exited ${deploy_rc} without an active subgraph" >&2
  done
fi

if [ "${subgraph_deployed}" -ne 1 ]; then
  echo "DOS Names subgraph was not activated after three deploy attempts" >&2
  exit 1
fi

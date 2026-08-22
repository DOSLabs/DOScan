#!/usr/bin/env python3
"""Validate the static DOS Name Service runtime contract for Testnet."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose" / "docker-compose-testnet.yml"
CADDY = ROOT / "docker-compose" / "Caddyfile-gcp-testnet"
BACKEND_ENV = ROOT / "docker-compose" / "envs" / "common-blockscout-testnet.env"
FRONTEND_ENV = ROOT / "docker-compose" / "envs" / "common-frontend-testnet.env"
BENS_TEMPLATE = ROOT / "docker-compose" / "bens" / "config.template.json"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-config.yml"
DEPENDENCY_WORKFLOW = ROOT / ".github" / "workflows" / "dependency-build.yml"
PLAYWRIGHT_SPEC = ROOT / ".github" / "scripts" / "testnet-bens-ui.spec.mjs"
RPC_RETRY_SCRIPT = ROOT / ".github" / "scripts" / "retry-testnet-rpc.sh"
PACKAGE_VERIFIER_SCRIPT = ROOT / ".github" / "scripts" / "verify-testnet-package.sh"
DOCKER_REMOVE_RETRY_SCRIPT = (
    ROOT / ".github" / "scripts" / "remove-docker-containers-with-retry.sh"
)
SUBGRAPH_DEPLOY_SCRIPT = ROOT / "docker-compose" / "bens" / "deploy-subgraph.sh"
CANONICAL_TESTNET_BLOCKCHAIN = "JASJZyVTWR7aviy4eY5yE8AVfdXtH33c1AinvzhLcVBARhcm9"
RETIRED_TESTNET_BLOCKCHAIN = "2EhCz8u48mSCUzxEEGsqY7d1PnqUKkc2B1zkTQaJxbT99wshkJ"
CANONICAL_TESTNET_BENS_RPC = "https://test.doschain.com/"
CANONICAL_BLOCKSCOUT_DB = "blockscout_jasj_20260809"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def validate() -> list[str]:
    errors: list[str] = []
    required_files = (
        COMPOSE,
        CADDY,
        BACKEND_ENV,
        FRONTEND_ENV,
        BENS_TEMPLATE,
        DEPLOY_WORKFLOW,
        DEPENDENCY_WORKFLOW,
        PLAYWRIGHT_SPEC,
        RPC_RETRY_SCRIPT,
        PACKAGE_VERIFIER_SCRIPT,
        DOCKER_REMOVE_RETRY_SCRIPT,
        SUBGRAPH_DEPLOY_SCRIPT,
    )
    for path in required_files:
        if not path.is_file():
            errors.append(f"Missing required BENS file: {path.relative_to(ROOT)}")
    if errors:
        return errors

    compose = COMPOSE.read_text(encoding="utf-8")
    caddy = CADDY.read_text(encoding="utf-8")
    backend_env = read_env(BACKEND_ENV)
    frontend_env = read_env(FRONTEND_ENV)
    config = json.loads(BENS_TEMPLATE.read_text(encoding="utf-8"))
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    dependency_workflow = DEPENDENCY_WORKFLOW.read_text(encoding="utf-8")
    rpc_retry_script = RPC_RETRY_SCRIPT.read_text(encoding="utf-8")
    package_verifier_script = PACKAGE_VERIFIER_SCRIPT.read_text(encoding="utf-8")
    docker_remove_retry_script = DOCKER_REMOVE_RETRY_SCRIPT.read_text(encoding="utf-8")
    subgraph_deploy_script = SUBGRAPH_DEPLOY_SCRIPT.read_text(encoding="utf-8")

    for path, content in (
        (COMPOSE, compose),
        (CADDY, caddy),
        (BACKEND_ENV, BACKEND_ENV.read_text(encoding="utf-8")),
    ):
        if CANONICAL_TESTNET_BLOCKCHAIN not in content:
            errors.append(
                f"{path.relative_to(ROOT)} must target the canonical Testnet blockchain"
            )
        if RETIRED_TESTNET_BLOCKCHAIN in content:
            errors.append(
                f"{path.relative_to(ROOT)} must not target the retired Testnet blockchain"
            )
    if caddy.count(CANONICAL_TESTNET_BLOCKCHAIN) != 2:
        errors.append(
            "Caddy Testnet RPC and WebSocket routes must both target the canonical blockchain"
        )
    if caddy.count('X-DOS-RPC-Origin "dos-testnet-r0-JASJZyVT"') != 2:
        errors.append("Caddy must identify both canonical Testnet RPC routes")
    if f"ethereum: dos-testnet:{CANONICAL_TESTNET_BENS_RPC}" not in compose:
        errors.append("Graph Node must bootstrap from the canonical public Testnet RPC")

    canonical_database_url = (
        f"postgresql://postgres:@db:5432/{CANONICAL_BLOCKSCOUT_DB}"
    )
    user_ops = compose.split("  user-ops-indexer:", 1)[-1].split(
        "\n  stats:", 1
    )[0]
    stats = compose.split("  stats:", 1)[-1].split("\n  caddy:", 1)[0]
    if canonical_database_url not in user_ops:
        errors.append("User Ops Indexer must share the canonical Blockscout database")
    if canonical_database_url not in stats:
        errors.append("Stats must read the canonical Blockscout database")
    if f'BLOCKSCOUT_DB="{CANONICAL_BLOCKSCOUT_DB}"' not in workflow:
        errors.append("Testnet deployment must identify the canonical Blockscout database")
    if 'pg_dump -U postgres -Fc "${BLOCKSCOUT_DB}"' not in workflow:
        errors.append("Testnet backup must dump the canonical Blockscout database")
    if 'pg_restore -U postgres -d "${BLOCKSCOUT_DB}"' not in workflow:
        errors.append("Testnet rollback must restore the canonical Blockscout database")

    for service in ("bens-db:", "bens-ipfs:", "bens-graph-node:", "bens:"):
        if service not in compose:
            errors.append(f"Testnet Compose is missing service {service[:-1]}")
    for image in (
        "ghcr.io/blockscout/bens:v1.7.3@sha256:",
        "graphprotocol/graph-node:v0.45.0@sha256:",
        "ipfs/kubo:v0.43.0@sha256:",
    ):
        if image not in compose:
            errors.append(f"Testnet Compose must pin {image}")
    if "bens_postgres_data:" not in compose or "bens_ipfs_data:" not in compose:
        errors.append("BENS state must use dedicated named volumes")
    if "-cshared_preload_libraries=pg_stat_statements" not in compose:
        errors.append("Graph Node Postgres must preload pg_stat_statements")
    if "doscan-bens-internal" in compose:
        errors.append("BENS database credentials must not be hardcoded")
    if compose.count("DOSCAN_BENS_SECRETS_ENV") != 3:
        errors.append("Every database client must load the dedicated BENS secret file")
    if "./bens/subgraph:/source:ro" not in compose:
        errors.append("The deployer must mount the fetched DOS Names subgraph")
    if "./bens/deploy-subgraph.sh:/runtime/deploy-subgraph.sh:ro" not in compose:
        errors.append("The deployer must mount the reviewed subgraph deploy script")
    if "exec /bin/sh /runtime/deploy-subgraph.sh" not in compose:
        errors.append("The deployer must run the reviewed subgraph deploy script")
    if "BENS_SUBGRAPH_VERSION: ${BENS_SUBGRAPH_VERSION:-testnet}" not in compose:
        errors.append("The deployer must receive the workflow's unique version label")
    graph_cli = "node node_modules/@graphprotocol/graph-cli/bin/run"
    if graph_cli not in subgraph_deploy_script:
        errors.append("The deployer must invoke Graph CLI through Node")
    for command in (
        "codegen --output-dir src/types/",
        "build",
        "create dos-names",
        "deploy dos-names",
    ):
        if f"run_graph_cli {command}" not in subgraph_deploy_script:
            errors.append(
                f"The deployer must invoke Graph CLI through Node for {command}"
            )
    if (
        "npm run codegen" in subgraph_deploy_script
        or "npm run build" in subgraph_deploy_script
        or "npx graph" in subgraph_deploy_script
    ):
        errors.append("The deployer must not rely on executable Graph CLI shims")

    expected_backend = {
        "MICROSERVICE_BENS_ENABLED": "true",
        "MICROSERVICE_BENS_URL": "http://bens:8050/",
        "MICROSERVICE_BENS_PROTOCOLS": "dos-names",
    }
    for key, expected in expected_backend.items():
        actual = backend_env.get(key)
        if actual != expected:
            errors.append(f"{key} must be {expected!r}, got {actual!r}")

    expected_frontend = {
        "NEXT_PUBLIC_NAME_SERVICE_API_HOST": "https://test.doscan.io",
        "NEXT_PUBLIC_NAME_SERVICE_PROTOCOLS": "['dos-names']",
    }
    for key, expected in expected_frontend.items():
        actual = frontend_env.get(key)
        if actual != expected:
            errors.append(f"{key} must be {expected!r}, got {actual!r}")

    if "handle_path /name-service/*" not in caddy or "reverse_proxy bens:8050" not in caddy:
        errors.append("Caddy must expose BENS under /name-service without route overlap")

    protocols = config.get("subgraphs_reader", {}).get("protocols", {})
    networks = config.get("subgraphs_reader", {}).get("networks", {})
    protocol = protocols.get("dos-names", {})
    if protocol.get("network_id") != 3939:
        errors.append("BENS protocol dos-names must target chain 3939")
    if protocol.get("meta", {}).get("short_name") != "DOS":
        errors.append("BENS protocol dos-names must use DOS as its short name")
    if protocol.get("address_resolve_technique") != "all_domains":
        errors.append("ENSv2 DOS names must use all_domains address resolution")
    if "native_token_contract" in protocol.get("specific", {}):
        errors.append("ENSv2 token IDs must not use the ENSv1 native NFT mapping")
    if networks.get("3939", {}).get("use_protocols") != ["dos-names"]:
        errors.append("BENS network 3939 must enable only dos-names")
    if networks.get("3939", {}).get("rpc_url") != CANONICAL_TESTNET_BENS_RPC:
        errors.append("BENS must use the canonical public Testnet RPC")

    ref_match = re.search(r"DOS_NAMES_TESTNET_SUBGRAPH_REF: ([0-9a-f]{40})", workflow)
    if ref_match is None:
        errors.append("The deployment workflow must pin a full DOS Names commit")
    if "https://github.com/DOS/DOS-Names-Contracts.git" not in workflow:
        errors.append("The deployment workflow must fetch from DOS Names")
    if "contracts/deployments/dos-testnet-3939.json" not in workflow:
        errors.append("The deployment workflow must consume the DOS Names manifest")
    if "merge-base --is-ancestor" not in workflow or "refs/remotes/origin/dos" not in workflow:
        errors.append("The deployment workflow must prove the DOS Names pin belongs to branch dos")
    testnet_job = workflow.split("  deploy-testnet:", 1)
    if len(testnet_job) != 2 or "run: python scripts/validate-testnet-bens.py" not in testnet_job[1].split(
        "\n  deploy-beta:", 1
    )[0]:
        errors.append("The Testnet deploy job must run the BENS validator directly")
    for acceptance_marker in (
        "FINAL_DEPLOYMENT_BLOCK",
        "SMOKE_RESOLVED_ADDRESS",
        ".resolved_address.hash",
        "/addresses/${SMOKE_RESOLVED_ADDRESS}",
        "/api/v2/search?q=${SMOKE_NAME}",
        "Verify Testnet DOS Name UI with Playwright",
    ):
        if acceptance_marker not in workflow:
            errors.append(
                f"The Testnet deployment acceptance gate is missing {acceptance_marker}"
            )
    if "DOSCAN_BENS_DB_PASSWORD" not in workflow or (
        "BENS database secrets derived from canonical password" not in workflow
    ):
        errors.append("BENS database credentials must derive from one canonical secret")
    if (
        ".github/scripts/retry-testnet-rpc.sh" not in workflow
        or '. "${SRC}/.github/scripts/retry-testnet-rpc.sh"' not in workflow
        or "testnet_rpc_request" not in workflow
    ):
        errors.append("Testnet deployment must package and use the RPC retry helper")
    contract_code_gate = workflow.split('contract_code="$(\n', 1)
    if len(contract_code_gate) != 2:
        errors.append("Testnet deployment must verify DOS Names contract bytecode")
    else:
        contract_code_gate = contract_code_gate[1].split(
            'if [ "${contract_code}"', 1
        )[0]
        if (
            'TESTNET_RPC_CONTRACT_CODE_URL="https://test.doschain.com/"'
            not in workflow
            or 'testnet_rpc_request "${rpc_body}" 0 "${TESTNET_RPC_CONTRACT_CODE_URL}"'
            not in contract_code_gate
            or "127.0.0.1:9650" in contract_code_gate
        ):
            errors.append(
                "DOS Names bytecode verification must use the public Testnet RPC"
            )
    if (
        "https://test.doschain.com/" not in rpc_retry_script
        or "for attempt in 1 2 3" not in rpc_retry_script
        or "--http1.1" not in rpc_retry_script
    ):
        errors.append("Testnet RPC retry helper must be bounded and use the canonical RPC")
    if (
        'test -s docker-compose/bens/config.json' not in workflow
        or 'bash .github/scripts/verify-testnet-package.sh /tmp/doscan-testnet-config.tgz'
        not in workflow
        or 'tar -tzf "${archive}" | grep -Fx "docker-compose/bens/config.json"'
        not in package_verifier_script
    ):
        errors.append("Testnet package must fail closed without the rendered BENS config")
    if (
        ".github/scripts/remove-docker-containers-with-retry.sh" not in workflow
        or 'for attempt in 1 2 3' not in docker_remove_retry_script
        or 'docker rm -f "${remaining[@]}"' not in docker_remove_retry_script
    ):
        errors.append("Testnet rollback must retry raced Docker container removals")
    if (
        "pull_caddy_image()" not in workflow
        or 'docker pull "${CADDY_IMAGE}"' not in workflow
    ):
        errors.append("Caddy validation must retry the pinned image pull")
    dependency_ref_match = re.search(
        r"DOS_NAMES_SUBGRAPH_REF: ([0-9a-f]{40})", dependency_workflow
    )
    if (
        ref_match is not None
        and dependency_ref_match is not None
        and ref_match.group(1) != dependency_ref_match.group(1)
    ):
        errors.append("Deploy and dependency workflows must pin the same DOS Names commit")
    if (
        'node "${checkout}/subgraph/dos-names/scripts/render-manifest.mjs"'
        not in dependency_workflow
        or "python scripts/render-testnet-bens.py" not in dependency_workflow
    ):
        errors.append("Dependency CI must render the pinned DOS Names runtime artifacts")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("DOScan Testnet BENS validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("DOScan Testnet BENS validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

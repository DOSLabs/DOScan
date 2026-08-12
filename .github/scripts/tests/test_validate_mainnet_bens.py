import json
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "docker-compose" / "docker-compose-mainnet.yml"
CADDY = ROOT / "docker-compose" / "Caddyfile-gcp-mainnet"
BACKEND_ENV = ROOT / "docker-compose" / "envs" / "common-blockscout-mainnet.env"
FRONTEND_ENV = ROOT / "docker-compose" / "envs" / "common-frontend-scan.env"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-config.yml"
CONFIG_TEMPLATE = ROOT / "docker-compose" / "bens" / "config.mainnet.template.json"
RENDERER = ROOT / "scripts" / "render-mainnet-bens.py"
RUNTIME = ROOT / ".github" / "scripts" / "mainnet-bens-runtime.sh"
MAINNET_RPC = (
    "http://host.docker.internal:9650/ext/bc/"
    "2ewKoUrSjnviEgGmeTiELHBmNjxVTVczBPowST471rYUZvA9bk/rpc"
)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


class MainnetBensConfigurationTests(unittest.TestCase):
    def test_mainnet_renderer_accepts_only_chain_7979(self):
        spec = importlib.util.spec_from_file_location("render_mainnet_bens", RENDERER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        deployment = {
            "chainId": 7979,
            "deploymentBlock": 117,
            "finalDeploymentBlock": 162,
            "smokeName": "bens-smoke.dos",
            "smokeResolvedAddress": "0x99999e454138f6be73E2bE82c890bc5765749999",
            "contracts": {
                "rootRegistry": "0x38FC582690c3F28099087A88520056afAb08ce5F",
                "dosRegistry": "0xb17Fec6fe18aC0b7F3dd934495E84eC06Cf88564",
                "dosRegistrar": "0x1F31e05948769174dA256D0484b8f26cfD3d8c97",
                "permissionedResolverImplementation": "0x72aB4bE8B13CF39F68c73bA1B409A1fdFc0448AD",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment.json"
            path.write_text(json.dumps(deployment), encoding="utf-8")
            self.assertEqual(module.load_deployment(path)["chainId"], 7979)
            deployment["chainId"] = 3939
            path.write_text(json.dumps(deployment), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "chainId must be 7979"):
                module.load_deployment(path)

    def test_mainnet_compose_runs_only_pinned_official_bens_services(self):
        compose = COMPOSE.read_text(encoding="utf-8")
        for service in (
            "bens-db:",
            "bens-ipfs:",
            "bens-graph-node:",
            "bens:",
            "bens-deployer:",
        ):
            self.assertIn(service, compose)
        for image in (
            "postgres:16.10@sha256:",
            "ipfs/kubo:v0.43.0@sha256:",
            "graphprotocol/graph-node:v0.45.0@sha256:",
            "ghcr.io/blockscout/bens:v1.7.3@sha256:",
        ):
            self.assertIn(image, compose)
        self.assertIn(f"ethereum: dos-mainnet:{MAINNET_RPC}", compose)
        bens_service = compose.split("\n  bens:\n", 1)[1].split(
            "\n  bens-deployer:\n", 1
        )[0]
        self.assertIn("host.docker.internal:host-gateway", bens_service)
        self.assertIn("bens_postgres_data:", compose)
        self.assertIn("bens_ipfs_data:", compose)
        self.assertEqual(compose.count("DOSCAN_BENS_SECRETS_ENV"), 3)
        self.assertNotIn('MICROSERVICE_BENS_ENABLED: "false"', compose)

    def test_mainnet_uses_standard_blockscout_name_service_env(self):
        backend = read_env(BACKEND_ENV)
        frontend = read_env(FRONTEND_ENV)
        self.assertEqual(backend["MICROSERVICE_BENS_ENABLED"], "true")
        self.assertEqual(backend["MICROSERVICE_BENS_URL"], "http://bens:8050/")
        self.assertEqual(backend["MICROSERVICE_BENS_PROTOCOLS"], "dos-names")
        self.assertEqual(
            frontend["NEXT_PUBLIC_NAME_SERVICE_API_HOST"],
            "https://doscan.io/name-service",
        )
        self.assertEqual(
            frontend["NEXT_PUBLIC_NAME_SERVICE_PROTOCOLS"], "['dos-names']"
        )

    def test_mainnet_caddy_exposes_bens_without_core_changes(self):
        caddy = CADDY.read_text(encoding="utf-8")
        self.assertIn("handle_path /name-service/*", caddy)
        self.assertIn("reverse_proxy bens:8050", caddy)

    def test_mainnet_bens_config_targets_chain_7979(self):
        config = json.loads(CONFIG_TEMPLATE.read_text(encoding="utf-8"))
        reader = config["subgraphs_reader"]
        self.assertEqual(reader["networks"]["7979"]["rpc_url"], MAINNET_RPC)
        self.assertEqual(reader["networks"]["7979"]["use_protocols"], ["dos-names"])
        protocol = reader["protocols"]["dos-names"]
        self.assertEqual(protocol["network_id"], 7979)
        self.assertEqual(protocol["tld_list"], ["dos"])
        self.assertEqual(protocol["specific"]["registry_contract"], "__ROOT_REGISTRY_ADDRESS__")

    def test_mainnet_workflow_consumes_the_canonical_manifest(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        mainnet_job = workflow.split("  deploy-mainnet:", 1)[1].split(
            "\n  deploy-testnet:", 1
        )[0]
        self.assertIn("contracts/deployments/dos-mainnet-7979.json", mainnet_job)
        self.assertIn("docker-compose/bens", mainnet_job)
        self.assertIn("mainnet-bens-runtime.sh", mainnet_job)
        self.assertIn("BENS_SUBGRAPH_VERSION", RUNTIME.read_text(encoding="utf-8"))
        self.assertIn("/name-service/api/v1/7979/domains/${SMOKE_NAME}", mainnet_job)
        self.assertIn("Verify Mainnet DOS Name UI with Playwright", mainnet_job)

    def test_mainnet_apply_script_parses_as_bash(self):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        apply_script = next(
            step["run"]
            for step in workflow["jobs"]["deploy-mainnet"]["steps"]
            if step.get("name") == "Apply configuration and verify services"
        )
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(git_bash) if git_bash.exists() else shutil.which("bash")
        self.assertIsNotNone(bash)
        result = subprocess.run(
            [bash, "-n"],
            input=apply_script,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mainnet_runtime_is_atomic_and_checks_the_exact_subgraph(self):
        runtime = RUNTIME.read_text(encoding="utf-8")
        for marker in (
            "bens_prepare",
            "bens_deploy",
            "bens_rollback",
            "bens-graph-node.dump",
            "bens-ipfs.tgz",
            "BENS_DB_VOLUME",
            "BENS_IPFS_VOLUME",
            "subgraph_ipfs_hash",
            ".data._meta.deployment == $cid",
            ".data._meta.hasIndexingErrors == false",
            "FINAL_DEPLOYMENT_BLOCK",
            "SMOKE_RESOLVED_ADDRESS",
        ):
            self.assertIn(marker, runtime)
        self.assertIn("for attempt in $(seq 1 60)", runtime)
        self.assertIn("docker volume rm", runtime)

    def test_mainnet_rollback_never_drops_database_after_incomplete_backup(self):
        runtime = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("BENS_BACKUP_COMPLETE=0", runtime)
        self.assertIn("pg_restore --list /backup/bens-graph-node.dump", runtime)
        self.assertIn("tar -tzf /backup/bens-ipfs.tgz", runtime)
        self.assertIn("bens_capture_prior_state", runtime)
        self.assertIn("bens_verify_restored_state", runtime)
        self.assertIn("http://backend:4000/api/v2/search", runtime)
        incomplete_guard = runtime.index(
            'if [ "${BENS_BACKUP_COMPLETE}" -ne 1 ]; then'
        )
        destructive_restore = runtime.index(
            "bens_compose exec -T bens-db dropdb --force"
        )
        self.assertLess(incomplete_guard, destructive_restore)
        guarded_section = runtime[incomplete_guard:destructive_restore]
        self.assertIn(
            "bens_compose up -d bens-db bens-ipfs bens-graph-node bens",
            guarded_section,
        )
        self.assertIn("return", guarded_section)

    def test_first_install_rollback_proves_runtime_and_volumes_are_removed(self):
        runtime = RUNTIME.read_text(encoding="utf-8")
        self.assertIn('bens_compose ps -aq "${service}"', runtime)
        self.assertIn('sudo docker volume rm "${volume}"', runtime)
        self.assertGreaterEqual(
            runtime.count('sudo docker volume inspect "${volume}"'), 2
        )


if __name__ == "__main__":
    unittest.main()

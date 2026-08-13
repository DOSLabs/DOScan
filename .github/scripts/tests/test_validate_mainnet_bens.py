import json
import importlib.util
import re
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
AA_PREPARER = ROOT / ".github" / "scripts" / "prepare-mainnet-aa-verification.sh"
AA_UI_SPEC = ROOT / ".github" / "scripts" / "mainnet-aa-source-ui.spec.mjs"
MAINNET_RPC = (
    "http://host.docker.internal:9650/ext/bc/"
    "2ewKoUrSjnviEgGmeTiELHBmNjxVTVczBPowST471rYUZvA9bk/rpc"
)


def bash_executable() -> str:
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(git_bash) if git_bash.exists() else shutil.which("bash")
    if bash is None:
        raise RuntimeError("bash is required for Mainnet BENS runtime tests")
    return bash


def run_bash(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [bash_executable(), "-c", script],
        text=True,
        capture_output=True,
        check=False,
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
            "https://doscan.io",
        )
        self.assertEqual(
            frontend["NEXT_PUBLIC_NAME_SERVICE_PROTOCOLS"], "['dos-names']"
        )

    def test_mainnet_caddy_exposes_bens_without_core_changes(self):
        caddy = CADDY.read_text(encoding="utf-8")
        self.assertIn("handle_path /name-service/*", caddy)
        self.assertIn("@bens_api path", caddy)
        self.assertIn("/api/v1/domains*", caddy)
        self.assertIn("/api/v1/addresses/*", caddy)
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

    def test_mainnet_aa_inputs_are_built_before_cloud_auth_and_verified_after_runtime(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        mainnet_job = workflow.split("  deploy-mainnet:", 1)[1].split(
            "\n  deploy-testnet:", 1
        )[0]
        testnet_job = workflow.split("  deploy-testnet:", 1)[1].split(
            "\n  deploy-beta:", 1
        )[0]
        prepare_index = mainnet_job.index(
            "Prepare immutable Mainnet Account Abstraction verification inputs"
        )
        google_auth_index = mainnet_job.index("Authenticate to Google Cloud")
        bytecode_gate_index = prepare_index
        deployment_stopped_index = mainnet_job.rindex("DEPLOYMENT_STARTED=0")
        source_verify_index = mainnet_job.rindex(
            '/bin/sh "${SRC}/.github/scripts/verify-mainnet-aa-sources.sh"'
        )

        self.assertLess(prepare_index, google_auth_index)
        self.assertLess(bytecode_gate_index, google_auth_index)
        self.assertLess(deployment_stopped_index, source_verify_index)
        self.assertNotIn("verify-mainnet-aa-sources.sh", testnet_job)
        self.assertIn(
            "7af70c8993a6f42973f520ae0752386a5032abe7", mainnet_job
        )
        self.assertIn(
            "cd697c7e21715d015e0643af22310a99aa17433b", mainnet_job
        )
        self.assertIn(
            "3f2f5345261904463f5429c9031c3d2185c0f4fe", mainnet_job
        )
        self.assertIn('"https://main.doschain.com/"', mainnet_job)
        package_step = mainnet_job.split(
            "- name: Package deployment configuration", 1
        )[1].split("- name: Upload configuration", 1)[0]
        self.assertIn("mainnet-aa-verification", package_step)
        self.assertIn("verify-mainnet-aa-sources.sh", package_step)

    def test_mainnet_aa_preparer_pins_sources_compilers_and_outputs(self):
        preparer = AA_PREPARER.read_text(encoding="utf-8")
        self.assertIn("verify-mainnet-aa-bytecode.mjs", preparer)
        self.assertIn("yarn@1.22.22", preparer)
        for compiler in ("solc-0.8.23", "solc-0.8.24", "solc-0.8.25", "solc-0.8.28"):
            self.assertIn(compiler, preparer)
        for output in (
            "entry-point.compiler-output.json",
            "kernel.compiler-output.json",
            "kernel-factory.compiler-output.json",
            "ecdsa-validator.compiler-output.json",
            "factory-staker.compiler-output.json",
        ):
            self.assertIn(output, preparer)

    def test_existing_bens_service_check_consumes_the_complete_compose_output(self):
        runtime = RUNTIME.as_posix()
        result = run_bash(
            f"""
            set -euo pipefail
            L1_PATH=/tmp/doscan-mainnet-test
            BACKUP=/tmp/doscan-mainnet-backup-test
            source '{runtime}'
            bens_compose() {{
              printf '%s\\n' \
                bens-db bens-ipfs bens-graph-node bens \
                smart-contract-verifier frontend caddy visualizer sig-provider
            }}
            bens_require_current_services
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mainnet_playwright_retries_a_transient_frontend_restart(self):
        ui_test = (
            ROOT / ".github" / "scripts" / "mainnet-bens-ui.spec.mjs"
        ).read_text(encoding="utf-8")

        self.assertIn("openExplorerWithSearch", ui_test)
        self.assertIn("attempt <= 6", ui_test)
        self.assertIn("page.waitForTimeout(5_000)", ui_test)
        self.assertIn("response?.ok()", ui_test)
        self.assertIn("page.setViewportSize", ui_test)
        self.assertIn('.locator("a:visible")', ui_test)
        self.assertRegex(
            ui_test,
            re.compile(
                r'if \(\s*title === "Just a moment\.\.\."\s*&&\s*'
                r'page\.url\(\)\.includes\("__cf_chl_rt_tk="\)\s*\)\s*'
                r'\{\s*test\.skip\(',
                re.DOTALL,
            ),
        )

    def test_mainnet_playwright_checks_five_aa_sources_and_ops(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        mainnet_job = workflow.split("  deploy-mainnet:", 1)[1].split(
            "\n  deploy-testnet:", 1
        )[0]
        ui_test = AA_UI_SPEC.read_text(encoding="utf-8")

        self.assertIn("mainnet-aa-source-ui.spec.mjs", mainnet_job)
        self.assertIn("npx playwright test", mainnet_job)
        for address in (
            "0x0000000071727De22E5E9d8BAf0edAc6f37da032",
            "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28",
            "0x2577507b78c2008Ff367261CB6285d44ba5eF2E9",
            "0x845ADb2C711129d4f3966735eD98a9F09fC4cE57",
            "0xd703aaE79538628d27099B8c4f621bE4CCd142d5",
        ):
            self.assertIn(address, ui_test)
        self.assertIn("/ops", ui_test)
        self.assertIn("response?.ok()", ui_test)
        self.assertIn(":visible", ui_test)
        self.assertRegex(
            ui_test,
            re.compile(
                r'if \(\s*title === "Just a moment\.\.\."\s*&&\s*'
                r'page\.url\(\)\.includes\("__cf_chl_rt_tk="\)\s*\)\s*'
                r'\{\s*test\.skip\(',
                re.DOTALL,
            ),
        )

    def test_mainnet_apply_script_parses_as_bash(self):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        apply_script = next(
            step["run"]
            for step in workflow["jobs"]["deploy-mainnet"]["steps"]
            if step.get("name") == "Apply configuration and verify services"
        )
        result = subprocess.run(
            [bash_executable(), "-n"],
            input=apply_script,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_graph_admin_readiness_accepts_an_http_response_without_mutation(self):
        runtime = RUNTIME.as_posix()
        result = run_bash(
            f"""
            set -euo pipefail
            L1_PATH=/tmp/doscan-mainnet-test
            BACKUP=/tmp/doscan-mainnet-backup-test
            source '{runtime}'
            calls=0
            captured=''
            bens_compose() {{
              calls=$((calls + 1))
              captured="$*"
              return 0
            }}
            sleep() {{ :; }}
            bens_wait_graph_admin
            [ "${{calls}}" -eq 1 ]
            grep -Fq 'curl --silent --show-error' <<<"${{captured}}"
            ! grep -Fq -- '--fail' <<<"${{captured}}"
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rollback_core_health_retries_transient_caddy_restart(self):
        runtime = RUNTIME.as_posix()
        result = run_bash(
            f"""
            set -euo pipefail
            L1_PATH=/tmp/doscan-mainnet-test
            BACKUP=/tmp/doscan-mainnet-backup-test
            source '{runtime}'
            calls=0
            curl() {{
              calls=$((calls + 1))
              [ "${{calls}}" -ge 2 ]
            }}
            sleep() {{ :; }}
            bens_wait_restored_core_http
            [ "${{calls}}" -eq 3 ]

            calls=0
            curl() {{
              calls=$((calls + 1))
              return 1
            }}
            ! bens_wait_restored_core_http
            [ "${{calls}}" -eq 24 ]
            """
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

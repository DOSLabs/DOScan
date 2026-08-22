import importlib.util
import http.server
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "validate-testnet-bens.py"
RPC_RETRY_SCRIPT = ROOT / ".github" / "scripts" / "retry-testnet-rpc.sh"
TESTNET_PACKAGE_VERIFIER = ROOT / ".github" / "scripts" / "verify-testnet-package.sh"
DOCKER_REMOVE_RETRY_SCRIPT = (
    ROOT / ".github" / "scripts" / "remove-docker-containers-with-retry.sh"
)
SUBGRAPH_DEPLOY_SCRIPT = ROOT / "docker-compose" / "bens" / "deploy-subgraph.sh"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_testnet_bens", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidateTestnetBensTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_repository_configuration_is_valid(self):
        self.assertEqual([], self.module.validate())

    def test_ensv2_registry_is_not_misreported_as_an_ensv1_nft(self):
        template = json.loads(
            (ROOT / "docker-compose" / "bens" / "config.template.json").read_text(
                encoding="utf-8"
            )
        )
        specific = template["subgraphs_reader"]["protocols"]["dos-names"]["specific"]

        self.assertNotIn("native_token_contract", specific)

    def test_doscan_does_not_vendor_the_custom_subgraph(self):
        self.assertFalse((ROOT / "docker-compose" / "bens" / "dos-names").exists())

    def test_bens_database_password_is_not_hardcoded(self):
        compose = (
            ROOT / "docker-compose" / "docker-compose-testnet.yml"
        ).read_text(encoding="utf-8")

        self.assertNotIn("doscan-bens-internal", compose)
        self.assertIn("DOSCAN_BENS_SECRETS_ENV", compose)

    def test_bens_uses_canonical_testnet_rpcs(self):
        public_rpc = "https://test.doschain.com/"
        template = json.loads(
            (ROOT / "docker-compose" / "bens" / "config.template.json").read_text(
                encoding="utf-8"
            )
        )
        compose = (
            ROOT / "docker-compose" / "docker-compose-testnet.yml"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        retry_script = RPC_RETRY_SCRIPT.read_text(encoding="utf-8")

        self.assertEqual(
            public_rpc,
            template["subgraphs_reader"]["networks"]["3939"]["rpc_url"],
        )
        self.assertIn(f"ethereum: dos-testnet:{public_rpc}", compose)
        self.assertNotIn("ethereum: dos-testnet:http://10.148.0.7:9650/", compose)
        bytecode_gate = workflow.split('contract_code="$(\n', 1)[1].split(
            'if [ "${contract_code}"', 1
        )[0]
        self.assertIn(public_rpc, retry_script)
        self.assertIn(
            'TESTNET_RPC_CONTRACT_CODE_URL="https://test.doschain.com/"',
            workflow,
        )
        self.assertIn(
            'testnet_rpc_request "${rpc_body}" 0 "${TESTNET_RPC_CONTRACT_CODE_URL}"',
            bytecode_gate,
        )
        self.assertNotIn('testnet_rpc_request "${rpc_body}" |', bytecode_gate)
        self.assertIn('local endpoint="${3:-https://test.doschain.com/}"', retry_script)
        self.assertIn('"${endpoint}"', retry_script)
        self.assertNotIn("10.148.0.7", bytecode_gate)
        self.assertNotIn("127.0.0.1:9650", bytecode_gate)
        public_rpc_gate = workflow.split('rpc_response="$(\n', 1)[1].split(
            'sudo docker compose ps', 1
        )[0]
        self.assertIn("X-DOS-RPC-Origin: dos-testnet-r0-", public_rpc_gate)
        self.assertNotIn("archive-dos-testnet-r0", public_rpc_gate)

    def test_all_testnet_runtime_rpc_targets_use_the_canonical_blockchain(self):
        canonical_blockchain = (
            "JASJZyVTWR7aviy4eY5yE8AVfdXtH33c1AinvzhLcVBARhcm9"
        )
        retired_blockchain = (
            "2EhCz8u48mSCUzxEEGsqY7d1PnqUKkc2B1zkTQaJxbT99wshkJ"
        )
        paths = (
            ROOT / "docker-compose" / "Caddyfile-gcp-testnet",
            ROOT / "docker-compose" / "docker-compose-testnet.yml",
            ROOT / "docker-compose" / "envs" / "common-blockscout-testnet.env",
        )

        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                content = path.read_text(encoding="utf-8")
                self.assertIn(canonical_blockchain, content)
                self.assertNotIn(retired_blockchain, content)

        caddy = paths[0].read_text(encoding="utf-8")
        self.assertEqual(2, caddy.count(canonical_blockchain))
        self.assertEqual(2, caddy.count('X-DOS-RPC-Origin "dos-testnet-r0-JASJZyVT"'))

    def test_account_abstraction_uses_the_canonical_blockscout_database(self):
        canonical_database = "blockscout_jasj_20260809"
        compose = (
            ROOT / "docker-compose" / "docker-compose-testnet.yml"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        user_ops = compose.split("  user-ops-indexer:", 1)[1].split(
            "\n  stats:", 1
        )[0]
        stats = compose.split("  stats:", 1)[1].split("\n  caddy:", 1)[0]
        testnet_deploy = workflow.split(
            "      - name: Apply testnet configuration and verify services", 1
        )[1].split("      - name: Verify Testnet DOS Name UI with Playwright", 1)[0]

        self.assertIn(
            f"postgresql://postgres:@db:5432/{canonical_database}", user_ops
        )
        self.assertIn(
            f"postgresql://postgres:@db:5432/{canonical_database}", stats
        )
        self.assertIn(f'BLOCKSCOUT_DB="{canonical_database}"', testnet_deploy)
        self.assertIn(
            'pg_dump -U postgres -Fc "${BLOCKSCOUT_DB}"', testnet_deploy
        )
        self.assertIn(
            'pg_restore -U postgres -d "${BLOCKSCOUT_DB}"', testnet_deploy
        )
        self.assertNotIn("pg_dump -U postgres -Fc blockscout", testnet_deploy)

    def test_push_deploys_only_affected_environment(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        changes_job = workflow.split("  changes:", 1)[1].split(
            "\n  deploy-mainnet:", 1
        )[0]
        mainnet_job = workflow.split("  deploy-mainnet:", 1)[1].split(
            "\n  deploy-testnet:", 1
        )[0]
        testnet_job = workflow.split("  deploy-testnet:", 1)[1].split(
            "\n  deploy-beta:", 1
        )[0]

        self.assertIn("needs: changes", mainnet_job)
        self.assertIn("needs.changes.outputs.mainnet == 'true'", mainnet_job)
        self.assertIn("needs: changes", testnet_job)
        self.assertIn("needs.changes.outputs.testnet == 'true'", testnet_job)
        self.assertIn("fetch-depth: 0", changes_job)
        self.assertIn("${{ github.event.before }}", changes_job)
        self.assertIn('git hash-object -t tree /dev/null', changes_job)
        self.assertIn('git diff --name-only "${diff_base}" "${GITHUB_SHA}"', changes_job)
        self.assertIn("docker-compose/docker-compose-mainnet.yml", changes_job)
        self.assertIn("docker-compose/docker-compose-testnet.yml", changes_job)
        self.assertIn("docker-compose/bens/config.template.json", changes_job)
        self.assertIn("DOS_NAMES_MAINNET_SUBGRAPH_REF", changes_job)
        self.assertIn("DOS_NAMES_TESTNET_SUBGRAPH_REF", changes_job)
        self.assertIn("mainnet=true", changes_job)
        self.assertIn("testnet=true", changes_job)

    def test_pin_split_keeps_mainnet_out_of_a_testnet_only_deploy(self):
        bash = "bash"
        if os.name == "nt":
            bash = r"C:\Program Files\Git\bin\bash.exe"
        git = shutil.which("git")
        self.assertIsNotNone(git)

        workflow_path = ROOT / ".github" / "workflows" / "deploy-config.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        changes_job = workflow.split("  changes:", 1)[1].split(
            "\n  deploy-mainnet:", 1
        )[0]
        selector = textwrap.dedent(changes_job.split("        run: |\n", 1)[1])
        split_pins = (
            "  DOS_NAMES_MAINNET_SUBGRAPH_REF: "
            "6224395661280a739c20ebd8a420913a0dd7fd6e\n"
            "  DOS_NAMES_TESTNET_SUBGRAPH_REF: "
            "130d42ae22881896cab89e33c3c3c096b9b8e989"
        )
        self.assertIn(split_pins, workflow)
        previous_workflow = workflow.replace(
            split_pins,
            "  DOS_NAMES_SUBGRAPH_REF: "
            "6224395661280a739c20ebd8a420913a0dd7fd6e",
            1,
        )

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            test_workflow = repo / ".github" / "workflows" / "deploy-config.yml"
            test_workflow.parent.mkdir(parents=True)
            subprocess.run([git, "init", "-q"], cwd=repo, check=True)
            subprocess.run([git, "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run([git, "config", "user.name", "Test"], cwd=repo, check=True)
            test_workflow.write_text(previous_workflow, encoding="utf-8")
            subprocess.run([git, "add", "."], cwd=repo, check=True)
            subprocess.run([git, "commit", "-qm", "previous"], cwd=repo, check=True)
            previous_sha = subprocess.run(
                [git, "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()
            test_workflow.write_text(workflow, encoding="utf-8")
            subprocess.run([git, "add", "."], cwd=repo, check=True)
            subprocess.run([git, "commit", "-qm", "current"], cwd=repo, check=True)
            current_sha = subprocess.run(
                [git, "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()
            selector = selector.replace("${{ github.event_name }}", "push")
            selector = selector.replace("${{ inputs.environment }}", "")
            selector = selector.replace("${{ github.event.before }}", previous_sha)
            output_path = repo / "output"
            environment = os.environ | {
                "GITHUB_OUTPUT": output_path.as_posix(),
                "GITHUB_SHA": current_sha,
            }
            result = subprocess.run(
                [bash, "-c", selector],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                {"mainnet=false", "testnet=true"},
                set(output_path.read_text(encoding="utf-8").splitlines()),
            )

    def test_testnet_helper_changes_select_only_testnet(self):
        bash = "bash"
        if os.name == "nt":
            bash = r"C:\\Program Files\\Git\\bin\\bash.exe"
        git = shutil.which("git")
        self.assertIsNotNone(git)

        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        changes_job = workflow.split("  changes:", 1)[1].split(
            "\n  deploy-mainnet:", 1
        )[0]
        selector = textwrap.dedent(changes_job.split("        run: |\n", 1)[1])

        for helper_name in (
            "verify-testnet-package.sh",
            "remove-docker-containers-with-retry.sh",
        ):
            with self.subTest(helper_name=helper_name), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory)
                workflow_path = repo / ".github" / "workflows" / "deploy-config.yml"
                helper_path = repo / ".github" / "scripts" / helper_name
                workflow_path.parent.mkdir(parents=True)
                helper_path.parent.mkdir(parents=True)
                subprocess.run([git, "init", "-q"], cwd=repo, check=True)
                subprocess.run([git, "config", "user.email", "test@example.com"], cwd=repo, check=True)
                subprocess.run([git, "config", "user.name", "Test"], cwd=repo, check=True)
                workflow_path.write_text(workflow, encoding="utf-8")
                subprocess.run([git, "add", "."], cwd=repo, check=True)
                subprocess.run([git, "commit", "-qm", "previous"], cwd=repo, check=True)
                previous_sha = subprocess.run(
                    [git, "rev-parse", "HEAD"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                helper_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
                subprocess.run([git, "add", "."], cwd=repo, check=True)
                subprocess.run([git, "commit", "-qm", "current"], cwd=repo, check=True)
                current_sha = subprocess.run(
                    [git, "rev-parse", "HEAD"],
                    cwd=repo,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                output_path = repo / "output"
                environment = os.environ | {
                    "GITHUB_OUTPUT": output_path.as_posix(),
                    "GITHUB_SHA": current_sha,
                }
                command = selector.replace("${{ github.event_name }}", "push")
                command = command.replace("${{ inputs.environment }}", "")
                command = command.replace("${{ github.event.before }}", previous_sha)
                result = subprocess.run(
                    [bash, "-c", command],
                    cwd=repo,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=environment,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(
                    {"mainnet=false", "testnet=true"},
                    set(output_path.read_text(encoding="utf-8").splitlines()),
                )

    def test_deployment_builds_and_verifies_immutable_account_abstraction_sources(
        self,
    ):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        testnet_job = workflow.split("  deploy-testnet:", 1)[1].split(
            "\n  deploy-beta:", 1
        )[0]

        self.assertIn(
            "AA_SOURCE_REPOSITORY: https://github.com/eth-infinitism/account-abstraction.git",
            testnet_job,
        )
        self.assertIn(
            "AA_SOURCE_REF: 4cbc06072cdc19fd60f285c5997f4f7f57a588de",
            testnet_job,
        )
        self.assertIn(
            "- name: Prepare immutable Account Abstraction verification inputs",
            testnet_job,
        )
        self.assertIn(
            'git -C "${checkout}" fetch --depth=1 origin "${AA_SOURCE_REF}"',
            testnet_job,
        )
        self.assertIn(
            '[ "$(git -C "${checkout}" rev-parse HEAD)" = "${AA_SOURCE_REF}" ]',
            testnet_job,
        )
        self.assertIn("npm install --global yarn@1.22.22", testnet_job)
        self.assertIn(
            'yarn --cwd "${checkout}" install --frozen-lockfile --non-interactive',
            testnet_job,
        )
        self.assertIn('yarn --cwd "${checkout}" compile', testnet_job)
        self.assertIn("extract-aa-verification-inputs.mjs", testnet_job)
        self.assertIn("account-abstraction-verification", testnet_job)
        self.assertIn(".github/scripts/verify-testnet-aa-sources.sh", testnet_job)
        mainnet_job = workflow.split("  deploy-mainnet:", 1)[1].split(
            "\n  deploy-testnet:", 1
        )[0]
        self.assertNotIn("verify-testnet-aa-sources.sh", mainnet_job)

        apply_step = testnet_job.split(
            "      - name: Apply testnet configuration and verify services", 1
        )[1].split("      - name: Verify Testnet DOS Name UI with Playwright", 1)[0]
        verifier_marker = (
            '/bin/sh "${SRC}/.github/scripts/verify-testnet-aa-sources.sh"'
        )
        verifier_index = apply_step.index(verifier_marker)
        self.assertIn(
            '"${SRC}/account-abstraction-verification"',
            apply_step[verifier_index:],
        )
        rollback_disabled_index = apply_step.rfind(
            "DEPLOYMENT_STARTED=0", 0, verifier_index
        )
        self.assertGreater(rollback_disabled_index, -1)
        self.assertLess(rollback_disabled_index, verifier_index)

        dependency_workflow = (
            ROOT / ".github" / "workflows" / "dependency-build.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "AA_SOURCE_REPOSITORY: https://github.com/eth-infinitism/account-abstraction.git",
            dependency_workflow,
        )
        self.assertIn(
            "AA_SOURCE_REF: 4cbc06072cdc19fd60f285c5997f4f7f57a588de",
            dependency_workflow,
        )
        self.assertIn(
            "- name: Verify immutable Account Abstraction verification inputs",
            dependency_workflow,
        )
        self.assertIn("extract-aa-verification-inputs.mjs", dependency_workflow)
        self.assertIn("verify-testnet-aa-sources.sh", dependency_workflow)

    def test_deployer_invokes_graph_cli_without_executable_shims(self):
        compose = (
            ROOT / "docker-compose" / "docker-compose-testnet.yml"
        ).read_text(encoding="utf-8")
        deploy_script = SUBGRAPH_DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("exec /bin/sh /runtime/deploy-subgraph.sh", compose)
        self.assertIn("run_graph_cli codegen --output-dir src/types/", deploy_script)
        self.assertIn("run_graph_cli build", deploy_script)
        self.assertIn("run_graph_cli create dos-names", deploy_script)
        self.assertIn("run_graph_cli deploy dos-names", deploy_script)
        self.assertNotIn("npm run codegen", deploy_script)
        self.assertNotIn("npm run build", deploy_script)
        self.assertNotIn("npx graph", deploy_script)

    def test_deployer_forwards_the_unique_subgraph_version(self):
        compose = (
            ROOT / "docker-compose" / "docker-compose-testnet.yml"
        ).read_text(encoding="utf-8")
        deployer = compose.split("  bens-deployer:", 1)[1].split("\n  backend:", 1)[0]

        self.assertIn(
            "BENS_SUBGRAPH_VERSION: ${BENS_SUBGRAPH_VERSION:-testnet}", deployer
        )
        self.assertIn(
            'BENS_SUBGRAPH_VERSION="github-${DEPLOY_ID}"',
            (ROOT / ".github" / "workflows" / "deploy-config.yml").read_text(
                encoding="utf-8"
            ),
        )

    def test_subgraph_retry_uses_manifest_cid_and_rejects_unready_states(self):
        manifest_cid = "Qm" + "B" * 44
        asset_cid = "Qm" + "A" * 44
        old_cid = "Qm" + "C" * 44
        ready = {
            "data": {
                "_meta": {
                    "deployment": manifest_cid,
                    "hasIndexingErrors": False,
                }
            }
        }
        rejected_states = [
            {
                "data": {
                    "_meta": {
                        "deployment": old_cid,
                        "hasIndexingErrors": False,
                    }
                }
            },
            {
                "errors": [{"message": "indexing unavailable"}],
                "data": {
                    "_meta": {
                        "deployment": manifest_cid,
                        "hasIndexingErrors": False,
                    }
                },
            },
            {"data": {}},
            {
                "data": {
                    "_meta": {
                        "deployment": manifest_cid,
                        "hasIndexingErrors": True,
                    }
                }
            },
        ]

        for rejected in rejected_states:
            with self.subTest(rejected=rejected):
                result, calls = self._run_subgraph_deployer(
                    [rejected, ready], manifest_cid, asset_cid
                )
                self.assertEqual(0, result.returncode, result.stderr)
                deploy_calls = [call for call in calls if call.startswith("deploy ")]
                self.assertEqual(2, len(deploy_calls), calls)
                self.assertNotIn("--ipfs-hash", deploy_calls[0])
                self.assertIn(f"--ipfs-hash {manifest_cid}", deploy_calls[1])
                self.assertNotIn(asset_cid, deploy_calls[1])
                self.assertEqual(1, calls.count("build"), calls)

        result, calls = self._run_subgraph_deployer(
            [rejected_states[0]] * 3, manifest_cid, asset_cid
        )
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(3, len([call for call in calls if call.startswith("deploy ")]))
        self.assertEqual(1, calls.count("build"), calls)

    def _run_subgraph_deployer(self, responses, manifest_cid, asset_cid):
        class ResponseHandler(http.server.BaseHTTPRequestHandler):
            queue = list(responses)

            def do_POST(self):
                length = int(self.headers.get("content-length", "0"))
                self.rfile.read(length)
                body = self.queue.pop(0) if self.queue else responses[-1]
                payload = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format, *_args):
                return

        bash = "bash"
        if os.name == "nt":
            bash = r"C:\Program Files\Git\bin\bash.exe"

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ResponseHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "source"
                work = root / "work"
                source.mkdir()
                (source / "package.json").write_text("{}", encoding="utf-8")
                calls_path = root / "graph-calls"
                graph_runner = root / "fake-graph-cli.sh"
                graph_runner.write_text(
                    "#!/bin/sh\n"
                    'printf "%s\\n" "$*" >> "$DOSCAN_GRAPH_CALLS"\n'
                    'if [ "$1" != "deploy" ]; then exit 0; fi\n'
                    'case " $* " in\n'
                    '  *" --ipfs-hash "*) exit 1 ;;\n'
                    "esac\n"
                    f'printf "%s\\n" "Add file to IPFS .. {asset_cid}"\n'
                    f'printf "%s\\n" "Build completed: {manifest_cid}"\n'
                    'printf "%s\\n" "HTTP error deploying the subgraph ECONNRESET"\n'
                    "exit 1\n",
                    encoding="utf-8",
                )
                graph_runner.chmod(0o755)
                npm_runner = root / "fake-npm.sh"
                npm_runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                npm_runner.chmod(0o755)
                environment = os.environ.copy()
                environment.update(
                    {
                        "DOSCAN_GRAPH_ADMIN_URL": "http://127.0.0.1:1",
                        "DOSCAN_GRAPH_QUERY_URL": (
                            f"http://127.0.0.1:{server.server_port}/graphql"
                        ),
                        "DOSCAN_GRAPH_IPFS_URL": "http://127.0.0.1:2",
                        "DOSCAN_GRAPH_CLI_RUNNER": graph_runner.as_posix(),
                        "DOSCAN_GRAPH_CALLS": calls_path.as_posix(),
                        "DOSCAN_NPM_RUNNER": npm_runner.as_posix(),
                        "DOSCAN_SUBGRAPH_SOURCE_DIR": source.as_posix(),
                        "DOSCAN_SUBGRAPH_WORK_DIR": work.as_posix(),
                        "DOSCAN_SUBGRAPH_DEPLOY_LOG": (root / "deploy.log").as_posix(),
                        "DOSCAN_SUBGRAPH_READINESS_ATTEMPTS": "1",
                        "DOSCAN_SUBGRAPH_RETRY_DELAY_SECONDS": "0",
                    }
                )
                result = subprocess.run(
                    [bash, SUBGRAPH_DEPLOY_SCRIPT.as_posix()],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=environment,
                )
                calls = (
                    calls_path.read_text(encoding="utf-8").splitlines()
                    if calls_path.exists()
                    else []
                )
                return result, calls
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_bens_runtime_config_is_readable_by_the_non_root_image_user(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('sudo rm -rf "${DEPLOY_PATH}/bens"', workflow)
        install_block = workflow.rsplit(
            'sudo rm -rf "${DEPLOY_PATH}/bens"', 1
        )[1].split('cd "${DEPLOY_PATH}"', 1)[0]

        self.assertIn('sudo chmod 0755 "${DEPLOY_PATH}/bens"', install_block)
        self.assertIn(
            'sudo chmod 0644 "${DEPLOY_PATH}/bens/config.json"', install_block
        )

    def test_account_abstraction_inputs_are_prepared_before_gcp_authentication(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        testnet_job = workflow.split("  deploy-testnet:", 1)[1].split(
            "  deploy-beta:", 1
        )[0]

        prepare_index = testnet_job.index(
            "- name: Prepare immutable Account Abstraction verification inputs"
        )
        auth_index = testnet_job.index("- name: Authenticate to Google Cloud")
        self.assertLess(prepare_index, auth_index)

    def test_caddy_validation_retries_the_pinned_image_pull(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        validation_step = workflow.split("- name: Validate Caddy configuration", 1)[
            1
        ].split("- name: Authenticate to Google Cloud", 1)[0]

        self.assertIn("pull_caddy_image()", validation_step)
        self.assertIn('docker pull "${CADDY_IMAGE}"', validation_step)
        self.assertIn("for attempt in 1 2 3", validation_step)
        self.assertIn('if [ "${attempt}" -eq 3 ]', validation_step)

    def test_rpc_retry_discards_failed_attempt_output(self):
        bash = "bash"
        if os.name == "nt":
            bash = r"C:\Program Files\Git\bin\bash.exe"

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            curl_path = directory_path / "fake-curl"
            counter_path = directory_path / "counter"
            curl_path.write_text(
                "#!/usr/bin/env bash\n"
                f'counter="{counter_path.as_posix()}"\n'
                'attempt="$(cat "${counter}" 2>/dev/null || echo 0)"\n'
                'attempt="$((attempt + 1))"\n'
                'printf "%s" "${attempt}" > "${counter}"\n'
                'if [ "${FAKE_CURL_ALWAYS_FAIL:-0}" -eq 1 ]; then\n'
                '  printf \'%s\' \'{"result":"0x"}\'\n'
                "  exit 92\n"
                "fi\n"
                'if [ "${attempt}" -eq 1 ]; then\n'
                '  printf \'%s\' \'{"result":"0x"}\'\n'
                "  exit 92\n"
                "fi\n"
                'printf \'%s\' \'{"result":"0x1234"}\'\n',
                encoding="utf-8",
            )
            curl_path.chmod(0o755)
            command = (
                f'source "{RPC_RETRY_SCRIPT.as_posix()}"; '
                f'TESTNET_RPC_CURL_BIN="{curl_path.as_posix()}"; '
                "TESTNET_RPC_RETRY_DELAY_SECONDS=0; "
                "testnet_rpc_request '{}'"
            )

            result = subprocess.run(
                [bash, "-c", command],
                capture_output=True,
                text=True,
                check=False,
            )
            failure_command = (
                f'source "{RPC_RETRY_SCRIPT.as_posix()}"; '
                f'TESTNET_RPC_CURL_BIN="{curl_path.as_posix()}"; '
                "TESTNET_RPC_RETRY_DELAY_SECONDS=0; "
                "export FAKE_CURL_ALWAYS_FAIL=1; "
                f'rm -f "{counter_path.as_posix()}"; '
                "if testnet_rpc_request '{}'; then exit 99; fi; "
                f'cat "{counter_path.as_posix()}"'
            )
            failure_result = subprocess.run(
                [bash, "-c", failure_command],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('{"result":"0x1234"}', result.stdout)
        self.assertEqual(0, failure_result.returncode, failure_result.stderr)
        self.assertEqual("3", failure_result.stdout)

    def test_testnet_package_verifier_requires_rendered_bens_config(self):
        bash = "bash"
        if os.name == "nt":
            bash = r"C:\\Program Files\\Git\\bin\\bash.exe"

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            package_root = directory_path / "package"
            bens_dir = package_root / "docker-compose" / "bens"
            bens_dir.mkdir(parents=True)
            archive_path = directory_path / "testnet-config.tgz"
            archive_argument = archive_path.as_posix()
            if os.name == "nt":
                archive_argument = f"/{archive_path.drive[0].lower()}{archive_argument[2:]}"

            subprocess.run(
                [
                    "tar",
                    "-czf",
                    str(archive_path),
                    "-C",
                    str(package_root),
                    "docker-compose",
                ],
                check=True,
            )
            missing_config = subprocess.run(
                [bash, TESTNET_PACKAGE_VERIFIER.as_posix(), archive_argument],
                capture_output=True,
                text=True,
                check=False,
            )

            (bens_dir / "config.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(
                [
                    "tar",
                    "-czf",
                    str(archive_path),
                    "-C",
                    str(package_root),
                    "docker-compose",
                ],
                check=True,
            )
            rendered_config = subprocess.run(
                [bash, TESTNET_PACKAGE_VERIFIER.as_posix(), archive_argument],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, missing_config.returncode)
        self.assertEqual(0, rendered_config.returncode, rendered_config.stderr)

    def test_docker_remove_retry_recovers_from_a_removal_race(self):
        bash = "bash"
        if os.name == "nt":
            bash = r"C:\\Program Files\\Git\\bin\\bash.exe"

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            docker_path = directory_path / "docker"
            state_path = directory_path / "container-state"
            calls_path = directory_path / "remove-calls"
            state_path.write_text("present\n", encoding="utf-8")
            docker_path.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'state="${FAKE_DOCKER_STATE:?}"\n'
                'calls="${FAKE_DOCKER_CALLS:?}"\n'
                'if [ "${FAKE_DOCKER_DAEMON_DOWN:-0}" -eq 1 ]; then\n'
                '  exit 71\n'
                "fi\n"
                'case "${1}" in\n'
                "  info)\n"
                "    if [ -f \"${calls}.inspect-error\" ]; then\n"
                "      exit 71\n"
                "    fi\n"
                "    ;;\n"
                "  inspect)\n"
                "    if [ \"${FAKE_DOCKER_INSPECT_DAEMON_ERROR:-0}\" -eq 1 ]; then\n"
                "      touch \"${calls}.inspect-error\"\n"
                "      exit 71\n"
                "    fi\n"
                "    if [ \"${FAKE_DOCKER_FINAL_INSPECT_DAEMON_ERROR:-0}\" -eq 1 ] && \\\n"
                "      [ \"$(wc -l < \"${calls}\" 2>/dev/null || echo 0)\" -ge 3 ]; then\n"
                "      touch \"${calls}.inspect-error\"\n"
                "      exit 71\n"
                "    fi\n"
                "    test -f \"${state}\"\n"
                "    ;;\n"
                "  rm)\n"
                "    printf 'remove\\n' >> \"${calls}\"\n"
                "    if [ \"${FAKE_DOCKER_FINAL_INSPECT_DAEMON_ERROR:-0}\" -eq 1 ]; then\n"
                "      exit 1\n"
                "    fi\n"
                "    if [ ! -f \"${calls}.raced\" ]; then\n"
                "      touch \"${calls}.raced\"\n"
                "      exit 1\n"
                "    fi\n"
                "    rm -f \"${state}\"\n"
                "    ;;\n"
                '  *) echo "unexpected docker command: ${1}" >&2; exit 64 ;;\n'
                "esac\n",
                encoding="utf-8",
            )
            docker_path.chmod(0o755)
            environment = os.environ | {
                "PATH": f"{directory_path}{os.pathsep}{os.environ['PATH']}",
                "FAKE_DOCKER_STATE": str(state_path),
                "FAKE_DOCKER_CALLS": str(calls_path),
                "DOCKER_REMOVE_RETRY_DELAY_SECONDS": "0",
            }
            result = subprocess.run(
                [bash, DOCKER_REMOVE_RETRY_SCRIPT.as_posix(), "container-id"],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )
            race_remove_calls = (
                calls_path.read_text().splitlines() if calls_path.exists() else []
            )
            daemon_down_result = subprocess.run(
                [bash, DOCKER_REMOVE_RETRY_SCRIPT.as_posix(), "container-id"],
                capture_output=True,
                text=True,
                check=False,
                env=environment | {"FAKE_DOCKER_DAEMON_DOWN": "1"},
            )
            inspect_daemon_error_result = subprocess.run(
                [bash, DOCKER_REMOVE_RETRY_SCRIPT.as_posix(), "container-id"],
                capture_output=True,
                text=True,
                check=False,
                env=environment | {"FAKE_DOCKER_INSPECT_DAEMON_ERROR": "1"},
            )
            inspect_error_path = Path(f"{calls_path}.inspect-error")
            calls_path.unlink(missing_ok=True)
            inspect_error_path.unlink(missing_ok=True)
            state_path.write_text("present\n", encoding="utf-8")
            final_inspect_daemon_error_result = subprocess.run(
                [bash, DOCKER_REMOVE_RETRY_SCRIPT.as_posix(), "container-id"],
                capture_output=True,
                text=True,
                check=False,
                env=environment
                | {"FAKE_DOCKER_FINAL_INSPECT_DAEMON_ERROR": "1"},
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["remove", "remove"], race_remove_calls)
        self.assertNotEqual(0, daemon_down_result.returncode)
        self.assertNotEqual(0, inspect_daemon_error_result.returncode)
        self.assertNotEqual(0, final_inspect_daemon_error_result.returncode)

    def test_deployment_fetches_an_immutable_dos_names_revision(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")

        self.assertRegex(
            workflow,
            r"DOS_NAMES_TESTNET_SUBGRAPH_REF: [0-9a-f]{40}",
        )
        self.assertIn(
            "https://github.com/DOS/DOS-Names-Contracts.git",
            workflow,
        )
        self.assertIn("merge-base --is-ancestor", workflow)
        self.assertIn("refs/remotes/origin/dos", workflow)

    def test_deployment_proves_contracts_indexing_and_real_lookup(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('method":"eth_getCode"', workflow)
        self.assertIn("hasIndexingErrors", workflow)
        self.assertIn("FINAL_DEPLOYMENT_BLOCK", workflow)
        self.assertIn("bens-smoke.dos", workflow)
        self.assertIn("SMOKE_RESOLVED_ADDRESS", workflow)
        self.assertIn(".resolved_address.hash", workflow)
        self.assertIn("/addresses/${SMOKE_RESOLVED_ADDRESS}", workflow)
        self.assertIn("/api/v2/search?q=${SMOKE_NAME}", workflow)
        self.assertIn("bens-graph-node.dump", workflow)
        self.assertIn("bens-ipfs.tgz", workflow)
        self.assertIn("Verify Testnet DOS Name UI with Playwright", workflow)

        dependency_workflow = (
            ROOT / ".github" / "workflows" / "dependency-build.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "node \"${checkout}/subgraph/dos-names/scripts/render-manifest.mjs\"",
            dependency_workflow,
        )
        self.assertIn("python scripts/render-testnet-bens.py", dependency_workflow)

    def test_remote_manifest_gate_accepts_a_valid_deployment(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        gate = workflow.split('DEPLOYMENT_JSON="${SRC}/docker-compose/bens/deployment.json"', 1)[
            1
        ].split('DEPLOYMENT_BLOCK="$(jq -er', 1)[0]
        match = re.search(r"'\"'\"'(.*?)'\"'\"'", gate, re.DOTALL)
        self.assertIsNotNone(match)
        jq_filter = match.group(1)
        deployment = {
            "chainId": 3939,
            "deploymentBlock": 120,
            "finalDeploymentBlock": 166,
            "smokeName": "bens-smoke.dos",
            "smokeResolvedAddress": "0x5555555555555555555555555555555555555555",
            "contracts": {
                "dosRegistry": "0x1111111111111111111111111111111111111111",
                "dosRegistrar": "0x2222222222222222222222222222222222222222",
                "permissionedResolverImplementation": "0x3333333333333333333333333333333333333333",
                "rootRegistry": "0x4444444444444444444444444444444444444444",
            },
        }
        command = ["jq", "-e", jq_filter]
        if shutil.which("jq") is None:
            command = ["wsl.exe", "jq", "-e", jq_filter]

        result = subprocess.run(
            command,
            input=json.dumps(deployment),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_testnet_job_runs_the_bens_validator_directly(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")
        testnet_job = workflow.split("  deploy-testnet:", 1)[1].split(
            "\n  deploy-beta:", 1
        )[0]

        self.assertIn("run: python scripts/validate-testnet-bens.py", testnet_job)

    def test_bens_password_has_one_canonical_secret_source(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("DOSCAN_BENS_DB_PASSWORD", workflow)
        self.assertIn("BENS database secrets derived from canonical password", workflow)

    def test_playwright_acceptance_spec_exists(self):
        ui_test_path = ROOT / ".github" / "scripts" / "testnet-bens-ui.spec.mjs"
        self.assertTrue(ui_test_path.is_file())

        ui_test = ui_test_path.read_text(encoding="utf-8")
        self.assertIn("timeout: 30_000", ui_test)
        self.assertIn("/name-services/domains/", ui_test)
        self.assertIn('getByText("Oops! Something went wrong")', ui_test)
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

    def test_frontend_bens_host_has_no_path_and_caddy_routes_bens_api(self):
        frontend_env = (
            ROOT / "docker-compose" / "envs" / "common-frontend-testnet.env"
        ).read_text(encoding="utf-8")
        caddy = (ROOT / "docker-compose" / "Caddyfile-gcp-testnet").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "NEXT_PUBLIC_NAME_SERVICE_API_HOST=https://test.doscan.io",
            frontend_env,
        )
        self.assertNotIn(
            "NEXT_PUBLIC_NAME_SERVICE_API_HOST=https://test.doscan.io/name-service",
            frontend_env,
        )
        self.assertIn("@bens_api path", caddy)
        self.assertIn("/api/v1/domains*", caddy)
        self.assertIn("/api/v1/addresses/*", caddy)
        self.assertIn("reverse_proxy bens:8050", caddy)

    def test_renderer_rejects_wrong_chain(self):
        renderer_path = ROOT / "scripts" / "render-testnet-bens.py"
        spec = importlib.util.spec_from_file_location("render_testnet_bens", renderer_path)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        with tempfile.TemporaryDirectory() as directory:
            deployment = Path(directory) / "deployment.json"
            deployment.write_text(
                json.dumps({"chainId": 7979, "deploymentBlock": 1, "contracts": {}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "chainId must be 3939"):
                renderer.load_deployment(deployment)

    def test_renderer_uses_dos_names_manifest_fields(self):
        renderer_path = ROOT / "scripts" / "render-testnet-bens.py"
        spec = importlib.util.spec_from_file_location("render_testnet_bens", renderer_path)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            deployment_path = directory_path / "deployment.json"
            output_path = directory_path / "config.json"
            deployment_path.write_text(
                json.dumps(
                    {
                        "chainId": 3939,
                        "deploymentBlock": 12,
                        "finalDeploymentBlock": 18,
                        "smokeName": "bens-smoke.dos",
                        "smokeResolvedAddress": "0x5555555555555555555555555555555555555555",
                        "contracts": {
                            "dosRegistry": "0x1111111111111111111111111111111111111111",
                            "dosRegistrar": "0x3333333333333333333333333333333333333333",
                            "permissionedResolverImplementation": "0x4444444444444444444444444444444444444444",
                            "rootRegistry": "0x2222222222222222222222222222222222222222",
                        },
                    }
                ),
                encoding="utf-8",
            )
            deployment = renderer.load_deployment(deployment_path)
            renderer.render_config(
                ROOT / "docker-compose" / "bens" / "config.template.json",
                output_path,
                deployment,
            )
            rendered = output_path.read_text(encoding="utf-8")
            self.assertIn("0x2222222222222222222222222222222222222222", rendered)
            self.assertNotIn("__ROOT_REGISTRY_ADDRESS__", rendered)

    def test_renderer_rejects_final_block_before_deployment(self):
        renderer_path = ROOT / "scripts" / "render-testnet-bens.py"
        spec = importlib.util.spec_from_file_location("render_testnet_bens", renderer_path)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        with tempfile.TemporaryDirectory() as directory:
            deployment = Path(directory) / "deployment.json"
            deployment.write_text(
                json.dumps(
                    {
                        "chainId": 3939,
                        "deploymentBlock": 12,
                        "finalDeploymentBlock": 11,
                        "smokeName": "bens-smoke.dos",
                        "smokeResolvedAddress": "0x5555555555555555555555555555555555555555",
                        "contracts": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "finalDeploymentBlock"):
                renderer.load_deployment(deployment)


if __name__ == "__main__":
    unittest.main()

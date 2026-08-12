import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "validate-testnet-bens.py"


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

    def test_deployment_fetches_an_immutable_dos_names_revision(self):
        workflow = (
            ROOT / ".github" / "workflows" / "deploy-config.yml"
        ).read_text(encoding="utf-8")

        self.assertRegex(
            workflow,
            r"DOS_NAMES_SUBGRAPH_REF: [0-9a-f]{40}",
        )
        self.assertIn(
            "https://github.com/DOS/DOS-Names-Contracts.git",
            workflow,
        )

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
            "cat-file -e FETCH_HEAD:contracts/deployments/dos-testnet-3939.json",
            dependency_workflow,
        )

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
        self.assertTrue(
            (ROOT / ".github" / "scripts" / "testnet-bens-ui.spec.mjs").is_file()
        )

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

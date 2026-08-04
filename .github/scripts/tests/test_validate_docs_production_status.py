import importlib.util
import tempfile
import unittest
from pathlib import Path


BACKEND_IMAGE = (
    "ghcr.io/dos/doscan:11.2.3.commit.86fd0dd5@"
    "sha256:423bab078a679d3290cc6e276774a8ed201686636933e0d066ce9859270f700d"
)
BACKEND_IMAGE_WITH_DIFFERENT_DIGEST = (
    "ghcr.io/dos/doscan:11.2.3.commit.86fd0dd5@"
    "sha256:523bab078a679d3290cc6e276774a8ed201686636933e0d066ce9859270f700d"
)
FRONTEND_IMAGE = (
    "metados/blockscout-frontend:2.10.0@"
    "sha256:4125d49b1658ba95b81075cabbc07120bebd90be95df49440aff5fa0e7e95eed"
)


class ValidateDocsProductionStatusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "validate-docs-production-status.py"
        )
        spec = importlib.util.spec_from_file_location(
            "validate_docs_production_status", script_path
        )
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary_directory.name)
        self.write_fixture_repository()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_fixture_repository(self):
        compose = """services:
  backend:
    image: {backend_image}
  frontend:
    image: {frontend_image}
"""
        for environment in ("mainnet", "testnet", "beta"):
            self.write(
                f"docker-compose/docker-compose-{environment}.yml",
                compose.format(
                    backend_image=BACKEND_IMAGE,
                    frontend_image=FRONTEND_IMAGE,
                ),
            )

        self.write(
            "docs/FEATURES.md",
            f"Backend image: `{BACKEND_IMAGE}`\nFrontend version: `2.10.0`\n",
        )
        self.write(
            "docs/CHANGELOG.md",
            f"Backend image: `{BACKEND_IMAGE}`\nFrontend version: `2.10.0`\n",
        )
        self.write(
            "docs/DOScan-ARCHITECTURE.md",
            (
                f"Backend image: `{BACKEND_IMAGE}`\n"
                f"Frontend image: `{FRONTEND_IMAGE}`\n"
                "Mainnet host: `doscan-mainnet`\n"
                "Mainnet zone: `asia-southeast1-b`\n"
                "Testnet host: `dos-testnet-r0`\n"
                "Testnet zone: `asia-southeast1-a`\n"
            ),
        )
        self.write(
            "docker-compose/envs/common-blockscout.env",
            "# MICROSERVICE_BENS_ENABLED=\n"
            "# MICROSERVICE_BENS_URL=\n"
            "# MICROSERVICE_BENS_PROTOCOLS=\n"
            "MICROSERVICE_METADATA_ENABLED=true\n",
        )
        for filename in (
            "common-frontend.env",
            "common-frontend-scan.env",
            "common-frontend-testnet.env",
            "common-frontend-beta.env",
        ):
            self.write(
                f"docker-compose/envs/{filename}",
                "# NEXT_PUBLIC_NAME_SERVICE_API_HOST=\n",
            )
        self.write(
            ".github/workflows/deploy-config.yml",
            """env:
  GCP_INSTANCE: doscan-mainnet
  GCP_ZONE: asia-southeast1-b
  GCP_TESTNET_INSTANCE: dos-testnet-r0
  GCP_TESTNET_ZONE: asia-southeast1-a
""",
        )

    def write(self, relative_path, content):
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def replace(self, relative_path, old, new):
        path = self.repo / relative_path
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def append(self, relative_path, content):
        path = self.repo / relative_path
        path.write_text(path.read_text(encoding="utf-8") + content, encoding="utf-8")

    def test_synchronized_repository_passes(self):
        self.assertEqual([], self.module.validate_repository(self.repo))

    def test_backend_digest_drift_names_the_compose_file(self):
        self.replace(
            "docker-compose/docker-compose-testnet.yml",
            BACKEND_IMAGE,
            BACKEND_IMAGE_WITH_DIFFERENT_DIGEST,
        )
        errors = self.module.validate_repository(self.repo)
        self.assertTrue(any("docker-compose-testnet.yml" in error for error in errors))
        self.assertTrue(any("backend image" in error for error in errors))

    def test_frontend_version_drift_names_the_document(self):
        self.replace("docs/FEATURES.md", "2.10.0", "2.9.0")
        errors = self.module.validate_repository(self.repo)
        self.assertTrue(any("docs/FEATURES.md" in error for error in errors))
        self.assertTrue(any("frontend version" in error for error in errors))

    def test_missing_and_invalid_sources_include_invariant_expected_and_actual(self):
        (self.repo / "docker-compose/docker-compose-beta.yml").unlink()
        invalid_frontend_image = "metados/blockscout-frontend:2.10.0"
        self.replace(
            "docker-compose/docker-compose-testnet.yml",
            FRONTEND_IMAGE,
            invalid_frontend_image,
        )

        errors = self.module.validate_repository(self.repo)

        missing_source = next(
            error for error in errors if "docker-compose-beta.yml" in error
        )
        self.assertIn("missing required file", missing_source)
        self.assertIn("expected 'present'", missing_source)
        self.assertIn("actual 'missing'", missing_source)

        invalid_pin = next(
            error
            for error in errors
            if "docker-compose-testnet.yml" in error and "frontend immutable image pin" in error
        )
        self.assertIn("expected 'tag@sha256:<64 lowercase hexadecimal characters>'", invalid_pin)
        self.assertIn(f"actual '{invalid_frontend_image}'", invalid_pin)

    def test_metadata_must_remain_enabled(self):
        self.replace(
            "docker-compose/envs/common-blockscout.env",
            "MICROSERVICE_METADATA_ENABLED=true",
            "MICROSERVICE_METADATA_ENABLED=false",
        )
        errors = self.module.validate_repository(self.repo)
        self.assertTrue(any("metadata enabled" in error for error in errors))

    def test_bens_configuration_is_rejected(self):
        self.append(
            "docker-compose/envs/common-blockscout.env",
            "MICROSERVICE_BENS_ENABLED=true\n",
        )
        errors = self.module.validate_repository(self.repo)
        self.assertTrue(any("BENS disabled" in error for error in errors))

    def test_explicitly_disabled_bens_is_allowed(self):
        self.append(
            "docker-compose/envs/common-blockscout.env",
            "MICROSERVICE_BENS_ENABLED=false\n",
        )

        self.assertEqual([], self.module.validate_repository(self.repo))

    def test_inline_comment_bens_enablement_is_rejected(self):
        self.append(
            "docker-compose/envs/common-blockscout.env",
            "MICROSERVICE_BENS_ENABLED=true # active deployment comment\n",
        )

        errors = self.module.validate_repository(self.repo)

        self.assertTrue(any("BENS disabled" in error for error in errors))

    def test_missing_required_frontend_env_files_are_diagnosed(self):
        frontend_env_files = (
            "common-frontend.env",
            "common-frontend-scan.env",
            "common-frontend-testnet.env",
            "common-frontend-beta.env",
        )
        for filename in frontend_env_files:
            (self.repo / "docker-compose/envs" / filename).unlink()

        errors = self.module.validate_repository(self.repo)

        self.assertEqual(4, sum("missing required file" in error for error in errors))
        for filename in frontend_env_files:
            self.assertTrue(any(filename in error for error in errors))

    def test_active_bens_values_and_frontend_name_service_host_are_rejected(self):
        self.append(
            "docker-compose/envs/common-blockscout.env",
            "MICROSERVICE_BENS_URL=https://bens.example\n"
            "MICROSERVICE_BENS_PROTOCOLS=dos\n",
        )
        self.append(
            "docker-compose/envs/common-frontend-testnet.env",
            "NEXT_PUBLIC_NAME_SERVICE_API_HOST=https://bens.example\n",
        )

        errors = self.module.validate_repository(self.repo)

        self.assertTrue(any("MICROSERVICE_BENS_URL" in error for error in errors))
        self.assertTrue(any("MICROSERVICE_BENS_PROTOCOLS" in error for error in errors))
        self.assertTrue(
            any("NEXT_PUBLIC_NAME_SERVICE_API_HOST" in error for error in errors)
        )

    def test_gcp_topology_drift_names_the_architecture_document(self):
        self.replace("docs/DOScan-ARCHITECTURE.md", "dos-testnet-r0", "stale-host")
        errors = self.module.validate_repository(self.repo)
        self.assertTrue(any("GCP_TESTNET_INSTANCE" in error for error in errors))

    def test_missing_sources_and_multiple_drifts_are_aggregated(self):
        (self.repo / "docker-compose/docker-compose-beta.yml").unlink()
        self.replace("docs/FEATURES.md", "2.10.0", "2.9.0")
        errors = self.module.validate_repository(self.repo)
        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("missing required file" in error for error in errors))
        self.assertTrue(any("frontend version" in error for error in errors))

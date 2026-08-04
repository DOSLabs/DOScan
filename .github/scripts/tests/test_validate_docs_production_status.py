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
            ),
        )

    def write(self, relative_path, content):
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def replace(self, relative_path, old, new):
        path = self.repo / relative_path
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

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

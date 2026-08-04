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
BACKEND_RUNTIME_VERSION = "v11.2.3.+commit.86fd0dd5"
FRONTEND_IMAGE = (
    "metados/blockscout-frontend:2.10.0@"
    "sha256:4125d49b1658ba95b81075cabbc07120bebd90be95df49440aff5fa0e7e95eed"
)
STALE_FRONTEND_IMAGE = (
    "metados/blockscout-frontend:2.9.0@"
    "sha256:6125d49b1658ba95b81075cabbc07120bebd90be95df49440aff5fa0e7e95eed"
)
VALIDATOR_COMMAND = "python .github/scripts/validate-docs-production-status.py"
REQUIRED_PUSH_PATHS = (
    "docker-compose/docker-compose-mainnet.yml",
    "docker-compose/docker-compose-testnet.yml",
    "docker-compose/docker-compose-beta.yml",
    "docker-compose/envs/common-blockscout.env",
    "docker-compose/envs/common-blockscout-mainnet.env",
    "docker-compose/envs/common-blockscout-testnet.env",
    "docker-compose/envs/common-blockscout-beta.env",
    "docker-compose/envs/common-frontend*.env",
    "docs/FEATURES.md",
    "docs/CHANGELOG.md",
    "docs/DOScan-ARCHITECTURE.md",
    ".github/workflows/deploy-config.yml",
    ".github/workflows/dependency-build.yml",
    ".github/scripts/validate-docs-production-status.py",
    ".github/scripts/tests/**",
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
    env_file:
      - ./envs/common-blockscout.env
      - ${{DOSCAN_BLOCKSCOUT_SECRETS_ENV:-/run/secrets/blockscout.env}}
      - ./envs/common-blockscout-{environment}.env
    environment:
      MICROSERVICE_METADATA_ENABLED: "true"
      MICROSERVICE_BENS_ENABLED: "false"
      MICROSERVICE_BENS_URL: ""
      MICROSERVICE_BENS_PROTOCOLS: ""
  frontend:
    image: {frontend_image}
"""
        for environment in ("mainnet", "testnet", "beta"):
            self.write(
                f"docker-compose/docker-compose-{environment}.yml",
                compose.format(
                    backend_image=BACKEND_IMAGE,
                    frontend_image=FRONTEND_IMAGE,
                    environment=environment,
                ),
            )
            self.write(
                f"docker-compose/envs/common-blockscout-{environment}.env",
                f"# {environment} overrides do not redefine protected keys.\n",
            )

        self.write(
            "docs/FEATURES.md",
            f"""# DOScan Feature Status

## Runtime Baseline

| Environment | Explorer | Chain ID | Frontend | Backend | Runtime status |
|---|---|---:|---|---|---|
| Mainnet | `https://doscan.io` | 7979 | `2.10.0` | `{BACKEND_RUNTIME_VERSION}` | healthy |
| Testnet | `https://test.doscan.io` | 3939 | `2.10.0` | `{BACKEND_RUNTIME_VERSION}` | healthy |

Both production environments pin the custom backend image below:

```text
{BACKEND_IMAGE}
```

## Backend Features

### Backend Integrations and Services

| Service or integration | Mainnet | Testnet | Runtime path |
|---|---|---|---|
| Metadata Service | Enabled | Enabled | `/metadata-api` |

## Deliberately Disabled or Blocked Features

| Feature | Status | Reason or prerequisite |
|---|---|---|
| BENS / name service | Disabled | Not configured for DOS Chain |
""",
        )
        self.write(
            "docs/CHANGELOG.md",
            f"""# DOScan Changelog

## [2026-08-04] - Production Documentation and Runtime Baseline

### Deployed

- Mainnet and Testnet run Frontend `2.10.0` and custom Backend `{BACKEND_RUNTIME_VERSION}` on GCP.
- Both production Compose files pin `{BACKEND_IMAGE}`.

### Changed

- Corrected feature status: the admin panel and BENS are disabled, while Metadata Service is enabled.

---

## [2026-02-01] - Historical Release

- Historical content is not the current production baseline.
""",
        )
        self.write(
            "docs/DOScan-ARCHITECTURE.md",
            f"""# DOScan Architecture

## Deployed Environments

| Environment | Public origin | Chain ID | GCP host | Zone | Deployment path |
|---|---|---:|---|---|---|
| Mainnet | `https://doscan.io` | 7979 | `doscan-mainnet` | `asia-southeast1-b` | `/opt/doscan-l1` |
| Testnet | `https://test.doscan.io` | 3939 | `dos-testnet-r0` | `asia-southeast1-a` | `/opt/doscan-testnet` |
| Beta | `https://beta.doscan.io` | 7979 | `doscan-mainnet` | `asia-southeast1-b` | `/opt/doscan-beta` |

## Runtime Versions

| Component | Production version |
|---|---|
| Frontend | `{FRONTEND_IMAGE}` |
| Backend | `{BACKEND_IMAGE}` |

## Backend Integrations

### Metadata Service

The backend enables Blockscout Metadata Service:

```env
MICROSERVICE_METADATA_ENABLED=true
```

BENS is not configured. Name-service UI and backend integration remain disabled.

## Historical Notes

Historical records are outside the current status sections.
""",
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

jobs:
  deploy:
    steps:
      - run: echo deploy
""",
        )
        push_paths = "\n".join(f'      - "{path}"' for path in REQUIRED_PUSH_PATHS)
        self.write(
            ".github/workflows/dependency-build.yml",
            f"""name: Dependency build

on:
  pull_request:
  push:
    branches: [main]
    paths:
{push_paths}

jobs:
  workflow-scripts:
    runs-on: ubuntu-latest
    steps:
      - name: Validate production documentation status
        run: {VALIDATOR_COMMAND}
""",
        )

    def write(self, relative_path, content):
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def replace(self, relative_path, old, new):
        path = self.repo / relative_path
        original = path.read_text(encoding="utf-8")
        self.assertIn(old, original, f"fixture mutation target missing: {old!r}")
        path.write_text(original.replace(old, new), encoding="utf-8")

    def append(self, relative_path, content):
        path = self.repo / relative_path
        path.write_text(path.read_text(encoding="utf-8") + content, encoding="utf-8")

    def assert_diagnostic(self, errors, path, invariant, actual=None):
        matches = [
            error
            for error in errors
            if path in error and invariant in error and "expected" in error and "actual" in error
        ]
        self.assertTrue(matches, "\n".join(errors))
        if actual is not None:
            self.assertTrue(any(actual in error for error in matches), "\n".join(matches))

    def test_synchronized_repository_passes(self):
        self.assertEqual([], self.module.validate_repository(self.repo))

    def test_repository_workflow_keeps_the_validator_bootstrapped(self):
        repository_root = Path(__file__).resolve().parents[3]
        workflow_path = repository_root / ".github/workflows/dependency-build.yml"

        self.assertEqual(
            [],
            self.module.dependency_workflow_errors(
                workflow_path.read_text(encoding="utf-8"),
                Path(".github/workflows/dependency-build.yml"),
            ),
        )

    def test_backend_digest_drift_names_the_compose_file(self):
        self.replace(
            "docker-compose/docker-compose-testnet.yml",
            BACKEND_IMAGE,
            BACKEND_IMAGE_WITH_DIFFERENT_DIGEST,
        )
        errors = self.module.validate_repository(self.repo)
        self.assert_diagnostic(
            errors, "docker-compose-testnet.yml", "backend image", BACKEND_IMAGE_WITH_DIFFERENT_DIGEST
        )

    def test_invalid_and_missing_sources_have_complete_aggregated_diagnostics(self):
        (self.repo / "docker-compose/docker-compose-beta.yml").unlink()
        invalid_frontend_image = "metados/blockscout-frontend:2.10.0"
        self.replace(
            "docker-compose/docker-compose-testnet.yml",
            FRONTEND_IMAGE,
            invalid_frontend_image,
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(errors, "docker-compose-beta.yml", "missing required file", "missing")
        self.assert_diagnostic(
            errors,
            "docker-compose-testnet.yml",
            "frontend immutable image pin",
            invalid_frontend_image,
        )

    def test_common_metadata_and_bens_source_invariants(self):
        self.replace(
            "docker-compose/envs/common-blockscout.env",
            "MICROSERVICE_METADATA_ENABLED=true",
            "MICROSERVICE_METADATA_ENABLED=false\nMICROSERVICE_BENS_ENABLED=true",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(errors, "common-blockscout.env", "metadata enabled", "false")
        self.assert_diagnostic(errors, "common-blockscout.env", "BENS disabled", "true")

    def test_env_parser_accepts_whitespace_quotes_and_comments_outside_quotes(self):
        self.write(
            "docker-compose/envs/common-blockscout.env",
            " MICROSERVICE_METADATA_ENABLED = \"true\" # required\n"
            "MICROSERVICE_BENS_ENABLED = 'false' # deliberately disabled\n"
            "MICROSERVICE_BENS_URL = \"\" # no endpoint\n"
            "MICROSERVICE_BENS_PROTOCOLS = '' # no protocols\n",
        )

        self.assertEqual([], self.module.validate_repository(self.repo))

    def test_frontend_name_service_host_is_rejected(self):
        self.append(
            "docker-compose/envs/common-frontend-testnet.env",
            "NEXT_PUBLIC_NAME_SERVICE_API_HOST=https://bens.example\n",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors,
            "common-frontend-testnet.env",
            "NEXT_PUBLIC_NAME_SERVICE_API_HOST disabled",
            "https://bens.example",
        )

    def test_document_status_mutations_report_the_parsed_current_value(self):
        cases = (
            (
                "docs/FEATURES.md",
                "| Metadata Service | Enabled | Enabled | `/metadata-api` |",
                "| Metadata Service | Disabled | Enabled | `/metadata-api` |",
                "metadata documentation status",
                "Mainnet=Disabled, Testnet=Enabled",
            ),
            (
                "docs/FEATURES.md",
                "| BENS / name service | Disabled | Not configured for DOS Chain |",
                "| BENS / name service | Enabled | Not configured for DOS Chain |",
                "BENS documentation status",
                "Enabled",
            ),
            (
                "docs/CHANGELOG.md",
                "while Metadata Service is enabled.",
                "while Metadata Service is disabled.",
                "metadata documentation status",
                "Disabled",
            ),
            (
                "docs/CHANGELOG.md",
                "BENS are disabled, while",
                "BENS are enabled, while",
                "BENS documentation status",
                "Enabled",
            ),
            (
                "docs/DOScan-ARCHITECTURE.md",
                "MICROSERVICE_METADATA_ENABLED=true",
                "MICROSERVICE_METADATA_ENABLED=false",
                "metadata documentation status",
                "false",
            ),
            (
                "docs/DOScan-ARCHITECTURE.md",
                "BENS is not configured.",
                "BENS is configured.",
                "BENS documentation status",
                "Configured",
            ),
        )
        for path, old, new, invariant, actual in cases:
            with self.subTest(path=path, invariant=invariant):
                self.replace(path, old, new)
                errors = self.module.validate_repository(self.repo)
                self.assert_diagnostic(errors, path, invariant, actual)
                self.replace(path, new, old)

    def test_features_current_frontend_version_uses_exact_table_fields(self):
        self.replace("docs/FEATURES.md", "| `2.10.0` |", "| `2.10.01` |")
        self.append("docs/FEATURES.md", "\nHistorical note: Frontend `2.10.0`.\n")

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, "docs/FEATURES.md", "frontend version", "2.10.01"
        )

    def test_features_current_backend_pin_is_not_hidden_by_history(self):
        self.replace(
            "docs/FEATURES.md",
            f"```text\n{BACKEND_IMAGE}\n```",
            f"```text\n{BACKEND_IMAGE_WITH_DIFFERENT_DIGEST}\n```",
        )
        self.append("docs/FEATURES.md", f"\nHistorical pin: `{BACKEND_IMAGE}`.\n")

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, "docs/FEATURES.md", "backend image", BACKEND_IMAGE_WITH_DIFFERENT_DIGEST
        )

    def test_changelog_current_release_is_not_hidden_by_history(self):
        self.replace(
            "docs/CHANGELOG.md",
            "run Frontend `2.10.0`",
            "run Frontend `2.9.0`",
        )
        self.append("docs/CHANGELOG.md", "\nHistorical note: Frontend `2.10.0`.\n")

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(errors, "docs/CHANGELOG.md", "frontend version", "2.9.0")

    def test_architecture_runtime_pin_is_not_hidden_by_history(self):
        self.replace("docs/DOScan-ARCHITECTURE.md", FRONTEND_IMAGE, STALE_FRONTEND_IMAGE)
        self.append(
            "docs/DOScan-ARCHITECTURE.md",
            f"\nHistorical frontend pin: `{FRONTEND_IMAGE}`.\n",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, "docs/DOScan-ARCHITECTURE.md", "frontend image", STALE_FRONTEND_IMAGE
        )

    def test_architecture_gcp_fields_are_not_hidden_by_history(self):
        self.replace(
            "docs/DOScan-ARCHITECTURE.md",
            "| Testnet | `https://test.doscan.io` | 3939 | `dos-testnet-r0` |",
            "| Testnet | `https://test.doscan.io` | 3939 | `stale-host` |",
        )
        self.append(
            "docs/DOScan-ARCHITECTURE.md",
            "\nHistorical host: `dos-testnet-r0`.\n",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, "docs/DOScan-ARCHITECTURE.md", "GCP_TESTNET_INSTANCE", "stale-host"
        )

    def test_each_backend_overlay_rejects_a_protected_override(self):
        cases = (
            ("mainnet", "MICROSERVICE_METADATA_ENABLED=false", "metadata enabled", "false"),
            ("testnet", "MICROSERVICE_BENS_ENABLED=true", "BENS disabled", "true"),
            (
                "beta",
                "MICROSERVICE_BENS_URL=https://bens.example",
                "BENS disabled",
                "https://bens.example",
            ),
        )
        for environment, assignment, invariant, actual in cases:
            with self.subTest(environment=environment):
                path = f"docker-compose/envs/common-blockscout-{environment}.env"
                self.write(path, f"{assignment}\n")
                errors = self.module.validate_repository(self.repo)
                self.assert_diagnostic(errors, path, invariant, actual)
                self.write(path, f"# {environment} overrides restored.\n")

    def test_backend_inline_protected_overrides_are_rejected(self):
        cases = (
            (
                "mainnet",
                'MICROSERVICE_METADATA_ENABLED: "true"',
                'MICROSERVICE_METADATA_ENABLED: "false"',
                "metadata enabled",
                "false",
            ),
            (
                "testnet",
                'MICROSERVICE_BENS_ENABLED: "false"',
                'MICROSERVICE_BENS_ENABLED: "true"',
                "BENS disabled",
                "true",
            ),
            (
                "beta",
                'MICROSERVICE_BENS_PROTOCOLS: ""',
                'MICROSERVICE_BENS_PROTOCOLS: "dos"',
                "BENS disabled",
                "dos",
            ),
        )
        for environment, old, new, invariant, actual in cases:
            with self.subTest(environment=environment):
                path = f"docker-compose/docker-compose-{environment}.yml"
                self.replace(path, old, new)
                errors = self.module.validate_repository(self.repo)
                self.assert_diagnostic(errors, path, invariant, actual)
                self.replace(path, new, old)

    def test_unresolved_secret_env_source_requires_all_inline_protected_locks(self):
        self.replace(
            "docker-compose/docker-compose-beta.yml",
            '      MICROSERVICE_BENS_PROTOCOLS: ""\n',
            "",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors,
            "docker-compose-beta.yml",
            "unresolved env source protection",
            "MICROSERVICE_BENS_PROTOCOLS",
        )

    def test_nested_workflow_env_cannot_overwrite_top_level_gcp_value(self):
        self.replace(
            ".github/workflows/deploy-config.yml",
            "  GCP_TESTNET_INSTANCE: dos-testnet-r0",
            "  GCP_TESTNET_INSTANCE: stale-host",
        )
        self.append(
            ".github/workflows/deploy-config.yml",
            """
  nested-env-probe:
    env:
      GCP_TESTNET_INSTANCE: dos-testnet-r0
    steps:
      - run: echo nested
""",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, "docs/DOScan-ARCHITECTURE.md", "GCP_TESTNET_INSTANCE", "stale-host"
        )

    def test_compose_extension_before_services_cannot_supply_runtime_image(self):
        path = "docker-compose/docker-compose-testnet.yml"
        compose = (self.repo / path).read_text(encoding="utf-8")
        self.write(
            path,
            """x-image-template:
  backend:
    image: {historical_image}
""".format(historical_image=BACKEND_IMAGE)
            + compose.replace(BACKEND_IMAGE, BACKEND_IMAGE_WITH_DIFFERENT_DIGEST),
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, path, "backend image", BACKEND_IMAGE_WITH_DIFFERENT_DIGEST
        )

    def test_duplicate_top_level_yaml_mappings_are_rejected(self):
        self.append(
            "docker-compose/docker-compose-testnet.yml",
            f"""
services:
  backend:
    image: {BACKEND_IMAGE}
""",
        )
        self.append(
            ".github/workflows/deploy-config.yml",
            """
env:
  GCP_INSTANCE: doscan-mainnet
""",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, "docker-compose-testnet.yml", "Compose structure", "duplicate"
        )
        self.assert_diagnostic(
            errors, ".github/workflows/deploy-config.yml", "workflow structure", "duplicate"
        )

    def test_unsupported_inline_environment_structure_fails_closed(self):
        self.replace(
            "docker-compose/docker-compose-beta.yml",
            "    environment:\n"
            '      MICROSERVICE_METADATA_ENABLED: "true"\n'
            '      MICROSERVICE_BENS_ENABLED: "false"\n'
            '      MICROSERVICE_BENS_URL: ""\n'
            '      MICROSERVICE_BENS_PROTOCOLS: ""',
            "    environment: {MICROSERVICE_METADATA_ENABLED: true}",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors, "docker-compose-beta.yml", "Compose structure", "unsupported"
        )

    def test_commented_validator_command_is_not_an_active_workflow_step(self):
        self.replace(
            ".github/workflows/dependency-build.yml",
            f"        run: {VALIDATOR_COMMAND}",
            f"        # run: {VALIDATOR_COMMAND}",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors,
            ".github/workflows/dependency-build.yml",
            "active validator run step",
            "missing",
        )

    def test_dependency_workflow_requires_the_complete_push_path_set(self):
        missing_path = "docker-compose/envs/common-blockscout-beta.env"
        self.replace(
            ".github/workflows/dependency-build.yml",
            f'      - "{missing_path}"\n',
            "",
        )

        errors = self.module.validate_repository(self.repo)

        self.assert_diagnostic(
            errors,
            ".github/workflows/dependency-build.yml",
            "required push paths",
            missing_path,
        )

    def test_yaml_block_scalars_may_contain_multiline_shell_quotes(self):
        self.replace(
            ".github/workflows/dependency-build.yml",
            f"        run: {VALIDATOR_COMMAND}",
            "        run: |\n"
            "          value=\"$(\n"
            f"          {VALIDATOR_COMMAND}\n"
            "          )\"",
        )

        self.assertEqual([], self.module.validate_repository(self.repo))


if __name__ == "__main__":
    unittest.main()

# Production Status Documentation Drift Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline CI validator that rejects production documentation when its critical deployment status disagrees with Compose, environment, or deployment workflow configuration.

**Architecture:** A Python standard-library script reads three Compose files, the active backend and frontend environment files, and the deployment workflow. It derives immutable image pins, required Metadata and BENS states, and GCP topology, then checks the three Markdown production status documents and returns every detected error in one run.

**Tech Stack:** Python 3, `unittest`, GitHub Actions YAML, Markdown source documents.

## Global Constraints

- Treat Compose, environment files, and `.github/workflows/deploy-config.yml` as canonical.
- Validate only critical production invariants: Backend and Frontend pins, Metadata enabled, BENS disabled, and Mainnet/Testnet GCP topology.
- Validate Mainnet, Testnet, and Beta image equality.
- Use only the Python standard library and make no network requests.
- Aggregate diagnostics with file, invariant, expected value, and actual value.
- Keep the Blockscout v11.2.4 upgrade outside this change.
- Preserve all existing deployment and environment validation behavior.

---

### Task 1: Parse canonical deployment state and validate immutable image pins

**Files:**
- Create: `.github/scripts/validate-docs-production-status.py`
- Create: `.github/scripts/tests/test_validate_docs_production_status.py`

**Interfaces:**
- Consumes: A repository root as `pathlib.Path`.
- Produces: `validate_repository(root: Path) -> list[str]` and `main() -> int`.
- Produces: Helper functions `read_required`, `read_env`, `extract_service_image`, `parse_immutable_image`, and `backend_runtime_version`.

- [ ] **Step 1: Write baseline and image drift tests**

Create a temporary repository fixture containing minimal Mainnet, Testnet, and Beta Compose files. Each file must define the same immutable Backend and Frontend images. Create synchronized Markdown fixtures and assert:

```python
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
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```text
python -m unittest .github/scripts/tests/test_validate_docs_production_status.py -v
```

Expected: import or attribute failure because the validator does not exist yet.

- [ ] **Step 3: Implement minimal source and image validation**

Implement these exact public interfaces:

```python
def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    # Read required files, derive canonical state, and append all mismatches.
    return errors

def main() -> int:
    errors = validate_repository(ROOT)
    if errors:
        print("Production documentation drift validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Production documentation drift validation passed.")
    return 0
```

Parse each Compose file by locating the requested service block and its `image:` key. Accept an immutable image only when it matches:

```python
IMMUTABLE_IMAGE_RE = re.compile(
    r"^(?P<repository>[^\s:@]+(?:/[^\s:@]+)*):"
    r"(?P<tag>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})$"
)
```

Require the same Backend image and the same Frontend image in all three Compose files. Require the full Backend pin in all three production status documents, the Frontend tag version in all three documents, and the full Frontend pin in `docs/DOScan-ARCHITECTURE.md`.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```text
python -m unittest .github/scripts/tests/test_validate_docs_production_status.py -v
```

Expected: baseline and image drift tests pass.

- [ ] **Step 5: Commit the image invariant slice**

```text
git add .github/scripts/validate-docs-production-status.py .github/scripts/tests/test_validate_docs_production_status.py
git commit -m "ci: validate production image documentation"
```

---

### Task 2: Validate Metadata, BENS, GCP topology, and aggregated diagnostics

**Files:**
- Modify: `.github/scripts/validate-docs-production-status.py`
- Modify: `.github/scripts/tests/test_validate_docs_production_status.py`

**Interfaces:**
- Consumes: `validate_repository(root: Path) -> list[str]` from Task 1.
- Produces: `read_env(path: Path) -> dict[str, str]`, `read_workflow_env(text: str, keys: tuple[str, ...]) -> dict[str, str]`, and formatted diagnostic strings.

- [ ] **Step 1: Add failing state and error aggregation tests**

Add these behaviors to the temporary fixture suite:

```python
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
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```text
python -m unittest .github/scripts/tests/test_validate_docs_production_status.py -v
```

Expected: the new Metadata, BENS, topology, and aggregation assertions fail.

- [ ] **Step 3: Implement the remaining critical invariants**

Read active env assignments while ignoring blank and commented lines. Require `MICROSERVICE_METADATA_ENABLED=true`. Reject an active BENS enablement, URL, or protocols value, and reject active `NEXT_PUBLIC_NAME_SERVICE_API_HOST` in every `common-frontend*.env` file.

Read these exact workflow variables:

```python
GCP_KEYS = (
    "GCP_INSTANCE",
    "GCP_ZONE",
    "GCP_TESTNET_INSTANCE",
    "GCP_TESTNET_ZONE",
)
```

Require every derived value in `docs/DOScan-ARCHITECTURE.md`. Format every mismatch through one helper:

```python
def diagnostic(path: Path, invariant: str, expected: object, actual: object) -> str:
    return (
        f"{path.as_posix()}: {invariant}; "
        f"expected {expected!r}; actual {actual!r}"
    )
```

When a file is missing, append a diagnostic and continue validating every source that remains readable.

- [ ] **Step 4: Run focused and existing script tests**

Run:

```text
python -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
python .github/scripts/validate-docs-production-status.py
python scripts/validate-blockscout-env-parity.py
```

Expected: all unit tests pass, the documentation validator passes on the real repository, and env parity passes.

- [ ] **Step 5: Commit the state invariant slice**

```text
git add .github/scripts/validate-docs-production-status.py .github/scripts/tests/test_validate_docs_production_status.py
git commit -m "ci: guard production status invariants"
```

---

### Task 3: Wire the guard into Dependency build and verify the complete change

**Files:**
- Modify: `.github/workflows/dependency-build.yml`

**Interfaces:**
- Consumes: `.github/scripts/validate-docs-production-status.py` from Tasks 1 and 2.
- Produces: A PR and path-filtered `main` push CI gate.

- [ ] **Step 1: Add a failing workflow source assertion**

Add a unit test that reads `.github/workflows/dependency-build.yml` from a supplied fixture root and requires the command:

```text
python .github/scripts/validate-docs-production-status.py
```

Expected before workflow modification: FAIL because the command is absent.

- [ ] **Step 2: Run the workflow assertion and verify RED**

Run:

```text
python -m unittest .github/scripts/tests/test_validate_docs_production_status.py -v
```

Expected: only the workflow integration assertion fails.

- [ ] **Step 3: Add the CI command and push path coverage**

In `workflow-scripts`, add:

```yaml
      - name: Validate production documentation status
        run: python .github/scripts/validate-docs-production-status.py
```

Add these push paths without changing the Elixir build change detector:

```yaml
      - "docker-compose/docker-compose-mainnet.yml"
      - "docker-compose/docker-compose-testnet.yml"
      - "docker-compose/docker-compose-beta.yml"
      - "docker-compose/envs/common-blockscout.env"
      - "docker-compose/envs/common-frontend*.env"
      - "docs/FEATURES.md"
      - "docs/CHANGELOG.md"
      - "docs/DOScan-ARCHITECTURE.md"
      - ".github/workflows/deploy-config.yml"
      - ".github/scripts/validate-docs-production-status.py"
```

- [ ] **Step 4: Run full local verification**

Run:

```text
python -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
python .github/scripts/validate-docs-production-status.py
python scripts/validate-blockscout-env-parity.py
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 5: Commit workflow integration**

```text
git add .github/workflows/dependency-build.yml .github/scripts/tests/test_validate_docs_production_status.py
git commit -m "ci: run production documentation drift guard"
```

- [ ] **Step 6: Review and publish**

Request an independent code review, fix all Critical and Important findings, rerun the complete verification set, push the branch, open a PR, wait for required CI, and merge only after review and CI are green.

---

## Execution Mode

JOY authorized implementation without an execution choice. Use inline execution with `superpowers:executing-plans`, preserving TDD evidence at every RED and GREEN boundary.

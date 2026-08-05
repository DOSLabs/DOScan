# Publish Cache Export Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep a successful production image publish successful when the optional GHCR registry cache export fails.

**Architecture:** Preserve the existing combined BuildKit image push and cache export step. Configure only the registry cache exporter to ignore export errors, while keeping image build and registry push failures fatal. Add a repository test that parses the real workflow step and a trigger-path test that keeps the guard active when the publish workflow changes.

**Tech Stack:** GitHub Actions YAML, Docker Buildx, Python `unittest`, `actionlint`

## Global Constraints

- Keep `push: true`; image build and image push failures must remain fatal.
- Add `ignore-error=true` only to the `cache-to` registry exporter for the combined indexer and API image.
- Preserve the existing cache reference `ghcr.io/dos/doscan:buildcache` and `mode=max`.
- Ensure Dependency build runs when `.github/workflows/publish-regular-docker-image-on-demand.yml` changes.
- Use English for repository artifacts and avoid Unicode dash characters.

---

### Task 1: Make registry cache export best effort

**Files:**
- Create: `.github/scripts/tests/test_publish_workflow.py`
- Modify: `.github/workflows/publish-regular-docker-image-on-demand.yml:60-69`
- Modify: `.github/workflows/dependency-build.yml:28-33`

**Interfaces:**
- Consumes: The existing `docker/build-push-action` step named `Build and push Docker image (indexer + API)`.
- Produces: A best-effort registry cache export that cannot mask a successful image push, plus CI coverage for the policy and trigger path.

- [ ] **Step 1: Write the failing tests**

Create a `unittest` module that reads the real workflows, isolates the named build step, parses its `with` mapping, and verifies these observable configuration contracts:

```python
self.assertEqual(build_inputs["push"], "true")
self.assertEqual(cache_options["type"], "registry")
self.assertEqual(cache_options["ref"], "ghcr.io/dos/doscan:buildcache")
self.assertEqual(cache_options["mode"], "max")
self.assertEqual(cache_options["ignore-error"], "true")
```

Add a separate test that verifies Dependency build includes this exact push path:

```python
self.assertIn(
    '      - ".github/workflows/publish-regular-docker-image-on-demand.yml"',
    dependency_workflow.splitlines(),
)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m unittest .github/scripts/tests/test_publish_workflow.py -v
```

Expected: two assertion failures, one for missing `ignore-error` and one for the missing Dependency build push path.

- [ ] **Step 3: Implement the minimal workflow changes**

Change the cache exporter to:

```yaml
cache-to: type=registry,ref=ghcr.io/dos/doscan:buildcache,mode=max,ignore-error=true
```

Add this path to Dependency build push paths:

```yaml
- ".github/workflows/publish-regular-docker-image-on-demand.yml"
```

- [ ] **Step 4: Verify GREEN and workflow syntax**

Run:

```powershell
python -m unittest .github/scripts/tests/test_publish_workflow.py -v
python -m unittest discover -s .github/scripts/tests -p 'test_*.py' -v
actionlint .github/workflows/publish-regular-docker-image-on-demand.yml .github/workflows/dependency-build.yml
git diff --check
```

Expected: focused tests pass, full suite passes with 0 failures, `actionlint` exits 0, and `git diff --check` exits 0.

- [ ] **Step 5: Commit**

```powershell
git add .github/scripts/tests/test_publish_workflow.py .github/workflows/publish-regular-docker-image-on-demand.yml .github/workflows/dependency-build.yml docs/superpowers/plans/2026-08-05-publish-cache-export-resilience.md
git commit -m "ci: tolerate registry cache export failures"
```

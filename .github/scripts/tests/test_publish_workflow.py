import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PUBLISH_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/publish-regular-docker-image-on-demand.yml"
DEPENDENCY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/dependency-build.yml"
BUILD_STEP_NAME = "Build and push Docker image (indexer + API)"


def build_step_inputs(workflow: str) -> dict[str, str]:
    step_start = workflow.index(f"- name: {BUILD_STEP_NAME}")
    step = workflow[step_start:].split("\n      - name:", 1)[0]
    with_mapping = step.split("\n        with:\n", 1)[1]

    return {
        key.strip(): value.strip()
        for line in with_mapping.splitlines()
        if line.startswith("          ") and ": " in line
        for key, value in [line.strip().split(": ", 1)]
    }


def parse_cache_options(cache_to: str) -> dict[str, str]:
    return dict(option.split("=", 1) for option in cache_to.split(","))


class PublishWorkflowTests(unittest.TestCase):
    def test_registry_cache_export_does_not_fail_the_image_push(self) -> None:
        build_inputs = build_step_inputs(PUBLISH_WORKFLOW.read_text(encoding="utf-8"))
        cache_options = parse_cache_options(build_inputs["cache-to"])

        self.assertEqual(build_inputs["push"], "true")
        self.assertEqual(cache_options["type"], "registry")
        self.assertEqual(cache_options["ref"], "ghcr.io/dos/doscan:buildcache")
        self.assertEqual(cache_options["mode"], "max")
        self.assertIn("ignore-error", cache_options)
        self.assertEqual(cache_options["ignore-error"], "true")

    def test_dependency_build_runs_for_the_publish_workflow(self) -> None:
        dependency_workflow = DEPENDENCY_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            '      - ".github/workflows/publish-regular-docker-image-on-demand.yml"',
            dependency_workflow.splitlines(),
        )


if __name__ == "__main__":
    unittest.main()

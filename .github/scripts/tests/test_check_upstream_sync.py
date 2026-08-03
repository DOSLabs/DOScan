import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "check-upstream-sync.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_upstream_sync", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GitRepository:
    def __init__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name)
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "test@example.com")

    def close(self):
        self.temp_dir.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit_file(self, content, message):
        (self.path / "release.txt").write_text(content, encoding="utf-8")
        self.git("add", "release.txt")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")


class CheckUpstreamSyncTests(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepository()
        self.module = load_module()

    def tearDown(self):
        self.repo.close()

    def test_missing_marker_requires_sync(self):
        target = self.repo.commit_file("release", "upstream release")
        self.repo.git("tag", "v1.2.3", target)

        result = self.module.determine_sync_state(
            self.repo.path, "v1.2.3", "synced-v1.2.3"
        )

        self.assertEqual("sync", result.action)
        self.assertEqual("marker-missing", result.reason)

    def test_rewritten_commit_with_identical_tree_is_skipped(self):
        original = self.repo.commit_file("release", "original release")
        tree = self.repo.git("rev-parse", f"{original}^{{tree}}")
        self.repo.git("tag", "-a", "synced-v1.2.3", "-m", f"upstream-tree: {tree}")

        self.repo.git("checkout", "--orphan", "rewritten")
        self.repo.git("add", "release.txt")
        self.repo.git("commit", "-m", "rewritten release")
        self.repo.git("tag", "v1.2.3")

        result = self.module.determine_sync_state(
            self.repo.path, "v1.2.3", "synced-v1.2.3"
        )

        self.assertEqual("skip", result.action)
        self.assertEqual("tree-equivalent", result.reason)

    def test_changed_tree_requires_sync_even_when_marker_exists(self):
        original = self.repo.commit_file("release one", "original release")
        tree = self.repo.git("rev-parse", f"{original}^{{tree}}")
        self.repo.git("tag", "-a", "synced-v1.2.3", "-m", f"upstream-tree: {tree}")
        changed = self.repo.commit_file("release two", "changed release")
        self.repo.git("tag", "v1.2.3", changed)

        result = self.module.determine_sync_state(
            self.repo.path, "v1.2.3", "synced-v1.2.3"
        )

        self.assertEqual("sync", result.action)
        self.assertEqual("tree-changed", result.reason)

    def test_legacy_marker_uses_upstream_merge_parent_tree(self):
        base = self.repo.commit_file("base", "fork base")
        self.repo.git("checkout", "-b", "upstream-release", base)
        upstream = self.repo.commit_file("release", "upstream release")
        upstream_tree = self.repo.git("rev-parse", f"{upstream}^{{tree}}")

        self.repo.git("checkout", "main")
        self.repo.git("merge", "--no-ff", upstream, "-m", "Merge upstream v1.2.3")
        self.repo.git("tag", "synced-v1.2.3")

        self.repo.git("checkout", "--orphan", "rewritten")
        self.repo.git("add", "release.txt")
        self.repo.git("commit", "-m", "rewritten upstream release")
        self.assertEqual(upstream_tree, self.repo.git("rev-parse", "HEAD^{tree}"))
        self.repo.git("tag", "v1.2.3")

        result = self.module.determine_sync_state(
            self.repo.path, "v1.2.3", "synced-v1.2.3"
        )

        self.assertEqual("skip", result.action)
        self.assertEqual("tree-equivalent", result.reason)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Decide whether an upstream release tag needs to be synchronized."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple


TREE_LINE = re.compile(r"^upstream-tree:\s*([0-9a-f]{40,64})$", re.MULTILINE)


class SyncState(NamedTuple):
    action: str
    reason: str
    target_tree: str
    synced_tree: str | None


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def ref_exists(repo: Path, ref: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=repo,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def marker_tree(repo: Path, marker: str, tag: str) -> str | None:
    contents = git(
        repo,
        "for-each-ref",
        "--format=%(contents)",
        f"refs/tags/{marker}",
    )
    match = TREE_LINE.search(contents)
    if match:
        return match.group(1)

    subject = f"Merge upstream {tag}"
    for commit in git(repo, "rev-list", "--first-parent", "--merges", marker).splitlines():
        if git(repo, "show", "-s", "--format=%s", commit).startswith(subject):
            parents = git(repo, "show", "-s", "--format=%P", commit).split()
            if len(parents) >= 2:
                return git(repo, "rev-parse", f"{parents[1]}^{{tree}}")
    return None


def determine_sync_state(repo: Path, tag: str, marker: str) -> SyncState:
    target_tree = git(repo, "rev-parse", f"{tag}^{{tree}}")
    if not ref_exists(repo, marker):
        return SyncState("sync", "marker-missing", target_tree, None)

    synced_tree = marker_tree(repo, marker, tag)
    if synced_tree is None:
        return SyncState("sync", "marker-provenance-missing", target_tree, None)
    if synced_tree == target_tree:
        return SyncState("skip", "tree-equivalent", target_tree, synced_tree)
    return SyncState("sync", "tree-changed", target_tree, synced_tree)


def append_github_output(path: str, state: SyncState) -> None:
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"skip={'true' if state.action == 'skip' else 'false'}\n")
        output.write(f"sync_reason={state.reason}\n")
        output.write(f"upstream_tree={state.target_tree}\n")
        output.write(f"synced_tree={state.synced_tree or ''}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--marker")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()

    marker = args.marker or f"synced-{args.tag}"
    state = determine_sync_state(args.repo, args.tag, marker)
    print(
        f"action={state.action} reason={state.reason} "
        f"upstream_tree={state.target_tree} synced_tree={state.synced_tree or 'unknown'}"
    )
    if github_output := os.environ.get("GITHUB_OUTPUT"):
        append_github_output(github_output, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

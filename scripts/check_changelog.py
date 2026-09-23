#!/usr/bin/env python3
"""Require CHANGELOG.md whenever repository skill files change."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def is_repository(root: Path) -> bool:
    return git(root, "rev-parse", "--is-inside-work-tree", check=False).strip() == "true"


def valid_base(root: Path, ref: str | None) -> str | None:
    if ref and set(ref) != {"0"}:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return ref
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return "HEAD^" if result.returncode == 0 else None


def working_tree_paths(root: Path) -> set[str]:
    paths: set[str] = set()
    for line in git(root, "status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        paths.add(path.strip('"'))
    return paths


def changed_paths(root: Path, base_ref: str | None) -> set[str]:
    working = working_tree_paths(root)
    if working:
        return working
    base = valid_base(root, base_ref)
    if not base:
        return set()
    return set(git(root, "diff", "--name-only", base, "HEAD").splitlines())


def relevant(path: str) -> bool:
    item = Path(path)
    if path == "CHANGELOG.md":
        return False
    if any(part in IGNORED_PARTS for part in item.parts):
        return False
    if item.suffix in IGNORED_SUFFIXES:
        return False
    return True


def validate_changelog(root: Path) -> None:
    changelog = root / "CHANGELOG.md"
    if not changelog.is_file():
        raise ValueError("CHANGELOG.md is missing")
    text = changelog.read_text(encoding="utf-8")
    if not re.search(r"(?m)^## \d{4}-\d{2}-\d{2}(?:\s|$)", text):
        raise ValueError("CHANGELOG.md needs a dated entry: ## YYYY-MM-DD")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", help="Git ref before the current change set")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()

    validate_changelog(root)
    if not is_repository(root):
        print("CHANGELOG guard skipped: no Git metadata in this working folder")
        return 0

    paths = changed_paths(root, args.base_ref)
    skill_changes = sorted(path for path in paths if relevant(path))
    if skill_changes and "CHANGELOG.md" not in paths:
        print("CHANGELOG.md must be updated with these Skill changes:", file=sys.stderr)
        for path in skill_changes:
            print(f"- {path}", file=sys.stderr)
        return 1

    print(f"CHANGELOG guard passed ({len(skill_changes)} Skill paths checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

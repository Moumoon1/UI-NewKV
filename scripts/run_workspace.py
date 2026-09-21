#!/usr/bin/env python3
"""Create and safely remove per-run temporary workspaces for this skill."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SKILL_NAME = "kv-ui-theme-adapter"
ROOT_NAME = "kv-ui-theme-adapter-runs"
MARKER_NAME = ".kv-ui-theme-adapter-run.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def workspace_root() -> Path:
    root = Path(tempfile.gettempdir()).resolve() / ROOT_NAME
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def validate_workspace(raw_path: str) -> tuple[Path, dict]:
    supplied = Path(raw_path)
    if supplied.is_symlink():
        raise ValueError("workspace path must not be a symlink")
    resolved = supplied.resolve(strict=True)
    root = workspace_root().resolve(strict=True)
    if resolved.parent != root or not resolved.name.startswith("run-"):
        raise ValueError(f"workspace must be one direct run-* child of {root}")
    marker_path = resolved / MARKER_NAME
    if marker_path.is_symlink() or not marker_path.is_file():
        raise ValueError(f"missing safe cleanup marker: {marker_path}")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("schemaVersion") != 1 or marker.get("skill") != SKILL_NAME:
        raise ValueError("workspace marker does not belong to this skill")
    if marker.get("workspace") != str(resolved):
        raise ValueError("workspace marker path mismatch")
    return resolved, marker


def init_workspace(args: argparse.Namespace) -> int:
    root = workspace_root()
    path = Path(tempfile.mkdtemp(prefix="run-", dir=root)).resolve()
    marker = {
        "schemaVersion": 1,
        "skill": SKILL_NAME,
        "workspace": str(path),
        "fileKey": args.file_key,
        "targetNodeId": args.target_id,
        "status": "active",
        "createdAt": utc_now(),
    }
    (path / MARKER_NAME).write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "created", "workspace": str(path)}, ensure_ascii=False))
    return 0


def inspect_workspace(args: argparse.Namespace) -> int:
    path, marker = validate_workspace(args.workspace)
    entries = sum(1 for item in path.rglob("*") if item.name != MARKER_NAME)
    print(
        json.dumps(
            {"status": "valid", "workspace": str(path), "entries": entries, "marker": marker},
            ensure_ascii=False,
        )
    )
    return 0


def cleanup_workspace(args: argparse.Namespace) -> int:
    path, marker = validate_workspace(args.workspace)
    marker["status"] = "cleaning"
    marker["cleanupStartedAt"] = utc_now()
    (path / MARKER_NAME).write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.rmtree(path)
    print(json.dumps({"status": "cleaned", "workspace": str(path)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a marked temporary run workspace")
    init.add_argument("--file-key", required=True)
    init.add_argument("--target-id", required=True)
    init.set_defaults(handler=init_workspace)

    inspect = sub.add_parser("inspect", help="validate and summarize a run workspace")
    inspect.add_argument("workspace")
    inspect.set_defaults(handler=inspect_workspace)

    cleanup = sub.add_parser("cleanup", help="safely delete one validated run workspace")
    cleanup.add_argument("workspace")
    cleanup.set_defaults(handler=cleanup_workspace)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate guarded Figma Plugin API code for one frozen color-diff batch."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("batch")
    args = parser.parse_args()
    script_dir = Path(__file__).parent
    batch = json.loads(Path(args.batch).read_text())
    print((script_dir / "snapshot_fingerprint.js").read_text())
    print((script_dir / "figma_apply_color_diff.js").read_text())
    print("const ops=" + json.dumps(batch, ensure_ascii=False, separators=(",", ":")) + ";")
    print("return await applyDeclaredColorDiff(figma,ops);")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a read-only Figma Plugin API verifier for a frozen snapshot template."""

import argparse
import json
from pathlib import Path

from snapshot_fingerprint import row_fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("template")
    parser.add_argument("--compact", action="store_true",
                        help="Return one whole-tree fingerprint instead of embedding every row hash")
    args = parser.parse_args()

    template = json.loads(Path(args.template).read_text())
    helper_dir = Path(__file__).parent
    snapshot_helper = (helper_dir / "figma_snapshot.js").read_text()
    fingerprint_helper = (helper_dir / "snapshot_fingerprint.js").read_text()
    expected = [
        {"id": row["id"], "hash": row_fingerprint(row)}
        for row in template["nodes"]
    ]
    expected_hash = row_fingerprint([row["hash"] for row in expected])
    root_id = json.dumps(template["rootId"])
    print(snapshot_helper)
    print(fingerprint_helper)
    if args.compact:
        print(
            f"""
const live=await snapshotThemeTree(figma,{root_id});
const actualHash=snapshotRowFingerprint(live.nodes.map(snapshotRowFingerprint));
const expectedHash={json.dumps(expected_hash)};
return {{
  rootId:live.rootId,
  capturedAt:live.capturedAt,
  errors:live.errors,
  nodeCount:live.nodes.length,
  mismatchCount:actualHash===expectedHash?0:1,
  mismatches:actualHash===expectedHash?[]:[{{reason:"whole-tree-fingerprint-mismatch",actualHash,expectedHash}}],
  verifiedTemplateHash:actualHash,
}};
"""
        )
        return
    payload = json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
    print(
        f"""
const expectedRows={payload};
const live=await snapshotThemeTree(figma,{root_id});
const mismatches=[];
const count=Math.max(live.nodes.length,expectedRows.length);
for(let i=0;i<count;i++){{
  const actual=live.nodes[i];
  const expected=expectedRows[i];
  if(!actual||!expected||actual.id!==expected.id||snapshotRowFingerprint(actual)!==expected.hash){{
    mismatches.push({{index:i,expectedId:expected?.id??null,actualId:actual?.id??null,expectedHash:expected?.hash??null,actualHash:actual?snapshotRowFingerprint(actual):null}});
  }}
}}
return {{
  rootId:live.rootId,
  capturedAt:live.capturedAt,
  errors:live.errors,
  nodeCount:live.nodes.length,
  mismatchCount:mismatches.length,
  mismatches:mismatches.slice(0,50),
  verifiedTemplateHash:{json.dumps(expected_hash)},
}};
"""
    )


if __name__ == "__main__":
    main()

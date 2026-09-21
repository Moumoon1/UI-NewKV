#!/usr/bin/env python3
"""Generate guarded Figma code for the blue-family correction trial/expand phase."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["trial", "expand"])
    parser.add_argument("operations")
    args = parser.parse_args()
    scripts = Path(__file__).parent
    operations = json.loads(Path(args.operations).read_text())
    print((scripts / "snapshot_fingerprint.js").read_text())
    print((scripts / "figma_apply_color_diff.js").read_text())
    print("const ops=" + json.dumps(operations, ensure_ascii=False, separators=(",", ":")) + ";")
    print("const applied=await applyDeclaredColorDiff(figma,ops);")
    if args.phase == "trial":
        print(
            """
const image=await figma.getNodeByIdAsync('1237:6623');
const fade=await figma.getNodeByIdAsync('1237:6624');
if(!image||!fade||!('resize' in image)||!('resize' in fade))throw new Error('missing Hero fit carriers');
if(Math.abs(image.width-414)>1e-6||Math.abs(image.height-349.5)>1e-6)throw new Error('unexpected KV carrier geometry');
if(Math.abs(fade.x)>1e-6||Math.abs(fade.y-328)>1e-6||Math.abs(fade.width-414)>1e-6||Math.abs(fade.height-32)>1e-6)throw new Error('unexpected bottom fade geometry');
image.resize(414,360);
fade.y=300;
fade.resize(414,60);
return {mutatedNodeIds:[...new Set([...applied.mutatedNodeIds,image.id,fade.id])],operationCount:applied.operationCount+2,capturedAt:new Date().toISOString()};
"""
        )
    else:
        print("return applied;")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Detect visible metallic-gradient stop collapse in mapped Figma Icon subtrees.

This is an early fail-fast guard, not a substitute for native-size visual review.
"""

import argparse
import json
import math
from pathlib import Path


def paint_groups(props):
    for field in ("fills", "strokes"):
        if field in props:
            yield field, props[field]
    for index, region in enumerate(props.get("vectorNetwork", {}).get("regions", [])):
        yield f"vectorNetwork/regions/{index}/fills", region.get("fills", [])


def spread(colors):
    return max((math.dist(a, b) for i, a in enumerate(colors) for b in colors[i + 1:]), default=0.0)


def inspect_metallic_stops(source, clone, mapping, roots,
                           min_source_spread=0.025, max_target_spread=0.005):
    source_rows = {row["id"]: row for row in source["nodes"]}
    clone_rows = {row["id"]: row for row in clone["nodes"]}
    roots = set(roots)
    missing = sorted(roots - source_rows.keys())
    if missing:
        raise ValueError(f"metallic roots missing in source: {missing}")

    def under_root(node_id):
        while node_id in source_rows:
            if node_id in roots:
                return True
            node_id = source_rows[node_id]["parentId"]
        return False

    findings = []
    checked = 0
    for source_id, source_row in source_rows.items():
        if not under_root(source_id):
            continue
        clone_id = mapping.get(source_id)
        if clone_id not in clone_rows:
            findings.append({"sourceId": source_id, "cloneId": clone_id,
                             "reason": "mapped clone node missing"})
            continue
        source_groups = dict(paint_groups(source_row["props"]))
        clone_groups = dict(paint_groups(clone_rows[clone_id]["props"]))
        for path, source_paints in source_groups.items():
            clone_paints = clone_groups.get(path, [])
            for index, source_paint in enumerate(source_paints):
                if (source_paint.get("visible") is False or source_paint.get("opacity", 1) <= 0
                        or not source_paint.get("type", "").startswith("GRADIENT")):
                    continue
                if index >= len(clone_paints):
                    findings.append({"sourceId": source_id, "cloneId": clone_id,
                                     "paintPath": f"{path}/{index}", "reason": "paint missing"})
                    continue
                clone_paint = clone_paints[index]
                source_stops = source_paint.get("gradientStops", [])
                clone_stops = clone_paint.get("gradientStops", [])
                if len(source_stops) != len(clone_stops):
                    findings.append({"sourceId": source_id, "cloneId": clone_id,
                                     "paintPath": f"{path}/{index}", "reason": "stop count changed"})
                    continue
                source_colors = [[s["color"][key] for key in "rgb"] for s in source_stops
                                 if s["color"].get("a", 1) > 0]
                clone_colors = [[s["color"][key] for key in "rgb"] for s in clone_stops
                                if s["color"].get("a", 1) > 0]
                if len(source_colors) < 2:
                    continue
                checked += 1
                source_spread = spread(source_colors)
                clone_spread = spread(clone_colors)
                if source_spread >= min_source_spread and clone_spread <= max_target_spread:
                    findings.append({"sourceId": source_id, "cloneId": clone_id,
                                     "paintPath": f"{path}/{index}",
                                     "reason": "visible gradient stops collapsed",
                                     "sourceSpread": round(source_spread, 4),
                                     "cloneSpread": round(clone_spread, 4)})
    return {"status": "fail" if findings else "pass", "metallicRoots": sorted(roots),
            "checkedVisibleGradients": checked, "findings": findings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("clone")
    parser.add_argument("node_map")
    parser.add_argument("--roots", nargs="+", required=True, help="source metallic Icon root IDs")
    parser.add_argument("--out")
    args = parser.parse_args()
    source = json.loads(Path(args.source).read_text())
    clone = json.loads(Path(args.clone).read_text())
    node_map = json.loads(Path(args.node_map).read_text())
    mapping = node_map.get("mapping", node_map)
    result = inspect_metallic_stops(source, clone, mapping, args.roots)
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({**result, "findings": result["findings"][:12]}, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

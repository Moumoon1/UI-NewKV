#!/usr/bin/env python3
"""Fail when a mapped multi-color visual unit is flattened during theming.

The relation plan is explicit on purpose: it can describe gradient stops, title
Paints, separate atmosphere shapes, button material layers, or any other set of
source color carriers that must remain visibly distinct after recoloring.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
from pathlib import Path


DEFAULT_SOURCE = {"rgb": 0.025, "saturation": 0.08, "value": 0.08}
DEFAULT_TARGET = {"rgb": 0.012, "saturation": 0.035, "value": 0.035}


def decode_pointer(path: str) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError(f"color path must be a JSON Pointer: {path!r}")
    return [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]


def resolve_pointer(value, path: str):
    for part in decode_pointer(path):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def rgba(value, label: str) -> tuple[float, float, float, float]:
    if not isinstance(value, dict) or not all(key in value for key in "rgb"):
        raise ValueError(f"{label} does not resolve to an RGB(A) color")
    result = tuple(float(value[key]) for key in "rgb") + (float(value.get("a", 1)),)
    if any(not math.isfinite(item) or item < 0 or item > 1 for item in result):
        raise ValueError(f"{label} contains a color channel outside 0..1")
    return result


def pairwise(values, metric):
    return [metric(values[left], values[right])
            for left in range(len(values)) for right in range(left + 1, len(values))]


def max_spread(values, metric) -> float:
    return max(pairwise(values, metric), default=0.0)


def rgb_distance(left, right) -> float:
    return math.dist(left[:3], right[:3])


def hsv_axis(index):
    return lambda left, right: abs(colorsys.rgb_to_hsv(*left[:3])[index]
                                   - colorsys.rgb_to_hsv(*right[:3])[index])


METRICS = {"rgb": rgb_distance, "saturation": hsv_axis(1), "value": hsv_axis(2)}


def mapping_dict(node_map):
    if not isinstance(node_map, dict):
        raise ValueError("node map must be an object")
    for key in ("mapping", "map"):
        if isinstance(node_map.get(key), dict):
            return node_map[key]
    return node_map


def audit_material_relations(source, target, node_map, plan):
    if plan.get("schemaVersion") != 1 or not isinstance(plan.get("relations"), list):
        raise ValueError("relation plan must contain schemaVersion=1 and relations")
    source_rows = {row["id"]: row for row in source.get("nodes", [])}
    target_rows = {row["id"]: row for row in target.get("nodes", [])}
    mapping = mapping_dict(node_map)
    findings, checked, exceptions = [], 0, []

    for relation in plan["relations"]:
        relation_id = relation.get("id")
        members = relation.get("members")
        if not relation_id or not isinstance(members, list) or len(members) < 2:
            raise ValueError("each relation needs an id and at least two members")
        allow_flatten = relation.get("allowFlatten", False)
        if allow_flatten and not str(relation.get("allowFlattenReason", "")).strip():
            raise ValueError(f"{relation_id}: allowFlatten requires allowFlattenReason")
        preserve = relation.get("preserve", ["rgb"])
        if not preserve or any(axis not in METRICS for axis in preserve):
            raise ValueError(f"{relation_id}: preserve must use rgb/saturation/value")
        preserve_order = relation.get("preserveOrder", [])
        if any(axis not in ("saturation", "value") for axis in preserve_order):
            raise ValueError(f"{relation_id}: preserveOrder only supports saturation/value")

        source_colors, target_colors, resolved = [], [], []
        for member in members:
            source_id = member.get("sourceId") or member.get("nodeId")
            source_path = member.get("sourcePath") or member.get("path")
            target_id = member.get("targetId") or mapping.get(source_id)
            target_path = member.get("targetPath") or source_path
            if source_id not in source_rows:
                raise ValueError(f"{relation_id}: source node missing: {source_id}")
            if target_id not in target_rows:
                findings.append({"relationId": relation_id, "reason": "mapped target node missing",
                                 "sourceId": source_id, "targetId": target_id})
                continue
            try:
                source_color = rgba(resolve_pointer(source_rows[source_id]["props"], source_path),
                                    f"{relation_id}:{source_id}{source_path}")
                target_color = rgba(resolve_pointer(target_rows[target_id]["props"], target_path),
                                    f"{relation_id}:{target_id}{target_path}")
            except (KeyError, IndexError, TypeError, ValueError) as error:
                findings.append({"relationId": relation_id, "reason": "color path unresolved",
                                 "sourceId": source_id, "targetId": target_id, "error": str(error)})
                continue
            source_colors.append(source_color)
            target_colors.append(target_color)
            resolved.append({"role": member.get("role"), "sourceId": source_id,
                             "targetId": target_id, "sourcePath": source_path,
                             "targetPath": target_path})

        if len(source_colors) != len(members):
            continue
        checked += 1
        source_thresholds = {**DEFAULT_SOURCE, **relation.get("minimumSourceSpread", {})}
        target_thresholds = {**DEFAULT_TARGET, **relation.get("minimumTargetSpread", {})}
        metrics = {axis: {"source": max_spread(source_colors, METRICS[axis]),
                          "target": max_spread(target_colors, METRICS[axis])}
                   for axis in METRICS}
        collapsed_axes = [axis for axis in preserve
                          if metrics[axis]["source"] >= source_thresholds[axis]
                          and metrics[axis]["target"] < target_thresholds[axis]]
        inverted_axes = []
        for axis in preserve_order:
            metric_index = 1 if axis == "saturation" else 2
            source_axis = [colorsys.rgb_to_hsv(*color[:3])[metric_index] for color in source_colors]
            target_axis = [colorsys.rgb_to_hsv(*color[:3])[metric_index] for color in target_colors]
            for left in range(len(source_axis)):
                for right in range(left + 1, len(source_axis)):
                    if abs(source_axis[left] - source_axis[right]) < source_thresholds[axis]:
                        continue
                    if ((source_axis[left] - source_axis[right])
                            * (target_axis[left] - target_axis[right]) < 0):
                        inverted_axes.append(axis)
                        break

        if collapsed_axes or inverted_axes:
            finding = {"relationId": relation_id,
                       "unitId": relation.get("unitId"),
                       "reason": "material color relation collapsed" if collapsed_axes
                       else "material color relation order inverted",
                       "collapsedAxes": sorted(set(collapsed_axes)),
                       "invertedAxes": sorted(set(inverted_axes)),
                       "metrics": {axis: {key: round(value, 4) for key, value in row.items()}
                                   for axis, row in metrics.items()},
                       "members": resolved}
            if allow_flatten:
                exceptions.append({**finding, "allowFlattenReason": relation["allowFlattenReason"]})
            else:
                findings.append(finding)

    return {"status": "fail" if findings else "pass", "checkedRelations": checked,
            "declaredRelations": len(plan["relations"]), "findings": findings,
            "allowedFlattenExceptions": exceptions}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("node_map", type=Path)
    parser.add_argument("relation_plan", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit_material_relations(
        json.loads(args.source.read_text()), json.loads(args.target.read_text()),
        json.loads(args.node_map.read_text()), json.loads(args.relation_plan.read_text()))
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({**result, "findings": result["findings"][:20]}, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

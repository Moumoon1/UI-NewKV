#!/usr/bin/env python3
"""Generate one guarded Figma program for several independent regions."""

import argparse
import json
from pathlib import Path


def validate_batch(plans):
    if not isinstance(plans, list) or len(plans) < 2:
        raise ValueError("batch requires at least two region plans")
    region_ids, write_keys = set(), set()
    for plan in plans:
        region_id = plan.get("regionId")
        if plan.get("schemaVersion") != 1 or not region_id or not isinstance(plan.get("operations"), list):
            raise ValueError("every batched plan needs schemaVersion=1, regionId and operations")
        if region_id in region_ids:
            raise ValueError(f"duplicate regionId: {region_id}")
        region_ids.add(region_id)
        gate = plan.get("batchEligibility", {})
        if (gate.get("representativeGateStatus") != "pass"
                or gate.get("independent") is not True
                or not gate.get("recipeHash") or not gate.get("dependencyHash")):
            raise ValueError(f"region is not eligible for guarded batching: {region_id}")
        if plan.get("reviewAfter") is False:
            raise ValueError(f"batched region must review in the same call: {region_id}")
        for operation in plan["operations"]:
            key = (operation.get("cloneId"), operation.get("property"))
            if key in write_keys:
                raise ValueError(f"overlapping region write: {key}")
            write_keys.add(key)


def build_batch(plans):
    validate_batch(plans)
    directory = Path(__file__).parent
    names = ("snapshot_fingerprint.js", "figma_apply_color_diff.js",
             "figma_region_runner.js", "figma_multi_region_runner.js")
    program = "\n".join((directory / name).read_text() for name in names)
    program += "\nconst regionPlans=" + json.dumps(plans, ensure_ascii=False, separators=(",", ":")) + ";\n"
    program += "return await applyAndReviewThemeRegions(figma,regionPlans);\n"
    if len(program) > 45000:
        raise ValueError("multi-region batch exceeds 45,000-character code budget; use fewer regions")
    return program


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plans", type=Path, nargs="+")
    args = parser.parse_args()
    build = build_batch([json.loads(path.read_text()) for path in args.plans])
    print(build, end="")


if __name__ == "__main__":
    main()

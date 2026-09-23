#!/usr/bin/env python3
"""Generate a guarded one-region Figma program, or fail before an oversize call."""
import argparse
import json
from pathlib import Path


def build(plan):
    if plan.get('schemaVersion') != 1 or not isinstance(plan.get('operations'), list):
        raise ValueError('region plan must contain schemaVersion=1 and operations')
    directory = Path(__file__).parent
    names = ('snapshot_fingerprint.js', 'figma_apply_color_diff.js', 'figma_region_runner.js')
    program = '\n'.join((directory / name).read_text() for name in names)
    program += '\nconst regionPlan=' + json.dumps(plan, ensure_ascii=False, separators=(',', ':')) + ';\n'
    program += 'return await applyAndReviewThemeRegion(figma,regionPlan);\n'
    if len(program) > 45000:
        raise ValueError('region exceeds 45,000-character code budget; split only this region into guarded technical batches')
    return program


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    args = parser.parse_args()
    print(build(json.loads(args.plan.read_text())), end='')


if __name__ == '__main__':
    main()

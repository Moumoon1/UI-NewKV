#!/usr/bin/env python3
"""Split only one region into size-safe writes; review after its final part."""
import argparse
import json
from pathlib import Path

from generate_figma_region_js import build


def split_region(plan, max_operations=60):
    operations = plan.get('operations')
    if not isinstance(operations, list) or max_operations < 1:
        raise ValueError('region operations and a positive maximum are required')
    batches, current = [], []
    for operation in operations:
        trial = current + [operation]
        draft = {**plan, 'operations': trial, 'reviewAfter': True}
        try:
            if len(trial) > max_operations:
                raise ValueError('operation limit')
            build(draft)
            current = trial
        except ValueError:
            if not current:
                raise ValueError('single region operation exceeds Figma code budget')
            batches.append(current)
            current = [operation]
            build({**draft, 'operations': current})
    if current or not batches:
        batches.append(current)
    result = []
    for index, batch in enumerate(batches):
        last = index == len(batches) - 1
        part = {**plan, 'operations': batch, 'reviewAfter': last}
        if not last:
            part['oldUiColors'] = []
            part['protectedNodeIds'] = []
        build(part)
        result.append(part)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    parser.add_argument('--max-operations', type=int, default=60)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    batches = split_region(plan, args.max_operations)
    paths = []
    for index, batch in enumerate(batches):
        path = args.plan.with_name(args.plan.stem + f'-part-{index}.json')
        path.write_text(json.dumps(batch, ensure_ascii=False, separators=(',', ':')))
        paths.append(str(path))
    print(json.dumps({'regionId': plan.get('regionId'), 'operations': len(plan['operations']),
                      'parts': len(paths), 'plans': paths}, ensure_ascii=False))


if __name__ == '__main__':
    main()

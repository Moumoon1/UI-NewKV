#!/usr/bin/env python3
"""Reject text/detail recipes on large, visibly painted non-text carriers.

This is a deliberately narrow semantic check. It catches a common dark-to-light
failure that channel coverage cannot: a Vector acting as a card or header
background being mistaken for dark text. Smaller decorative shapes remain a
visual-review responsibility.
"""

import argparse
import json
from pathlib import Path

from execution_audit import color_inventory


DETAIL_ROLES = {'text', 'text.muted', 'detail', 'detail.muted'}


def inspect(source, manifest):
    nodes = {row['id']: row for row in source['nodes']}
    root = nodes[source['rootId']]['props']
    root_width = root.get('width') or 0
    if root_width <= 0:
        return {'status': 'fail', 'error': 'source root width required for visible-surface check'}
    active = {row['path'] for row in color_inventory(source)['entries']
              if not row['inactive']}
    candidates = []
    violations = []
    for entry in manifest.get('entries', []):
        path = entry.get('path', '')
        node = nodes.get(entry.get('nodeId'))
        if not node or path not in active or '/props/fills/' not in path:
            continue
        props = node['props']
        if (props.get('type') == 'TEXT' or props.get('width', 0) < root_width * .55
                or props.get('height', 0) < 40):
            continue
        fill_index = path.split('/props/fills/', 1)[1].split('/', 1)[0]
        if not fill_index.isdigit():
            continue
        fills = props.get('fills', [])
        if int(fill_index) >= len(fills):
            continue
        fill = fills[int(fill_index)]
        if fill.get('type') == 'IMAGE':
            continue
        role = entry.get('role', '')
        candidate = {'path': path, 'nodeId': node['id'], 'name': props.get('name'),
                     'role': role, 'width': props.get('width'), 'height': props.get('height')}
        candidates.append(candidate)
        solid_opaque = (fill.get('type') == 'SOLID' and fill.get('opacity', 1) >= .8
                        and props.get('opacity', 1) >= .8)
        if (role in DETAIL_ROLES or role.startswith('text.') or
                (role == 'secondary' and solid_opaque)):
            violations.append(candidate)
    return {'status': 'fail' if violations else 'pass',
            'candidateCount': len(candidates), 'violations': violations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    result = inspect(json.loads(args.source.read_text()),
                     json.loads(args.manifest.read_text()))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())

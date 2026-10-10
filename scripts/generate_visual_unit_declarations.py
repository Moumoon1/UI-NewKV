#!/usr/bin/env python3
"""Make an intentionally incomplete visual-unit root review template.

Roots come from a same-source workbench, but visual basis, sibling dependencies
and rule scopes remain blank until a reviewer inspects them. This template is
not accepted by compile_visual_unit_registry.py as a completed declaration.
"""
import argparse
import json
from pathlib import Path

from execution_audit import color_inventory
from theme_audit import snapshot_document


def build(source, workbench):
    source_hash = color_inventory(source)['sourceHash']
    if (workbench.get('status') != 'review-workbench-only' or
            workbench.get('sourceHash') != source_hash):
        raise ValueError('workbench must match complete source snapshot')
    nodes = snapshot_document(source)['nodes']
    grouped = {}
    for item in workbench.get('units', []):
        root_id = item['unitId']
        row = grouped.setdefault(root_id, {'paths': set(), 'kinds': set(),
                                           'regionName': item.get('regionName', '')})
        row['paths'].update(item['pendingPaths'])
        row['kinds'].update(item.get('channelKinds', [item['channelKind']]))
    grouped.setdefault(source['rootId'], {'paths': set(), 'kinds': set(),
                                          'regionName': 'page'})
    units = []
    for index, root_id in enumerate(sorted(grouped), 1):
        if root_id not in nodes:
            raise ValueError('workbench unit root absent from source')
        hint = grouped[root_id]
        units.append({'id': 'unit-' + str(index).zfill(3),
                      'rootNodeId': root_id,
                      'basis': '', 'reviewRuleIds': [],
                      'extraDependencyNodeIds': [],
                      'reviewNodeIds': [root_id],
                      'reviewHint': {'name': nodes[root_id]['props'].get('name', ''),
                                     'regionName': hint['regionName'],
                                     'pendingPaths': len(hint['paths']),
                                     'channelKinds': sorted(hint['kinds'])}})
    return {'schemaVersion': 1, 'sourceHash': source_hash,
            'status': 'needs-review', 'units': units,
            'note': 'Fill basis, reviewRuleIds and actual sibling/host dependencies; prune/restructure roots before compiling.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('workbench', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.source.read_text()),
                   json.loads(args.workbench.read_text()))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'status': result['status'], 'roots': len(result['units'])}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Prove planned vectorNetwork colors are mirrors of writable Paint channels.

This is only an offline source/target relationship. The staged Figma preview
must still read back every returned vector target after its Paint setters.
"""
import argparse
import json
from pathlib import Path

from execution_audit import color_inventory
from theme_audit import target_equal


def inspect(source, manifest, write_plan):
    inventory = {row['path']: row for row in color_inventory(source)['entries']}
    planned = {row['path']: row for row in manifest.get('entries', [])}
    errors, mirrors = [], []
    direct = [op for op in write_plan.get('operations', [])
              if op.get('property') in ('vectorNetwork', 'vectorPaths')]
    if direct:
        errors.append({'error': 'direct vector-data setters are not allowed in the mirror path',
                       'operations': [op.get('sourceId') for op in direct]})
    by_node = {}
    for path, item in inventory.items():
        if '/props/fills/' in path or '/props/strokes/' in path:
            by_node.setdefault(item['nodeId'], []).append((path, item))
    for path, entry in planned.items():
        if '/props/vectorNetwork/' not in path or entry.get('disposition') != 'change':
            continue
        source_item = inventory.get(path)
        if source_item is None:
            errors.append({'path': path, 'error': 'vector target absent from source inventory'})
            continue
        choices = []
        for peer_path, peer in by_node.get(source_item['nodeId'], []):
            peer_plan = planned.get(peer_path)
            if not peer_plan or not target_equal(source_item['source'], peer['source']):
                continue
            target = peer_plan.get('target') if peer_plan.get('disposition') == 'change' else peer['source']
            if target_equal(entry.get('target'), target):
                choices.append(peer_path)
        if not choices:
            errors.append({'path': path, 'error': 'no same-node writable Paint mirror with matching source and target'})
        else:
            mirrors.append({'sourceId': source_item['nodeId'], 'vectorPath': path,
                            'mirrorPaintPath': sorted(choices)[0], 'target': entry['target']})
    return {'status': 'fail' if errors else 'pass', 'mirrorCount': len(mirrors),
            'directSetterCount': len(direct), 'readbackRequirements': mirrors, 'errors': errors,
            'note': 'Figma staged preview must verify all readbackRequirements after Paint writes.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('write_plan', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(json.loads(args.source.read_text()),
                     json.loads(args.manifest.read_text()),
                     json.loads(args.write_plan.read_text()))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({key: result[key] for key in
                      ('status', 'mirrorCount', 'directSetterCount')}, ensure_ascii=False))
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())

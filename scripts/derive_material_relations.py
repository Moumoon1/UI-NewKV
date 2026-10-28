#!/usr/bin/env python3
"""Freeze visible multi-stop gradient roles for the material-collapse audit.

Alpha-only fades and exactly protected assets are reported as exceptions, not
claimed to be chromatic material relations.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from execution_audit import color_inventory
from theme_audit import parts


def build(source, manifest):
    classified = {entry['path']: entry for entry in manifest['entries']}
    groups = defaultdict(list)
    for row in color_inventory(source)['entries']:
        path = row['path']
        if row['inactive'] or '/gradientStops/' not in path or '/vectorNetwork/' in path:
            continue
        groups[path.split('/gradientStops/')[0]].append(row)
    relations, exceptions = [], []
    for prefix, rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        entries = [classified.get(row['path']) for row in rows]
        if any(entry is None for entry in entries):
            raise ValueError('gradient stop absent from manifest: ' + prefix)
        source_colors = [row['source'] for row in rows]
        spread = max(math.dist([a[key] for key in 'rgb'], [b[key] for key in 'rgb'])
                     for a in source_colors for b in source_colors)
        if all(entry['disposition'] == 'preserve' for entry in entries):
            exceptions.append({'paintPath': prefix, 'reason': 'precisely protected material'})
            continue
        if any(entry['disposition'] == 'ignore' for entry in entries):
            exceptions.append({'paintPath': prefix, 'reason': 'visually inactive after approved KV removal'})
            continue
        if any(color.get('a', 1) <= .01 for color in source_colors):
            exceptions.append({'paintPath': prefix, 'reason': 'transparent fade endpoint; review in composite boundary gate'})
            continue
        if spread < .025:
            exceptions.append({'paintPath': prefix, 'reason': 'no distinct source RGB material roles'})
            continue
        members = []
        for row in rows:
            tokens = parts(row['path'])
            members.append({'sourceId': row['nodeId'],
                            'sourcePath': '/' + '/'.join(tokens[3:]),
                            'role': classified[row['path']]['role']})
        relations.append({'id': 'gradient:' + prefix, 'members': members,
                          'preserve': ['rgb'], 'preserveRoleGroups': True})
    return {'schemaVersion': 1, 'relations': relations, 'exceptions': exceptions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    plan = build(json.loads(args.source.read_text()), json.loads(args.manifest.read_text()))
    args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    print(json.dumps({'relations': len(plan['relations']),
                      'exceptions': len(plan['exceptions'])}))


if __name__ == '__main__':
    main()

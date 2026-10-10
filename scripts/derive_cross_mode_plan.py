#!/usr/bin/env python3
"""Enumerate cross-mode alpha/appearance obligations from a frozen source.

The caller identifies exact visual-removal and state roots; generated evidence
IDs are review obligations, not proof that a screenshot has passed.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from execution_audit import _alpha_paths, color_inventory
from theme_audit import digest, parts, snapshot_document


def build(source, manifest, hidden_roots=(), state_roots=(), boundary_roots=()):
    doc = snapshot_document(source)
    nodes = doc['nodes']
    for name, roots in [('hidden', hidden_roots), ('state', state_roots),
                        ('boundary', boundary_roots)]:
        if not set(roots) <= nodes.keys():
            raise ValueError('unknown ' + name + ' root')
    if not boundary_roots:
        raise ValueError('explicit boundary review roots required')
    inventory = {row['path']: row for row in color_inventory(source)['entries']}

    def within(node_id, root_id):
        while node_id in nodes:
            if node_id == root_id:
                return True
            node_id = nodes[node_id]['parentId']
        return False

    def host(node_id):
        current = node_id
        while current in nodes:
            props = nodes[current]['props']
            if any(isinstance(paint, dict) and paint.get('visible', True) and
                   paint.get('opacity', 1) > 0 for paint in props.get('fills') or []):
                return current
            current = nodes[current]['parentId']
        raise ValueError('appearance channel without painted host: ' + node_id)

    entries = []
    required_boundary = set()
    groups = defaultdict(set)
    for entry in manifest['entries']:
        path = entry['path']
        source_row = inventory.get(path)
        if not source_row or source_row['inactive']:
            continue
        node_id = entry.get('nodeId') or parts(path)[1]
        role = entry['role'].lower()
        alpha_paths = _alpha_paths(doc, path)
        appearance = any(token in role for token in
                         ('text', 'title', 'atmosphere', 'fade', 'transition'))
        gradient = '/gradientStops/' in path
        if not (alpha_paths or appearance or gradient):
            continue
        if any(within(node_id, root) for root in hidden_roots):
            decision = 'remove-visually'
        elif nodes[node_id]['props'].get('isMask') or 'structure' in role:
            decision = 'preserve-structural'
        elif any(within(node_id, root) for root in state_roots):
            decision = 'preserve-state'
        else:
            decision = 'recompute-appearance'
        if decision == 'preserve-state' and not any(word in role for word in
                                                  ('state', 'disabled', 'locked')):
            raise ValueError('state root needs state role: ' + path)
        if decision == 'preserve-structural' and not any(word in role for word in
                                                       ('mask', 'structure')):
            raise ValueError('structural root needs structural role: ' + path)
        record = {'path': path, 'sourceAlphaPaths': alpha_paths,
                  'decision': decision, 'hostNodeIds': [host(node_id)],
                  'reviewSceneId': 'whole-page-1x'}
        if decision in ('recompute-appearance', 'remove-visually'):
            record['targetCompositeEvidenceId'] = 'native-preview:' + node_id
        entries.append(record)
        if gradient or 'atmosphere' in role:
            required_boundary.add(node_id)
            owners = [root for root in boundary_roots if within(node_id, root)]
            owner = owners[-1] if owners else boundary_roots[0]
            groups[owner].add(node_id)
    boundary_groups = [{'id': 'boundary:' + root, 'kind': 'surface-edge',
                        'nodeIds': sorted(ids), 'reviewSceneId': 'whole-page-1x',
                        'evidenceId': 'native-preview:' + root}
                       for root, ids in groups.items()]
    if required_boundary and not boundary_groups:
        raise ValueError('gradient/atmosphere boundary review missing')
    return {'schemaVersion': 1, 'sourceHash': digest(doc), 'entries': entries,
            'boundaryGroups': boundary_groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--hidden-root', action='append', default=[])
    parser.add_argument('--state-root', action='append', default=[])
    parser.add_argument('--boundary-root', action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    plan = build(json.loads(args.source.read_text()), json.loads(args.manifest.read_text()),
                 args.hidden_root, args.state_root, args.boundary_root)
    args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    print(json.dumps({'candidates': len(plan['entries']),
                      'boundaryGroups': len(plan['boundaryGroups'])}))


if __name__ == '__main__':
    main()

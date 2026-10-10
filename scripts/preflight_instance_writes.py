#!/usr/bin/env python3
"""Reject write plans that use setters blocked inside Figma instances.

This is a capability check, not a visual or full theme audit. Run it before the
only Figma write. A planned detach must name every instance ancestor and carry
an explicit post-detach node-mapping strategy.
"""

import argparse
import json
from pathlib import Path


INSTANCE_BLOCKED_PROPERTIES = frozenset({'vectorNetwork', 'vectorPaths'})


def inspect(source, plan):
    rows = {row['id']: row for row in source['nodes']}
    if len(rows) != len(source['nodes']):
        raise ValueError('duplicate source node IDs')
    if source.get('errors'):
        raise ValueError('source snapshot has read errors')
    if plan.get('sourceRootId') != source.get('rootId'):
        raise ValueError('write plan refers to a different source root')

    detach = set(plan.get('detachInstanceIds') or [])
    mapping = plan.get('postDetachMapping')
    invalid_detach = sorted(node_id for node_id in detach
                            if node_id not in rows or rows[node_id]['props'].get('type') != 'INSTANCE')
    detach_ancestor_gaps = []
    for node_id in detach - set(invalid_detach):
        cursor = rows[node_id].get('parentId')
        while cursor in rows:
            if rows[cursor]['props'].get('type') == 'INSTANCE' and cursor not in detach:
                detach_ancestor_gaps.append({'nodeId': node_id, 'missingAncestor': cursor})
            cursor = rows[cursor].get('parentId')
    blocked = []
    redundant = []
    unknown = []
    for index, op in enumerate(plan.get('operations') or []):
        node_id = op.get('sourceId')
        if node_id not in rows:
            unknown.append({'operation': index, 'sourceId': node_id})
            continue
        prop = op.get('property')
        # A color-only planner may accidentally schedule a setter because the
        # serialized Paint contains the *key* boundVariables, even when every
        # binding is empty and every target says preserve. Figma still rejects
        # vector-data setters in instances, so reject this plan before clone.
        if (prop in INSTANCE_BLOCKED_PROPERTIES and 'targets' in op
                and not op.get('changes') and all(t < 0 for t in op['targets'])):
            value = rows[node_id]['props'].get(prop)
            def active_binding(item):
                if isinstance(item, list):
                    return any(active_binding(part) for part in item)
                if isinstance(item, dict):
                    binding = item.get('boundVariables')
                    if isinstance(binding, dict) and any(binding.values()):
                        return True
                    return any(active_binding(part) for key, part in item.items()
                               if key != 'boundVariables')
                return False
            if not active_binding(value):
                redundant.append({'operation': index, 'sourceId': node_id,
                                  'property': prop,
                                  'reason': 'all targets preserve and no active color binding'})
                continue
        if prop not in INSTANCE_BLOCKED_PROPERTIES:
            continue
        ancestors = []
        cursor = rows[node_id].get('parentId')
        while cursor in rows:
            if rows[cursor]['props'].get('type') == 'INSTANCE':
                ancestors.append(cursor)
            cursor = rows[cursor].get('parentId')
        unresolved = [node for node in ancestors if node not in detach]
        if unresolved or (ancestors and mapping not in ('structural-fingerprint', 'verified-node-map')):
            blocked.append({'operation': index, 'sourceId': node_id,
                            'property': prop, 'instanceAncestors': ancestors,
                            'missingDetaches': unresolved,
                            'mappingRequired': bool(ancestors) and mapping not in
                            ('structural-fingerprint', 'verified-node-map')})

    errors = []
    if invalid_detach:
        errors.append({'kind': 'invalid-detach-targets', 'nodeIds': invalid_detach})
    if detach and mapping not in ('structural-fingerprint', 'verified-node-map'):
        errors.append({'kind': 'detach-mapping-required'})
    if detach_ancestor_gaps:
        errors.append({'kind': 'detach-ancestor-gaps', 'pairs': detach_ancestor_gaps})
    if unknown:
        errors.append({'kind': 'unknown-operation-targets', 'operations': unknown})
    if blocked:
        errors.append({'kind': 'instance-blocked-setters', 'operations': blocked})
    if redundant:
        errors.append({'kind': 'redundant-setters', 'operations': redundant})
    return {'status': 'fail' if errors else 'pass',
            'sourceRootId': source['rootId'],
            'plannedOperations': len(plan.get('operations') or []),
            'blockedSetterCount': len(blocked),
            'redundantSetterCount': len(redundant),
            'unknownTargetCount': len(unknown),
            'invalidDetachCount': len(invalid_detach),
            'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('write_plan', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(json.loads(args.source.read_text()),
                     json.loads(args.write_plan.read_text()))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({key: result[key] for key in
                      ('status', 'blockedSetterCount', 'redundantSetterCount', 'unknownTargetCount',
                       'invalidDetachCount')}, ensure_ascii=False))
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())

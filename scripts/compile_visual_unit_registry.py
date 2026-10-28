#!/usr/bin/env python3
"""Compile reviewed visual-unit roots into exact, single-owner carrier paths.

The caller authors unit roots, evidence, dependencies and review rules. This
compiler only projects those decisions over every source channel; it does not
infer visual semantics, occlusion, or a screenshot PASS.
"""
import argparse
import json
from pathlib import Path

from execution_audit import color_inventory, coverage, visual_units
from theme_audit import digest, parts, snapshot_document


def build(source, manifest, declarations, max_active_per_unit=75):
    doc = snapshot_document(source)
    nodes = doc['nodes']
    source_hash = digest(doc)
    if (declarations.get('schemaVersion') != 1 or
            declarations.get('sourceHash') != source_hash or
            not isinstance(declarations.get('units'), list) or
            not declarations['units']):
        raise ValueError('reviewed unit declarations must bind this source snapshot')
    if max_active_per_unit < 1:
        raise ValueError('max active carriers must be positive')
    if coverage(source, manifest)['status'] != 'pass':
        raise ValueError('complete reviewed manifest required')
    inventory = {item['path']: item for item in color_inventory(source)['entries']}
    known_paths = {item['path'] for item in manifest['entries']}
    if known_paths != inventory.keys():
        raise ValueError('manifest and inventory paths differ')
    reviewed = {}
    roots = {}
    for entry in declarations['units']:
        unit_id = entry.get('id')
        root_id = entry.get('rootNodeId')
        if not isinstance(unit_id, str) or not unit_id.strip() or unit_id in reviewed:
            raise ValueError('unique nonempty unit id required')
        if root_id not in nodes or root_id in roots:
            raise ValueError('unique source root node per visual unit required')
        if not isinstance(entry.get('basis'), str) or not entry['basis'].strip():
            raise ValueError('unit needs source hierarchy/rendering basis: ' + unit_id)
        for key in ('reviewRuleIds', 'extraDependencyNodeIds'):
            value = entry.get(key)
            if not isinstance(value, list) or len(value) != len(set(value)):
                raise ValueError(key + ' must be a unique list: ' + unit_id)
        if not entry['reviewRuleIds'] or any(not isinstance(v, str) or not v
                                          for v in entry['reviewRuleIds']):
            raise ValueError('reviewRuleIds must be nonempty: ' + unit_id)
        if not set(entry['extraDependencyNodeIds']) <= nodes.keys():
            raise ValueError('unknown extra dependency: ' + unit_id)
        review_nodes = entry.get('reviewNodeIds', [root_id])
        if (not isinstance(review_nodes, list) or not review_nodes or
                len(review_nodes) != len(set(review_nodes)) or
                not set(review_nodes) <= nodes.keys()):
            raise ValueError('invalid reviewNodeIds: ' + unit_id)
        reviewed[unit_id] = {**entry, 'reviewNodeIds': review_nodes}
        roots[root_id] = unit_id

    def lineage(node_id):
        chain = []
        while node_id in nodes:
            chain.append(node_id)
            if node_id == source['rootId']:
                return chain
            node_id = nodes[node_id]['parentId']
        raise ValueError('carrier disconnected from source root')

    carriers = {unit_id: [] for unit_id in reviewed}
    carrier_nodes = {unit_id: set() for unit_id in reviewed}
    active_counts = {unit_id: 0 for unit_id in reviewed}
    for path in sorted(known_paths):
        node_id = parts(path)[1]
        owner = next((roots[ancestor] for ancestor in lineage(node_id)
                      if ancestor in roots), None)
        if owner is None:
            raise ValueError('unassigned channel; add a reviewed containing unit: ' + path)
        carriers[owner].append(path)
        carrier_nodes[owner].add(node_id)
        if not inventory[path]['inactive']:
            active_counts[owner] += 1
    oversized = {key: count for key, count in active_counts.items()
                 if count > max_active_per_unit}
    if oversized:
        raise ValueError('review units too broad for active carriers: ' + str(oversized))
    units = []
    for unit_id, entry in reviewed.items():
        if not carriers[unit_id]:
            raise ValueError('reviewed unit has no color carriers: ' + unit_id)
        dependencies = set(carrier_nodes[unit_id]) | set(entry['extraDependencyNodeIds'])
        dependencies.add(entry['rootNodeId'])
        dependencies.update(entry['reviewNodeIds'])
        units.append({'id': unit_id, 'basis': entry['basis'],
                      'carrierPaths': carriers[unit_id],
                      'dependencyNodeIds': sorted(dependencies),
                      'reviewNodeIds': entry['reviewNodeIds'],
                      'reviewRuleIds': entry['reviewRuleIds']})
    registry = {'schemaVersion': 1, 'sourceHash': source_hash, 'units': units}
    audit = visual_units(source, manifest, registry)
    if audit['status'] != 'pass':
        raise ValueError('compiled visual units fail carrier coverage')
    return {'registry': registry,
            'report': {'status': 'ready-for-rule-scope-review',
                       'sourceHash': source_hash, 'unitCount': len(units),
                       'carrierCount': len(known_paths),
                       'activeCarrierCount': sum(active_counts.values()),
                       'activeCarriersByUnit': active_counts,
                       'registryHash': digest(registry),
                       'note': 'Only exact structural ownership passed. Rule scopes, sibling overlays and native visual review remain required.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('reviewed_units', type=Path)
    parser.add_argument('--max-active-per-unit', type=int, default=75)
    parser.add_argument('--out-registry', type=Path, required=True)
    parser.add_argument('--out-report', type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.source.read_text()),
                   json.loads(args.manifest.read_text()),
                   json.loads(args.reviewed_units.read_text()),
                   args.max_active_per_unit)
    args.out_registry.write_text(json.dumps(result['registry'], ensure_ascii=False, indent=2))
    args.out_report.write_text(json.dumps(result['report'], ensure_ascii=False, indent=2))
    print(json.dumps({k: result['report'][k] for k in
                      ('status', 'unitCount', 'carrierCount', 'activeCarrierCount')}))


if __name__ == '__main__':
    main()

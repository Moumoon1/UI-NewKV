#!/usr/bin/env python3
"""Make a compact, lossless review index for one frozen Figma source snapshot.

This indexes channels by actual node and visual region. It deliberately does
not guess semantic roles or mark Phase 1W complete: a reviewer must assign
the role, protection decision, and target recipe for every active channel.
"""
import argparse
from collections import defaultdict
from pathlib import Path

from execution_audit import color_inventory
from theme_audit import read_json, save_json, snapshot_document


def build(snapshot, region_depth=2):
    if region_depth < 0:
        raise ValueError('region depth must be non-negative')
    doc = snapshot_document(snapshot)
    nodes = doc['nodes']
    root_id = snapshot['rootId']
    inventory = color_inventory(snapshot)
    grouped = defaultdict(list)
    for entry in inventory['entries']:
        if not entry['inactive']:
            grouped[entry['nodeId']].append(entry['path'])

    def ancestry(node_id):
        chain = []
        seen = set()
        while node_id in nodes:
            if node_id in seen:
                raise ValueError('parent cycle at ' + node_id)
            seen.add(node_id)
            chain.append(node_id)
            if node_id == root_id:
                break
            node_id = nodes[node_id]['parentId']
        if not chain or chain[-1] != root_id:
            raise ValueError('node disconnected from source root: ' + chain[0])
        return list(reversed(chain))

    records = []
    region_counts = defaultdict(lambda: {'nodes': 0, 'activeChannels': 0})
    for node_id, paths in grouped.items():
        row = nodes[node_id]
        props = row['props']
        chain = ancestry(node_id)
        region_id = chain[min(region_depth, len(chain) - 1)]
        names = [nodes[item]['props'].get('name', '') for item in chain]
        record = {
            'nodeId': node_id,
            'regionId': region_id,
            'regionName': nodes[region_id]['props'].get('name', ''),
            'ancestry': list(zip(chain, names)),
            'type': props.get('type'),
            'name': props.get('name', ''),
            'textPreview': (props.get('characters') or '')[:100],
            'bounds': [props.get(key) for key in ('x', 'y', 'width', 'height')],
            'hasImageFill': any(isinstance(p, dict) and p.get('type') == 'IMAGE'
                                for p in props.get('fills') or []),
            'isMask': bool(props.get('isMask')),
            'activeChannelPaths': sorted(paths),
            'needsSemanticClassification': True,
        }
        records.append(record)
        region_counts[region_id]['nodes'] += 1
        region_counts[region_id]['activeChannels'] += len(paths)
    records.sort(key=lambda row: (row['regionId'], row['ancestry'], row['nodeId']))
    regions = [{'id': region_id,
                'name': nodes[region_id]['props'].get('name', ''), **counts}
               for region_id, counts in region_counts.items()]
    regions.sort(key=lambda row: (-row['activeChannels'], row['id']))
    active_count = sum(len(row['activeChannelPaths']) for row in records)
    return {
        'schemaVersion': 1,
        'sourceHash': inventory['sourceHash'],
        'rootId': root_id,
        'regionDepth': region_depth,
        'activeChannels': active_count,
        'inactiveChannels': len(inventory['entries']) - active_count,
        'nodesNeedingClassification': len(records),
        'regions': regions,
        'nodes': records,
        'status': 'review-index-only',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--region-depth', type=int, default=2)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = build(read_json(args.source), args.region_depth)
    save_json(args.out, report)
    print({'activeChannels': report['activeChannels'],
           'nodesNeedingClassification': report['nodesNeedingClassification'],
           'regions': len(report['regions'])})


if __name__ == '__main__':
    main()

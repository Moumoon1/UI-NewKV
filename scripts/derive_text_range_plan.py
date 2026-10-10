#!/usr/bin/env python3
"""Expand every visible styled text range into exact channel/host obligations.

The returned relationships freeze scope and a cross-mode minimum. They do not
invent pixel samples or assert that the rendered text is legible.
"""
import argparse
import json
from pathlib import Path

from execution_audit import _visible_nodes, color_inventory
from theme_audit import digest, escape, snapshot_document


def build(source, manifest, media_cover_ids=(), disabled_root_ids=()):
    doc = snapshot_document(source)
    visible = _visible_nodes(doc, source['rootId'])
    covers = set(media_cover_ids)
    if not covers <= doc['nodes'].keys():
        raise ValueError('unknown protected media cover root')
    disabled_roots = set(disabled_root_ids)
    if any(root not in doc['nodes'] or doc['nodes'][root]['props'].get('opacity') != .5
           for root in disabled_roots):
        raise ValueError('disabled roots must be actual 50% visual units')
    inventory = {row['path'] for row in color_inventory(source)['entries']}
    indexed = {row['path']: row for row in manifest['entries']}
    if len(indexed) != len(manifest['entries']):
        raise ValueError('duplicate manifest paths')

    def ancestors(node_id):
        cursor = doc['nodes'][node_id]['parentId']
        while cursor in doc['nodes']:
            yield cursor
            cursor = doc['nodes'][cursor]['parentId']

    def rendered_host(node_id):
        hosts = []
        for parent in ancestors(node_id):
            row = doc['nodes'][parent]['props']
            if any(isinstance(paint, dict) and paint.get('visible', True) and
                   paint.get('opacity', 1) > 0 for paint in row.get('fills') or []):
                hosts.append(parent)
        if not hosts:
            raise ValueError('visible text has no painted host: ' + node_id)
        return hosts

    entries, relationships = [], []
    for node_id, row in doc['nodes'].items():
        props = row['props']
        if not visible.get(node_id) or props.get('type') != 'TEXT' or not props.get('characters'):
            continue
        source_runs = props.get('textRuns', {}).get('fills') or []
        if not source_runs:
            raise ValueError('visible text missing styled fill runs: ' + node_id)
        media_cover = next((root for root in covers if root in (node_id, *ancestors(node_id))), None)
        disabled_root = next((root for root in disabled_roots
                              if root in (node_id, *ancestors(node_id))), None)
        ranges = []
        for index, run in enumerate(source_runs):
            prefix = '/nodes/' + escape(node_id) + '/props/textRuns/fills/' + str(index) + '/'
            channels = sorted(path for path in inventory if path.startswith(prefix))
            if not channels:
                raise ValueError('styled text range has no color channels: ' + node_id)
            dispositions = {indexed.get(path, {}).get('disposition') for path in channels}
            if media_cover:
                if dispositions != {'preserve'}:
                    raise ValueError('media-cover text must preserve exact colors: ' + node_id)
                ranges.append({'start': run['start'], 'end': run['end'], 'channelPaths': channels,
                    'action': 'protected', 'role': 'protected-media-overlay',
                    'reason': 'Visible label inside the exact media cover.',
                    'protectionClass': 'protected-media-overlay', 'coverNodeId': media_cover})
                continue
            if len(dispositions) != 1 or not dispositions <= {'change', 'preserve'}:
                raise ValueError('mixed or unclassified text range: ' + node_id)
            hosts = rendered_host(node_id)
            pair_id = 'text:' + node_id + ':' + str(index)
            role = indexed[channels[0]].get('role', 'text')
            ranges.append({'start': run['start'], 'end': run['end'], 'channelPaths': channels,
                'action': dispositions.pop(), 'role': role,
                'reason': 'Styled range reviewed on all painted ancestor hosts.',
                'hostNodeIds': hosts, 'contrastPairIds': [pair_id],
                **({'disabledStateRootId': disabled_root} if disabled_root else {})})
            relationships.append({'id': pair_id, 'kind': 'text',
                'nodeIds': [node_id] + hosts, 'sampleIds': ['native-range'],
                **({'disabledStateRootId': disabled_root} if disabled_root else {}),
                'minimumContrast': 3 if manifest.get('themeTransition') in
                    ('dark-to-light', 'light-to-dark') and not disabled_root else None})
        entries.append({'nodeId': node_id, 'ranges': ranges})
    return {'schemaVersion': 1, 'sourceHash': digest(doc), 'entries': entries}, relationships


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--media-cover', action='append', default=[])
    parser.add_argument('--disabled-root', action='append', default=[])
    parser.add_argument('--out-plan', type=Path, required=True)
    parser.add_argument('--out-relationships', type=Path, required=True)
    args = parser.parse_args()
    plan, relationships = build(json.loads(args.source.read_text()),
                                json.loads(args.manifest.read_text()), args.media_cover,
                                args.disabled_root)
    args.out_plan.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    args.out_relationships.write_text(json.dumps(relationships, ensure_ascii=False, indent=2))
    print(json.dumps({'textNodes': len(plan['entries']),
                      'contrastPairs': len(relationships)}, ensure_ascii=False))


if __name__ == '__main__':
    main()

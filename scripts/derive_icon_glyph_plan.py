#!/usr/bin/env python3
"""Expand explicitly reviewed Icon roots into channel-level audit obligations.

This tool does not discover semantic Icon roots from node names or colors. The
caller must supply the roots identified in the source rendering, and preserved
glyphs must carry individual neutral evidence.
"""
import argparse
import json
from pathlib import Path

from execution_audit import _visible_nodes, color_inventory
from theme_audit import digest, snapshot_document


def build(source, manifest, icon_roots, neutral_evidence=None):
    doc = snapshot_document(source)
    nodes = doc['nodes']
    visible = _visible_nodes(doc, source['rootId'])
    inventory = {row['path']: row for row in color_inventory(source)['entries']
                 if not row['inactive'] and visible.get(row['nodeId'])}
    classified = {row['path']: row for row in manifest['entries']}
    neutral_evidence = neutral_evidence or {}
    if len(classified) != len(manifest['entries']):
        raise ValueError('duplicate color manifest path')
    if not icon_roots or len(icon_roots) != len(set(icon_roots)):
        raise ValueError('explicit unique Icon roots required')
    if not set(icon_roots) <= nodes.keys():
        raise ValueError('unknown Icon root')

    def within(node_id, root_id):
        while node_id in nodes:
            if node_id == root_id:
                return True
            node_id = nodes[node_id]['parentId']
        return False

    roots = []
    for root_id in icon_roots:
        channels = []
        for path, item in inventory.items():
            node_id = item['nodeId']
            if not within(node_id, root_id):
                continue
            entry = classified.get(path)
            if not entry or entry['disposition'] not in ('change', 'preserve'):
                raise ValueError('Icon channel unclassified: ' + path)
            if nodes[node_id]['props'].get('isMask'):
                part = 'protected'
            elif '/props/effects/' in path:
                part = 'reflection'
            elif node_id == root_id and nodes[node_id]['props'].get('type') in ('FRAME', 'GROUP'):
                part = 'container'
            else:
                part = 'glyph'
            action = 'protected' if part == 'protected' else entry['disposition']
            if part == 'protected' and entry['disposition'] != 'preserve':
                raise ValueError('structural Icon mask must preserve color: ' + path)
            channel = {'path': path, 'part': part, 'action': action,
                       'reason': entry['reason']}
            if part == 'glyph' and action == 'preserve':
                evidence = neutral_evidence.get(path)
                if not isinstance(evidence, str) or not evidence.strip():
                    raise ValueError('preserved Icon glyph needs exact neutral evidence: ' + path)
                channel.update(themeNeutral=True, neutralEvidence=evidence)
            channels.append(channel)
        if not channels:
            raise ValueError('Icon root has no visible color channels: ' + root_id)
        roots.append({'rootNodeId': root_id, 'channels': channels})
    return {'schemaVersion': 1, 'sourceHash': digest(doc), 'roots': roots}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--root', action='append', required=True)
    parser.add_argument('--neutral-evidence', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.neutral_evidence.read_text()) if args.neutral_evidence else {}
    plan = build(json.loads(args.source.read_text()), json.loads(args.manifest.read_text()),
                 args.root, evidence)
    args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    print(json.dumps({'iconRoots': len(plan['roots']),
                      'channels': sum(len(root['channels']) for root in plan['roots'])}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""List every frozen contrast sample with conservative property candidates.

This is a review queue, not contrast evidence. A candidate is only a possible
solid layer; native screenshots must establish the actual rendered host before
an author writes contrastSamples.json.
"""
import argparse
import json
from pathlib import Path

from theme_audit import at, digest, escape, snapshot_document


def _solid_paint(doc, color_path):
    try:
        paint = at(doc, color_path.rsplit('/', 1)[0])
        color = at(doc, color_path)
    except (KeyError, IndexError, ValueError, TypeError):
        return None
    if (not isinstance(paint, dict) or paint.get('type') != 'SOLID' or
            paint.get('visible') is False or paint.get('blendMode', 'NORMAL') != 'NORMAL' or
            not isinstance(color, dict) or
            not all(k in color for k in ('r', 'g', 'b'))):
        return None
    return paint, color


def _opaque_solid(doc, node_id, color_path):
    value = _solid_paint(doc, color_path)
    if not value or value[0].get('opacity', 1) != 1 or value[1].get('a', 1) != 1:
        return False
    cursor = node_id
    while cursor in doc['nodes']:
        row = doc['nodes'][cursor]
        if row['props'].get('opacity', 1) != 1:
            return False
        cursor = row['parentId']
    return True


def _candidate(doc, node_id, path):
    if not path or not _opaque_solid(doc, node_id, path):
        return None
    return {'layers': [{'colorPath': path}]}


def _foreground_candidate(doc, node_id, path, host_id, background):
    value = _solid_paint(doc, path) if path else None
    if not value or not host_id:
        return None
    paint, color = value
    props = doc['nodes'][node_id]['props']
    if any(isinstance(item, dict) and item.get('visible', True)
           for key in ('strokes', 'effects') for item in props.get(key) or []):
        return None
    cursor = doc['nodes'][node_id]['parentId']
    while cursor != host_id:
        if cursor not in doc['nodes'] or doc['nodes'][cursor]['props'].get('opacity', 1) != 1:
            return None
        cursor = doc['nodes'][cursor]['parentId']
    alpha_paths = []
    if paint.get('opacity', 1) != 1:
        if 'opacity' not in paint:
            return None
        alpha_paths.append(path.rsplit('/', 1)[0] + '/opacity')
    if props.get('opacity', 1) != 1:
        if 'opacity' not in props:
            return None
        alpha_paths.append('/nodes/' + escape(node_id) + '/props/opacity')
    layer = {'colorPath': path, 'alphaPaths': alpha_paths}
    if (paint.get('opacity', 1) == 1 and color.get('a', 1) == 1 and
            props.get('opacity', 1) == 1):
        return {'layers': [layer]}
    if background is None:
        return None
    return {'layers': background['layers'] + [layer]}


def _host_path(doc, host_id):
    props = doc['nodes'][host_id]['props']
    fills = props.get('fills')
    if (not isinstance(fills, list) or len(fills) != 1 or
            any(effect.get('visible', True) for effect in props.get('effects') or []
                if isinstance(effect, dict))):
        return None
    return '/nodes/' + escape(host_id) + '/props/fills/0/color'


def build(source, projected, manifest, rule_ledger):
    before = snapshot_document(source)
    after = snapshot_document(projected)
    if set(before['nodes']) != set(after['nodes']):
        raise ValueError('source and projected nodes must share source IDs')
    plan = manifest.get('textRangePlan', {})
    if plan.get('sourceHash') != digest(before):
        raise ValueError('text range plan source hash mismatch')
    rules = {row['id']: row for row in rule_ledger.get('rules', [])}
    verifier = rules.get('contrast-baseline', {}).get('verifier', {})
    relations = verifier.get('relationships')
    if not isinstance(relations, list) or not relations:
        raise ValueError('frozen contrast relationships required')
    ranges = {}
    for node in plan.get('entries', []):
        for run in node.get('ranges', []):
            for pair_id in run.get('contrastPairIds', []):
                if pair_id in ranges:
                    raise ValueError('duplicate text contrast pair: ' + pair_id)
                ranges[pair_id] = (node['nodeId'], run)
    queue = []
    for pair in relations:
        pair_id = pair['id']
        if pair_id not in ranges:
            raise ValueError('frozen contrast pair lacks reviewed text range: ' + pair_id)
        node_id, run = ranges[pair_id]
        if pair.get('kind') != 'text' or pair.get('nodeIds', [None])[0] != node_id:
            raise ValueError('contrast pair kind or text node differs from range plan')
        hosts = run.get('hostNodeIds') or []
        nearest = hosts[0] if hosts else None
        if nearest and nearest not in before['nodes']:
            raise ValueError('unknown painted host: ' + nearest)
        paths = run.get('channelPaths') or []
        foreground = paths[0] if len(paths) == 1 else None
        background = _host_path(before, nearest) if nearest else None
        candidates = {}
        for label, doc in (('source', before), ('actual', after)):
            host_candidate = _candidate(doc, nearest, background) if nearest else None
            candidates[label] = {
                'foreground': _foreground_candidate(doc, node_id, foreground,
                                                    nearest, host_candidate),
                'background': host_candidate,
            }
        needs = []
        if not all(candidates[k]['foreground'] for k in candidates):
            needs.append('foreground-gradient-multiple-or-unresolved-composite')
        if not all(candidates[k]['background'] for k in candidates):
            needs.append('host-gradient-multiple-or-unresolved-composite')
        # Even two solid property candidates do not prove that a sibling IMAGE,
        # overlay, mask or effect leaves the painted ancestor visible at the text.
        needs.append('native-host-and-glyph-review')
        queue.append({'pairId': pair_id, 'nodeId': node_id,
                      'text': before['nodes'][node_id]['props'].get('characters', ''),
                      'range': [run.get('start'), run.get('end')],
                      'role': run.get('role'), 'hostNodeIds': hosts,
                      'channelPaths': paths, 'sampleIds': pair.get('sampleIds'),
                      'candidates': candidates, 'needsReview': needs,
                      'reviewed': False})
    return {'schemaVersion': 1, 'status': 'needs-review',
            'sourceHash': digest(before), 'actualHash': digest(after),
            'policy': verifier.get('policy', 'source-baseline'),
            'decisionContext': verifier.get('decisionContext'),
            'pairCount': len(queue),
            'solidCandidatePairs': sum(all(row['candidates'][k][side]
                    for k in ('source', 'actual') for side in ('foreground', 'background'))
                    for row in queue), 'queue': queue,
            'note': 'Property candidates are not native screenshot evidence or contrast PASS.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('source', 'projected', 'manifest', 'rule_ledger'):
        parser.add_argument(field, type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = build(*(json.loads(getattr(args, field).read_text()) for field in
                     ('source', 'projected', 'manifest', 'rule_ledger')))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'status': result['status'], 'pairCount': result['pairCount'],
                      'solidCandidatePairs': result['solidCandidatePairs']}))


if __name__ == '__main__':
    main()

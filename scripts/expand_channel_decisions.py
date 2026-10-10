#!/usr/bin/env python3
"""Expand reviewed semantic rules into a path-exact color manifest draft.

This is a planning aid, not a semantic classifier or a visual PASS. Broad rules
must acknowledge the exact set of source paths they matched. Unresolved paths,
overlap conflicts and protection risks remain visible in the report.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from execution_audit import color_inventory, coverage, _visible_nodes
from theme_audit import escape, snapshot_document


def _hex(color):
    return '#' + ''.join(f'{round(color[k] * 255):02X}' for k in 'rgb')


def _rgb(value):
    if isinstance(value, str) and len(value) == 7 and value.startswith('#'):
        try:
            numbers = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        except ValueError as exc:
            raise ValueError('target must be #RRGGBB') from exc
        return dict(zip('rgb', numbers))
    if isinstance(value, dict) and all(k in value for k in 'rgb'):
        return {k: value[k] for k in 'rgb'}
    raise ValueError('target must be #RRGGBB or RGB object')


def paths_hash(paths):
    payload = json.dumps(sorted(paths), ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _ancestors(nodes, node_id):
    result = []
    while node_id in nodes:
        result.append(node_id)
        node_id = nodes[node_id]['parentId']
    return result


def _channel_kind(path):
    if '/textRuns/' in path:
        return 'styled-text'
    if '/vectorNetwork/' in path:
        return 'vector-mirror'
    if '/effects/' in path:
        return 'effect'
    if '/strokes/' in path:
        return 'stroke'
    if '/gradientStops/' in path:
        return 'gradient-stop'
    return 'fill-or-other'


def _match(selector, item, nodes, ancestry):
    if not isinstance(selector, dict) or not selector:
        raise ValueError('rule selector must be a non-empty object')
    allowed = {'path', 'nodeId', 'subtreeId', 'nodeType', 'name',
               'sourceHex', 'channelKind'}
    if set(selector) - allowed:
        raise ValueError('unknown selector keys: ' + ','.join(sorted(set(selector) - allowed)))
    node_id = item['nodeId']
    props = nodes[node_id]['props']
    checks = {
        'path': item['path'], 'nodeId': node_id,
        'subtreeId': ancestry[node_id], 'nodeType': props.get('type'),
        'name': props.get('name'), 'sourceHex': _hex(item['source']),
        'channelKind': _channel_kind(item['path']),
    }
    return all((expected in checks[key] if key == 'subtreeId'
                else expected == checks[key]) for key, expected in selector.items())


def _scope_risk(rule, paths, matched, nodes, ancestry):
    if not paths or rule.get('disposition') != 'preserve' or not str(rule.get('role', '')).startswith('protected'):
        return []
    risks = []
    for path in paths:
        node_id = matched[path]['nodeId']
        names = [nodes[ancestor]['props'].get('name', '') for ancestor in ancestry[node_id]]
        text = nodes[node_id]['props'].get('characters', '')
        action_words = ('button', 'cta', '按钮', '去发布', '领取', '提交', '参与', '生成')
        if any(word in name.lower() for name in names for word in action_words) or any(
                word in text for word in ('去发布', '领取', '提交', '参与', '生成')):
            risks.append({'path': path, 'nodeId': node_id,
                          'error': 'broad protection may include editable action'})
    return risks


def build(source, decisions):
    doc = snapshot_document(source)
    nodes = doc['nodes']
    inventory = color_inventory(source)
    source_hash = inventory['sourceHash']
    if decisions.get('schemaVersion') != 1 or decisions.get('sourceHash') != source_hash:
        raise ValueError('decisions must match this complete source snapshot')
    rules = decisions.get('rules')
    if not isinstance(rules, list):
        raise ValueError('rules list required')
    if len({r.get('id') for r in rules}) != len(rules):
        raise ValueError('duplicate rule id')
    if any(not isinstance(r.get('id'), str) or not r['id'].strip() for r in rules):
        raise ValueError('every rule needs a non-empty id')
    ancestry = {node_id: _ancestors(nodes, node_id) for node_id in nodes}
    active = {item['path']: item for item in inventory['entries'] if not item['inactive']}
    grouped = defaultdict(list)
    for item in active.values():
        props = nodes[item['nodeId']]['props']
        grouped[(props.get('type'), _hex(item['source']))].append(item)
    group_index = []
    for (node_type, source_hex), items in grouped.items():
        paths = sorted(item['path'] for item in items)
        contexts = []
        seen_contexts = set()
        for item in items:
            node_id = item['nodeId']
            chain = list(reversed(ancestry[node_id]))
            region = chain[min(2, len(chain) - 1)]
            props = nodes[node_id]['props']
            context = (region, props.get('name', ''),
                       (props.get('characters') or '')[:60], _channel_kind(item['path']))
            if context not in seen_contexts:
                seen_contexts.add(context)
                contexts.append({'regionId': region,
                                 'regionName': nodes[region]['props'].get('name', ''),
                                 'nodeId': node_id, 'name': props.get('name', ''),
                                 'textPreview': context[2], 'channelKind': context[3]})
        group_index.append({'suggestedSelector': {'nodeType': node_type,
                                                   'sourceHex': source_hex},
                            'matchedCount': len(paths), 'matchedPaths': paths,
                            'reviewedPathsHash': paths_hash(paths),
                            'contexts': contexts,
                            'crossContext': len({c['regionId'] for c in contexts}) > 1 or
                                            len({c['channelKind'] for c in contexts}) > 1})
    group_index.sort(key=lambda row: (-row['matchedCount'],
                                      row['suggestedSelector']['nodeType'],
                                      row['suggestedSelector']['sourceHex']))
    matches = defaultdict(list)
    rule_matches = []
    invalid_rules = []
    for rule in rules:
        selector = rule.get('selector')
        if not isinstance(selector, dict) or not selector:
            raise ValueError('rule selector must be a non-empty object')
        if selector.get('subtreeId') == source['rootId'] and len(selector) == 1:
            raise ValueError('unqualified source-root catch-all is forbidden')
        if any(k in selector and selector[k] not in nodes for k in ('nodeId', 'subtreeId')):
            raise ValueError('unknown selected node')
        paths = [item['path'] for item in inventory['entries']
                 if not item['inactive'] and _match(selector, item, nodes, ancestry)]
        actual_hash = paths_hash(paths)
        acknowledgement = rule.get('reviewedPathsHash')
        if len(paths) > 1 and acknowledgement != actual_hash:
            invalid_rules.append({'ruleId': rule['id'], 'error': 'matched path set not reviewed',
                                  'expectedReviewedPathsHash': actual_hash})
        if not paths:
            invalid_rules.append({'ruleId': rule['id'], 'error': 'rule matches no active source paths'})
        for key in ('role', 'reason', 'ruleId'):
            if not isinstance(rule.get(key), str) or not rule[key].strip():
                invalid_rules.append({'ruleId': rule['id'], 'error': key + ' required'})
        if rule.get('disposition') not in ('change', 'preserve'):
            invalid_rules.append({'ruleId': rule['id'], 'error': 'active channels require change/preserve'})
        if rule.get('disposition') == 'change':
            for key in ('recipeId', 'sceneId'):
                if not isinstance(rule.get(key), str) or not rule[key].strip():
                    invalid_rules.append({'ruleId': rule['id'], 'error': key + ' required'})
            try:
                _rgb(rule.get('target'))
            except ValueError as exc:
                invalid_rules.append({'ruleId': rule['id'], 'error': str(exc)})
        if rule.get('anchorId') is not None:
            if (rule.get('anchorId') not in
                    {'background', 'card', 'number', 'icon', 'button', 'tab'} or
                    rule.get('disposition') != 'change'):
                invalid_rules.append({'ruleId': rule['id'],
                                      'error': 'anchorId requires a changed color rule'})
        rule_matches.append({'ruleId': rule['id'], 'matchedPaths': sorted(paths),
                             'matchedCount': len(paths), 'reviewedPathsHash': actual_hash})
        for path in paths:
            matches[path].append(rule)
    conflicts = []
    entries = []
    selected_by_path = {}
    for item in inventory['entries']:
        path = item['path']
        if item['inactive']:
            entries.append({'path': path, 'nodeId': item['nodeId'],
                            'role': 'inactive-stored', 'disposition': 'ignore',
                            'reason': 'Source channel is hidden or has zero effective alpha.',
                            'ruleId': 'inactive-source-channel'})
            continue
        candidates = matches[path]
        if not candidates:
            continue
        if len(candidates) > 1:
            overrides = [r for r in candidates if r['selector'].get('path') == path and
                         set(r.get('overrides', [])) == {x['id'] for x in candidates if x is not r}]
            if len(overrides) != 1:
                conflicts.append({'path': path, 'ruleIds': [r['id'] for r in candidates]})
                continue
            selected = overrides[0]
        else:
            selected = candidates[0]
        selected_by_path[path] = selected
        entry = {'path': path, 'nodeId': item['nodeId'],
                 'role': selected.get('role'), 'disposition': selected.get('disposition'),
                 'reason': selected.get('reason'), 'ruleId': selected.get('ruleId')}
        if selected.get('disposition') == 'change' and selected.get('target') is not None:
            try:
                entry['target'] = {**item['source'], **_rgb(selected['target'])}
            except ValueError:
                pass  # Invalid-rule report and coverage retain the failure.
            entry.update(recipeId=selected.get('recipeId'),
                         sceneId=selected.get('sceneId'))
            if selected.get('anchorId') is not None:
                entry['anchorId'] = selected['anchorId']
        entries.append(entry)
    unresolved = sorted(set(active) - {entry['path'] for entry in entries})
    protection_risks = []
    for rule, match in zip(rules, rule_matches):
        selected_paths = [path for path in match['matchedPaths']
                          if selected_by_path.get(path) is rule]
        protection_risks.extend(_scope_risk(rule, selected_paths, active,
                                            nodes, ancestry))
    visible = _visible_nodes(doc, source['rootId'])
    text_review, icon_review = [], []
    by_node = defaultdict(list)
    for item in inventory['entries']:
        if not item['inactive']:
            by_node[item['nodeId']].append(item['path'])
    for node_id, row in nodes.items():
        props = row['props']
        if not visible.get(node_id):
            continue
        if props.get('type') == 'TEXT' and props.get('characters'):
            runs = []
            for index, run in enumerate(props.get('textRuns', {}).get('fills') or []):
                prefix = '/nodes/' + escape(node_id) + '/props/textRuns/fills/' + str(index) + '/'
                runs.append({'start': run.get('start'), 'end': run.get('end'),
                             'channelPaths': [p for p in by_node[node_id] if p.startswith(prefix)]})
            text_review.append({'nodeId': node_id, 'name': props.get('name'),
                                'text': props.get('characters'), 'fontSize': props.get('fontSize'),
                                'runs': runs, 'titleCandidate': bool((props.get('fontSize') or 0) >= 18)})
        if props.get('type') in ('VECTOR', 'BOOLEAN_OPERATION', 'ELLIPSE') and by_node[node_id]:
            icon_review.append({'nodeId': node_id, 'name': props.get('name'),
                                'type': props.get('type'), 'channelPaths': by_node[node_id],
                                'review': 'icon-glyph-or-surface-or-decoration'})
    manifest = {'schemaVersion': 1, 'sourceHash': source_hash,
                'entries': entries}
    if decisions.get('themeTransition'):
        manifest['themeTransition'] = decisions['themeTransition']
    if decisions.get('schemeAnchorContract'):
        manifest['schemeAnchorContract'] = decisions['schemeAnchorContract']
    cover = coverage(source, manifest)
    status = ('ready-for-semantic-review' if not (unresolved or conflicts or invalid_rules
              or protection_risks or cover['status'] != 'pass') else 'needs-review')
    return {'schemaVersion': 1, 'sourceHash': source_hash, 'status': status,
            'activeChannels': len(active), 'resolvedActiveChannels': len(active) - len(unresolved),
            'unresolvedPaths': unresolved, 'conflicts': conflicts,
            'invalidRules': invalid_rules, 'protectionRisks': protection_risks,
            'ruleMatches': rule_matches, 'coverage': cover,
            'suggestedGroups': group_index,
            'textRangeReview': text_review, 'iconAndSurfaceReview': icon_review,
            'manifestDraft': manifest,
            'note': 'No semantic or visual PASS. Review titles, icons, material, protection and hosts separately.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('decisions', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--out-manifest', type=Path)
    args = parser.parse_args()
    report = build(json.loads(args.source.read_text()),
                   json.loads(args.decisions.read_text()))
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out_manifest:
        payload = (report['manifestDraft'] if report['status'] == 'ready-for-semantic-review'
                   else {'schemaVersion': 1, 'sourceHash': report['sourceHash'],
                         'status': 'needs-review', 'entries': [],
                         'reason': 'Do not use: semantic decision expansion is incomplete.'})
        args.out_manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps({'status': report['status'], 'active': report['activeChannels'],
                      'resolved': report['resolvedActiveChannels'],
                      'unresolved': len(report['unresolvedPaths']),
                      'conflicts': len(report['conflicts']),
                      'protectionRisks': len(report['protectionRisks'])}))


if __name__ == '__main__':
    main()

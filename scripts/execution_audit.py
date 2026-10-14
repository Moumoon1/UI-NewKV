#!/usr/bin/env python3
"""Coverage, completion, batching and timings. Offline; never edits Figma."""
import argparse
import colorsys
from collections import Counter
import math
import re
import sys

from theme_audit import (MISSING, at, canonical, compare, digest, equal, escape,
                         check_gate, color_relations, mapped_document, overlaps, parts, policy_check, scene_state,
                         read_json, save_json, snapshot_document, target_equal)
from contrast_audit import compare_contrast, displayed_color, luminance


def color_inventory(snapshot):
    doc = snapshot_document(snapshot)
    entries = []

    def scan(value, path, node_id, inactive, gradient=False):
        if isinstance(value, dict):
            if all(k in value for k in ('r', 'g', 'b')):
                if not all(type(value[k]) in (int, float) and math.isfinite(value[k])
                           and 0 <= value[k] <= 1 for k in ('r', 'g', 'b')):
                    raise ValueError('invalid RGB: ' + path)
                entries.append({'path': path, 'nodeId': node_id, 'source': value,
                                'inactive': inactive or (value.get('a') == 0 and not gradient)})
                return
            hidden = inactive or value.get('visible') is False or value.get('opacity') == 0
            if str(value.get('type', '')).startswith('GRADIENT_'):
                gradient = True
                stops = value.get('gradientStops', [])
                hidden = hidden or bool(stops) and all(s.get('color', {}).get('a', 1) == 0 for s in stops)
            for key, child in value.items():
                scan(child, path + '/' + escape(key), node_id, hidden, gradient)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                scan(child, path + '/' + str(i), node_id, inactive, gradient)

    def visit(node_id, inactive=False):
        row = doc['nodes'][node_id]
        props = row['props']
        hidden = inactive or props.get('visible') is False or props.get('opacity') == 0
        base = '/nodes/' + escape(node_id) + '/props/'
        for key in ('fills', 'strokes', 'effects', 'vectorNetwork', 'textDecorationColor'):
            if key in props:
                scan(props[key], base + key, node_id, hidden)
        for key in ('fills', 'textDecorationColor'):
            if key in props.get('textRuns', {}):
                scan(props['textRuns'][key], base + 'textRuns/' + key, node_id, hidden)
        for child in row['children']:
            visit(child, hidden)

    visit(snapshot['rootId'])
    return {'schemaVersion': 1, 'sourceHash': digest(doc), 'entries': entries,
            'count': len(entries), 'note': 'Stored channels, not inferred semantic or raster coverage.'}


def color_binding_audit(snapshot):
    """Fail if a deliverable clone still depends on a color variable/style."""
    doc = snapshot_document(snapshot)
    residual = []

    def active(value):
        return value not in (None, '', [], {}, {'$undefined': True})

    def add(node_id, path, kind):
        residual.append({'nodeId': node_id, 'path': path, 'kind': kind})

    def scan(value, node_id, path):
        if isinstance(value, dict):
            binding = value.get('boundVariables')
            if isinstance(binding, dict) and active(binding.get('color')):
                add(node_id, path + '/boundVariables/color', 'color-variable')
            for key, child in value.items():
                if key != 'boundVariables':
                    scan(child, node_id, path + '/' + escape(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan(child, node_id, path + '/' + str(index))

    for node_id, row in doc['nodes'].items():
        props = row['props']
        base = '/nodes/' + escape(node_id) + '/props'
        for key in ('fillStyleId', 'strokeStyleId'):
            if active(props.get(key)):
                add(node_id, base + '/' + key, 'paint-style')
        if active(props.get('effectStyleId')) and any(
                isinstance(effect, dict) and isinstance(effect.get('color'), dict)
                for effect in props.get('effects', [])):
            add(node_id, base + '/effectStyleId', 'color-effect-style')
        node_bindings = props.get('boundVariables')
        if isinstance(node_bindings, dict):
            for key in ('fills', 'strokes', 'effects', 'textRangeFills'):
                if active(node_bindings.get(key)):
                    add(node_id, base + '/boundVariables/' + key, 'color-variable')
        for key in ('fills', 'strokes', 'effects', 'vectorNetwork'):
            if key in props:
                scan(props[key], node_id, base + '/' + key)
        for key, runs in props.get('textRuns', {}).items():
            if key == 'fillStyleId':
                for index, run in enumerate(runs):
                    if active(run.get('value')):
                        add(node_id, base + '/textRuns/fillStyleId/' + str(index), 'paint-style')
            elif key == 'fills':
                scan(runs, node_id, base + '/textRuns/fills')
    return {'status': 'fail' if residual else 'pass', 'residualCount': len(residual),
            'residualBindings': residual}


def coverage(snapshot, manifest):
    inventory = color_inventory(snapshot)
    if manifest.get('schemaVersion') != 1 or manifest.get('sourceHash') != inventory['sourceHash']:
        raise ValueError('manifest does not match complete source snapshot')
    expected = {e['path']: e for e in inventory['entries']}
    entries = manifest.get('entries')
    if not isinstance(entries, list):
        raise ValueError('manifest entries required')
    actual = {}
    errors = []
    for entry in entries:
        path = entry.get('path')
        parts(path)
        if path in actual:
            raise ValueError('duplicate manifest channel: ' + path)
        actual[path] = entry
        if not all(isinstance(entry.get(k), str) and entry[k].strip()
                   for k in ('role', 'reason', 'ruleId')):
            errors.append({'path': path, 'error': 'role/reason/ruleId required'})
        elif entry['role'].strip().lower() in (
                'unknown', 'unclassified', 'pending', 'todo', 'tbd'):
            errors.append({'path': path, 'error': 'placeholder role is not semantic classification'})
        disposition = entry.get('disposition')
        if disposition not in ('change', 'preserve', 'ignore'):
            errors.append({'path': path, 'error': 'unknown disposition'})
        if disposition == 'ignore' and path in expected and not expected[path]['inactive']:
            errors.append({'path': path, 'error': 'visible channel cannot be silently ignored'})
        if disposition == 'change':
            target = entry.get('target')
            if not isinstance(target, dict) or not all(k in target for k in ('r', 'g', 'b')):
                errors.append({'path': path, 'error': 'target RGB required'})
            elif not all(type(target[k]) in (int, float) and math.isfinite(target[k])
                         and 0 <= target[k] <= 1 for k in ('r', 'g', 'b')):
                errors.append({'path': path, 'error': 'invalid target RGB'})
            elif path in expected and target_equal(target, expected[path]['source']):
                errors.append({'path': path, 'error': 'unchanged color needs an explicit preserve reason'})
            if not all(isinstance(entry.get(k), str) and entry[k].strip()
                       for k in ('recipeId', 'sceneId')):
                errors.append({'path': path, 'error': 'changed channel needs recipe and representative scene'})
    missing, extra = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
    return {'status': 'fail' if missing or extra or errors else 'pass',
            'sourceHash': inventory['sourceHash'], 'manifestHash': digest(manifest),
            'expected': len(expected), 'classified': len(expected.keys() & actual.keys()),
            'missingPaths': missing, 'extraPaths': extra, 'errors': errors,
            'dispositions': dict(Counter(e.get('disposition') for e in entries))}


def complete(before, after, manifest, policy, mapping=None):
    cover = coverage(before, manifest)
    source, actual = mapped_document(before, after, mapping)
    allowed, protected = policy_check(policy)
    guard = compare(before, after, policy, mapping)
    incomplete, invalid = [], []
    for path, change in allowed.items():
        if not equal(at(source, path), change['before']):
            invalid.append({'path': path, 'error': 'planned before differs from source baseline'})
        if not target_equal(at(actual, path), change['after']):
            incomplete.append({'path': path, 'actual': at(actual, path), 'target': change['after']})
    known_paths = {e['path'] for e in color_inventory(before)['entries']}
    for entry in manifest['entries']:
        path = entry['path']
        if path not in known_paths:
            continue
        disposition = entry.get('disposition')
        if disposition == 'change' and any(overlaps(path, p) for p in protected):
            invalid.append({'path': path, 'error': 'protected channel classified as change'})
        target = entry.get('target') if disposition == 'change' else at(source, path)
        if not target_equal(at(actual, path), target):
            incomplete.append({'path': path, 'actual': at(actual, path), 'target': target})
        # Keep intended changes tied to the predeclared exact allow-list, even if omitted in Figma.
        if disposition == 'change':
            from theme_audit import differences, assess_changes
            permission = assess_changes(differences(at(source, path), target, path), policy)
            if permission['status'] != 'pass':
                invalid.append({'path': path, 'error': 'target not authorized in policy'})
    return {'status': 'pass' if cover['status'] == guard['status'] == 'pass'
            and not incomplete and not invalid else 'fail',
            'coverage': cover, 'propertyGuard': guard, 'incompleteTargets': incomplete,
            'invalidPlan': invalid, 'actualHash': digest(actual),
            'note': 'Machine completion only; visual review and semantic mapping are still required.'}


def batch_plan(batch, max_operations=64, max_bytes=48000):
    if max_operations < 1 or max_bytes < 1024 or not isinstance(batch.get('operations'), list):
        raise ValueError('positive operation limit and byte limit >=1024 required')
    groups, current = [], []
    for op in batch['operations']:
        if set(op) != {'path', 'before', 'after'} or op['before'] == MISSING or op['after'] == MISSING:
            raise ValueError('batch planner supports atomic existing-property writes only')
        parts(op['path'])
        if any(overlaps(op['path'], prev['path']) for prev in batch['operations'][:sum(map(len, groups)) + len(current)]):
            raise ValueError('overlapping operations')
        trial = current + [op]
        payload = {'schemaVersion': 1, 'batchId': 'planned', 'operations': trial}
        if len(trial) > max_operations or len(canonical(payload).encode()) > max_bytes:
            if not current:
                raise ValueError('one atomic operation exceeds payload limit; cannot split it')
            groups.append(current)
            current = [op]
            if len(canonical({**payload, 'operations': current}).encode()) > max_bytes:
                raise ValueError('one atomic operation exceeds payload limit; cannot split it')
        else:
            current = trial
    if current:
        groups.append(current)
    prefix = batch.get('batchId', 'batch')
    return {'status': 'pass', 'operationCount': len(batch['operations']),
            'batches': [{'schemaVersion': 1, 'batchId': prefix + '-' + str(i), 'operations': ops}
                        for i, ops in enumerate(groups)],
            'note': 'Batch only within one phase and validated scene group; these are not write permissions.'}


MACHINE_RULES = {'source-unchanged', 'clone-allowed-differences', 'color-coverage', 'plan-complete',
                 'contrast-baseline', 'color-relations', 'visual-unit-coverage', 'icon-glyph-coverage',
                 'color-bindings-clear', 'text-range-coverage',
                 'cross-mode-composite-coverage', 'surface-system'}
VISUAL_RULES = {'kv-fit', 'theme-consistency', 'clarity', 'hierarchy', 'button-salience',
                'cta-salience', 'icon-clarity', 'readability', 'material-layers',
                'surface-discernibility', 'state-discernibility', 'control-family-consistency',
                'cross-mode-composite', 'surface-continuity'}


def _visible_nodes(doc, root_id):
    visible = {}
    def visit(node_id, hidden=False):
        row = doc['nodes'][node_id]
        props = row['props']
        current = hidden or props.get('visible') is False or props.get('opacity') == 0
        visible[node_id] = not current
        for child in row['children']:
            visit(child, current)
    visit(root_id)
    return visible


def _is_descendant(doc, node_id, ancestor_id):
    current = node_id
    while current in doc['nodes']:
        if current == ancestor_id:
            return True
        current = doc['nodes'][current]['parentId']
    return False


def icon_glyph_requirements(source, manifest, rules):
    """Require channel-level coverage of every declared functional Icon subtree.

    A preserved glyph channel is only valid when it is explicitly proven to be
    theme-neutral. This prevents changing an Icon container while leaving a warm
    source-theme path inside the glyph.
    """
    doc = snapshot_document(source)
    rule = rules.get('icon-clarity', {})
    if rule.get('applicable') is not True:
        return {'status': 'pass', 'applicable': False, 'rootCount': 0,
                'channelCount': 0, 'errors': []}
    plan = manifest.get('iconGlyphPlan')
    if (not isinstance(plan, dict) or plan.get('schemaVersion') != 1 or
            plan.get('sourceHash') != digest(doc) or not isinstance(plan.get('roots'), list) or
            not plan['roots']):
        return {'status': 'fail', 'applicable': True, 'rootCount': 0, 'channelCount': 0,
                'errors': [{'error': 'fresh nonempty iconGlyphPlan bound to source snapshot required'}]}
    visible = _visible_nodes(doc, source['rootId'])
    inventory = {entry['path']: entry for entry in color_inventory(source)['entries']
                 if not entry['inactive'] and visible.get(entry['nodeId'])}
    manifest_index = {entry['path']: entry for entry in manifest.get('entries', [])}
    icon_scope = set(rule.get('scopeNodeIds', []))
    errors, seen_roots, total = [], set(), 0
    for root in plan['roots']:
        root_id = root.get('rootNodeId')
        if root_id in seen_roots:
            errors.append({'rootNodeId': root_id, 'error': 'duplicate Icon root'})
            continue
        seen_roots.add(root_id)
        if root_id not in doc['nodes'] or root_id not in icon_scope:
            errors.append({'rootNodeId': root_id, 'error': 'Icon root missing or omitted from icon-clarity scope'})
            continue
        expected = {path for path, item in inventory.items()
                    if _is_descendant(doc, item['nodeId'], root_id)}
        channels = root.get('channels')
        if not isinstance(channels, list):
            errors.append({'rootNodeId': root_id, 'error': 'Icon channels required'})
            continue
        indexed = {}
        for channel in channels:
            path = channel.get('path')
            if path in indexed:
                errors.append({'rootNodeId': root_id, 'path': path, 'error': 'duplicate Icon channel'})
                continue
            indexed[path] = channel
            part = channel.get('part')
            action = channel.get('action')
            if part not in {'glyph', 'container', 'reflection', 'protected'}:
                errors.append({'rootNodeId': root_id, 'path': path, 'error': 'unknown Icon channel part'})
            if action not in {'change', 'preserve', 'protected'}:
                errors.append({'rootNodeId': root_id, 'path': path, 'error': 'unknown Icon channel action'})
                continue
            expected_disposition = 'change' if action == 'change' else 'preserve'
            if manifest_index.get(path, {}).get('disposition') != expected_disposition:
                errors.append({'rootNodeId': root_id, 'path': path,
                               'error': 'Icon action differs from color manifest disposition'})
            if not isinstance(channel.get('reason'), str) or not channel['reason'].strip():
                errors.append({'rootNodeId': root_id, 'path': path, 'error': 'Icon channel reason required'})
            if part == 'glyph' and action == 'preserve' and not (
                    channel.get('themeNeutral') is True and
                    isinstance(channel.get('neutralEvidence'), str) and
                    channel['neutralEvidence'].strip()):
                errors.append({'rootNodeId': root_id, 'path': path,
                               'error': 'preserved glyph channel needs explicit theme-neutral evidence'})
        missing = sorted(expected - indexed.keys())
        extra = sorted(indexed.keys() - expected)
        if missing:
            errors.append({'rootNodeId': root_id, 'error': 'visible Icon channels missing', 'paths': missing})
        if extra:
            errors.append({'rootNodeId': root_id, 'error': 'undeclared/nonvisible Icon channels', 'paths': extra})
        total += len(expected)
    return {'status': 'fail' if errors else 'pass', 'applicable': True,
            'rootCount': len(seen_roots), 'channelCount': total, 'errors': errors}


def text_range_requirements(source, manifest, relationships, rules, projected=None):
    """Require every visible styled text fill range to be classified and contrast-bound."""
    doc = snapshot_document(source)
    visible = _visible_nodes(doc, source['rootId'])
    plan = manifest.get('textRangePlan')
    hidden_roots = set(plan.get('hiddenRootIds', [])) if isinstance(plan, dict) else set()
    if not hidden_roots <= doc['nodes'].keys():
        return {'status': 'fail', 'applicable': True, 'textNodeCount': 0,
                'rangeCount': 0, 'errors': [{'error': 'unknown planned hidden root'}]}
    if projected is not None:
        target_doc = snapshot_document(projected)
        if any(root not in target_doc['nodes'] or
               target_doc['nodes'][root]['props'].get('opacity') != 0 for root in hidden_roots):
            return {'status': 'fail', 'applicable': True, 'textNodeCount': 0,
                    'rangeCount': 0, 'errors': [{'error': 'planned hidden root is not hidden in projection'}]}
    def planned_hidden(node_id):
        cursor = node_id
        while cursor in doc['nodes']:
            if cursor in hidden_roots:
                return True
            cursor = doc['nodes'][cursor]['parentId']
        return False
    active_text_nodes = {
        item['nodeId'] for item in color_inventory(source)['entries']
        if not item['inactive'] and '/textRuns/fills/' in item['path']
    }
    text_nodes = {node_id: row for node_id, row in doc['nodes'].items()
                  if visible.get(node_id) and not planned_hidden(node_id) and
                  node_id in active_text_nodes and
                  row['props'].get('type') == 'TEXT' and
                  isinstance(row['props'].get('characters'), str) and
                  row['props']['characters']}
    if not text_nodes:
        return {'status': 'pass', 'applicable': False, 'textNodeCount': 0,
                'rangeCount': 0, 'errors': []}
    if (not isinstance(plan, dict) or plan.get('schemaVersion') != 1 or
            plan.get('sourceHash') != digest(doc) or not isinstance(plan.get('entries'), list)):
        return {'status': 'fail', 'applicable': True, 'textNodeCount': len(text_nodes),
                'rangeCount': 0, 'errors': [{'error': 'fresh textRangePlan bound to source snapshot required'}]}
    relation_index = {pair['id']: pair for pair in relationships}
    manifest_index = {entry['path']: entry for entry in manifest.get('entries', [])}
    inventory = {entry['path']: entry for entry in color_inventory(source)['entries']}
    inventory_paths = set(inventory)
    entries = plan['entries']; indexed = {}; errors = []; range_count = 0
    for entry in entries:
        node_id = entry.get('nodeId')
        if node_id in indexed:
            errors.append({'nodeId': node_id, 'error': 'duplicate text range plan entry'})
        indexed[node_id] = entry
    for node_id in sorted(set(indexed) - set(text_nodes)):
        errors.append({'nodeId': node_id, 'error': 'text range plan targets non-visible or empty text'})
    for node_id in sorted(set(text_nodes) - set(indexed)):
        errors.append({'nodeId': node_id, 'error': 'visible text node missing from text range plan'})
    readability_scope = set(rules.get('readability', {}).get('scopeNodeIds', []))
    for node_id, row in text_nodes.items():
        entry = indexed.get(node_id)
        if not entry:
            continue
        source_runs = row['props'].get('textRuns', {}).get('fills')
        ranges = entry.get('ranges')
        if not isinstance(source_runs, list) or not source_runs:
            errors.append({'nodeId': node_id, 'error': 'styled text fill ranges missing from source snapshot'})
            continue
        if not isinstance(ranges, list):
            errors.append({'nodeId': node_id, 'error': 'text ranges required'})
            continue
        expected_spans = [(run.get('start'), run.get('end')) for run in source_runs]
        actual_spans = [(run.get('start'), run.get('end')) for run in ranges]
        if actual_spans != expected_spans:
            errors.append({'nodeId': node_id, 'error': 'plan must preserve every styled fill range boundary',
                           'expected': expected_spans, 'actual': actual_spans})
        for index, text_range in enumerate(ranges):
            range_count += 1
            prefix = '/nodes/' + escape(node_id) + '/props/textRuns/fills/' + str(index)
            expected_channels = sorted(path for path in inventory_paths if path.startswith(prefix + '/'))
            channels = text_range.get('channelPaths')
            if not isinstance(channels, list) or sorted(channels) != expected_channels:
                errors.append({'nodeId': node_id, 'rangeIndex': index,
                               'error': 'range must name every stored text color channel',
                               'expectedPaths': expected_channels})
                continue
            action = text_range.get('action')
            if action not in {'change', 'preserve', 'protected'}:
                errors.append({'nodeId': node_id, 'rangeIndex': index, 'error': 'unknown text range action'})
                continue
            if not isinstance(text_range.get('role'), str) or not text_range['role'].strip() or \
                    not isinstance(text_range.get('reason'), str) or not text_range['reason'].strip():
                errors.append({'nodeId': node_id, 'rangeIndex': index,
                               'error': 'text range role and reason required'})
            dispositions = {manifest_index.get(path, {}).get('disposition') for path in channels
                            if not inventory[path]['inactive']}
            expected_disposition = 'change' if action == 'change' else 'preserve'
            if dispositions != {expected_disposition}:
                errors.append({'nodeId': node_id, 'rangeIndex': index,
                               'error': 'text range action differs from color manifest dispositions'})
            if action == 'protected':
                protection = text_range.get('protectionClass')
                if protection not in {'protected-media-overlay', 'protected-rank-top3',
                                       'protected-marketing-banner', 'brand', 'semantic-status'}:
                    errors.append({'nodeId': node_id, 'rangeIndex': index,
                                   'error': 'exact supported text protection class required'})
                if protection == 'protected-media-overlay':
                    cover = text_range.get('coverNodeId')
                    if (cover not in doc['nodes'] or cover == source['rootId'] or
                            not _is_descendant(doc, node_id, cover)):
                        errors.append({'nodeId': node_id, 'rangeIndex': index,
                                       'error': 'media protection must name an actual containing cover subtree'})
                continue
            hosts = text_range.get('hostNodeIds')
            pair_ids = text_range.get('contrastPairIds')
            if (not isinstance(hosts, list) or not hosts or not set(hosts) <= doc['nodes'].keys() or
                    not isinstance(pair_ids, list) or not pair_ids):
                errors.append({'nodeId': node_id, 'rangeIndex': index,
                               'error': 'non-protected text range needs actual hosts and contrast pairs'})
                continue
            for pair_id in pair_ids:
                pair = relation_index.get(pair_id)
                if not pair or node_id not in pair.get('nodeIds', []) or not set(hosts) <= set(pair.get('nodeIds', [])):
                    errors.append({'nodeId': node_id, 'rangeIndex': index, 'pairId': pair_id,
                                   'error': 'contrast pair does not cover this text range and its hosts'})
                elif manifest.get('themeTransition') in {'light-to-dark', 'dark-to-light'}:
                    disabled_root = text_range.get('disabledStateRootId')
                    minimum = pair.get('minimumContrast')
                    if disabled_root:
                        if (disabled_root not in hosts or
                                doc['nodes'][disabled_root]['props'].get('opacity') != .5 or
                                pair.get('disabledStateRootId') != disabled_root or
                                minimum is not None):
                            errors.append({'nodeId': node_id, 'rangeIndex': index, 'pairId': pair_id,
                                           'error': 'disabled text exception needs exact 50% ancestor and measured-only pair'})
                    elif type(minimum) not in (int, float) or not math.isfinite(minimum) or minimum < 3:
                        errors.append({'nodeId': node_id, 'rangeIndex': index, 'pairId': pair_id,
                                       'error': 'cross-mode visible text needs an explicit minimumContrast >= 3'})
            if node_id not in readability_scope:
                errors.append({'nodeId': node_id, 'rangeIndex': index,
                               'error': 'visible non-protected text omitted from readability visual scope'})
    return {'status': 'fail' if errors else 'pass', 'applicable': True,
            'textNodeCount': len(text_nodes), 'rangeCount': range_count, 'errors': errors}


def _alpha_paths(doc, color_path):
    result = []
    color = at(doc, color_path)
    if isinstance(color, dict) and color.get('a', 1) < 1:
        result.append(color_path + '/a')
    tokens = parts(color_path)
    for length in range(len(tokens) - 1, 2, -1):
        path = '/' + '/'.join(escape(v) for v in tokens[:length])
        value = at(doc, path)
        if isinstance(value, dict) and type(value.get('opacity')) in (int, float) and value['opacity'] < 1:
            result.append(path + '/opacity')
    current = tokens[1]
    while current in doc['nodes']:
        opacity_path = '/nodes/' + escape(current) + '/props/opacity'
        opacity = at(doc, opacity_path)
        if type(opacity) in (int, float) and opacity < 1:
            result.append(opacity_path)
        current = doc['nodes'][current]['parentId']
    return sorted(set(result))


def cross_mode_composite_requirements(source, actual, manifest, rules, mapping=None):
    """Cross-mode themes must re-evaluate appearance alpha and gradient edges."""
    source_doc, actual_doc = mapped_document(source, actual, mapping)
    transition = manifest.get('themeTransition')
    if transition not in {'light-to-light', 'dark-to-dark', 'light-to-dark', 'dark-to-light'}:
        return {'status': 'fail', 'applicable': True,
                'errors': [{'error': 'explicit themeTransition required'}]}
    if transition in {'light-to-light', 'dark-to-dark'}:
        return {'status': 'pass', 'applicable': False, 'candidateCount': 0,
                'boundaryGroupCount': 0, 'errors': []}
    inventory = {entry['path']: entry for entry in color_inventory(source)['entries']}
    candidates = {}
    for entry in manifest.get('entries', []):
        path = entry.get('path'); source_entry = inventory.get(path)
        if not source_entry or source_entry['inactive']:
            continue
        role = entry.get('role', '').lower()
        alpha_paths = _alpha_paths(source_doc, path)
        appearance_role = any(token in role for token in ('text', 'title', 'atmosphere', 'fade', 'transition'))
        gradient = '/gradientStops/' in path
        if alpha_paths or appearance_role or gradient:
            candidates[path] = {'nodeId': entry.get('nodeId') or parts(path)[1],
                                'role': entry.get('role'), 'alphaPaths': alpha_paths,
                                'gradient': gradient}
    plan = manifest.get('crossModeCompositePlan')
    if (not isinstance(plan, dict) or plan.get('schemaVersion') != 1 or
            plan.get('sourceHash') != digest(source_doc) or not isinstance(plan.get('entries'), list)):
        return {'status': 'fail', 'applicable': True, 'candidateCount': len(candidates),
                'boundaryGroupCount': 0,
                'errors': [{'error': 'fresh crossModeCompositePlan required for cross-mode adaptation'}]}
    indexed = {}; errors = []
    for item in plan['entries']:
        path = item.get('path')
        if path in indexed:
            errors.append({'path': path, 'error': 'duplicate cross-mode composite entry'})
        indexed[path] = item
    for path in sorted(set(candidates) - set(indexed)):
        errors.append({'path': path, 'error': 'cross-mode appearance/alpha channel omitted'})
    for path in sorted(set(indexed) - set(candidates)):
        errors.append({'path': path, 'error': 'cross-mode entry is not an active candidate'})
    composite_scope = set(rules.get('cross-mode-composite', {}).get('scopeNodeIds', []))
    for path, candidate in candidates.items():
        item = indexed.get(path)
        if not item:
            continue
        if sorted(item.get('sourceAlphaPaths', [])) != candidate['alphaPaths']:
            errors.append({'path': path, 'error': 'source alpha contributors must be enumerated exactly'})
        decision = item.get('decision')
        if decision not in {'recompute-appearance', 'remove-visually',
                            'preserve-state', 'preserve-structural'}:
            errors.append({'path': path, 'error': 'unknown cross-mode alpha/composite decision'})
            continue
        role = (candidate['role'] or '').lower()
        if decision == 'preserve-structural' and not any(v in role for v in ('mask', 'structure')):
            errors.append({'path': path, 'error': 'appearance color cannot reuse alpha as structural'})
        if decision == 'preserve-state' and not any(v in role for v in ('state', 'disabled', 'locked')):
            errors.append({'path': path, 'error': 'non-state appearance cannot reuse state alpha'})
        if decision in {'recompute-appearance', 'remove-visually'} and not item.get('targetCompositeEvidenceId'):
            errors.append({'path': path, 'error': 'appearance decision needs target composite evidence'})
        if (not isinstance(item.get('hostNodeIds'), list) or not item['hostNodeIds'] or
                not set(item['hostNodeIds']) <= source_doc['nodes'].keys() or
                not isinstance(item.get('reviewSceneId'), str) or not item['reviewSceneId'].strip()):
            errors.append({'path': path, 'error': 'actual hosts and 1:1 review scene required'})
        if candidate['nodeId'] not in composite_scope:
            errors.append({'path': path, 'error': 'candidate omitted from cross-mode composite visual scope'})
    groups = plan.get('boundaryGroups')
    if not isinstance(groups, list) or not groups:
        errors.append({'error': 'cross-mode adaptation requires surface/gradient boundary groups'})
        groups = []
    boundary_nodes = set()
    for group in groups:
        nodes = group.get('nodeIds')
        if (group.get('kind') not in {'surface-edge', 'gradient-terminal', 'card-atmosphere'} or
                not isinstance(nodes, list) or not nodes or not set(nodes) <= source_doc['nodes'].keys() or
                not group.get('reviewSceneId') or not group.get('evidenceId')):
            errors.append({'groupId': group.get('id'), 'error': 'invalid cross-mode boundary group'})
            continue
        boundary_nodes.update(nodes)
    required_boundary_nodes = {c['nodeId'] for c in candidates.values()
                               if c['gradient'] or 'atmosphere' in (c['role'] or '').lower()}
    if not required_boundary_nodes <= boundary_nodes:
        errors.append({'error': 'gradient/atmosphere candidates missing boundary review',
                       'nodeIds': sorted(required_boundary_nodes - boundary_nodes)})
    continuity_scope = set(rules.get('surface-continuity', {}).get('scopeNodeIds', []))
    if not boundary_nodes <= continuity_scope:
        errors.append({'error': 'boundary nodes omitted from surface-continuity visual scope',
                       'nodeIds': sorted(boundary_nodes - continuity_scope)})
    return {'status': 'fail' if errors else 'pass', 'applicable': True,
            'transition': transition, 'candidateCount': len(candidates),
            'boundaryGroupCount': len(groups), 'errors': errors,
            'actualHash': digest(actual_doc)}


def visual_units(source, manifest, registry, rules=None):
    """Require a primary visual unit for every inventoried color channel.

    Membership is authored from source evidence, never guessed from RGB/name.
    Ancestors are read dependencies, not extra write permission.
    """
    doc = snapshot_document(source)
    if registry.get('schemaVersion') != 1 or registry.get('sourceHash') != digest(doc):
        raise ValueError('visual units must bind the source snapshot')
    coverage_result = coverage(source, manifest)
    if coverage_result['status'] != 'pass':
        raise ValueError('complete classified manifest required before visual units')
    units = registry.get('units')
    if not isinstance(units, list) or not units:
        raise ValueError('nonempty visual units required')
    known = {e['path'] for e in manifest['entries']}
    assigned, indexed = {}, {}
    for unit in units:
        name = unit.get('id')
        if not isinstance(name, str) or not name.strip() or name in indexed:
            raise ValueError('missing/duplicate visual unit ID')
        if not isinstance(unit.get('basis'), str) or not unit['basis'].strip():
            raise ValueError('visual unit needs original structure/rendering evidence')
        for key in ('carrierPaths', 'dependencyNodeIds', 'reviewNodeIds', 'reviewRuleIds'):
            values = unit.get(key)
            if (not isinstance(values, list) or not values or
                    any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values)):
                raise ValueError('nonempty unique visual unit ' + key + ' required')
        if not set(unit['dependencyNodeIds']) <= doc['nodes'].keys():
            raise ValueError('missing visual unit dependency')
        if not set(unit['reviewNodeIds']) <= set(unit['dependencyNodeIds']):
            raise ValueError('visual review roots must belong to unit dependencies')
        dependencies = set(unit['dependencyNodeIds'])
        carrier_nodes = set()
        for path in unit['carrierPaths']:
            if path not in known or path in assigned:
                raise ValueError('unknown or multiply assigned visual carrier: ' + path)
            node = parts(path)[1]
            if node not in dependencies:
                raise ValueError('visual carrier outside its unit dependencies: ' + path)
            assigned[path] = name; carrier_nodes.add(node)
        for node in list(dependencies):
            parent = doc['nodes'][node]['parentId']
            while parent in doc['nodes']:
                dependencies.add(parent)
                parent = doc['nodes'][parent]['parentId']
        if rules is not None:
            for rule_id in unit['reviewRuleIds']:
                rule = rules.get(rule_id, {})
                if rule.get('kind') != 'visual' or not rule.get('applicable'):
                    raise ValueError('visual unit references absent/inapplicable visual rule')
                if not set(unit['reviewNodeIds']) <= set(rule['scopeNodeIds']):
                    raise ValueError('visual unit roots outside frozen visual rule scope')
        indexed[name] = {**unit, 'dependencies': sorted(dependencies),
                         'carrierNodeIds': sorted(carrier_nodes)}
    missing = sorted(known - assigned.keys())
    return {'status': 'fail' if missing else 'pass', 'missingCarrierPaths': missing,
            'unitCount': len(units), 'registryHash': digest(registry), 'units': indexed}


def affected_units(source, manifest, registry, relations, frozen, changes):
    """Compute the relation closure to recheck after any local correction."""
    result = visual_units(source, manifest, registry)
    if result['status'] != 'pass':
        return result
    changed = changes.get('changedPaths')
    if (not isinstance(changed, list) or not changed or
            any(not isinstance(p, str) for p in changed) or len(set(changed)) != len(changed)):
        raise ValueError('unique source-namespace changedPaths required')
    nodes = snapshot_document(source)['nodes']
    for path in changed:
        tokens = parts(path)
        if len(tokens) < 3 or tokens[0] != 'nodes' or tokens[1] not in nodes or tokens[2] != 'props':
            raise ValueError('changed path must identify an existing source node property')
    units = result['units']
    owner = {p: name for name, u in units.items() for p in u['carrierPaths']}
    node_owners = {}
    for name, unit in units.items():
        for node in set(unit['carrierNodeIds']) | set(unit['reviewNodeIds']):
            node_owners.setdefault(node, set()).add(name)
    pairs = frozen['pairs'] if isinstance(frozen, dict) else frozen
    orders = frozen.get('emphasisOrders', []) if isinstance(frozen, dict) else []
    edges = []
    for group in relations['groups']:
        if not set(group['paths']) <= owner.keys():
            raise ValueError('color relation includes an unregistered carrier')
        edges.append(('color', group['id'], {owner[p] for p in group['paths']}))
    pair_edges = {}
    for pair in pairs:
        if not set(pair['nodeIds']) <= nodes.keys():
            raise ValueError('contrast pair contains missing source node')
        members = set().union(*(node_owners.get(n, set()) for n in pair['nodeIds']))
        if not members:
            raise ValueError('contrast pair has no registered visual unit')
        pair_edges[pair['id']] = members
        edges.append(('contrast', pair['id'], members))
    for order in orders:
        members = pair_edges[order['strongerPairId']] | pair_edges[order['weakerPairId']]
        edges.append(('order', order['id'], members))
    affected = {name for name, u in units.items()
                if any(parts(p)[1] in u['dependencies'] for p in changed)}
    pending = True
    while pending:
        before = set(affected)
        for _, _, members in edges:
            if members & affected:
                affected.update(members)
        pending = before != affected
    return {'status': 'pass', 'registryHash': result['registryHash'],
            'affectedUnitIds': sorted(affected),
            'colorRelationIds': sorted(i for k, i, m in edges if k == 'color' and m & affected),
            'contrastPairIds': sorted(i for k, i, m in edges if k == 'contrast' and m & affected),
            'emphasisOrderIds': sorted(i for k, i, m in edges if k == 'order' and m & affected),
            'requiredReviewRuleIds': sorted({r for n in affected for r in units[n]['reviewRuleIds']}),
            'dependencyNodeIds': sorted({d for n in affected for d in units[n]['dependencies']}),
            'note': 'Invalidates affected gates; includes read-only/protected members, never grants writes.'}


def perceptual_lab(rgb):
    """sRGB / D65 CIELAB; L* measures perceived lightness, not HSV V."""
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    xyz = [sum(v * w for v, w in zip(linear, row)) / white
           for row, white in [((.4124564, .3575761, .1804375), .95047),
                              ((.2126729, .7151522, .0721750), 1.),
                              ((.0193339, .1191920, .9503041), 1.08883)]]
    def f(v):
        return v ** (1 / 3) if v > (6 / 29) ** 3 else v / (3 * (6 / 29) ** 2) + 4 / 29
    x, y, z = map(f, xyz)
    return [116 * y - 16, 500 * (x - y), 200 * (y - z)]


def appearance_spread(colors):
    labs = [perceptual_lab(c) for c in colors]
    return {'lightnessSpread': max(v[0] for v in labs) - min(v[0] for v in labs),
            'colorSpreadDeltaE76': max(math.dist(a, b) for a in labs for b in labs),
            'lightness': [v[0] for v in labs], 'luminance': [luminance(c) for c in colors]}


def _anchor_matches(target, anchor):
    """Figma SOLID RGB and opaque gradient RGBA represent the same anchor.

    Missing alpha means 1; nonopaque stops cannot establish a stable anchor.
    """
    if not isinstance(target, dict) or not isinstance(anchor, dict):
        return False
    return (all(k in target and k in anchor for k in 'rgb') and
            target_equal({k: target[k] for k in 'rgb'}, {k: anchor[k] for k in 'rgb'}) and
            target_equal(target.get('a', 1), anchor.get('a', 1)) and
            target_equal(target.get('a', 1), 1))


def interaction_requirements(source, manifest, rules):
    """Derive mandatory button comparison coverage from the full source inventory."""
    doc = snapshot_document(source)
    active = {e['path'] for e in color_inventory(source)['entries'] if not e['inactive']}
    entries = [e for e in manifest['entries'] if e['path'] in active
               and e['role'] in {'button.material', 'cta.base', 'cta.material'}]
    small = {e['path'] for e in entries if e['role'] == 'button.material'}
    cta = {e['path'] for e in entries if e['role'].startswith('cta.')}
    if not small or not cta:
        return {'status': 'pass', 'applicable': False, 'errors': []}
    errors = []
    contract = manifest.get('schemeAnchorContract', {})
    button_anchor = contract.get('button') if isinstance(contract, dict) else None
    if (not isinstance(button_anchor, dict) or set(button_anchor) not in
            ({'r', 'g', 'b'}, {'r', 'g', 'b', 'a'}) or
            not all(type(button_anchor[k]) in (int, float) and math.isfinite(button_anchor[k])
                    and 0 <= button_anchor[k] <= 1 for k in ('r', 'g', 'b'))):
        errors.append({'error': 'schemeAnchorContract.button RGB required for main button family'})
    anchor_entries = [e for e in entries if e.get('anchorId') == 'button']
    small_anchors = [e for e in anchor_entries if e['role'] == 'button.material']
    cta_anchors = [e for e in anchor_entries if e['role'].startswith('cta.')]
    if not small_anchors or not cta_anchors:
        errors.append({'error': 'each main small-button and CTA family needs button anchor channels'})
    elif isinstance(button_anchor, dict):
        for entry in anchor_entries:
            if entry.get('disposition') != 'change' or not _anchor_matches(entry.get('target'), button_anchor):
                errors.append({'path': entry['path'],
                               'error': 'button anchor target differs from schemeAnchorContract.button'})
    family_rule = rules.get('control-family-consistency', {})
    if family_rule.get('kind') != 'visual' or family_rule.get('applicable') is not True:
        errors.append({'error': 'button/CTA control-family visual comparison cannot be skipped'})
    scope = set(family_rule.get('scopeNodeIds', []))
    def covered(path, roots):
        node = parts(path)[1]; ancestors = {node}
        while node in doc['nodes']:
            node = doc['nodes'][node]['parentId']
            ancestors.add(node)
        return bool(roots & ancestors)
    for e in entries:
        if not covered(e['path'], scope):
            errors.append({'path': e['path'], 'error': 'button/CTA omitted from control-family visual scope'})
    rule = rules.get('button-appearance-family', {})
    verifier = rule.get('verifier', {})
    if (rule.get('kind') != 'machine' or not rule.get('applicable')
            or verifier.get('type') != 'displayed-relations'):
        errors.append({'error': 'mandatory button-appearance-family native comparison missing'})
    else:
        joined = set()
        for group in verifier.get('groups', []):
            paths = set(group.get('carrierPaths', []))
            if group.get('relationType') == 'appearance-family' and paths & small and paths & cta:
                group_roots = set(group.get('nodeIds', []))
                if not group_roots or not group_roots <= doc['nodes'].keys():
                    errors.append({'error': 'button appearance group needs existing comparison roots'})
                else:
                    joined.update(path for path in paths & (small | cta) if covered(path, group_roots))
        missing = sorted((small | cta) - joined)
        if missing:
            errors.append({'error': 'all button/CTA material paths need a joint appearance family',
                           'missingPaths': missing})
    return {'status': 'fail' if errors else 'pass', 'applicable': True, 'errors': errors}


def scheme_anchor_requirements(manifest, source=None):
    """Fail closed when a selected six-color proposal drifts during execution.

    Each public anchor needs at least one stable visible carrier in the manifest.
    Material-only derivatives may have other colors, but the declared anchor
    channel itself must target the exact selected RGB.
    """
    contract = manifest.get('schemeAnchorContract')
    if contract is None:
        return {'status': 'pass', 'applicable': False, 'errors': []}
    names = ('background', 'card', 'number', 'icon', 'button', 'tab')
    errors = []
    if not isinstance(contract, dict) or set(contract) != set(names):
        return {'status': 'fail', 'applicable': True,
                'errors': [{'error': 'schemeAnchorContract must contain exactly six public anchors'}]}

    def valid_rgb(value):
        return (isinstance(value, dict) and set(value) in ({'r', 'g', 'b'}, {'r', 'g', 'b', 'a'})
                and all(type(value[k]) in (int, float) and math.isfinite(value[k])
                        and 0 <= value[k] <= 1 for k in ('r', 'g', 'b')))

    entries = manifest.get('entries', [])
    source_doc = snapshot_document(source) if source is not None else None
    applicability = manifest.get('schemeAnchorApplicability', {})
    if not isinstance(applicability, dict) or set(applicability) - {'tab'}:
        errors.append({'error': 'only tab may have an anchor applicability exception'})
        applicability = {}
    tab_exception = applicability.get('tab')
    if tab_exception is not None:
        if any(entry.get('anchorId') == 'tab' for entry in entries):
            errors.append({'anchorId': 'tab', 'error': 'no-Tab exception conflicts with tab anchor carrier'})
        if source is None:
            errors.append({'anchorId': 'tab', 'error': 'no-Tab exception requires source snapshot'})
        else:
            try:
                doc = snapshot_document(source)
                visible = _visible_nodes(doc, source['rootId'])
                visible_ids = sorted(node_id for node_id, is_visible in visible.items() if is_visible)
                named_tabs = sorted(node_id for node_id in visible_ids if
                                    re.search(r'(?i)(?:^|[^a-z])tabs?(?:$|[^a-z])|选中.?tab|标签页',
                                              str(doc['nodes'][node_id]['props'].get('name', ''))))
                expected = {'status': 'not-applicable', 'sourceRootId': source['rootId'],
                            'sourceHash': digest(source),
                            'reviewedVisibleNodeIdsHash': digest(visible_ids),
                            'finding': 'no-visible-tab',
                            'userAuthorization': '允许无 Tab 豁免'}
                if (not isinstance(tab_exception, dict) or
                        any(tab_exception.get(key) != value for key, value in expected.items()) or
                        not isinstance(tab_exception.get('reason'), str) or
                        not tab_exception['reason'].strip() or named_tabs):
                    errors.append({'anchorId': 'tab', 'error': 'no-Tab exception lacks bound exhaustive source evidence',
                                   'namedTabCandidates': named_tabs})
            except (ValueError, KeyError, TypeError) as exc:
                errors.append({'anchorId': 'tab', 'error': 'invalid no-Tab source evidence', 'detail': str(exc)})
    for name in names:
        anchor = contract[name]
        if not valid_rgb(anchor):
            errors.append({'anchorId': name, 'error': 'anchor must be finite RGB(A)'})
            continue
        carriers = [e for e in entries if e.get('anchorId') == name]
        if not carriers and name == 'tab' and tab_exception is not None:
            continue
        if not carriers:
            errors.append({'anchorId': name, 'error': 'stable visible anchor channel missing'})
            continue
        for entry in carriers:
            if entry.get('inactive') is True:
                errors.append({'anchorId': name, 'path': entry.get('path'),
                               'error': 'anchor channel cannot be inactive'})
            if entry.get('disposition') != 'change' or not _anchor_matches(entry.get('target'), anchor):
                errors.append({'anchorId': name, 'path': entry.get('path'),
                               'error': 'anchor target differs from selected schemeAnchorContract'})
            if name == 'icon' and source_doc is not None:
                match = re.fullmatch(r'/nodes/([^/]+)/props/fills/(\d+)/(?:color|gradientStops/\d+/color)',
                                     str(entry.get('path', '')))
                if match:
                    node = source_doc['nodes'].get(match.group(1))
                    fills = node['props'].get('fills', []) if node else []
                    index = int(match.group(2))
                    def opaque_cover(paint):
                        if (not isinstance(paint, dict) or paint.get('visible') is False or
                                paint.get('opacity', 1) != 1 or
                                paint.get('blendMode', 'NORMAL') != 'NORMAL'):
                            return False
                        if paint.get('type') == 'SOLID':
                            return paint.get('color', {}).get('a', 1) == 1
                        if str(paint.get('type', '')).startswith('GRADIENT_'):
                            stops = paint.get('gradientStops', [])
                            return bool(stops) and all(
                                stop.get('color', {}).get('a', 1) == 1 for stop in stops)
                        return False
                    if index < len(fills) and any(opaque_cover(paint) for paint in fills[index + 1:]):
                        errors.append({'anchorId': name, 'path': entry.get('path'),
                                       'error': 'icon anchor is covered by a higher fully opaque visible Fill'})
    unknown = sorted({e.get('anchorId') for e in entries if e.get('anchorId') is not None} - set(names))
    if unknown:
        errors.append({'anchorIds': unknown, 'error': 'unknown scheme anchor IDs'})
    return {'status': 'fail' if errors else 'pass', 'applicable': True, 'errors': errors}


def verify_displayed_relations(source, actual, rule, evidence):
    """Check native continuity or source-relative lightness/color family relations."""
    if evidence.get('sourceHash') != digest(source) or evidence.get('actualHash') != digest(actual):
        raise ValueError('displayed samples must bind the fresh corresponding snapshots')
    groups = rule.get('verifier', {}).get('groups')
    samples = evidence.get('groups')
    if not isinstance(groups, list) or not groups or not isinstance(samples, list):
        raise ValueError('frozen displayed groups and fresh samples required')
    index = {g['id']: g for g in samples}
    if len({g['id'] for g in groups}) != len(groups) or len(index) != len(samples) or set(index) != {g['id'] for g in groups}:
        raise ValueError('displayed samples must cover exactly the frozen groups')
    results, images, native_evidence = [], {}, []
    for group in groups:
        points, limit = group.get('xy'), group.get('maximumChannelDelta')
        kind = group.get('relationType', 'continuity')
        if kind not in {'continuity', 'source-topology', 'appearance-family',
                        'source-appearance-equivalence', 'surface-linked-appearance'} or not isinstance(points, list) or len(points) < 2:
            raise ValueError('known displayed relation and frozen comparison points required')
        if kind == 'continuity' and (type(limit) not in (int, float) or not 0 <= limit <= 255):
            raise ValueError('continuity needs an explicit scene tolerance')
        if kind == 'source-topology' and (
                type(limit) not in (int, float) or not 0 <= limit <= 16):
            raise ValueError('source topology needs a tolerance no greater than 16/255')
        if kind in {'appearance-family', 'source-appearance-equivalence', 'surface-linked-appearance'}:
            if not isinstance(group.get('basis'), str) or not group['basis'].strip():
                raise ValueError('appearance relation needs predeclared source evidence')
        if kind == 'surface-linked-appearance':
            if group.get('targetBasis') != 'surface-recipe':
                raise ValueError('surface-linked appearance must use the surface recipe')
            anchor = group.get('anchorPointIndex')
            if not isinstance(anchor, int) or isinstance(anchor, bool) or not 0 <= anchor < len(points):
                raise ValueError('surface-linked appearance needs a valid surface anchor point')
        if kind == 'appearance-family':
            for key in ('additionalLightnessSpread', 'additionalColorSpreadDeltaE76'):
                value = group.get(key)
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError('appearance family needs frozen finite source-relative allowances')
        ids = group.get('nodeIds', [])
        if not ids or not set(ids) <= source['nodes'].keys() or not set(ids) <= actual['nodes'].keys():
            raise ValueError('continuity nodes must exist in both corresponding snapshots')
        measured = {}
        for side, doc in [('source', source), ('actual', actual)]:
            values = index[group['id']].get(side)
            if not isinstance(values, list) or len(values) != len(points) or [v.get('xy') for v in values] != points:
                raise ValueError('continuity sampling coordinates differ from the frozen responsibilities')
            if any(set(v) != {'image', 'xy'} for v in values):
                raise ValueError('displayed continuity requires native screenshot pixels')
            colors = [displayed_color(doc, v, images) for v in values]
            for value in values:
                image = images[(value['image']['path'], value['image']['sha256'])]
                if list(image.size) != group.get('nativePixels'):
                    raise ValueError('continuity requires the frozen 1:1 screenshot size')
                if side == 'actual' and value['image'] not in native_evidence:
                    native_evidence.append(value['image'])
            measured[side] = {'rgb8': [[round(c * 255) for c in rgb] for rgb in colors],
                              'maximumChannelDelta': max(abs(a[c] - b[c]) * 255 for a in colors for b in colors for c in range(3))}
            if kind in {'appearance-family', 'source-appearance-equivalence', 'surface-linked-appearance'}:
                measured[side].update(appearance_spread(colors))
        if kind == 'appearance-family':
            limits = {'lightnessSpread': measured['source']['lightnessSpread'] + group['additionalLightnessSpread'],
                      'colorSpreadDeltaE76': measured['source']['colorSpreadDeltaE76'] + group['additionalColorSpreadDeltaE76']}
            passed = all(measured['actual'][key] <= value + 1e-9 for key, value in limits.items())
            measured['limits'] = limits
        elif kind in {'source-appearance-equivalence', 'surface-linked-appearance'}:
            source_equivalent = (measured['source']['lightnessSpread'] <= 2 and
                                 measured['source']['colorSpreadDeltaE76'] <= 2)
            limits = {'lightnessSpread': measured['source']['lightnessSpread'],
                      'colorSpreadDeltaE76': measured['source']['colorSpreadDeltaE76']}
            passed = source_equivalent and all(
                measured['actual'][key] <= value + 1e-9 for key, value in limits.items())
            measured['sourceAppearanceEquivalent'] = source_equivalent
            measured['limits'] = limits
            if kind == 'surface-linked-appearance':
                measured['anchorPointIndex'] = group['anchorPointIndex']
                measured['targetBasis'] = group['targetBasis']
        elif kind == 'source-topology':
            source_continuous = measured['source']['maximumChannelDelta'] <= limit + 1e-9
            target_limit = min(limit, measured['source']['maximumChannelDelta'] + 4)
            passed = not source_continuous or measured['actual']['maximumChannelDelta'] <= target_limit + 1e-9
            measured['sourceContinuous'] = source_continuous
            measured['targetContinuous'] = measured['actual']['maximumChannelDelta'] <= limit + 1e-9
            measured['targetLimit'] = target_limit
        else:
            passed = all(v['maximumChannelDelta'] <= limit + 1e-9 for v in measured.values())
        results.append({'id': group['id'], 'status': 'pass' if passed else 'fail', **measured})
    return {'status': 'pass' if all(g['status'] == 'pass' for g in results) else 'fail',
            'groups': results, 'nativeEvidence': native_evidence}


def verify_all_displayed_relations(source, actual, rules, evidence):
    """Partition one evidence file by frozen rules, without dropping any groups."""
    applicable = [r for r in rules.values()
                  if r.get('kind') == 'machine' and r.get('applicable') and
                  r.get('verifier', {}).get('type') == 'displayed-relations']
    declared = [g['id'] for r in applicable for g in r['verifier']['groups']]
    samples = evidence.get('groups', [])
    ids = [g['id'] for g in samples]
    if (len(set(declared)) != len(declared) or len(set(ids)) != len(ids) or
            set(ids) != set(declared)):
        raise ValueError('displayed evidence must cover exactly all frozen rule groups')
    return {r['id']: verify_displayed_relations(source, actual, r,
                {**evidence, 'groups': [g for g in samples if g['id'] in
                    {v['id'] for v in r['verifier']['groups']}]})
            for r in applicable}


def verify_rule(source, actual, rule):
    verifier = rule.get('verifier', {})
    kind = verifier.get('type')
    failures = []
    if kind in ('preserve-values', 'preserve-hsv'):
        paths = verifier.get('paths')
        if not isinstance(paths, list) or not paths or len(set(paths)) != len(paths):
            raise ValueError('nonempty unique verifier paths required')
        channels = verifier.get('channels')
        if kind == 'preserve-hsv' and (not isinstance(channels, list) or not channels
                                      or not set(channels) <= {'s', 'v', 'a'}):
            raise ValueError('HSV verifier channels must be s/v/a')
        for path in paths:
            baseline, value = at(source, path), at(actual, path)
            if baseline == MISSING or value == MISSING:
                failures.append({'path': path, 'error': 'missing value'})
                continue
            if kind == 'preserve-values':
                valid = equal(baseline, value)
            else:
                def hsv(color):
                    if not isinstance(color, dict) or not all(k in color for k in ('r', 'g', 'b')):
                        raise ValueError('HSV verifier requires RGB color objects')
                    h, s, v = colorsys.rgb_to_hsv(color['r'], color['g'], color['b'])
                    return {'s': s, 'v': v, 'a': color.get('a', 1)}
                left, right = hsv(baseline), hsv(value)
                valid = all(target_equal(left[c], right[c]) for c in channels)
            if not valid:
                failures.append({'path': path, 'source': baseline, 'actual': value})
    elif kind == 'target-values':
        targets = verifier.get('targets')
        if not isinstance(targets, list) or not targets:
            raise ValueError('nonempty declared target values required')
        for target in targets:
            path = target['path']; value = at(actual, path)
            if value == MISSING or not target_equal(value, target['expected']):
                failures.append({'path': path, 'actual': value, 'expected': target['expected']})
    else:
        raise ValueError('unsupported machine verifier: ' + str(kind))
    return {'status': 'fail' if failures else 'pass', 'failures': failures}


def finalize(spec):
    """Recompute machine checks and match fresh scene gates to the frozen rule ledger."""
    source = read_json(spec['sourceBefore'])
    source_now = read_json(spec['sourceNow'])
    actual = read_json(spec['cloneNow'])
    plan = read_json(spec['manifest'])
    policy = read_json(spec['policy'])
    mapping = read_json(spec['nodeMap']) if spec.get('nodeMap') else None
    ledger = read_json(spec['ruleLedger'])
    if ledger.get('schemaVersion') != 1 or not isinstance(ledger.get('rules'), list):
        raise ValueError('rule ledger required')
    rules = {}
    source_ids = set(snapshot_document(source)['nodes'])
    for rule in ledger['rules']:
        name = rule.get('id')
        if not isinstance(name, str) or not name or name in rules:
            raise ValueError('missing/duplicate ledger rule ID')
        if rule.get('kind') not in ('machine', 'visual') or type(rule.get('applicable')) is not bool:
            raise ValueError('rule kind and explicit applicability required')
        if not all(isinstance(rule.get(k), str) and rule[k].strip() for k in ('acceptance', 'source')):
            raise ValueError('rule source and concrete acceptance required')
        if not rule['applicable'] and not rule.get('notApplicableEvidence'):
            raise ValueError('not-applicable needs predeclared evidence')
        if rule['kind'] == 'visual' and rule['applicable']:
            scope = rule.get('scopeNodeIds')
            if not isinstance(scope, list) or not scope or not set(scope) <= source_ids:
                raise ValueError('visual rule requires existing source scopeNodeIds')
        rules[name] = rule
    if not (MACHINE_RULES | VISUAL_RULES) <= rules.keys():
        raise ValueError('baseline rules cannot be omitted')
    for name in MACHINE_RULES:
        if rules[name]['kind'] != 'machine' or not rules[name]['applicable']:
            raise ValueError('baseline machine rules cannot be skipped')
    for name in VISUAL_RULES:
        if rules[name]['kind'] != 'visual':
            raise ValueError('baseline visual rule kind mismatch')
    for name in ('kv-fit', 'theme-consistency', 'clarity', 'hierarchy', 'readability'):
        if not rules[name]['applicable']:
            raise ValueError('whole-page baseline visual rule cannot be skipped')
    ledger_hash = digest(ledger)
    if plan.get('ruleLedgerHash') != ledger_hash:
        raise ValueError('manifest must bind the frozen rule ledger')
    # The compiler records semantic classification IDs on color channels.
    # Those IDs are checked by coverage and the frozen recipe; only gate IDs
    # need matching machine/visual declarations in the rule ledger.
    if any(entry['ruleId'] not in rules and
           entry['ruleId'] not in ('inactive-source-channel', 'protected-hero-controls') and
           not entry['ruleId'].startswith('semantic-theme:')
           for entry in plan['entries']):
        raise ValueError('manifest references an undeclared rule')
    done = complete(source, actual, plan, policy, mapping)
    source_guard = compare(source, source_now, {'schemaVersion': 1, 'allowedChanges': [], 'protectedPaths': []})
    machine = {'source-unchanged': source_guard, 'clone-allowed-differences': done['propertyGuard'],
               'color-coverage': done['coverage'], 'plan-complete': done,
               'color-bindings-clear': color_binding_audit(actual)}
    relation_rule = rules['color-relations'].get('verifier', {})
    if not spec.get('colorRelations') or relation_rule.get('type') != 'color-relations':
        raise ValueError('frozen colorRelations are required, including after local corrections')
    relations = read_json(spec['colorRelations'])
    if relation_rule.get('groupsHash') != digest(relations):
        raise ValueError('color relations differ from frozen groups')
    automatic_relations = relations.get('automaticGroupPlans', [])
    if not relations.get('groups') and not relation_rule.get('emptyEvidence') and not automatic_relations:
        raise ValueError('empty color relations require predeclared source evidence')
    machine['color-relations'] = color_relations(source, actual, relations, mapping, plan)
    if not relations.get('groups') and relation_rule.get('emptyEvidence'):
        machine['color-relations']['notApplicableEvidence'] = relation_rule['emptyEvidence']
    source_doc, actual_doc = mapped_document(source, actual, mapping)
    surface_rule = rules['surface-system'].get('verifier', {})
    if (surface_rule.get('type') != 'surface-system' or
            surface_rule.get('planHash') != digest(plan.get('surfaceSystemPlan'))):
        raise ValueError('surface-system rule must bind the frozen surfaceSystemPlan')
    from surface_system_audit import inspect as inspect_surface_system
    machine['surface-system'] = inspect_surface_system(source, actual, plan, rules, mapping)
    machine['scheme-anchor-conformance'] = scheme_anchor_requirements(plan, source)
    machine['interaction-requirements'] = interaction_requirements(source, plan, rules)
    from interaction_entry_audit import inspect as inspect_entries
    machine['interaction-entry-coverage'] = inspect_entries(source, plan, ledger)
    unit_rule = rules['visual-unit-coverage'].get('verifier', {})
    if not spec.get('visualUnits') or unit_rule.get('type') != 'visual-unit-coverage':
        raise ValueError('frozen visualUnits are required for full and local runs')
    registry = read_json(spec['visualUnits'])
    if unit_rule.get('registryHash') != digest(registry):
        raise ValueError('visual units differ from the frozen registry')
    unit_result = visual_units(source, plan, registry, rules)
    machine['visual-unit-coverage'] = unit_result
    machine['icon-glyph-coverage'] = icon_glyph_requirements(source, plan, rules)
    contrast_rule = rules['contrast-baseline'].get('verifier', {})
    if contrast_rule.get('type') != 'contrast-baseline' or not spec.get('contrastSamples'):
        raise ValueError('frozen contrast relationships and fresh contrastSamples required')
    machine['contrast-baseline'] = compare_contrast(
        source_doc, actual_doc, read_json(spec['contrastSamples']), contrast_rule.get('relationships'),
        contrast_rule.get('emphasisOrders', []), contrast_rule.get('policy', 'source-baseline'),
        contrast_rule.get('decisionContext'))
    mapped_actual_snapshot = {**actual, 'rootId': source['rootId'],
                              'nodes': [{'id': node_id, **row}
                                        for node_id, row in actual_doc['nodes'].items()]}
    machine['text-range-coverage'] = text_range_requirements(
        source, plan, contrast_rule.get('relationships', []), rules, mapped_actual_snapshot)
    machine['cross-mode-composite-coverage'] = cross_mode_composite_requirements(
        source, actual, plan, rules, mapping)
    if any(r.get('kind') == 'machine' and r.get('applicable') and
           r.get('verifier', {}).get('type') == 'displayed-relations' for r in rules.values()):
        if not spec.get('displayedSamples'):
            raise ValueError('fresh displayedSamples required for displayed relations')
        machine.update(verify_all_displayed_relations(
            source_doc, actual_doc, rules, read_json(spec['displayedSamples'])))
    for rule in rules.values():
        if rule['kind'] == 'machine' and rule['applicable'] and rule['id'] not in machine:
            machine[rule['id']] = verify_rule(source_doc, actual_doc, rule)
    reviewed, gate_results, unit_reviews = {}, [], set()
    errors = []
    whole_page_reviewed = False
    family_rule = rules['control-family-consistency']
    family_compared = not family_rule['applicable']
    reviewed_evidence = []
    for scene in spec.get('visualScenes', []):
        scene_spec, gate = read_json(scene['spec']), read_json(scene['gate'])
        if scene_spec.get('recipe', {}).get('ruleLedgerHash') != ledger_hash:
            errors.append({'sceneId': scene_spec.get('sceneId'), 'error': 'scene uses stale or missing rules'})
            continue
        state = scene_state(actual, scene_spec)
        result = check_gate(state, gate)
        gate_results.append(result)
        if result['status'] != 'pass':
            continue
        reviewed_evidence.extend(gate.get('evidence', []))
        context = set(state['payload']['context'])
        requirements = {r['id']: r for r in scene_spec['reviewRequirements']}
        family_requirement = requirements.get('control-family-consistency', {})
        family_nodes = {mapping.get(n, n) if mapping else n
                        for n in family_rule.get('scopeNodeIds', [])}
        if (family_rule['applicable'] and
                family_requirement.get('acceptance') == family_rule['acceptance'] and
                family_nodes <= set(family_requirement.get('nodeIds', []))):
            family_compared = True
        for unit_id, unit in unit_result['units'].items():
            clone_ids = lambda ids: {mapping.get(n, n) if mapping else n for n in ids}
            if (clone_ids(unit['dependencies']) <= context and
                    all(rule_id in requirements and
                        requirements[rule_id]['acceptance'] == rules[rule_id]['acceptance'] and
                        clone_ids(unit['reviewNodeIds']) <= set(requirements[rule_id]['nodeIds'])
                        for rule_id in unit['reviewRuleIds'])):
                unit_reviews.add(unit_id)
        if scene_spec.get('reviewScope') == 'whole-page':
            if set(state['payload']['context']) != set(snapshot_document(actual)['nodes']):
                errors.append({'sceneId': scene_spec['sceneId'], 'error': 'whole-page scene has incomplete context'})
            elif any(r['id'] == 'hierarchy' and actual['rootId'] in r['nodeIds']
                     for r in scene_spec['reviewRequirements']):
                whole_page_reviewed = True
        for requirement in scene_spec['reviewRequirements']:
            name = requirement['id']
            rule = rules.get(name)
            if not rule or rule['kind'] != 'visual' or not rule['applicable'] or requirement['acceptance'] != rule['acceptance']:
                errors.append({'sceneId': scene_spec['sceneId'], 'ruleId': name, 'error': 'review differs from frozen acceptance'})
            else:
                reviewed.setdefault(name, set()).update(requirement['nodeIds'])
    missing = sorted(name for name, rule in rules.items()
                     if rule['kind'] == 'visual' and rule['applicable'] and name not in reviewed)
    uncovered = {name: sorted({mapping.get(n, n) if mapping else n for n in rule['scopeNodeIds']}
                             - reviewed.get(name, set()))
                 for name, rule in rules.items() if rule['kind'] == 'visual' and rule['applicable']}
    uncovered = {name: nodes for name, nodes in uncovered.items() if nodes}
    if not whole_page_reviewed:
        errors.append({'error': 'fresh whole-page hierarchy review required; local passes are insufficient'})
    unreviewed_units = sorted(unit_result['units'].keys() - unit_reviews)
    if unreviewed_units:
        errors.append({'error': 'visual unit lacks a fresh complete-context review',
                       'unitIds': unreviewed_units})
    if not family_compared:
        errors.append({'error': 'fresh cross-region control-family comparison required; separate local passes are insufficient'})
    for result in machine.values():
        for evidence in result.get('nativeEvidence', []):
            if evidence not in reviewed_evidence:
                errors.append({'error': 'displayed relation uses an image outside the fresh accepted visual gate', 'image': evidence['path']})
    passed = all(v['status'] == 'pass' for v in machine.values()) and all(g['status'] == 'pass' for g in gate_results)
    return {'status': 'pass' if passed and not missing and not uncovered and not errors else 'fail',
            'ruleLedgerHash': ledger_hash, 'machineChecks': machine, 'visualGates': gate_results,
            'missingVisualRules': missing, 'uncoveredVisualNodes': uncovered, 'errors': errors,
            'unreviewedVisualUnits': unreviewed_units,
            'note': 'Verifies recorded coverage and evidence freshness, not the truth of an artistic judgment.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    inv = subs.add_parser('inventory'); inv.add_argument('source')
    cov = subs.add_parser('coverage'); cov.add_argument('source'); cov.add_argument('manifest')
    done = subs.add_parser('complete')
    for field in ('source', 'actual', 'manifest', 'policy'):
        done.add_argument(field)
    done.add_argument('--map', dest='mapping')
    batch = subs.add_parser('batch-plan'); batch.add_argument('batch')
    batch.add_argument('--max-operations', type=int, default=64)
    batch.add_argument('--max-bytes', type=int, default=48000)
    final = subs.add_parser('finalize'); final.add_argument('spec')
    impact = subs.add_parser('impact', help='compute visual-unit closure before a local correction')
    for field in ('source', 'manifest', 'registry', 'relations', 'relationships', 'changes'):
        impact.add_argument(field)
    for sub in (inv, cov, done, batch, final, impact):
        sub.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'inventory':
            result = color_inventory(read_json(args.source))
        elif args.command == 'coverage':
            result = coverage(read_json(args.source), read_json(args.manifest))
        elif args.command == 'complete':
            result = complete(read_json(args.source), read_json(args.actual), read_json(args.manifest),
                              read_json(args.policy), read_json(args.mapping) if args.mapping else None)
        elif args.command == 'batch-plan':
            result = batch_plan(read_json(args.batch), args.max_operations, args.max_bytes)
        elif args.command == 'impact':
            result = affected_units(*(read_json(getattr(args, field)) for field in
                                      ('source', 'manifest', 'registry', 'relations', 'relationships', 'changes')))
        else:
            result = finalize(read_json(args.spec))
        save_json(args.out, result)
        print(canonical({'status': result.get('status', 'recorded'), 'output': args.out}))
        return 0 if result.get('status', 'pass') == 'pass' else 1
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        save_json(args.out, {'status': 'error', 'error': str(exc)})
        print(canonical({'status': 'error', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())

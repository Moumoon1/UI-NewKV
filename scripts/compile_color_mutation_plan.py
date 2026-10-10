#!/usr/bin/env python3
"""Compile a reviewed manifest into an offline write plan and source-ID projection.

The compiler only plans already-authorized color/binding/opacity changes. It
never invents semantic roles, target colors, detach choices or visual PASS.
The expected projection deliberately excludes the new KV subtree; Figma's
guarded write function inserts and locks that separately.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from execution_audit import color_binding_audit, coverage
from derive_vector_mirrors import inspect as inspect_vector_mirrors
from generate_theme_apply_js import build as build_writer
from preflight_instance_writes import inspect as inspect_instance_writes
from theme_audit import at, differences, digest, equal, parts, save_json, snapshot_document


def _path_map(source):
    rows = snapshot_document(source)['nodes']
    paths = {source['rootId']: []}
    pending = [source['rootId']]
    while pending:
        node_id = pending.pop()
        for index, child in enumerate(rows[node_id]['children']):
            paths[child] = paths[node_id] + [index]
            pending.append(child)
    if set(paths) != set(rows):
        raise ValueError('source node graph is disconnected')
    return paths


def _set_pointer(document, path, value):
    tokens = parts(path)
    cursor = document
    for token in tokens[:-1]:
        cursor = cursor[int(token)] if isinstance(cursor, list) else cursor[token]
    key = tokens[-1]
    if isinstance(cursor, list):
        cursor[int(key)] = deepcopy(value)
    else:
        cursor[key] = deepcopy(value)


def _clear_paint_bindings(value):
    if isinstance(value, dict):
        value.pop('boundVariables', None)
        for child in value.values():
            _clear_paint_bindings(child)
    elif isinstance(value, list):
        for child in value:
            _clear_paint_bindings(child)


def _active(value):
    return value not in (None, '', [], {}, {'$undefined': True})


def _has_active_color_binding(value):
    if isinstance(value, dict):
        bindings = value.get('boundVariables')
        if isinstance(bindings, dict) and any(_active(v) for v in bindings.values()):
            return True
        return any(_has_active_color_binding(child) for key, child in value.items()
                   if key != 'boundVariables')
    if isinstance(value, list):
        return any(_has_active_color_binding(child) for child in value)
    return False


def _clear_node_bindings(before, props):
    node_bindings = props.get('boundVariables')
    old_node_bindings = before.get('boundVariables') or {}
    for prop, style in (('fills', 'fillStyleId'), ('strokes', 'strokeStyleId')):
        needs_setter = (not equal(before.get(prop), props.get(prop)) or
                        _active(before.get(style)) or _active(old_node_bindings.get(prop)) or
                        _has_active_color_binding(before.get(prop)))
        if needs_setter and _active(props.get(style)):
            props[style] = ''
        if needs_setter and prop in props:
            _clear_paint_bindings(props[prop])
        if needs_setter and isinstance(node_bindings, dict):
            node_bindings.pop(prop, None)
    effects = props.get('effects') or []
    if any(isinstance(effect, dict) and isinstance(effect.get('color'), dict)
           for effect in effects):
        if _active(props.get('effectStyleId')) or any(
                isinstance(effect, dict) and _active(effect.get('boundVariables'))
                for effect in effects):
            raise ValueError('color effect binding needs an explicit effect setter')
    node_bindings = props.get('boundVariables')
    if isinstance(node_bindings, dict) and _active(node_bindings.get('effects')):
        raise ValueError('node color effect binding needs an explicit effect setter')
    text_runs = props.get('textRuns') or {}
    old_runs = (before.get('textRuns') or {}).get('fills') or []
    new_runs = text_runs.get('fills') or []
    if _active(old_node_bindings.get('textRangeFills')) and not old_runs:
        raise ValueError('text range binding has no writable styled range')
    old_styles = (before.get('textRuns') or {}).get('fillStyleId') or []
    new_styles = text_runs.get('fillStyleId') or []
    for index, (old, new) in enumerate(zip(old_runs, new_runs)):
        style = old_styles[index].get('value') if index < len(old_styles) else None
        needs_setter = (not equal(old['value'], new['value']) or _active(style) or
                        _active(old_node_bindings.get('textRangeFills')) or
                        _has_active_color_binding(old['value']))
        if needs_setter:
            _clear_paint_bindings(new['value'])
            if index < len(new_styles):
                new_styles[index]['value'] = ''
    if isinstance(node_bindings, dict):
        node_bindings.pop('textRangeFills', None)
    if 'vectorNetwork' in props and (
            not equal(before.get('vectorNetwork'), props.get('vectorNetwork')) or
            _has_active_color_binding(before.get('vectorNetwork'))):
        _clear_paint_bindings(props['vectorNetwork'])
    decoration = props.get('textDecorationColor')
    if isinstance(decoration, dict) and _active(decoration.get('boundVariables')):
        raise ValueError('text decoration color binding needs an explicit writer')


def _apply_opacity(expected, rows, node_paths, opacity_ops):
    seen = set()
    normalized = []
    for op in opacity_ops:
        node_id = op.get('sourceId')
        if node_id not in rows or not isinstance(op.get('reason'), str) or not op['reason'].strip():
            raise ValueError('opacity exception needs exact source node and reason')
        prop = op.get('property')
        index = op.get('paintIndex') if prop == 'fills' else None
        key = (node_id, prop, index)
        if key in seen:
            raise ValueError('duplicate opacity exception')
        seen.add(key)
        value = op.get('after')
        if type(value) not in (int, float) or not 0 <= value <= 1:
            raise ValueError('opacity target must be 0..1')
        props = rows[node_id]['props']
        if prop == 'opacity':
            before = props.get('opacity', 1)
            props['opacity'] = value
        elif prop == 'fills' and isinstance(index, int) and isinstance(props.get('fills'), list) \
                and 0 <= index < len(props['fills']):
            before = props['fills'][index].get('opacity', 1)
            props['fills'][index]['opacity'] = value
            _clear_paint_bindings(props['fills'])
        else:
            raise ValueError('unsupported opacity exception')
        if 'before' not in op or not equal(before, op['before']):
            raise ValueError('opacity before mismatch')
        path = node_paths[node_id]
        if 'path' in op and op['path'] != path:
            raise ValueError('opacity source path mismatch')
        normalized.append({**op, 'path': path})
    return normalized


def _apply_text_paint_alpha(rows, text_ops):
    seen = set()
    for op in text_ops:
        node_id = op.get('sourceId')
        if node_id not in rows or rows[node_id]['props'].get('type') != 'TEXT' or \
                not isinstance(op.get('reason'), str) or not op['reason'].strip():
            raise ValueError('text Paint alpha exception needs exact TEXT and reason')
        start, end, paint_index = op.get('start'), op.get('end'), op.get('paintIndex')
        key = (node_id, start, end, paint_index)
        if key in seen:
            raise ValueError('duplicate text Paint alpha exception')
        seen.add(key)
        value = op.get('after')
        if type(value) not in (int, float) or not 0 <= value <= 1:
            raise ValueError('text Paint alpha target must be 0..1')
        runs = rows[node_id]['props'].get('textRuns', {}).get('fills') or []
        matches = [run for run in runs if run['start'] == start and run['end'] == end]
        if len(matches) != 1 or not isinstance(paint_index, int) or \
                paint_index < 0 or paint_index >= len(matches[0]['value']):
            raise ValueError('text Paint alpha range/paint missing')
        paint = matches[0]['value'][paint_index]
        if 'before' in op and not equal(paint.get('opacity', 1), op['before']):
            raise ValueError('text Paint alpha before mismatch')
        paint['opacity'] = value
        _clear_paint_bindings(matches[0]['value'])
    return text_ops


def build(source, kv_source, manifest, options):
    source_doc = snapshot_document(source)
    kv_doc = snapshot_document(kv_source)
    if options.get('schemaVersion') != 1 or options.get('sourceHash') != digest(source_doc):
        raise ValueError('options do not match source snapshot')
    if options.get('kvSourceId') != kv_source.get('rootId') or \
            kv_doc['nodes'][kv_source['rootId']]['props'].get('type') != 'FRAME':
        raise ValueError('explicit complete KV Frame snapshot required')
    cover = coverage(source, manifest)
    if cover['status'] != 'pass':
        raise ValueError('color manifest must have complete reviewed channel coverage')
    if not isinstance(options.get('schemeId'), str) or not options['schemeId'].strip():
        raise ValueError('schemeId required')
    if not isinstance(options.get('sourceFingerprint'), str) or not options['sourceFingerprint']:
        raise ValueError('live source fingerprint required')
    expected = deepcopy(source)
    source_rows = {row['id']: row for row in source['nodes']}
    target_rows = {row['id']: row for row in expected['nodes']}
    node_paths = _path_map(source)
    for entry in manifest['entries']:
        if entry['disposition'] != 'change':
            continue
        tokens = parts(entry['path'])
        if len(tokens) < 6 or tokens[:1] != ['nodes'] or tokens[2] != 'props':
            raise ValueError('invalid changed color path: ' + entry['path'])
        if tokens[3] not in ('fills', 'strokes', 'textRuns', 'vectorNetwork'):
            raise ValueError('changed channel has no supported writer: ' + entry['path'])
        current = at(source_doc, entry['path'])
        target = entry['target']
        if not isinstance(current, dict) or not isinstance(target, dict):
            raise ValueError('changed channel must be a complete RGB object')
        if any(key not in current or key not in target for key in 'rgb'):
            raise ValueError('changed channel has incomplete RGB')
        if set(target) != set(current) or any(
                key not in ('r', 'g', 'b') and not equal(current[key], target[key])
                for key in current):
            raise ValueError('manifest color change may not alter alpha or structure')
        _set_pointer(target_rows[tokens[1]]['props'], '/' + '/'.join(tokens[3:]), target)
    for row in expected['nodes']:
        _clear_node_bindings(source_rows[row['id']]['props'], row['props'])
    opacity_ops = _apply_opacity(expected, target_rows, node_paths,
                                 options.get('opacityOps') or [])
    text_alpha_ops = _apply_text_paint_alpha(target_rows,
                                              options.get('textPaintAlphaOps') or [])
    operations = []
    for row in source['nodes']:
        node_id = row['id']
        before = row['props']
        after = target_rows[node_id]['props']
        for prop in ('fills', 'strokes'):
            binding = (before.get('boundVariables') or {}).get(prop)
            if not equal(before.get(prop), after.get(prop)) or \
                    not equal(before.get('fillStyleId' if prop == 'fills' else 'strokeStyleId'),
                              after.get('fillStyleId' if prop == 'fills' else 'strokeStyleId')) or \
                    _active(binding):
                if not isinstance(before.get(prop), list) or not isinstance(after.get(prop), list):
                    if before.get('type') == 'TEXT' and prop == 'fills' and \
                            before.get('fills') == {'$mixed': True} and \
                            after.get('fills') == {'$mixed': True}:
                        continue  # Styled range setters clear the mixed text paint style.
                    raise ValueError('non-list Paint property requires manual writer: ' + node_id)
                operations.append({'kind': 'property', 'sourceId': node_id,
                                   'property': prop, 'path': node_paths[node_id],
                                   'before': before[prop], 'after': after[prop],
                                   'colorChanged': any(e['disposition'] == 'change' and
                                        e['path'].startswith('/nodes/' + node_id + '/props/' + prop + '/')
                                        for e in manifest['entries']),
                                   'bindingCleared': not equal(before.get(
                                        'fillStyleId' if prop == 'fills' else 'strokeStyleId'),
                                        after.get('fillStyleId' if prop == 'fills' else 'strokeStyleId'))})
        old_runs = (before.get('textRuns') or {}).get('fills') or []
        new_runs = (after.get('textRuns') or {}).get('fills') or []
        old_styles = (before.get('textRuns') or {}).get('fillStyleId') or []
        text_binding = _active((before.get('boundVariables') or {}).get('textRangeFills'))
        if len(old_runs) != len(new_runs):
            raise ValueError('styled text run structure changed')
        for index, (old, new) in enumerate(zip(old_runs, new_runs)):
            if old['start'] != new['start'] or old['end'] != new['end']:
                raise ValueError('styled text range changed')
            style_changed = (index < len(old_styles) and _active(old_styles[index].get('value')))
            if not equal(old['value'], new['value']) or style_changed or text_binding:
                operations.append({'kind': 'text-range', 'sourceId': node_id,
                                   'path': node_paths[node_id], 'start': old['start'],
                                   'end': old['end'], 'before': old['value'],
                                   'after': new['value'],
                                   'bindingCleared': True})
    detach = options.get('detachInstanceIds') or []
    if len(detach) != len(set(detach)) or any(
            node_id not in source_rows or source_rows[node_id]['props'].get('type') != 'INSTANCE'
            for node_id in detach):
        raise ValueError('invalid explicit detachInstanceIds')
    write_plan = {'schemaVersion': 1, 'schemeId': options['schemeId'],
                  'sourceRootId': source['rootId'], 'kvSourceId': kv_source['rootId'],
                  'sourceFingerprint': options['sourceFingerprint'],
                  'operations': operations, 'opacityOps': opacity_ops,
                  'detachInstanceIds': detach,
                  'postDetachMapping': 'structural-fingerprint' if detach else None}
    mixed_needing_range = [row['id'] for row in source['nodes']
                           if row['props'].get('type') == 'TEXT' and
                           row['props'].get('fills') == {'$mixed': True} and
                           not equal(row['props'].get('fillStyleId'),
                                     target_rows[row['id']]['props'].get('fillStyleId')) and
                           not any(op['kind'] == 'text-range' and op['sourceId'] == row['id']
                                   for op in operations)]
    if mixed_needing_range:
        raise ValueError('mixed text style has no range setter: ' + mixed_needing_range[0])
    binding_check = color_binding_audit(expected)
    if binding_check['status'] != 'pass':
        raise ValueError('projected UI still has color bindings')
    vector_check = inspect_vector_mirrors(source, manifest, write_plan)
    if vector_check['status'] != 'pass':
        raise ValueError('vector mirror plan incomplete: ' + str(vector_check['errors'][:2]))
    instance_check = inspect_instance_writes(source, write_plan)
    if instance_check['status'] != 'pass':
        raise ValueError('instance write plan invalid: ' + str(instance_check['errors'][:2]))
    writer = build_writer(source, manifest, write_plan, kv_source)
    if len(writer) > 45000:
        raise ValueError('generated Figma write function exceeds 45000-character budget')
    policy = {'schemaVersion': 1,
              'allowedChanges': differences(source_doc, snapshot_document(expected)),
              'protectedPaths': options.get('protectedPaths') or []}
    node_map = {node_id: node_id for node_id in source_rows}
    return {'expectedClone': expected, 'writePlan': write_plan,
            'policy': policy, 'nodeMap': node_map,
            'summary': {'operations': len(operations),
                        'opacityOps': len(opacity_ops),
                        'textPaintAlphaOps': len(text_alpha_ops),
                        'detachInstanceIds': len(detach),
                        'allowedChanges': len(policy['allowedChanges']),
                        'writerCharacters': len(writer),
                        'sourceHash': cover['sourceHash']}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'kv_source', 'manifest', 'options'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    values = [json.loads(getattr(args, name).read_text()) for name in
              ('source', 'kv_source', 'manifest', 'options')]
    result = build(*values)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for key in ('expectedClone', 'writePlan', 'policy', 'nodeMap'):
        save_json(args.out_dir / (key + '.json'), result[key])
    print(json.dumps(result['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()

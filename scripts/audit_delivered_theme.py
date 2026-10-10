#!/usr/bin/env python3
"""Audit one delivered Figma clone against its frozen source, plan and preview."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops

from execution_audit import color_binding_audit, color_inventory
from theme_audit import at, escape, snapshot_document, target_equal


def _pixels_identical(a, b):
    """Check every channel; RGBA getbbox() defaults to alpha-only in Pillow."""
    if a.size != b.size:
        return False
    delta = ImageChops.difference(a.convert('RGBA'), b.convert('RGBA'))
    return all(channel.getbbox() is None for channel in delta.split())


def rows(snapshot):
    snapshot_document(snapshot)
    return {row['id']: row for row in snapshot['nodes']}


def structural_map(source, actual, actual_root, *, excluded_root=None):
    source_rows, actual_rows = rows(source), rows(actual)
    mapping, mapped_ids, pending = {}, set(), [(source['rootId'], actual_root)]
    while pending:
        old_id, new_id = pending.pop()
        old, new = source_rows[old_id], actual_rows[new_id]
        if old_id in mapping or new_id in mapped_ids:
            raise ValueError('duplicate structural mapping')
        mapping[old_id] = new_id
        mapped_ids.add(new_id)
        old_children = old['children']
        new_children = [child for child in new['children'] if child != excluded_root]
        if len(old_children) != len(new_children):
            raise ValueError(f'child count changed at {old_id}')
        pending.extend(zip(old_children, new_children))
    if len(mapping) != len(source_rows):
        raise ValueError('structural map incomplete')
    return mapping


def _paint_without_bindings(value):
    if isinstance(value, list):
        return [_paint_without_bindings(item) for item in value]
    if isinstance(value, dict):
        return {key: _paint_without_bindings(item) for key, item in value.items()
                if key != 'boundVariables'}
    return value


def _same_rendered_paints(expected, actual):
    return target_equal(_paint_without_bindings(actual),
                        _paint_without_bindings(expected))


def audit(source, expected, final, kv_source, manifest, write_plan, preview_png, final_png):
    errors = []
    src, exp, dst, kv_src = rows(source), rows(expected), rows(final), rows(kv_source)
    final_root = dst[final['rootId']]
    candidates = [child for child in final_root['children']
                  if dst[child]['props'].get('name') == kv_src[kv_source['rootId']]['props']['name']
                  and target_equal(dst[child]['props'].get('width'),
                                   kv_src[kv_source['rootId']]['props'].get('width'))
                  and target_equal(dst[child]['props'].get('height'),
                                   kv_src[kv_source['rootId']]['props'].get('height'))]
    if len(candidates) != 1:
        raise ValueError('unique inserted KV root not found')
    kv_root = candidates[0]
    mapping = structural_map(source, final, final['rootId'], excluded_root=kv_root)
    kv_mapping = structural_map(kv_source, final, kv_root)
    if len(dst) != len(src) + len(kv_src):
        errors.append('final node count is not source + locked KV')
    if set(mapping.values()) & set(kv_mapping.values()):
        errors.append('UI and KV subtree overlap')
    if set(mapping.values()) | set(kv_mapping.values()) != set(dst):
        errors.append('unexpected or missing final nodes')
    placement = write_plan.get('kvPlacement')
    if (not isinstance(placement, dict) or
            type(placement.get('childIndex')) is not int or
            not 0 <= placement['childIndex'] < len(final_root['children']) or
            any(type(placement.get(k)) not in (int, float) for k in ('x', 'y'))):
        raise ValueError('kvPlacement needs frozen childIndex, x and y')
    if final_root['children'][placement['childIndex']] != kv_root:
        errors.append('KV is not at the frozen child index')
    if any(not target_equal(dst[kv_root]['props'].get(k), placement[k]) for k in ('x', 'y')):
        errors.append('KV position differs from frozen placement')
    if dst[kv_root]['props'].get('locked') is not True:
        errors.append('KV root is not locked')

    detached = set(write_plan['detachInstanceIds'])
    max_geometry_drift = 0
    geometry_keys = ('width', 'height', 'rotation', 'characters', 'fontName',
                     'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing')
    for old_id, new_id in mapping.items():
        before, after = src[old_id]['props'], dst[new_id]['props']
        planned = exp[old_id]['props']
        if not target_equal(after.get('opacity', 1), planned.get('opacity', 1)):
            errors.append(f'node opacity mismatch: {old_id}')
        for key in ('fills', 'strokes', 'effects'):
            if before.get('type') == 'TEXT' and key == 'fills':
                continue  # Exact styled character spans are checked below.
            if key in planned and not _same_rendered_paints(planned[key], after.get(key)):
                errors.append(f'paint/material mismatch: {old_id}/{key}')
        expected_type = 'FRAME' if old_id in detached else before['type']
        if after['type'] != expected_type:
            errors.append(f'node type changed unexpectedly: {old_id}')
        for key in geometry_keys:
            if key in before:
                actual_value, old_value = after.get(key), before[key]
                if key in ('width', 'height') and isinstance(actual_value, (int, float)):
                    drift = abs(actual_value - old_value)
                    max_geometry_drift = max(max_geometry_drift, drift)
                    if drift > .002:
                        errors.append(f'geometry changed: {old_id}/{key}')
                elif not target_equal(actual_value, old_value):
                    errors.append(f'geometry/text changed: {old_id}/{key}')
        if old_id != source['rootId']:
            for key in ('x', 'y'):
                if key in before:
                    actual_value, old_value = after.get(key), before[key]
                    if isinstance(actual_value, (int, float)):
                        drift = abs(actual_value - old_value)
                        max_geometry_drift = max(max_geometry_drift, drift)
                        if drift > .002:
                            errors.append(f'local position changed: {old_id}/{key}')
                    elif not target_equal(actual_value, old_value):
                        errors.append(f'local position changed: {old_id}/{key}')
    for old_id, new_id in kv_mapping.items():
        before, after = kv_src[old_id]['props'], dst[new_id]['props']
        excluded = {'x', 'y', 'relativeTransform', 'locked'} if old_id == kv_source['rootId'] else set()
        for key, value in before.items():
            if key not in excluded and not target_equal(after.get(key), value):
                errors.append(f'locked KV changed: {old_id}/{key}')
    inventory = color_inventory(source)
    if len(inventory['entries']) != len(manifest['entries']):
        errors.append('manifest no longer covers source color inventory')
    entry_by_path = {item['path']: item for item in manifest['entries']}
    channels_checked = 0
    final_doc = snapshot_document(final)
    for item in inventory['entries']:
        entry = entry_by_path.get(item['path'])
        if not entry:
            errors.append(f'missing manifest entry: {item["path"]}')
            continue
        old_id, new_id = item['nodeId'], mapping[item['nodeId']]
        if '/props/textRuns/fills/' in item['path']:
            channels_checked += 1
            continue  # Figma merges adjacent equal styled ranges; compare spans below.
        old_prefix = '/nodes/' + escape(old_id)
        new_path = '/nodes/' + escape(new_id) + item['path'][len(old_prefix):]
        try:
            actual_color = at(final_doc, new_path)
        except (KeyError, IndexError, TypeError, ValueError):
            errors.append(f'final color path missing: {item["path"]}')
            continue
        expected_color = entry['target'] if entry['disposition'] == 'change' else item['source']
        if not all(target_equal(actual_color.get(key), expected_color[key]) for key in 'rgb'):
            errors.append(f'final color mismatch: {item["path"]}')
        channels_checked += 1

    text_spans_checked = 0
    for old_id, new_id in mapping.items():
        expected_runs = exp[old_id]['props'].get('textRuns', {}).get('fills', [])
        if not expected_runs:
            continue
        actual_runs = dst[new_id]['props'].get('textRuns', {}).get('fills', [])
        for wanted in expected_runs:
            cursor = wanted['start']
            for observed in actual_runs:
                if observed['end'] <= cursor or observed['start'] >= wanted['end']:
                    continue
                if observed['start'] > cursor:
                    break
                if not _same_rendered_paints(wanted['value'], observed['value']):
                    errors.append(f'text paint mismatch: {old_id}/{wanted["start"]}:{wanted["end"]}')
                    break
                cursor = min(wanted['end'], observed['end'])
                if cursor == wanted['end']:
                    break
            if cursor != wanted['end']:
                errors.append(f'text span missing: {old_id}/{wanted["start"]}:{wanted["end"]}')
            text_spans_checked += 1

    # The imported KV retains its own bindings. Audit only mapped UI nodes.
    ui_snapshot = {**final, 'nodes': [{**dst[new_id], 'id': new_id}
                                     for new_id in mapping.values()]}
    ui_snapshot['rootId'] = final['rootId']
    ui_root = next(row for row in ui_snapshot['nodes'] if row['id'] == final['rootId'])
    ui_root['children'] = [c for c in ui_root['children'] if c != kv_root]
    bindings = color_binding_audit(ui_snapshot)
    if bindings['status'] != 'pass':
        errors.append(f'UI color bindings remain: {bindings["residualCount"]}')
    with Image.open(preview_png) as a, Image.open(final_png) as b:
        dimensions = tuple(round(final_root['props'][k]) for k in ('width', 'height'))
        if a.size != b.size or a.size != dimensions:
            errors.append('preview/final screenshot dimensions differ')
            pixel_equal = False
        else:
            pixel_equal = _pixels_identical(a, b)
            if not pixel_equal:
                errors.append('final screenshot differs from approved preview')
    return {'status': 'fail' if errors else 'pass',
            'auditScope': 'write-and-render-conformance-only',
            'visualApproval': 'not-assessed',
            'note': 'Does not authorize delivery; execution_audit finalize and source-entry hierarchy review are required.',
            'sourceNodes': len(src),
            'finalNodes': len(dst), 'kvNodes': len(kv_mapping),
            'mappedUiNodes': len(mapping), 'detachedInstances': len(detached),
            'colorChannelsChecked': channels_checked,
            'textSpansChecked': text_spans_checked,
            'maxGeometryDriftPx': max_geometry_drift,
            'uiBindings': bindings['residualCount'], 'pixelIdenticalToPreview': pixel_equal,
            'kvCloneId': kv_root, 'kvPlacementChecked': placement is not None,
            'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'expected', 'final', 'kv_source', 'manifest', 'write_plan',
                 'preview_png', 'final_png'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(*(json.loads(getattr(args, name).read_text()) for name in
                     ('source', 'expected', 'final', 'kv_source', 'manifest', 'write_plan')),
                   args.preview_png, args.final_png)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'errors'}, ensure_ascii=False))
    if result['errors']:
        print(json.dumps(result['errors'][:30], ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()

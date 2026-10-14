#!/usr/bin/env python3
"""Catch Icon-container role leakage and weak selected Tabs before native preview.

These are conservative checks. Native 1:1 review remains required for gradients,
alpha compositing, and the final visual hierarchy.
"""

from __future__ import annotations


def _solid(props):
    if props.get('visible') is False or props.get('opacity', 1) != 1:
        return None
    paints = [paint for paint in props.get('fills') or [] if paint.get('visible', True)]
    if len(paints) != 1:
        return None
    paint = paints[0]
    if (paint.get('type') != 'SOLID' or paint.get('opacity', 1) != 1 or
            paint.get('blendMode', 'NORMAL') != 'NORMAL'):
        return None
    color = paint.get('color', {})
    return color if color.get('a', 1) == 1 and all(k in color for k in 'rgb') else None


def _luminance(color):
    def linear(value):
        return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
    return sum(weight * linear(color[key]) for key, weight in
               zip('rgb', (.2126, .7152, .0722)))


def _contrast(left, right):
    low, high = sorted((_luminance(left), _luminance(right)))
    return (high + .05) / (low + .05)


def _contains_center(carrier, glyph):
    a, b = carrier['props'], glyph['props']
    if not all(isinstance(a.get(k), (int, float)) and
               isinstance(b.get(k), (int, float)) for k in ('x', 'y', 'width', 'height')):
        return False
    if min(a['width'], a['height'], b['width'], b['height']) <= 0:
        return False
    area_ratio = a['width'] * a['height'] / (b['width'] * b['height'])
    cx, cy = b['x'] + b['width'] / 2, b['y'] + b['height'] / 2
    return (1 <= area_ratio <= 9 and a['x'] <= cx <= a['x'] + a['width'] and
            a['y'] <= cy <= a['y'] + a['height'])


def _host(nodes, node_id):
    parent_id = nodes[node_id]['parentId']
    while parent_id in nodes:
        color = _solid(nodes[parent_id]['props'])
        if color is not None:
            return parent_id, color
        parent_id = nodes[parent_id]['parentId']
    return None, None


def _descendant_text(nodes, node_id):
    pending = list(nodes[node_id]['children'])
    while pending:
        child_id = pending.pop()
        child = nodes[child_id]
        if child['props'].get('type') == 'TEXT' and _solid(child['props']) is not None:
            yield child_id
        pending.extend(child['children'])


def inspect(source, projected, manifest, contrast_policy='source-baseline'):
    source_nodes, target_nodes = source['nodes'], projected['nodes']
    entries = manifest.get('entries', [])
    by_node = {}
    for entry in entries:
        by_node.setdefault(entry.get('nodeId'), []).append(entry)
    issues, containers, tabs = [], [], []

    for root in manifest.get('iconGlyphPlan', {}).get('roots', []):
        glyph_id = root.get('rootNodeId')
        if glyph_id not in source_nodes:
            continue
        glyph = source_nodes[glyph_id]
        parent = source_nodes.get(glyph['parentId'])
        if parent is None:
            continue
        for sibling_id in parent['children']:
            if sibling_id == glyph_id:
                break
            sibling = source_nodes[sibling_id]
            props = sibling['props']
            if (props.get('visible') is False or props.get('opacity', 1) == 0 or
                    not (props.get('fills') or props.get('strokes')) or
                    not _contains_center(sibling, glyph)):
                continue
            active = [e for e in by_node.get(sibling_id, [])
                      if e.get('disposition') != 'ignore']
            host_kind = root.get('hostKind', 'standalone-icon')
            button_host = host_kind == 'button'
            bad = [e for e in active if not e.get('role', '').startswith(
                'button.' if button_host else 'icon.container')]
            containers.append({'glyphId': glyph_id, 'containerId': sibling_id,
                               'roles': sorted(set(e.get('role', '') for e in active)),
                               'hostKind': host_kind})
            if (not active or bad or host_kind not in {'standalone-icon', 'button'} or
                    (button_host and not root.get('buttonHostReason'))):
                issues.append({'kind': 'icon-container-role', 'glyphId': glyph_id,
                               'containerId': sibling_id,
                               'roles': sorted(set(e.get('role', '') for e in active))})

    tab_ids = sorted({e.get('nodeId') for e in entries
                      if e.get('role') == 'interaction.tab.selected' and e.get('nodeId')})
    for tab_id in tab_ids:
        if tab_id not in source_nodes or tab_id not in target_nodes:
            issues.append({'kind': 'selected-tab-missing', 'nodeId': tab_id})
            continue
        source_tab = _solid(source_nodes[tab_id]['props'])
        target_tab = _solid(target_nodes[tab_id]['props'])
        source_host_id, source_host = _host(source_nodes, tab_id)
        target_host_id, target_host = _host(target_nodes, tab_id)
        if None in (source_tab, target_tab, source_host, target_host):
            tabs.append({'nodeId': tab_id, 'status': 'needs-native-composite-review'})
            continue
        before = _contrast(source_tab, source_host)
        after = _contrast(target_tab, target_host)
        row = {'nodeId': tab_id, 'hostId': source_host_id,
               'targetHostId': target_host_id,
               'sourceBoundaryContrast': round(before, 4),
               'targetBoundaryContrast': round(after, 4), 'labels': []}
        if contrast_policy == 'source-baseline' and after + 1e-9 < before:
            issues.append({'kind': 'selected-tab-boundary-regression', **row})
        for text_id in _descendant_text(source_nodes, tab_id):
            if text_id not in target_nodes:
                continue
            source_text = _solid(source_nodes[text_id]['props'])
            target_text = _solid(target_nodes[text_id]['props'])
            if source_text is None or target_text is None:
                continue
            text_before = _contrast(source_text, source_tab)
            text_after = _contrast(target_text, target_tab)
            label = {'nodeId': text_id, 'sourceContrast': round(text_before, 4),
                     'targetContrast': round(text_after, 4)}
            row['labels'].append(label)
            if contrast_policy == 'source-baseline' and text_after + 1e-9 < text_before:
                issues.append({'kind': 'selected-tab-label-regression',
                               'tabId': tab_id, **label})
        tabs.append(row)

    return {'status': 'fail' if issues else 'pass', 'issues': issues,
            'iconContainers': containers, 'selectedTabs': tabs,
            'note': 'Solid-color and role preflight only; native composite and visual state review remain mandatory.'}

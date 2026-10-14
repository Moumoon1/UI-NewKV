#!/usr/bin/env python3
"""Fail-closed audit for surfaces, peer card bases and risky boundaries.

The audit deliberately separates a stable surface carrier from atmosphere and
material overlays.  Geometry is evidence, never the eligibility rule: semantic
roles and card ancestry discover review obligations, and authored plans must
classify every discovered painted node exactly once.
"""

import argparse
import json
import math
import re
from pathlib import Path

from contrast_audit import delta_e76
from execution_audit import color_inventory
from theme_audit import MISSING, at, digest, mapped_document, snapshot_document


SURFACE_KINDS = {'page', 'card', 'container', 'chrome', 'interaction',
                 'atmosphere', 'decoration', 'icon', 'state', 'protected', 'proxy'}
STABLE_KINDS = {'page', 'card', 'container'}
SURFACE_ROLE_TOKENS = {'page', 'background', 'surface', 'card', 'container',
                       'panel', 'section', 'chrome', 'atmosphere'}
COMMON_CONTENT_INSETS = (8, 12, 16, 20, 24, 32)
ROLE_KIND_PREFIXES = (
    ('surface.proxy', 'proxy'),
    ('surface.container', 'container'),
    ('surface.card', 'card'),
    ('surface.page', 'page'),
    ('card.chrome', 'chrome'),
    ('surface.chrome', 'chrome'),
    ('card.atmosphere', 'atmosphere'),
    ('surface.atmosphere', 'atmosphere'),
)
CONTINUOUS_CARD_KINDS = {'chrome', 'atmosphere', 'decoration'}


def _visible(doc, node_id):
    current = node_id
    while current in doc['nodes']:
        props = doc['nodes'][current]['props']
        if props.get('visible') is False or props.get('opacity', 1) == 0:
            return False
        current = doc['nodes'][current]['parentId']
    return True


def _box(doc, node_id, root_id):
    """Return an axis-aligned root-local box for ordinary unrotated layouts."""
    x = y = 0.0
    current = node_id
    while current in doc['nodes']:
        props = doc['nodes'][current]['props']
        if props.get('rotation', 0) not in (0, None):
            return None
        # Group children retain coordinates in the containing frame's space
        # in the collected Figma tree; adding an ancestor Group origin again
        # shifts the evidence away from the rendered carrier.
        if current != root_id and (current == node_id or props.get('type') != 'GROUP'):
            x += props.get('x', 0) or 0
            y += props.get('y', 0) or 0
        current = doc['nodes'][current]['parentId']
    props = doc['nodes'][node_id]['props']
    width, height = props.get('width'), props.get('height')
    if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0
               for v in (x, y, width, height)):
        return None
    return (x, y, x + width, y + height)


def _candidate_nodes(source):
    doc = snapshot_document(source)
    root_id = source['rootId']
    rows = [row for row in color_inventory(source)['entries']
            if not row['inactive'] and '/props/fills/' in row['path']]
    all_paths = {}
    for row in rows:
        node = doc['nodes'][row['nodeId']]
        props = node['props']
        if props.get('type') == 'TEXT' or not _visible(doc, row['nodeId']):
            continue
        paint_path = row['path'].split('/color', 1)[0]
        paint = at({'nodes': doc['nodes']}, paint_path)
        if isinstance(paint, dict) and paint.get('type') == 'IMAGE':
            continue
        all_paths.setdefault(row['nodeId'], []).append(row['path'])
    return doc, root_id, {
        node_id: sorted(values) for node_id, values in all_paths.items()}


def _role_is_surface(role):
    tokens = {token for token in re.split(r'[^a-z0-9]+', str(role).lower()) if token}
    return bool(tokens & SURFACE_ROLE_TOKENS)


def _semantic_surface_candidates(manifest, surfaces, doc, root_id, all_paths):
    """Find surface obligations without using size as a semantic shortcut.

    The exhaustive color manifest supplies authored surface roles.  Every
    declared surface is included, and every visible painted descendant of a
    declared card is included regardless of width, height or area.  The latter
    may later be classified as a container, interaction, icon or decoration;
    size never decides whether it receives review.
    """
    result = {}

    if root_id in all_paths:
        result[root_id] = all_paths[root_id]

    for entry in manifest.get('entries', []):
        node_id = entry.get('nodeId')
        if (node_id in all_paths and '/props/fills/' in str(entry.get('path')) and
                _role_is_surface(entry.get('role'))):
            result[node_id] = all_paths[node_id]

    for surface in surfaces.values():
        node_id = surface['nodeId']
        if node_id in all_paths:
            result[node_id] = all_paths[node_id]

    for card in surfaces.values():
        if card['kind'] != 'card':
            continue
        stack = list(doc['nodes'][card['nodeId']]['children'])
        while stack:
            node_id = stack.pop()
            node = doc['nodes'][node_id]
            stack.extend(node['children'])
            if node_id not in all_paths or not _visible(doc, node_id):
                continue
            result[node_id] = all_paths[node_id]
    return result


def _geometry_evidence(doc, node_id, root_id, surfaces):
    """Report relative geometry as classification evidence, never a cutoff."""
    box = _box(doc, node_id, root_id)
    evidence = {'nodeId': node_id, 'rootLocalBox': list(box or [])}
    if not box:
        return evidence

    card_nodes = {surface['nodeId'] for surface in surfaces.values()
                  if surface['kind'] == 'card'}
    current = doc['nodes'][node_id]['parentId']
    while current in doc['nodes'] and current not in card_nodes:
        current = doc['nodes'][current]['parentId']
    if current not in card_nodes:
        return evidence

    card_box = _box(doc, current, root_id)
    if not card_box:
        return evidence
    card_width = card_box[2] - card_box[0]
    card_height = card_box[3] - card_box[1]
    width = box[2] - box[0]
    height = box[3] - box[1]
    if card_width <= 0 or card_height <= 0:
        return evidence

    insets = {
        'left': box[0] - card_box[0],
        'top': box[1] - card_box[1],
        'right': card_box[2] - box[2],
        'bottom': card_box[3] - box[3],
    }

    def common_match(value):
        nearest = min(COMMON_CONTENT_INSETS, key=lambda candidate: abs(candidate - value))
        return nearest if abs(nearest - value) <= 1 else None

    evidence['cardGeometry'] = {
        'cardNodeId': current,
        'widthRatio': width / card_width,
        'heightRatio': height / card_height,
        'areaRatio': width * height / (card_width * card_height),
        'insetsPx': insets,
        'commonInsetMatchesPx': {
            side: common_match(value) for side, value in insets.items()},
        'symmetricHorizontalInset': abs(insets['left'] - insets['right']) <= 1,
        'symmetricVerticalInset': abs(insets['top'] - insets['bottom']) <= 1,
    }
    return evidence


def _boundary_candidates(doc, root_id, surfaces):
    result = {}
    painted_cache = {}

    def painted(node_id):
        if doc['nodes'][node_id]['props'].get('type') == 'TEXT':
            return False
        for paint in doc['nodes'][node_id]['props'].get('fills') or []:
            if (isinstance(paint, dict) and paint.get('visible', True) and
                    paint.get('opacity', 1) > 0 and paint.get('type') != 'IMAGE'):
                return True
        return False

    def painted_subtree(node_id):
        if node_id not in painted_cache:
            painted_cache[node_id] = (_visible(doc, node_id) and
                (painted(node_id) or any(painted_subtree(child_id)
                                      for child_id in doc['nodes'][node_id]['children'])))
        return painted_cache[node_id]

    # Sibling visual units that meet along an edge can be one displayed surface
    # even when their colors come from different nested paints or alpha stacks.
    # Discover the contact from source geometry, before authored relationship
    # groups can accidentally omit it.
    root_box = _box(doc, root_id, root_id)
    for parent_id, parent in doc['nodes'].items():
        siblings = [(node_id, _box(doc, node_id, root_id)) for node_id in parent['children']
                    if painted_subtree(node_id)]
        siblings = [(node_id, box) for node_id, box in siblings if box]
        for index, (left_id, left) in enumerate(siblings):
            for right_id, right in siblings[index + 1:]:
                for axis, side in ((1, 'bottom'), (0, 'right')):
                    lower, upper = (left, right) if left[axis] <= right[axis] else (right, left)
                    lower_id, upper_id = ((left_id, right_id) if left[axis] <= right[axis]
                                          else (right_id, left_id))
                    edge = lower[axis + 2]
                    overlap = (max(lower[1-axis], upper[1-axis]),
                               min(lower[3-axis], upper[3-axis]))
                    if root_box:
                        overlap = (max(overlap[0], root_box[1-axis]),
                                   min(overlap[1], root_box[3-axis]))
                    if (abs(edge - upper[axis]) > .5 or overlap[1] - overlap[0] < 8 or
                            (root_box and not root_box[axis] <= edge <= root_box[axis+2])):
                        continue
                    candidate_id = 'adjacent:' + parent_id + ':' + lower_id + ':' + upper_id
                    result[candidate_id] = {'id': candidate_id, 'kind': 'adjacent-surfaces',
                        'nodeIds': [lower_id, upper_id],
                        'rootLocalEdge': {'side': side, 'coordinate': edge,
                                          'span': list(overlap)}}

    # Any painted descendant crossing a clipping edge creates a review duty.
    for clip_id, clip in doc['nodes'].items():
        if not clip['props'].get('clipsContent') or not _visible(doc, clip_id):
            continue
        clip_box = _box(doc, clip_id, root_id)
        if not clip_box:
            continue
        descendants = []
        stack = list(clip['children'])
        while stack:
            child_id = stack.pop()
            child = doc['nodes'][child_id]
            stack.extend(child['children'])
            if painted(child_id) and _visible(doc, child_id):
                descendants.append(child_id)
        for side, index, direction in (('left', 0, -1), ('top', 1, -1),
                                       ('right', 2, 1), ('bottom', 3, 1)):
            crossing = []
            for child_id in descendants:
                child_box = _box(doc, child_id, root_id)
                if not child_box:
                    continue
                delta = child_box[index] - clip_box[index]
                if delta * direction > .5:
                    crossing.append(child_id)
            if crossing:
                candidate_id = 'clip:' + clip_id + ':' + side
                result[candidate_id] = {'id': candidate_id, 'kind': 'clip-edge',
                                        'nodeIds': sorted({clip_id, *crossing}),
                                        'rootLocalEdge': {
                                            'side': side,
                                            'coordinate': clip_box[index],
                                            'span': ([clip_box[1], clip_box[3]] if index in (0, 2)
                                                     else [clip_box[0], clip_box[2]])}}

    # A page-like child that stops before the root bottom is a common H5/root seam.
    root_box = _box(doc, root_id, root_id)
    root_width = root_box[2] - root_box[0]
    for surface in surfaces.values():
        if surface['kind'] != 'page' or surface['nodeId'] == root_id:
            continue
        box = _box(doc, surface['nodeId'], root_id)
        if (box and box[2] - box[0] >= root_width * .9 and
                root_box[3] - box[3] > .5):
            candidate_id = 'terminal:' + surface['nodeId'] + ':bottom'
            result[candidate_id] = {'id': candidate_id, 'kind': 'surface-terminal',
                                    'nodeIds': [surface['nodeId'], root_id],
                                    'rootLocalEdge': {
                                        'side': 'bottom', 'coordinate': box[3],
                                        'span': [box[0], box[2]]}}
    return result


def _rgb(doc, path):
    color = at({'nodes': doc['nodes']}, path)
    if color == MISSING or not isinstance(color, dict) or not all(k in color for k in 'rgb'):
        raise ValueError('stable surface path is not an RGB color: ' + path)
    return [color[k] for k in 'rgb']


def _same_srgb8(a, b):
    return all(math.floor(value * 255 + .5) == math.floor(other * 255 + .5)
               for value, other in zip(a, b))


def _required_kind(role):
    normalized = str(role or '').lower()
    for prefix, kind in ROLE_KIND_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + '.'):
            return kind
    return None


def _nearest_card_surface(doc, node_id, surfaces):
    by_node = {surface['nodeId']: surface for surface in surfaces.values()
               if surface['kind'] == 'card'}
    current = node_id
    while current in doc['nodes']:
        if current in by_node:
            return by_node[current]
        current = doc['nodes'][current]['parentId']
    return None


def _source_same_card_surface_groups(source_doc, actual_doc, surfaces):
    """Keep source-identical card/chrome bases identical after recoloring.

    Containers are deliberately excluded: a real grouping container may need
    new discernibility even when the source was weak. Interactions, icons and
    states are separate semantic roles. This gate covers only stable card
    chrome/atmosphere/decoration colors that were exactly the card base in the
    source and therefore had no independent visible color boundary to preserve.
    """
    groups = []
    for surface in surfaces.values():
        if surface['kind'] not in CONTINUOUS_CARD_KINDS:
            continue
        card = _nearest_card_surface(source_doc, surface['nodeId'], surfaces)
        if not card:
            continue
        card_path = card.get('stableRepresentativePath')
        if not isinstance(card_path, str):
            continue
        member_paths = []
        for path in surface.get('carrierPaths', []):
            if '/gradientStops/' in path:
                continue
            paint = at({'nodes': source_doc['nodes']}, path.split('/color', 1)[0])
            if not isinstance(paint, dict) or paint.get('type') != 'SOLID':
                continue
            if _same_srgb8(_rgb(source_doc, card_path), _rgb(source_doc, path)):
                member_paths.append(path)
        if not member_paths:
            continue
        actual_card = _rgb(actual_doc, card_path)
        passed = all(_same_srgb8(actual_card, _rgb(actual_doc, path))
                     for path in member_paths)
        groups.append({
            'id': 'source-same:' + card['id'] + ':' + surface['id'],
            'status': 'pass' if passed else 'fail',
            'cardSurfaceId': card['id'],
            'memberSurfaceId': surface['id'],
            'paths': [card_path, *member_paths],
        })
    return groups


def _boundary_group_geometry_valid(candidate, group, root_box):
    native = group.get('nativePixels')
    expected_native = [round(root_box[2] - root_box[0]),
                       round(root_box[3] - root_box[1])]
    if native != expected_native:
        return False
    xy = group.get('xy')
    if (not isinstance(xy, list) or len(xy) < 2 or
            any(not isinstance(point, list) or len(point) != 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in point) for point in xy)):
        return False
    edge = candidate.get('rootLocalEdge')
    if not edge:
        return False
    axis = 0 if edge['side'] in {'left', 'right'} else 1
    cross = [point[axis] for point in xy]
    along = [point[1 - axis] for point in xy]
    coordinate = edge['coordinate']
    span = edge['span']
    crosses = min(cross) <= coordinate <= max(cross)
    if group.get('samplingMode') == 'root-edge-inward':
        # Root-edge exteriors are absent from a clipped native PNG. Require
        # the two nearest *available* pixel columns/rows, never arbitrary
        # interior points or this exception on an internal boundary.
        extent = expected_native[axis]
        side = edge['side']
        expected_cross = ([0, 1] if side in {'left', 'top'} and coordinate == 0
                          else [extent - 3, extent - 2]
                          if side in {'right', 'bottom'} and coordinate == extent - .5
                          else [extent - 2, extent - 1]
                          if side in {'right', 'bottom'} and coordinate == extent
                          else None)
        crosses = (candidate.get('kind') == 'clip-edge' and
                   expected_cross is not None and
                   sorted(set(cross)) == expected_cross and
                   bool(group.get('samplingBasis')))
    return (crosses and
            max(cross) - min(cross) <= 4 and
            all(span[0] <= value <= span[1] for value in along))


def discover(source):
    """List visible painted nodes and their discovered boundary obligations."""
    doc, root_id, all_paths = _candidate_nodes(source)
    painted = [{
        'nodeId': node_id,
        'name': doc['nodes'][node_id]['props'].get('name'),
        'carrierPaths': paths,
        'rootLocalBox': list(_box(doc, node_id, root_id) or []),
    } for node_id, paths in sorted(all_paths.items())]
    boundaries = list(_boundary_candidates(doc, root_id, {}).values())
    return {'schemaVersion': 1, 'sourceHash': digest(doc),
            'paintedCandidates': painted,
            'boundaryCandidates': boundaries,
            'clipBoundaryCandidates': [row for row in boundaries if row['kind'] == 'clip-edge'],
            'note': ('The painted-node list has no size cutoff. Semantic roles and card '
                     'ancestry decide which nodes surfaceSystemPlan must classify. '
                     'Boundary discovery finds ordinary axis-aligned sibling contacts; '
                     'irregular or overlapping contours still need a full native visual review.')}


def inspect(source, actual, manifest, rules, mapping=None):
    source_doc, root_id, all_paths = _candidate_nodes(source)
    _, actual_doc = mapped_document(source, actual, mapping)
    plan = manifest.get('surfaceSystemPlan')
    errors = []
    if (not isinstance(plan, dict) or plan.get('schemaVersion') != 1 or
            plan.get('sourceHash') != digest(source_doc)):
        return {'status': 'fail', 'errors': [
            {'error': 'surfaceSystemPlan must bind the complete source snapshot'}]}

    entries = plan.get('surfaces')
    if not isinstance(entries, list) or not entries:
        return {'status': 'fail', 'errors': [{'error': 'nonempty surface inventory required'}]}
    surfaces = {}
    classified_nodes = {}
    active_paths = {row['path'] for row in color_inventory(source)['entries'] if not row['inactive']}
    manifest_by_path = {row.get('path'): row for row in manifest.get('entries', [])
                        if isinstance(row, dict) and isinstance(row.get('path'), str)}
    for surface in entries:
        surface_id = surface.get('id')
        node_id = surface.get('nodeId')
        kind = surface.get('kind')
        if (not isinstance(surface_id, str) or not surface_id or surface_id in surfaces or
                node_id not in source_doc['nodes'] or kind not in SURFACE_KINDS or
                not isinstance(surface.get('basis'), str) or not surface['basis'].strip()):
            errors.append({'surfaceId': surface_id, 'error': 'invalid surface inventory entry'})
            continue
        if node_id in classified_nodes:
            errors.append({'nodeId': node_id, 'error': 'painted surface node classified more than once'})
        classified_nodes[node_id] = surface_id
        paths = surface.get('carrierPaths')
        if (not isinstance(paths, list) or not paths or len(paths) != len(set(paths)) or
                not set(paths) <= active_paths):
            errors.append({'surfaceId': surface_id, 'error': 'surface carrierPaths must be active unique source fills'})
        for path in paths or []:
            required_kind = _required_kind(manifest_by_path.get(path, {}).get('role'))
            if required_kind and required_kind != kind:
                errors.append({
                    'surfaceId': surface_id,
                    'path': path,
                    'manifestRole': manifest_by_path[path].get('role'),
                    'surfaceKind': kind,
                    'error': 'manifest surface role conflicts with surfaceSystemPlan kind',
                })
        representative = surface.get('stableRepresentativePath')
        if kind in STABLE_KINDS:
            if representative not in set(paths or []):
                errors.append({'surfaceId': surface_id,
                               'error': 'stable page/card/container needs a representative carrier path'})
            host_id = surface.get('hostSurfaceId')
            relation_id = surface.get('boundaryRelationshipId')
            if kind != 'page' or node_id != root_id:
                if not isinstance(host_id, str) or not isinstance(relation_id, str):
                    errors.append({'surfaceId': surface_id,
                                   'error': 'non-root stable surface needs hostSurfaceId and boundaryRelationshipId'})
        surfaces[surface_id] = surface

    # A background proxy has no independent emphasis color. Its dependency is
    # expressed with existing native appearance relations, regardless of shape.
    displayed = {}
    for rule in rules.values():
        if (rule.get('kind') == 'machine' and rule.get('applicable') is True and
                rule.get('verifier', {}).get('type') == 'displayed-relations'):
            for group in rule['verifier'].get('groups', []):
                displayed[group.get('id')] = group
    for surface in surfaces.values():
        if surface['kind'] != 'proxy':
            continue
        surface_id = surface['id']
        host_ids = surface.get('hostSurfaceIds', [surface.get('hostSurfaceId')])
        if (not isinstance(host_ids, list) or not host_ids or
                any(not isinstance(h, str) for h in host_ids) or
                len(set(host_ids)) != len(host_ids)):
            host_ids = []
        hosts = [surfaces.get(h) for h in host_ids]
        paths = surface.get('carrierPaths', [])
        groups = surface.get('appearanceGroupIds')
        visual = rules.get(surface.get('visualReviewRuleId'), {})
        if not hosts or any(not h or h['kind'] not in STABLE_KINDS for h in hosts):
            errors.append({'surfaceId': surface_id, 'error': 'background proxy needs a real stable host surface'})
            continue
        scope = {surface['nodeId'], *(h['nodeId'] for h in hosts)}
        if any(manifest_by_path.get(p, {}).get('role') != 'surface.proxy' or
               manifest_by_path.get(p, {}).get('anchorId') is not None for p in paths):
            errors.append({'surfaceId': surface_id, 'error': 'background proxy cannot select an independent role or scheme anchor'})
        if (not isinstance(groups, list) or not groups or
                any(not isinstance(g, str) for g in groups) or len(set(groups)) != len(groups)):
            errors.append({'surfaceId': surface_id, 'error': 'background proxy needs frozen native appearance dependencies'})
            groups = []
        covered_paths, covered_hosts = set(), set()
        for group_id in groups:
            group = displayed.get(group_id, {})
            carriers = group.get('carrierPaths', [])
            anchor_path = group.get('anchorPath')
            matches = [h for h in hosts if anchor_path in h.get('carrierPaths', [])]
            group_scope = {surface['nodeId'], *(h['nodeId'] for h in matches)}
            points = group.get('xy')
            if (group.get('relationType') != 'surface-linked-appearance' or
                    group.get('targetBasis') != 'surface-recipe' or
                    len(matches) != 1 or
                    group.get('anchorPointIndex') != 0 or
                    not group_scope <= set(group.get('nodeIds', [])) or
                    not isinstance(carriers, list) or not carriers or
                    not set(carriers) <= set(paths) or not group.get('basis') or
                    not isinstance(points, list) or len(points) < 2 or
                    any(point == points[0] for point in points[1:]) or
                    not group.get('nativePixels')):
                errors.append({'surfaceId': surface_id, 'groupId': group_id,
                               'error': 'proxy appearance relation must bind actual host and dependent carriers'})
            covered_paths.update(carriers)
            covered_hosts.update(h['id'] for h in matches)
        if covered_paths != set(paths):
            errors.append({'surfaceId': surface_id, 'error': 'proxy appearance dependencies must cover every carrier'})
        if covered_hosts != set(host_ids):
            errors.append({'surfaceId': surface_id, 'error': 'proxy appearance dependencies must cover every host'})
        if (visual.get('kind') != 'visual' or visual.get('applicable') is not True or
                not visual.get('acceptance') or not scope <= set(visual.get('scopeNodeIds', []))):
            errors.append({'surfaceId': surface_id, 'error': 'proxy dependency needs native visual responsibility review'})

    candidates = _semantic_surface_candidates(
        manifest, surfaces, source_doc, root_id, all_paths)
    for surface in surfaces.values():
        node_id = surface['nodeId']
        if node_id in candidates and set(surface.get('carrierPaths', [])) != set(candidates[node_id]):
            errors.append({'surfaceId': surface['id'],
                           'error': 'detected surface fill classification is incomplete',
                           'missingPaths': sorted(set(candidates[node_id]) - set(surface.get('carrierPaths', []))),
                           'extraPaths': sorted(set(surface.get('carrierPaths', [])) - set(candidates[node_id]))})

    omitted = sorted(set(candidates) - set(classified_nodes))
    if omitted:
        errors.append({'error': 'semantically relevant visible fill omitted from surface inventory',
                       'nodeIds': omitted})
    extra = sorted(set(classified_nodes) - set(candidates))
    if extra:
        errors.append({'error': 'surface inventory includes nodes outside semantic painted candidates',
                       'nodeIds': extra})

    relationships = rules.get('contrast-baseline', {}).get('verifier', {}).get('relationships', [])
    relation_index = {row.get('id'): row for row in relationships}
    for surface in surfaces.values():
        if surface['kind'] not in STABLE_KINDS or (
                surface['kind'] == 'page' and surface['nodeId'] == root_id):
            continue
        host = surfaces.get(surface.get('hostSurfaceId'))
        relation = relation_index.get(surface.get('boundaryRelationshipId'))
        if not host:
            errors.append({'surfaceId': surface['id'], 'error': 'unknown host surface'})
            continue
        if (not relation or relation.get('kind') != 'surface' or
                not {surface['nodeId'], host['nodeId']} <= set(relation.get('nodeIds', [])) or
                not relation.get('sampleIds') or
                type(relation.get('minimumDeltaE')) not in (int, float) or
                relation['minimumDeltaE'] <= 0):
            errors.append({'surfaceId': surface['id'],
                           'error': 'surface boundary must bind a nonzero sampled surface relationship'})
            continue
        if surface['kind'] == 'container':
            if relation['minimumDeltaE'] < 4:
                errors.append({'surfaceId': surface['id'],
                               'error': 'card inner container requires minimumDeltaE >= 4'})
            target_mode = manifest.get('themeTransition', '').split('-to-')[-1]
            maximum = relation.get('maximumDeltaE')
            if (target_mode == 'light' and
                    (type(maximum) not in (int, float) or not math.isfinite(maximum) or
                     maximum < relation['minimumDeltaE'])):
                errors.append({'surfaceId': surface['id'],
                               'error': 'light UI inner container requires a frozen maximumDeltaE'})

    groups = plan.get('cardBaseGroups')
    card_ids = {s['id'] for s in surfaces.values() if s['kind'] == 'card'}
    if not isinstance(groups, list) or (card_ids and not groups):
        errors.append({'error': 'card surfaces require peer base groups'})
        groups = []
    grouped = []
    group_results = []
    for group in groups:
        ids = group.get('surfaceIds')
        allowance = group.get('additionalDeltaE')
        if (not isinstance(group.get('id'), str) or not group['id'] or
                not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or
                not set(ids) <= card_ids or type(allowance) not in (int, float) or
                not math.isfinite(allowance) or not 0 <= allowance <= 3 or
                not isinstance(group.get('basis'), str) or not group['basis'].strip()):
            errors.append({'groupId': group.get('id'), 'error': 'invalid card base group'})
            continue
        grouped.extend(ids)
        source_colors = [_rgb(source_doc, surfaces[s]['stableRepresentativePath']) for s in ids]
        actual_colors = [_rgb(actual_doc, surfaces[s]['stableRepresentativePath']) for s in ids]
        def spread(colors):
            return max((delta_e76(a, b) for i, a in enumerate(colors)
                        for b in colors[i + 1:]), default=0)
        source_spread, actual_spread = spread(source_colors), spread(actual_colors)
        limit = source_spread + allowance
        passed = actual_spread <= limit + 1e-9
        group_results.append({'id': group['id'], 'status': 'pass' if passed else 'fail',
                              'sourceDeltaE76': source_spread,
                              'actualDeltaE76': actual_spread, 'maximumDeltaE76': limit})
        if not passed:
            errors.append({'groupId': group['id'],
                           'error': 'peer card stable bases diverged beyond source relationship',
                           'sourceDeltaE76': source_spread,
                           'actualDeltaE76': actual_spread,
                           'maximumDeltaE76': limit})
    if len(grouped) != len(set(grouped)) or set(grouped) != card_ids:
        errors.append({'error': 'every card surface must occur in exactly one peer base group',
                       'missingSurfaceIds': sorted(card_ids - set(grouped))})

    same_color_groups = _source_same_card_surface_groups(
        source_doc, actual_doc, surfaces)
    for group in same_color_groups:
        if group['status'] != 'pass':
            errors.append({
                'groupId': group['id'],
                'error': ('source-identical card and chrome/atmosphere/decoration '
                          'base colors must remain target-identical'),
                'paths': group['paths'],
            })

    boundary_candidates = _boundary_candidates(source_doc, root_id, surfaces)
    reviews = plan.get('boundaryReviews')
    if not isinstance(reviews, list):
        errors.append({'error': 'boundaryReviews must be an explicit list'})
        reviews = []
    review_index = {row.get('candidateId'): row for row in reviews}
    if len(review_index) != len(reviews):
        errors.append({'error': 'duplicate boundary review candidate'})
    if set(review_index) != set(boundary_candidates):
        errors.append({'error': 'detected risky boundaries and reviews differ',
                       'missingCandidateIds': sorted(set(boundary_candidates) - set(review_index)),
                       'extraCandidateIds': sorted(set(review_index) - set(boundary_candidates))})
    displayed_groups = {}
    for rule in rules.values():
        if rule.get('applicable') and rule.get('verifier', {}).get('type') == 'displayed-relations':
            for group in rule['verifier'].get('groups', []):
                displayed_groups[group.get('id')] = group
    for candidate_id, review in review_index.items():
        candidate = boundary_candidates.get(candidate_id)
        group = displayed_groups.get(review.get('displayedGroupId'))
        decision = review.get('decision')
        maximum = group.get('maximumChannelDelta') if group else None
        delta_valid = (type(maximum) in (int, float) and math.isfinite(maximum) and
                       0 <= maximum <= (16 if decision in {'continuous', 'fade'} or
                                               candidate and candidate['kind'] == 'adjacent-surfaces'
                                               else 255))
        geometry_valid = bool(candidate and group and
                              _boundary_group_geometry_valid(
                                  candidate, group, _box(source_doc, root_id, root_id)))
        if (not candidate or review.get('decision') not in {'continuous', 'intentional-edge', 'fade'} or
                not isinstance(review.get('basis'), str) or not review['basis'].strip() or
                not group or not set(candidate['nodeIds']) <= set(group.get('nodeIds', [])) or
                (candidate['kind'] == 'adjacent-surfaces' and
                 group.get('relationType') != 'source-topology') or
                not delta_valid or not geometry_valid):
            errors.append({'candidateId': candidate_id,
                           'error': ('risky boundary needs a tight native 1:1 relation '
                                     'straddling the discovered edge')})

    return {'status': 'fail' if errors else 'pass', 'errors': errors,
            'candidateSurfaceCount': len(candidates), 'surfaceCount': len(surfaces),
            'candidateGeometryEvidence': [
                _geometry_evidence(source_doc, node_id, root_id, surfaces)
                for node_id in sorted(candidates)],
            'cardBaseGroups': group_results,
            'sourceSameColorSurfaceGroups': same_color_groups,
            'boundaryCandidates': list(boundary_candidates.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    candidate = sub.add_parser('discover')
    candidate.add_argument('source', type=Path)
    audit = sub.add_parser('audit')
    audit.add_argument('source', type=Path)
    audit.add_argument('actual', type=Path)
    audit.add_argument('manifest', type=Path)
    audit.add_argument('rule_ledger', type=Path)
    args = parser.parse_args()
    if args.mode == 'discover':
        result = discover(json.loads(args.source.read_text()))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    ledger = json.loads(args.rule_ledger.read_text())
    result = inspect(json.loads(args.source.read_text()), json.loads(args.actual.read_text()),
                     json.loads(args.manifest.read_text()),
                     {row['id']: row for row in ledger.get('rules', [])})
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())

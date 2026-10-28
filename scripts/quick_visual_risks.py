#!/usr/bin/env python3
"""Cheap, explicit checks before a full Figma theme preview.

The seam check reads a native 1:1 PNG. Button and icon checks use actual
palette/snapshot values; their JSON is evidence for, not a substitute for,
local 1:1 visual review.
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
from pathlib import Path
from button_text_policy import decide
from color_priority import check_body_colors, explicit_deep_selection


def rgb_hex(value):
    value = value.lstrip('#')
    if len(value) != 6:
        raise ValueError('expected six-digit hex color')
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(rgb):
    values = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
              for c in rgb]
    return sum(a * b for a, b in zip(values, (.2126, .7152, .0722)))


def contrast(a, b):
    x, y = luminance(a), luminance(b)
    return (max(x, y) + .05) / (min(x, y) + .05)


def seam(image_path, seam_y, columns, max_step=16, radius=2, transition_start=None):
    from PIL import Image

    im = Image.open(image_path).convert('RGB')
    if not columns or any(x < 0 or x >= im.width for x in columns):
        raise ValueError('sample columns must be inside the image')
    if seam_y - radius < 0 or seam_y + radius >= im.height:
        raise ValueError('seam band is outside the image')
    if transition_start is not None and not 0 <= transition_start < seam_y:
        raise ValueError('transition start must precede the seam')
    samples = []
    for x in columns:
        first = transition_start if transition_start is not None else seam_y - radius
        rows = [im.getpixel((x, y)) for y in range(first, seam_y + radius + 1)]
        steps = [max(abs(a - b) for a, b in zip(rows[i], rows[i + 1]))
                 for i in range(len(rows) - 1)]
        samples.append({'x': x, 'sampleYStart': first,
                        'rows': rows if transition_start is None else
                        [rows[0], rows[-1]],
                        'adjacentMaxDeltas': steps if transition_start is None else [],
                        'largestStep': max(steps),
                        'largestStepY': first + steps.index(max(steps))})
    return {'status': 'pass' if all(s['largestStep'] <= max_step for s in samples) else 'fail',
            'kind': 'kv-seam-pixel-precheck', 'image': str(image_path),
            'seamY': seam_y, 'transitionStartY': transition_start,
            'maxAllowedChannelStep': max_step, 'samples': samples,
            'note': 'Use only columns confirmed unobstructed in the native crop; inspect the full transition for a second edge.'}


def button(button_color, candidates, tone_direction='bright', body_colors=None,
           minimum_saturation=None, deep_selection=None, minimum_brightness=None,
           background_kind='solid', text_backgrounds=None, sample_scope=None):
    background = rgb_hex(button_color)
    background_hue = colorsys.rgb_to_hsv(*background)[0]
    decision = decide(button_color, background_kind, text_backgrounds, sample_scope)
    rows = []
    for name, color in candidates.items():
        ratios = [contrast(rgb_hex(color), rgb_hex(sample))
                  for sample in decision['textBackgrounds']]
        rows.append({'name': name, 'color': color,
                     'contrast': round(min(ratios), 4),
                     'contrastMax': round(max(ratios), 4)})
    needed = {'white', decision['defaultChosen']}
    body_check = check_body_colors(
        [rgb_hex(c) for c in [button_color] + (body_colors or [])],
        tone_direction, minimum_saturation, deep_selection, minimum_brightness)
    errors = list(body_check['errors'])
    if candidates.get('white', '').upper() != '#FFFFFF':
        errors.append('white candidate must be pure #FFFFFF')
    if 'tinted-white' in candidates:
        hue, saturation, brightness = colorsys.rgb_to_hsv(*rgb_hex(candidates['tinted-white']))
        if brightness < .95 or saturation > .16:
            errors.append('tinted-white is not a slight hue-tinted near-white')
        if saturation >= .03 and min(abs(hue-background_hue), 1-abs(hue-background_hue)) > .21:
            errors.append('tinted-white hue is unrelated to the button')
    if 'same-family-dark' in candidates:
        hue, saturation, brightness = colorsys.rgb_to_hsv(*rgb_hex(candidates['same-family-dark']))
        if brightness > .5 or saturation < .15 or \
                min(abs(hue-background_hue), 1-abs(hue-background_hue)) > .21:
            errors.append('dark label is not from the button color family')
    return {'status': 'pass' if needed <= candidates.keys() and not errors else 'fail',
            'kind': 'button-text-decision', 'buttonColor': button_color,
            'textDecision': decision,
            'candidates': rows, 'missing': sorted(needed - candidates.keys()),
            'errors': errors,
            'bodyColorCheck': body_check,
            'note': 'Check the selected default at actual size; compare alternatives only for a documented legibility exception.'}


def icon(snapshot_path, node_id, top_index, minimum_brightness=None,
         target_ui_mode=None, body_stop_indices=None,
         tone_direction='bright', non_body_stop_reasons=None,
         deep_selection=None, minimum_saturation=None):
    doc = json.loads(Path(snapshot_path).read_text())
    row = next((n for n in doc['nodes'] if n['id'] == node_id), None)
    if row is None:
        raise ValueError('icon node missing from snapshot')
    fills = row['props'].get('fills', [])
    if not 0 <= top_index < len(fills):
        raise ValueError('top paint index outside fills')
    paint = fills[top_index]
    if paint.get('type', '').startswith('GRADIENT'):
        stops = [s['color'] for s in paint.get('gradientStops', [])]
    elif paint.get('type') == 'SOLID':
        stops = [paint['color']]
    else:
        stops = []
    colors = []
    for i, color in enumerate(stops):
        h, s, v = colorsys.rgb_to_hsv(color['r'], color['g'], color['b'])
        colors.append({'index': i, 'rgb': [color['r'], color['g'], color['b']],
                       'hsv': [round(h, 4), round(s, 4), round(v, 4)],
                       'alpha': color.get('a', 1)})
    opaque = paint.get('visible', True) and paint.get('opacity', 1) == 1 and \
        paint.get('blendMode', 'NORMAL') == 'NORMAL' and all(c['alpha'] == 1 for c in colors)
    if target_ui_mode is not None and target_ui_mode not in {'light', 'dark'}:
        raise ValueError('target UI mode must be light or dark')
    if minimum_brightness is not None and (not math.isfinite(minimum_brightness) or not 0 <= minimum_brightness <= 1):
        raise ValueError('minimum brightness must be in 0..1')
    if body_stop_indices is None:
        body_stop_indices = list(range(len(colors)))
    if not body_stop_indices or len(set(body_stop_indices)) != len(body_stop_indices) or \
            any(not isinstance(i, int) or i < 0 or i >= len(colors)
                for i in body_stop_indices):
        raise ValueError('body stop indices must identify visible stops')
    excluded = set(range(len(colors))) - set(body_stop_indices)
    reasons = non_body_stop_reasons or {}
    if any(not isinstance(reasons.get(str(i)), str) or
           not reasons[str(i)].strip() for i in excluded):
        raise ValueError('excluded non-body stops require a reason')
    dim = []
    if tone_direction == 'clean-deep' and not explicit_deep_selection(deep_selection):
        raise ValueError('clean-deep requires an explicit user choice and its reference')
    if minimum_saturation is not None and (not math.isfinite(minimum_saturation) or not 0 <= minimum_saturation <= 1):
        raise ValueError('minimum saturation must be in 0..1')
    for c in colors:
        value = max(c['rgb'])
        requested_fail = minimum_brightness is not None and value < minimum_brightness
        body = c['index'] in body_stop_indices
        dark_fail = body and target_ui_mode == 'dark' and value <= .8
        light_fail = False
        if body and target_ui_mode == 'light':
            if tone_direction == 'bright':
                light_fail = value < 1
            elif tone_direction == 'gold-bright':
                light_fail = value < 249/255
            elif tone_direction == 'clean-deep':
                light_fail = value < .58 or colorsys.rgb_to_hsv(*c['rgb'])[1] < .4
            elif tone_direction != 'clean-deep':
                raise ValueError('light Icon tone direction must be bright, gold-bright, or clean-deep')
        saturation_fail = body and minimum_saturation is not None and colorsys.rgb_to_hsv(*c['rgb'])[1] < minimum_saturation
        if requested_fail or dark_fail or light_fail or saturation_fail:
            dim.append(c['index'])
    return {'status': 'fail' if not opaque or not colors or dim else 'pass',
            'kind': 'icon-effective-top-paint-precheck', 'nodeId': node_id,
            'topPaintIndex': top_index, 'opaqueNormal': opaque,
            'stops': colors, 'dimStopIndices': dim,
            'minimumBrightnessRequested': minimum_brightness,
            'targetUiMode': target_ui_mode, 'bodyStopIndices': body_stop_indices,
            'toneDirection': tone_direction,
            'note': 'Top index must be confirmed by the Figma stack; check rendered glyph area and lower-layer contribution.'}


def inspect_review(review, source_hash, projected_hash):
    """Bind one native preview and its three visual risk decisions to a plan."""
    errors = []
    if review.get('schemaVersion') != 1 or review.get('sourceHash') != source_hash or \
            review.get('projectedHash') != projected_hash:
        errors.append('review is not bound to the frozen source and projection')
    image_path = Path(review.get('screenshot', ''))
    if not image_path.is_file():
        errors.append('native preview screenshot missing')
    elif hashlib.sha256(image_path.read_bytes()).hexdigest() != review.get('screenshotSha256'):
        errors.append('native preview screenshot hash mismatch')
    checks = {}
    cfg = review.get('seam')
    if isinstance(cfg, dict) and image_path.is_file():
        try:
            if len(cfg.get('columns', [])) < 2 or cfg.get('maxStep', 16) > 16:
                raise ValueError('seam needs at least two exposed columns and maxStep <= 16')
            checks['seam'] = seam(image_path, cfg['seamY'], cfg['columns'],
                                  cfg.get('maxStep', 16),
                                  transition_start=cfg.get('transitionStartY'))
        except (KeyError, ValueError, OSError) as exc:
            errors.append(f'seam: {exc}')
    else:
        errors.append('seam configuration missing')
    for kind, fn in (('buttons', button), ('icons', icon)):
        rows = review.get(kind)
        if not isinstance(rows, list) or not rows:
            absence = review.get(f'{kind}NotApplicable')
            if not isinstance(absence, dict) or not absence.get('reason') or \
                    absence.get('sourceHash') != source_hash:
                errors.append(f'{kind}: representative evidence or source-bound absence missing')
            continue
        for row in rows:
            try:
                key = f'{kind}:{row["id"]}'
                if kind == 'buttons':
                    checks[key] = fn(row['buttonColor'], row['candidates'],
                                     row.get('toneDirection', 'bright'), row.get('bodyColors'),
                                     row.get('minimumSaturation'), row.get('deepSelection'),
                                     row.get('minimumBrightness'), row.get('backgroundKind', 'solid'),
                                     row.get('textBackgrounds'), row.get('sampleScope'))
                    if row['chosen'] not in row['candidates']:
                        raise ValueError('chosen candidate not present')
                    if row['chosen'] != checks[key]['textDecision']['defaultChosen']:
                        exception = row.get('legibilityException', {})
                        if (not isinstance(exception, dict) or
                                not isinstance(exception.get('reason'), str) or
                                not exception['reason'].strip() or
                                not isinstance(exception.get('affectedText'), str) or
                                not exception['affectedText'].strip() or
                                not all(Path(exception.get(k, '')).is_file() for k in
                                        ('defaultPreviewImage', 'alternativePreviewImage'))):
                            raise ValueError('non-default text needs a specific legibility exception and local comparison images')
                else:
                    if review.get('targetUiMode') not in {'light', 'dark'}:
                        raise ValueError('targetUiMode required for Icon brightness gate')
                    checks[key] = fn(row['snapshot'], row['nodeId'],
                                     row['topIndex'], row.get('minimumBrightness'),
                                     review['targetUiMode'], row.get('bodyStopIndices'),
                                     row.get('toneDirection', 'bright'),
                                     row.get('nonBodyStopReasons'), row.get('deepSelection'),
                                     row.get('minimumSaturation'))
                if row.get('visualStatus') != 'pass' or not Path(row.get('previewImage', '')).is_file():
                    raise ValueError('1:1 local visual evidence missing')
            except (KeyError, ValueError, OSError) as exc:
                errors.append(f'{kind}: {exc}')
    if review.get('overallVisualStatus') != 'pass':
        errors.append('overall visual conclusion missing')
    failed = [key for key, result in checks.items() if result['status'] != 'pass']
    return {'status': 'pass' if not errors and not failed else 'fail',
            'failedChecks': failed, 'errors': errors, 'checks': checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='kind', required=True)
    s = sub.add_parser('seam')
    s.add_argument('--image', type=Path, required=True)
    s.add_argument('--seam-y', type=int, required=True)
    s.add_argument('--columns', required=True, help='comma-separated unobstructed pixel x positions')
    s.add_argument('--max-step', type=int, default=16)
    s.add_argument('--transition-start', type=int,
                   help='scan the full blend region for a second hard edge')
    b = sub.add_parser('button')
    b.add_argument('--button', required=True)
    b.add_argument('--white', default='#FFFFFF')
    b.add_argument('--tinted-white')
    b.add_argument('--same-family-dark')
    b.add_argument('--background-kind', choices=('solid', 'gradient'), default='solid')
    b.add_argument('--text-backgrounds', help='comma-separated effective hex backgrounds under text')
    b.add_argument('--sample-scope', choices=('text-coverage',))
    b.add_argument('--tone-direction', choices=('bright', 'gold-bright', 'clean-deep'), default='bright')
    b.add_argument('--body-colors', help='comma-separated remaining visible body stop hex colors')
    b.add_argument('--minimum-saturation', type=float)
    b.add_argument('--minimum-brightness', type=float)
    b.add_argument('--deep-selection', help='JSON with userRequest and reference for an explicit deep choice')
    i = sub.add_parser('icon')
    i.add_argument('--snapshot', type=Path, required=True)
    i.add_argument('--node-id', required=True)
    i.add_argument('--top-index', type=int, required=True)
    i.add_argument('--minimum-brightness', type=float)
    i.add_argument('--target-ui-mode', choices=('light', 'dark'), required=True)
    i.add_argument('--body-stop-indices', help='comma-separated body stop indices; defaults to all')
    i.add_argument('--tone-direction', choices=('bright', 'gold-bright', 'clean-deep'),
                   default='bright')
    i.add_argument('--non-body-stop-reasons', help='JSON object keyed by excluded stop index')
    i.add_argument('--minimum-saturation', type=float)
    i.add_argument('--deep-selection', help='JSON with userRequest and reference')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.kind == 'seam':
        result = seam(args.image, args.seam_y,
                      [int(x) for x in args.columns.split(',')], args.max_step,
                      transition_start=args.transition_start)
    elif args.kind == 'button':
        result = button(args.button, {k: v for k, v in {'white': args.white,
                                     'tinted-white': args.tinted_white,
                                     'same-family-dark': args.same_family_dark}.items() if v},
                        args.tone_direction,
                        args.body_colors.split(',') if args.body_colors else None,
                        args.minimum_saturation,
                        json.loads(args.deep_selection) if args.deep_selection else None,
                        args.minimum_brightness, args.background_kind,
                        args.text_backgrounds.split(',') if args.text_backgrounds else None,
                        args.sample_scope)
    else:
        result = icon(args.snapshot, args.node_id, args.top_index,
                      args.minimum_brightness, args.target_ui_mode,
                      ([int(x) for x in args.body_stop_indices.split(',')]
                       if args.body_stop_indices else None), args.tone_direction,
                      (json.loads(args.non_body_stop_reasons)
                       if args.non_body_stop_reasons else None),
                      json.loads(args.deep_selection) if args.deep_selection else None,
                      args.minimum_saturation)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(rendered + '\n')
    print(rendered)
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())

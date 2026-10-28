"""Validate authored body colors before optimizing text contrast.

HSV V is a numeric guardrail, not perceptual lightness. Visual chroma and
rendered area still require review. Explicit S minima use the 0..1 scale.
"""
import colorsys
import math


def explicit_deep_selection(evidence):
    return isinstance(evidence, dict) and all(
        isinstance(evidence.get(key), str) and evidence[key].strip()
        for key in ('userRequest', 'reference'))


def check_body_colors(colors, tone_direction='bright', minimum_saturation=None,
                      deep_selection=None, minimum_brightness=None):
    errors = []
    if tone_direction not in {'bright', 'gold-bright', 'clean-deep'}:
        raise ValueError('unsupported body tone direction')
    for value in (minimum_saturation, minimum_brightness):
        if value is not None and (isinstance(value, bool) or
                                 not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError('HSB limits must be finite numbers in 0..1')
    if tone_direction == 'clean-deep' and not explicit_deep_selection(deep_selection):
        errors.append('clean-deep requires an explicit user choice and its reference; contrast is not authorization')
    # The documented warm-gold #F9DB92 has V=249/255 (rounded HSB B=98).
    floor = {'bright': 1, 'gold-bright': 249/255, 'clean-deep': .58}[tone_direction]
    floor = max(floor, minimum_brightness or 0)
    rows = []
    for color in colors:
        if len(color) != 3 or any(not math.isfinite(c) or not 0 <= c <= 1 for c in color):
            raise ValueError('body RGB must be finite numbers in 0..1')
        h, s, b = colorsys.rgb_to_hsv(*color)
        rows.append({'h': h, 's': s, 'b': b})
        if b < floor:
            errors.append(f'body[{len(rows)-1}] B={b:.4f} below {floor:.4f}')
        saturation_floor = max(minimum_saturation or 0,
                               .4 if tone_direction == 'clean-deep' else 0)
        if s < saturation_floor:
            errors.append(f'body[{len(rows)-1}] S={s:.4f} below {saturation_floor:.4f}')
    if not rows:
        errors.append('visible body colors missing')
    return {'status': 'fail' if errors else 'pass', 'toneDirection': tone_direction,
            'bodyHsb': rows, 'minimumBrightness': floor,
            'minimumSaturationRequested': minimum_saturation, 'errors': errors}

"""Style default only: 1.7 white contrast, sampled under the actual text."""
import math

THRESHOLD = 1.7
POLICY = 'contrast-1.7'


def white_contrast(color):
    if not isinstance(color, str) or len(color) != 7 or not color.startswith('#'):
        raise ValueError('background must be #RRGGBB')
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return 1.05 / (sum(v * w for v, w in zip(linear, (.2126, .7152, .0722))) + .05)


def direction(ratio):
    if not math.isfinite(ratio) or not 1 <= ratio <= 21:
        raise ValueError('contrast must be finite and in 1..21')
    return 'white' if ratio >= THRESHOLD else 'same-family-dark'


def decide(button_color, background_kind='solid', text_backgrounds=None, sample_scope=None):
    if background_kind not in {'solid', 'gradient'}:
        raise ValueError('backgroundKind must be solid or gradient')
    if background_kind == 'gradient' and (not text_backgrounds or sample_scope != 'text-coverage'):
        raise ValueError('gradient needs effective textBackgrounds with sampleScope=text-coverage')
    colors = [button_color] if text_backgrounds is None else text_backgrounds
    if not isinstance(colors, list) or not colors or (background_kind == 'solid' and len(set(colors)) != 1):
        raise ValueError('supply effective backgrounds; solid requires one distinct color')
    ratios = [white_contrast(c) for c in colors]
    maximum = max(ratios)
    return {'policy': POLICY, 'threshold': THRESHOLD, 'backgroundKind': background_kind,
            'textBackgrounds': colors, 'whiteContrasts': ratios,
            'whiteContrastMin': min(ratios), 'whiteContrastMax': maximum,
            'defaultChosen': direction(maximum),
            'note': 'Style direction only; sample location and actual legibility need visual review.'}

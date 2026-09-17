#!/usr/bin/env python3
"""Compare declared visual relationships against the original, without editing Figma."""
import argparse
import hashlib
import math
import sys
from pathlib import Path

from theme_audit import at, digest, mapped_document, read_json, save_json


KINDS = {'text', 'surface', 'state', 'icon', 'button'}


def unit(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('color and alpha must be finite numbers in [0,1]')
    return value


def luminance(rgb):
    linear = [unit(v) / 12.92 if v <= .04045 else ((unit(v) + .055) / 1.055) ** 2.4
              for v in rgb]
    if len(linear) != 3:
        raise ValueError('RGB requires three channels')
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    low, high = sorted((luminance(a), luminance(b)))
    return (high + .05) / (low + .05)


def displayed_color(doc, spec, images):
    """Normal-blend solid stacks, or verified native screenshot pixels."""
    if set(spec) == {'layers'}:
        layers = spec['layers']
        if not isinstance(layers, list) or not layers:
            raise ValueError('nonempty bottom-to-top solid layers required')
        result = [0., 0., 0.]
        for i, layer in enumerate(layers):
            paint = at(doc, layer['colorPath'].rsplit('/', 1)[0])
            if (not isinstance(paint, dict) or paint.get('type') != 'SOLID' or
                    paint.get('visible') is False or paint.get('blendMode', 'NORMAL') != 'NORMAL'):
                raise ValueError('solid layers require actual visible NORMAL solid paints')
            color = at(doc, layer['colorPath'])
            if not isinstance(color, dict) or not all(k in color for k in ('r', 'g', 'b')):
                raise ValueError('missing actual color path: ' + layer['colorPath'])
            rgb = [unit(color[k]) for k in ('r', 'g', 'b')]
            alpha = unit(color.get('a', 1))
            paths = layer.get('alphaPaths', [])
            if len(paths) != len(set(paths)):
                raise ValueError('duplicate alpha would weaken a layer twice')
            for path in paths:
                alpha *= unit(at(doc, path))
            if i == 0 and alpha != 1:
                raise ValueError('solid stack must start on an actual opaque host')
            result = [fg * alpha + bg * (1 - alpha) for fg, bg in zip(rgb, result)]
        return result
    if set(spec) == {'image', 'xy'}:
        evidence = spec['image']; path = evidence['path']
        key = (path, evidence['sha256'])
        if key not in images:
            data_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            if data_hash != evidence['sha256']:
                raise ValueError('screenshot changed: ' + path)
            from PIL import Image
            image = Image.open(path).convert('RGBA')
            if image.getchannel('A').getextrema() != (255, 255):
                raise ValueError('screenshot must contain its actual opaque host')
            images[key] = image
        image = images[key]; xy = spec['xy']
        if (not isinstance(xy, list) or len(xy) != 2 or
                any(type(v) is not int for v in xy) or
                not 0 <= xy[0] < image.width or not 0 <= xy[1] < image.height):
            raise ValueError('sample outside native screenshot')
        return [c / 255 for c in image.getpixel(tuple(xy))[:3]]
    raise ValueError('use actual solid-layer paths or verified screenshot coordinates')


def compare_contrast(source, actual, spec, expected_pairs, expected_orders=None):
    if spec.get('schemaVersion') != 1:
        raise ValueError('contrast schemaVersion must be 1')
    if spec.get('sourceHash') != digest(source) or spec.get('actualHash') != digest(actual):
        raise ValueError('contrast evidence does not match the actual snapshots')
    pairs = spec.get('pairs')
    if not isinstance(pairs, list) or not pairs or not expected_pairs:
        raise ValueError('frozen contrast relationships and actual samples required')
    ids = [p['id'] for p in pairs]; expected_ids = [p['id'] for p in expected_pairs]
    if len(set(ids)) != len(ids) or len(set(expected_ids)) != len(expected_ids):
        raise ValueError('duplicate contrast relationship')
    if set(ids) != set(expected_ids):
        raise ValueError('missing or extra contrast relationship')
    expected = {p['id']: p for p in expected_pairs}
    images = {}; results = []
    for pair in pairs:
        frozen = expected[pair['id']]
        if pair['kind'] not in KINDS or pair['kind'] != frozen['kind']:
            raise ValueError('contrast relationship kind changed')
        if (not pair.get('nodeIds') or set(pair['nodeIds']) != set(frozen['nodeIds']) or
                not set(pair['nodeIds']) <= source['nodes'].keys() or
                not set(pair['nodeIds']) <= actual['nodes'].keys()):
            raise ValueError('contrast relationship node scope changed or missing')
        samples = pair.get('samples', [])
        sample_ids = [s['id'] for s in samples]
        if (not samples or len(set(sample_ids)) != len(sample_ids) or
                set(sample_ids) != set(frozen['sampleIds'])):
            raise ValueError('missing, duplicate or undeclared comparison sample')
        for sample in samples:
            if not isinstance(sample.get('basis'), str) or not sample['basis'].strip():
                raise ValueError('actual host / sampling basis required')
            colors = {}; ratios = {}
            for key, doc in [('source', source), ('actual', actual)]:
                colors[key] = {side: displayed_color(doc, sample[key][side], images)
                               for side in ('foreground', 'background')}
                ratios[key] = contrast(colors[key]['foreground'], colors[key]['background'])
            results.append({'pairId': pair['id'], 'sampleId': sample['id'], 'kind': pair['kind'],
                            'nodeIds': pair['nodeIds'], 'colors': colors, 'ratios': ratios,
                            'status': 'pass' if ratios['actual'] + 1e-9 >= ratios['source'] else 'fail'})
    orders = spec.get('emphasisOrders', [])
    expected_orders = expected_orders or []
    if orders != expected_orders:
        raise ValueError('emphasis order differs from frozen relationships')
    if len({o['id'] for o in orders}) != len(orders):
        raise ValueError('duplicate emphasis order')
    indexed = {(r['pairId'], r['sampleId']): r for r in results}
    order_results = []
    for order in orders:
        strong = indexed[(order['strongerPairId'], order['sampleId'])]
        weak = indexed[(order['weakerPairId'], order['sampleId'])]
        if any(strong['colors'][key]['background'] != weak['colors'][key]['background']
               for key in ('source', 'actual')):
            raise ValueError('relative emphasis requires the same actual host')
        baseline = strong['ratios']['source'] / weak['ratios']['source']
        current = strong['ratios']['actual'] / weak['ratios']['actual']
        if baseline <= 1:
            raise ValueError('declared stronger member is not stronger in source')
        order_results.append({'id': order['id'], 'sourceStrengthRatio': baseline,
                              'actualStrengthRatio': current,
                              'status': 'pass' if current > 1 and current + 1e-9 >= baseline else 'fail'})
    return {'status': 'pass' if all(r['status'] == 'pass' for r in results + order_results) else 'fail',
            'pairCount': len(pairs), 'samples': results, 'emphasisOrders': order_results,
            'note': 'Each declared relationship must not regress; visual discernibility is checked separately.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'actual', 'spec', 'relationships'):
        parser.add_argument(name)
    parser.add_argument('--map', dest='mapping'); parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        source, actual = mapped_document(read_json(args.source), read_json(args.actual),
                                        read_json(args.mapping) if args.mapping else None)
        frozen = read_json(args.relationships)
        result = compare_contrast(source, actual, read_json(args.spec),
                                  frozen['pairs'] if isinstance(frozen, dict) else frozen,
                                  frozen.get('emphasisOrders', []) if isinstance(frozen, dict) else [])
        save_json(args.out, result)
        print(result['status']); return 0 if result['status'] == 'pass' else 1
    except (ValueError, KeyError, TypeError, OSError) as exc:
        save_json(args.out, {'status': 'error', 'error': str(exc)})
        print(str(exc)); return 2


if __name__ == '__main__':
    sys.exit(main())

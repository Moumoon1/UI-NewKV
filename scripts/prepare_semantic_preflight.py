#!/usr/bin/env python3
"""Assemble reviewed semantic obligations before the static preflight.

No roots, protection scope, visual basis or color roles are inferred. The
generated relationships are audit obligations, not native-image evidence.
"""
import argparse
import json
from pathlib import Path

from compile_visual_unit_registry import build as visual_registry
from derive_cross_mode_plan import build as cross_mode_plan
from derive_icon_glyph_plan import build as icon_glyph_plan
from derive_text_range_plan import build as text_range_plan
from execution_audit import color_inventory, coverage


def build(source, manifest, reviewed):
    source_hash = color_inventory(source)['sourceHash']
    if (reviewed.get('schemaVersion') != 1 or
            reviewed.get('sourceHash') != source_hash):
        raise ValueError('semantic review choices must bind this source snapshot')
    if coverage(source, manifest)['status'] != 'pass':
        raise ValueError('complete reviewed color manifest required')
    required = ('iconRootIds', 'neutralIconEvidence', 'mediaCoverIds',
                'disabledRootIds', 'hiddenRootIds', 'stateRootIds',
                'boundaryRootIds', 'visualUnits', 'surfaceSystemPlan')
    missing = [key for key in required if key not in reviewed]
    if missing:
        raise ValueError('explicit reviewed semantic choices missing: ' + ', '.join(missing))
    for key in ('iconRootIds', 'mediaCoverIds', 'disabledRootIds',
                'hiddenRootIds', 'stateRootIds', 'boundaryRootIds'):
        if not isinstance(reviewed[key], list):
            raise ValueError(key + ' must be an explicit list')
    if not isinstance(reviewed['neutralIconEvidence'], dict):
        raise ValueError('neutralIconEvidence must be a path-keyed object')
    if not reviewed['iconRootIds'] and not reviewed.get('iconNotApplicableEvidence'):
        raise ValueError('Icon roots or explicit not-applicable evidence required')
    enriched = dict(manifest)
    surface_plan = reviewed['surfaceSystemPlan']
    if (not isinstance(surface_plan, dict) or surface_plan.get('schemaVersion') != 1 or
            surface_plan.get('sourceHash') != source_hash):
        raise ValueError('surfaceSystemPlan must bind this source snapshot')
    enriched['surfaceSystemPlan'] = surface_plan
    text_plan, text_relationships = text_range_plan(
        source, manifest, reviewed['mediaCoverIds'], reviewed['disabledRootIds'],
        reviewed['hiddenRootIds'])
    enriched['textRangePlan'] = text_plan
    if reviewed['iconRootIds']:
        enriched['iconGlyphPlan'] = icon_glyph_plan(
            source, manifest, reviewed['iconRootIds'], reviewed['neutralIconEvidence'])
    if manifest.get('themeTransition') in ('dark-to-light', 'light-to-dark'):
        if not reviewed['boundaryRootIds']:
            raise ValueError('cross-mode boundary roots require explicit review')
        enriched['crossModeCompositePlan'] = cross_mode_plan(
            source, manifest, reviewed['hiddenRootIds'],
            reviewed['stateRootIds'], reviewed['boundaryRootIds'])
    max_active = reviewed.get('visualUnitMaxActive', 75)
    if (type(max_active) is not int or not 1 <= max_active <= 100):
        raise ValueError('visualUnitMaxActive must be an integer from 1 to 100')
    visual = visual_registry(source, enriched, reviewed['visualUnits'],
                             max_active_per_unit=max_active)
    report = {'status': 'ready-for-ledger-and-native-review',
              'sourceHash': source_hash,
              'textNodes': len(text_plan['entries']),
              'textContrastRelationships': len(text_relationships),
              'iconRoots': len(enriched.get('iconGlyphPlan', {}).get('roots', [])),
              'crossModeEntries': len(enriched.get('crossModeCompositePlan', {}).get('entries', [])),
              'visualUnits': visual['report']['unitCount'],
              'visualCarriers': visual['report']['carrierCount'],
              'note': 'Rule ledger, actual host/pixel contrast samples, semantic correctness and 1:1 preview still require independent review.'}
    return {'manifest': enriched, 'visualUnits': visual['registry'],
            'textContrastRelationships': text_relationships, 'report': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('reviewed_choices', type=Path)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.source.read_text()),
                   json.loads(args.manifest.read_text()),
                   json.loads(args.reviewed_choices.read_text()))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, key in (('manifest-semantic.json', 'manifest'),
                      ('visual-units.json', 'visualUnits'),
                      ('text-contrast-relationships.json', 'textContrastRelationships'),
                      ('semantic-preflight-report.json', 'report')):
        (args.out_dir / name).write_text(json.dumps(result[key], ensure_ascii=False, indent=2))
    print(json.dumps(result['report'], ensure_ascii=False))


if __name__ == '__main__':
    main()

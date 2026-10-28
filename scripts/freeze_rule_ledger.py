#!/usr/bin/env python3
"""Validate an authored rule ledger and bind it to a reviewed manifest.

Template output is intentionally incomplete. Freezing checks structure and
semantic-plan scope, but never declares an actual 1:1 visual PASS.
"""
import argparse
import json
from pathlib import Path

from execution_audit import (MACHINE_RULES, VISUAL_RULES, icon_glyph_requirements,
                             text_range_requirements, visual_units)
from contrast_audit import transition_policy
from theme_audit import digest, snapshot_document
from interaction_entry_audit import inspect as inspect_entries
from surface_system_audit import inspect as inspect_surfaces


def template():
    return {'schemaVersion': 1, 'status': 'needs-review',
            'sourceInteractions': {'schemaVersion': 1, 'sourceHash': '',
                                   'sourceReviewEvidence': '', 'entries': None,
                                   'nonInteractiveText': None},
            'rules': [{'id': name, 'kind': kind, 'applicable': None,
                       'source': '', 'acceptance': '',
                       **({'scopeNodeIds': []} if kind == 'visual' else {})}
                      for kind, names in (('machine', MACHINE_RULES),
                                          ('visual', VISUAL_RULES))
                      for name in sorted(names)]}


def freeze(source, manifest, registry, color_relations, ledger):
    doc = snapshot_document(source)
    if ledger.get('schemaVersion') != 1 or not isinstance(ledger.get('rules'), list):
        raise ValueError('authored ledger schemaVersion/rules required')
    rules = ledger['rules']
    indexed = {rule.get('id'): rule for rule in rules}
    if len(indexed) != len(rules):
        raise ValueError('duplicate ledger rule ID')
    missing = (MACHINE_RULES | VISUAL_RULES) - indexed.keys()
    if missing:
        raise ValueError('missing required ledger rules: ' + ', '.join(sorted(missing)))
    for rule in rules:
        name = rule.get('id')
        kind = rule.get('kind')
        expected = ('visual' if name in VISUAL_RULES else
                    'machine' if name in MACHINE_RULES else kind)
        if kind not in ('visual', 'machine') or kind != expected:
            raise ValueError('wrong rule kind: ' + str(name))
        if type(rule.get('applicable')) is not bool:
            raise ValueError('rule applicability must be reviewed boolean: ' + name)
        for field in ('source', 'acceptance'):
            if not isinstance(rule.get(field), str) or not rule[field].strip():
                raise ValueError('reviewed ' + field + ' required: ' + name)
        if not rule['applicable'] and not rule.get('notApplicableEvidence'):
            raise ValueError('not-applicable rule needs evidence: ' + name)
        if kind == 'visual' and rule['applicable']:
            scope = rule.get('scopeNodeIds')
            if (not isinstance(scope, list) or not scope or
                    len(scope) != len(set(scope)) or not set(scope) <= doc['nodes'].keys()):
                raise ValueError('reviewed visual scope nodes required: ' + name)
    by_id = indexed
    unit_rule = by_id['visual-unit-coverage'].get('verifier', {})
    if (unit_rule.get('type') != 'visual-unit-coverage' or
            unit_rule.get('registryHash') != digest(registry)):
        raise ValueError('visual-unit rule must bind exact registry hash')
    color_rule = by_id['color-relations'].get('verifier', {})
    if (color_rule.get('type') != 'color-relations' or
            color_rule.get('groupsHash') != digest(color_relations)):
        raise ValueError('color-relations rule must bind exact groups hash')
    contrast = by_id['contrast-baseline'].get('verifier', {})
    if (contrast.get('type') != 'contrast-baseline' or
            not isinstance(contrast.get('relationships'), list)):
        raise ValueError('contrast rule needs authored relationships')
    transition_policy(manifest.get('themeTransition'),
                      contrast.get('policy', 'source-baseline'),
                      contrast.get('decisionContext'))
    surface_rule = by_id['surface-system'].get('verifier', {})
    if (surface_rule.get('type') != 'surface-system' or
            surface_rule.get('planHash') != digest(manifest.get('surfaceSystemPlan'))):
        raise ValueError('surface-system rule must bind exact surfaceSystemPlan hash')
    surface_result = inspect_surfaces(source, source, manifest, by_id)
    if surface_result['status'] != 'pass':
        raise ValueError('surface system obligations incomplete: ' + str(surface_result['errors'][:2]))
    unit_result = visual_units(source, manifest, registry, by_id)
    if unit_result['status'] != 'pass':
        raise ValueError('visual unit carrier coverage incomplete')
    icon_result = icon_glyph_requirements(source, manifest, by_id)
    if icon_result['status'] != 'pass':
        raise ValueError('Icon glyph coverage incomplete: ' + str(icon_result['errors'][:2]))
    text_result = text_range_requirements(source, manifest,
                                           contrast['relationships'], by_id)
    if text_result['status'] != 'pass':
        raise ValueError('text range/host coverage incomplete: ' + str(text_result['errors'][:2]))
    frozen = dict(ledger)
    entry_result = inspect_entries(source, manifest, ledger)
    if entry_result['status'] != 'pass':
        raise ValueError('source interaction obligations incomplete: ' + str(entry_result['errors'][:2]))
    frozen.pop('status', None)
    enriched = dict(manifest)
    enriched['ruleLedgerHash'] = digest(frozen)
    report = {'status': 'ready-for-static-preflight',
              'sourceHash': digest(doc), 'ruleCount': len(rules),
              'visualUnits': unit_result['unitCount'],
              'iconChannels': icon_result['channelCount'],
              'textRanges': text_result['rangeCount'],
              'surfaceCandidates': surface_result['candidateSurfaceCount'],
              'ruleLedgerHash': enriched['ruleLedgerHash'],
              'note': 'Only authored scope and semantic-plan structure passed; static machine audit and native preview remain mandatory.'}
    return {'ruleLedger': frozen, 'manifest': enriched, 'report': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    draft = sub.add_parser('template')
    draft.add_argument('--out', type=Path, required=True)
    final = sub.add_parser('freeze')
    final.add_argument('source', type=Path)
    final.add_argument('manifest', type=Path)
    final.add_argument('visual_units', type=Path)
    final.add_argument('color_relations', type=Path)
    final.add_argument('authored_ledger', type=Path)
    final.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'template':
        args.out.write_text(json.dumps(template(), ensure_ascii=False, indent=2))
        print(json.dumps({'status': 'needs-review', 'rules': len(template()['rules'])}))
        return
    result = freeze(json.loads(args.source.read_text()),
                    json.loads(args.manifest.read_text()),
                    json.loads(args.visual_units.read_text()),
                    json.loads(args.color_relations.read_text()),
                    json.loads(args.authored_ledger.read_text()))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, key in (('rule-ledger-frozen.json', 'ruleLedger'),
                      ('manifest-frozen.json', 'manifest'),
                      ('rule-ledger-report.json', 'report')):
        (args.out_dir / name).write_text(json.dumps(result[key], ensure_ascii=False, indent=2))
    print(json.dumps(result['report'], ensure_ascii=False))


if __name__ == '__main__':
    main()

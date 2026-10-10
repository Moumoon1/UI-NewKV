#!/usr/bin/env python3
"""Run the independent machine gates on one frozen offline theme projection.

This deliberately does not claim visual approval. A successful result is a
prerequisite for, not a replacement for, the 1:1 preview review in Phase 5.
"""

import argparse
import json
from pathlib import Path

import execution_audit as audit
import derive_vector_mirrors as vector_mirrors
import material_relation_audit as material
import preflight_instance_writes as instance
import preflight_visible_surfaces as visible_surfaces
import interaction_entry_audit as interaction_entries
import surface_system_audit as surface_system
from theme_audit import color_relations, digest, mapped_document, read_json
from contrast_audit import compare_contrast, transition_policy


STATIC_FILES = (
    'sourceBefore', 'expectedClone', 'manifest', 'writePlan', 'policy',
    'ruleLedger', 'visualUnits', 'colorRelations',
    'materialRelations', 'nodeMap',
)
REQUIRED_FILES = STATIC_FILES + ('contrastSamples',)


def run(spec, stage='full'):
    if stage not in ('static', 'full'):
        raise ValueError('preflight stage must be static or full')
    required = STATIC_FILES if stage == 'static' else REQUIRED_FILES
    missing = [key for key in required if not spec.get(key)]
    if missing:
        return {'status': 'fail', 'missingInputs': missing, 'checks': {}}
    inputs = {key: read_json(spec[key]) for key in required}
    source = inputs['sourceBefore']
    projected = inputs['expectedClone']
    manifest = inputs['manifest']
    mapping = inputs['nodeMap']
    ledger = inputs['ruleLedger']
    rules = {row['id']: row for row in ledger.get('rules', [])}
    checks = {}

    def check(name, callback):
        try:
            checks[name] = callback()
        except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
            checks[name] = {'status': 'fail', 'error': str(error)}

    def frozen_contract():
        names = audit.MACHINE_RULES | audit.VISUAL_RULES
        absent = sorted(names - rules.keys())
        duplicate = len(rules) != len(ledger.get('rules', []))
        if ledger.get('schemaVersion') != 1 or absent or duplicate:
            return {'status': 'fail', 'missingRuleIds': absent, 'duplicateRuleIds': duplicate}
        if manifest.get('ruleLedgerHash') != digest(ledger):
            return {'status': 'fail', 'error': 'manifest does not bind the frozen rule ledger'}
        surface_verifier = rules.get('surface-system', {}).get('verifier', {})
        if (surface_verifier.get('type') != 'surface-system' or
                surface_verifier.get('planHash') != digest(manifest.get('surfaceSystemPlan'))):
            return {'status': 'fail', 'error': 'surface-system rule does not bind the frozen plan'}
        contrast_verifier = rules.get('contrast-baseline', {}).get('verifier', {})
        transition_policy(manifest.get('themeTransition'),
                          contrast_verifier.get('policy', 'source-baseline'),
                          contrast_verifier.get('decisionContext'))
        has_gradient = any('/gradientStops/' in item['path'] and not item['inactive']
                           for item in audit.color_inventory(source)['entries'])
        if has_gradient and not inputs['materialRelations'].get('relations'):
            return {'status': 'fail', 'error': 'visible gradients require nonempty material relations'}
        return {'status': 'pass', 'ruleCount': len(rules)}

    check('frozen-contract', frozen_contract)
    check('instance-write-capability', lambda: instance.inspect(source, inputs['writePlan']))
    check('vector-mirror-readback-plan', lambda: vector_mirrors.inspect(
        source, manifest, inputs['writePlan']))
    check('visible-surface-roles', lambda: visible_surfaces.inspect(source, manifest))
    check('plan-complete', lambda: audit.complete(
        source, projected, manifest, inputs['policy'], mapping))
    check('color-bindings-clear', lambda: audit.color_binding_audit(projected))
    check('scheme-anchor-conformance', lambda: audit.scheme_anchor_requirements(manifest))
    check('icon-glyph-coverage', lambda: audit.icon_glyph_requirements(source, manifest, rules))
    check('text-range-coverage', lambda: audit.text_range_requirements(
        source, manifest, rules.get('contrast-baseline', {}).get('verifier', {}).get('relationships', []), rules))
    check('cross-mode-composite-coverage', lambda: audit.cross_mode_composite_requirements(
        source, projected, manifest, rules, mapping))
    check('visual-unit-coverage', lambda: audit.visual_units(
        source, manifest, inputs['visualUnits'], rules))
    check('interaction-requirements', lambda: audit.interaction_requirements(source, manifest, rules))
    check('interaction-entry-coverage', lambda: interaction_entries.inspect(source, manifest, ledger))
    check('surface-system', lambda: surface_system.inspect(
        source, projected, manifest, rules, mapping))
    check('material-relations', lambda: material.audit_material_relations(
        source, projected, mapping, inputs['materialRelations']))
    check('color-relations', lambda: color_relations(
        source, projected, inputs['colorRelations'], mapping, manifest))

    def contrast():
        before, after = mapped_document(source, projected, mapping)
        rule = rules['contrast-baseline']['verifier']
        return compare_contrast(before, after, inputs['contrastSamples'],
                                rule['relationships'], rule.get('emphasisOrders', []),
                                rule.get('policy', 'source-baseline'), rule.get('decisionContext'))

    if stage == 'full':
        check('contrast-baseline', contrast)
    failed = sorted(name for name, result in checks.items() if result.get('status') != 'pass')
    status = 'fail' if failed else 'ready-for-preview' if stage == 'static' else 'pass'
    return {'status': status, 'stage': stage, 'sourceHash': digest(source),
            'projectedHash': digest(projected), 'failedChecks': failed, 'checks': checks,
            'note': ('Static gates only; screenshot evidence and final contrast remain pending.'
                     if stage == 'static' else
                     'Machine preflight only; native 1:1 visual preview still requires separate approval.')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--stage', choices=('static', 'full'), default='full')
    args = parser.parse_args()
    result = run(json.loads(args.spec.read_text()), args.stage)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({key: result.get(key) for key in
                      ('status', 'missingInputs', 'failedChecks')}, ensure_ascii=False))
    return 0 if result['status'] in ('pass', 'ready-for-preview') else 1


if __name__ == '__main__':
    raise SystemExit(main())

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from freeze_rule_ledger import freeze, template
from prepare_semantic_preflight import build as prepare
import test_prepare_semantic_preflight as fixture_module
from theme_audit import digest


class FreezeRuleLedgerTests(unittest.TestCase):
    def fixture(self):
        helper = fixture_module.PrepareSemanticPreflightTests()
        source = helper.source()
        semantic = prepare(source, helper.manifest(source), helper.reviewed(source))
        color_relations = {'schemaVersion': 1, 'groups': []}
        ledger = template()
        ledger['sourceInteractions'] = {
            'schemaVersion': 1, 'sourceHash': semantic['manifest']['sourceHash'],
            'sourceReviewEvidence': 'Synthetic static label and decorative icon; no controls.',
            'entries': [], 'nonInteractiveText': [{'nodeIds': ['label'], 'reason': 'Static greeting.'}]}
        for rule in ledger['rules']:
            rule['applicable'] = True
            rule['source'] = 'Reviewed source UI and Skill policy.'
            rule['acceptance'] = 'Actual scope must pass its independent check.'
            if rule['kind'] == 'visual':
                rule['scopeNodeIds'] = ['page', 'label', 'icon']
            if rule['id'] == 'visual-unit-coverage':
                rule['verifier'] = {'type': 'visual-unit-coverage',
                                    'registryHash': digest(semantic['visualUnits'])}
            if rule['id'] == 'color-relations':
                rule['verifier'] = {'type': 'color-relations',
                                    'groupsHash': digest(color_relations)}
            if rule['id'] == 'contrast-baseline':
                rule['verifier'] = {'type': 'contrast-baseline',
                                    'relationships': semantic['textContrastRelationships']}
            if rule['id'] == 'surface-system':
                rule['verifier'] = {'type': 'surface-system',
                                    'planHash': digest(semantic['manifest']['surfaceSystemPlan'])}
        return source, semantic, color_relations, ledger

    def test_template_is_not_a_frozen_pass(self):
        source, semantic, relations, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, 'reviewed boolean'):
            freeze(source, semantic['manifest'], semantic['visualUnits'],
                   relations, template())

    def test_frozen_ledger_binds_manifest_without_visual_pass(self):
        source, semantic, relations, ledger = self.fixture()
        result = freeze(source, semantic['manifest'], semantic['visualUnits'],
                        relations, ledger)
        self.assertEqual(result['report']['status'], 'ready-for-static-preflight')
        self.assertEqual(result['report']['textRanges'], 1)
        self.assertEqual(result['report']['iconChannels'], 1)
        self.assertEqual(result['manifest']['ruleLedgerHash'],
                         digest(result['ruleLedger']))
        self.assertNotIn('status', result['ruleLedger'])

    def test_rejects_missing_scope_and_stale_registry_hash(self):
        source, semantic, relations, ledger = self.fixture()
        next(r for r in ledger['rules'] if r['id'] == 'readability')['scopeNodeIds'] = []
        with self.assertRaisesRegex(ValueError, 'visual scope'):
            freeze(source, semantic['manifest'], semantic['visualUnits'],
                   relations, ledger)
        source, semantic, relations, ledger = self.fixture()
        next(r for r in ledger['rules'] if r['id'] == 'visual-unit-coverage')['verifier']['registryHash'] = 'old'
        with self.assertRaisesRegex(ValueError, 'registry hash'):
            freeze(source, semantic['manifest'], semantic['visualUnits'],
                   relations, ledger)

    def test_allows_explicit_custom_visual_rule(self):
        source, semantic, relations, ledger = self.fixture()
        ledger['rules'].append({'id': 'task-specific-card-edge', 'kind': 'visual',
                                'applicable': True, 'scopeNodeIds': ['page'],
                                'source': 'User-specific visual requirement.',
                                'acceptance': 'Inspect native edge at 1:1.'})
        result = freeze(source, semantic['manifest'], semantic['visualUnits'],
                        relations, ledger)
        self.assertEqual(result['report']['ruleCount'], len(ledger['rules']))

    def test_cannot_freeze_without_source_interaction_inventory(self):
        source, semantic, relations, ledger = self.fixture()
        del ledger['sourceInteractions']
        with self.assertRaisesRegex(ValueError, 'source interaction obligations'):
            freeze(source, semantic['manifest'], semantic['visualUnits'], relations, ledger)

    def test_cross_mode_rejects_source_baseline_before_preview(self):
        source, semantic, relations, ledger = self.fixture()
        semantic['manifest']['themeTransition'] = 'dark-to-light'
        with self.assertRaisesRegex(ValueError, 'contextual contrast'):
            freeze(source, semantic['manifest'], semantic['visualUnits'],
                   relations, ledger)

    def test_cross_mode_requires_matching_context(self):
        source, semantic, relations, ledger = self.fixture()
        semantic['manifest']['themeTransition'] = 'dark-to-light'
        verifier = next(rule for rule in ledger['rules']
                        if rule['id'] == 'contrast-baseline')['verifier']
        verifier['policy'] = 'contextual'
        verifier['decisionContext'] = {
            'sourceUiMode': 'light', 'targetUiMode': 'dark',
            'adaptationMode': 'style-adaptation', 'reason': 'Reviewed mode change.'}
        with self.assertRaisesRegex(ValueError, 'differ from themeTransition'):
            freeze(source, semantic['manifest'], semantic['visualUnits'],
                   relations, ledger)


if __name__ == '__main__':
    unittest.main()

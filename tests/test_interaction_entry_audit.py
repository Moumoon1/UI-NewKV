import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from interaction_entry_audit import inspect
from execution_audit import color_inventory
from contrast_audit import compare_contrast, contrast
from theme_audit import digest, snapshot_document


class EntryAuditTests(unittest.TestCase):
    def setUp(self):
        def solid(rgb, opacity=1):
            return {'type': 'SOLID', 'opacity': opacity, 'color': dict(zip('rgb', rgb))}
        self.source = {'schemaVersion': 1, 'rootId': 'card', 'errors': [], 'nodes': [
            {'id': 'card', 'parentId': None, 'children': ['entry'],
             'props': {'type': 'FRAME', 'fills': [solid([1, .976, .918])]}},
            {'id': 'entry', 'parentId': 'card', 'children': ['body', 'label'],
             'props': {'type': 'GROUP'}},
            {'id': 'body', 'parentId': 'entry', 'children': [],
             'props': {'type': 'VECTOR', 'fills': [solid([.8, .60, .30])]}},
            {'id': 'label', 'parentId': 'entry', 'children': [],
             'props': {'type': 'TEXT', 'characters': '查看片单', 'fills': [solid([.2, .1, .05])]}}]}
        inventory = color_inventory(self.source)
        self.manifest = {'entries': [{**e, 'role': 'interaction.entry' if e['nodeId'] == 'body' else 'text.primary'}
                                    for e in inventory['entries']]}
        self.pair = {'id': 'entry-boundary', 'kind': 'button', 'nodeIds': ['body', 'card'],
                     'sampleIds': ['body', 'edge'], 'minimumDeltaE': 10}
        self.entry = {'rootId': 'entry', 'hostId': 'card', 'priority': 'secondary',
                      'affordance': 'filled', 'textNodeIds': ['label'],
                      'carrierPaths': ['/nodes/body/props/fills/0/color'],
                      'sourceEvidence': 'Synthetic source: filled secondary entry, not atmosphere.',
                      'boundaryPairId': 'entry-boundary',
                      'boundaryBasis': 'Fixture-specific body separation; not a universal threshold.',
                      'adjacentHostIds': ['card'], 'adjacentHostEvidence': 'All edges border uniform card.',
                      'boundaryComparisons': [{'hostId': 'card', 'pairId': 'entry-boundary',
                          'basis': 'Actual body and inner boundary against card.',
                          'sampleResponsibilities': {'body': 'body', 'edge': 'edge'}}],
                      'visualReviewRuleId': 'entry-review:entry'}
        self.ledger = {'sourceInteractions': {
            'schemaVersion': 1, 'sourceHash': inventory['sourceHash'],
            'sourceReviewEvidence': 'Synthetic whole card; no icon-only entries.',
            'entries': [self.entry], 'nonInteractiveText': []}, 'rules': [
                {'id': 'contrast-baseline', 'verifier': {'relationships': [self.pair]}},
                *[{'id': name, 'kind': 'visual', 'applicable': True, 'scopeNodeIds': ['entry', 'card']}
                  for name in ('button-salience', 'hierarchy')],
                {'id': 'entry-review:entry', 'kind': 'visual', 'applicable': True,
                 'scopeNodeIds': ['entry', 'card'], 'acceptance': 'Native local body, edge and text review.'}]}

    def check(self):
        return inspect(self.source, self.manifest, self.ledger)

    def test_secondary_entry_without_cta_passes_recorded_obligations(self):
        self.assertEqual(self.check()['status'], 'pass')

    def test_reclassified_as_atmosphere_fails_even_with_complete_channels(self):
        self.manifest['entries'][1]['role'] = 'card.atmosphere'
        self.assertEqual(self.check()['status'], 'fail')

    def test_missing_or_stale_inventory_fails(self):
        for inventory in (None, {}, {**self.ledger['sourceInteractions'], 'sourceHash': 'stale'}):
            with self.subTest(inventory=inventory):
                self.assertEqual(inspect(self.source, self.manifest,
                    {**self.ledger, 'sourceInteractions': inventory})['status'], 'fail')

    def test_label_contrast_does_not_substitute_for_body_boundary(self):
        self.pair.update(kind='text', nodeIds=['label', 'card'])
        self.assertEqual(self.check()['status'], 'fail')

    def test_label_cannot_be_registered_as_filled_button_body(self):
        self.entry['carrierPaths'] = ['/nodes/label/props/fills/0/color']
        self.assertEqual(self.check()['status'], 'fail')

    def test_omitted_entry_cannot_silently_drop_its_source_text(self):
        self.ledger['sourceInteractions']['entries'] = []
        self.assertEqual(self.check()['status'], 'fail')

    def test_explicit_noninteractive_source_is_supported(self):
        inv = self.ledger['sourceInteractions']
        inv['entries'] = []
        inv['nonInteractiveText'] = [{'nodeIds': ['label'], 'reason': 'For this alternate fixture it is static copy.'}]
        self.assertEqual(self.check()['status'], 'pass')

    def test_entry_and_host_must_both_be_visually_reviewed(self):
        self.ledger['rules'][1]['scopeNodeIds'] = ['entry']
        self.assertEqual(self.check()['status'], 'fail')

    def test_boundary_cannot_be_measurement_only_or_disabled(self):
        self.pair.pop('minimumDeltaE')
        self.assertEqual(self.check()['status'], 'fail')

    def test_valid_text_link_does_not_require_inventing_a_plate(self):
        self.entry.update(affordance='text', carrierPaths=['/nodes/label/props/fills/0/color'])
        self.pair.update(kind='text', nodeIds=['label', 'card'])
        self.assertEqual(self.check()['status'], 'pass')

    def test_malformed_entries_and_exclusions_fail_closed(self):
        self.ledger['sourceInteractions']['entries'] = [None]
        self.ledger['sourceInteractions']['nonInteractiveText'] = [None]
        self.assertEqual(self.check()['status'], 'fail')

    def test_hidden_carrier_cannot_substitute_for_visible_body(self):
        self.source['nodes'][2]['props']['fills'][0]['visible'] = False
        self.ledger['sourceInteractions']['sourceHash'] = color_inventory(self.source)['sourceHash']
        self.assertEqual(self.check()['status'], 'fail')

    def test_correct_outline_entry_does_not_require_filled_body(self):
        props = self.source['nodes'][2]['props']
        props['strokes'] = props.pop('fills')
        self.entry.update(affordance='outline', carrierPaths=['/nodes/body/props/strokes/0/color'])
        inventory = color_inventory(self.source)
        self.ledger['sourceInteractions']['sourceHash'] = inventory['sourceHash']
        self.manifest['entries'][1]['path'] = self.entry['carrierPaths'][0]
        self.assertEqual(self.check()['status'], 'pass')

    def test_cannot_register_only_one_of_multiple_visible_body_paints(self):
        self.source['nodes'][2]['props']['fills'].append({
            'type': 'SOLID', 'color': {'r': .9, 'g': .8, 'b': .5}})
        inventory = color_inventory(self.source)
        self.ledger['sourceInteractions']['sourceHash'] = inventory['sourceHash']
        self.manifest['entries'] = [{**e, 'role': 'interaction.entry' if e['nodeId'] == 'body' else 'text.primary'}
                                    for e in inventory['entries']]
        self.assertEqual(self.check()['status'], 'fail')
        self.entry['carrierPaths'].append('/nodes/body/props/fills/1/color')
        self.assertEqual(self.check()['status'], 'pass')

    def test_old_single_host_inventory_requires_explicit_adjacency_review(self):
        self.entry.pop('adjacentHostIds')
        self.assertEqual(self.check()['status'], 'fail')

    def test_page_neighbor_cannot_be_covered_by_card_pair(self):
        self.source['nodes'].append({'id': 'page', 'parentId': None, 'children': ['card'],
                                     'props': {'type': 'FRAME'}})
        self.source['rootId'] = 'page'
        self.source['nodes'][0]['parentId'] = 'page'
        self.ledger['sourceInteractions']['sourceHash'] = color_inventory(self.source)['sourceHash']
        self.entry['adjacentHostIds'].append('page')
        for rule in self.ledger['rules'][1:]:
            rule['scopeNodeIds'].append('page')
        self.assertEqual(self.check()['status'], 'fail')
        self.ledger['rules'][0]['verifier']['relationships'].append({
            **self.pair, 'id': 'page-boundary', 'nodeIds': ['body', 'page']})
        self.entry['boundaryComparisons'].append({
            **self.entry['boundaryComparisons'][0], 'hostId': 'page', 'pairId': 'page-boundary'})
        self.assertEqual(self.check()['status'], 'pass')

    def test_body_sample_alone_does_not_cover_edge(self):
        self.entry['boundaryComparisons'][0]['sampleResponsibilities']['edge'] = 'body'
        self.assertEqual(self.check()['status'], 'fail')

    def test_gradient_requires_weakest_body_sample(self):
        self.source['nodes'][2]['props']['fills'][0] = {
            'type': 'GRADIENT_LINEAR', 'opacity': 1,
            'gradientStops': [{'position': 0, 'color': {'r': .8, 'g': .6, 'b': .3, 'a': 1}},
                              {'position': 1, 'color': {'r': .9, 'g': .8, 'b': .5, 'a': 1}}]}
        inventory = color_inventory(self.source)
        self.ledger['sourceInteractions']['sourceHash'] = inventory['sourceHash']
        self.manifest['entries'] = [{**e, 'role': 'interaction.entry' if e['nodeId'] == 'body' else 'text.primary'}
                                    for e in inventory['entries']]
        self.entry['carrierPaths'] = [e['path'] for e in inventory['entries'] if e['nodeId'] == 'body']
        self.assertEqual(self.check()['status'], 'fail')
        self.pair['sampleIds'].append('weak')
        self.entry['boundaryComparisons'][0]['sampleResponsibilities']['weak'] = 'weakest-body'
        self.assertEqual(self.check()['status'], 'pass')

    def test_full_page_rules_do_not_replace_dedicated_entry_review(self):
        self.ledger['rules'].pop()
        self.assertEqual(self.check()['status'], 'fail')

    def contrast(self, alpha):
        source = snapshot_document(self.source)
        actual = copy.deepcopy(source)
        actual['nodes']['body']['props']['fills'][0]['opacity'] = alpha
        host = {'colorPath': '/nodes/card/props/fills/0/color'}
        paint = {'colorPath': '/nodes/body/props/fills/0/color',
                 'alphaPaths': ['/nodes/body/props/fills/0/opacity']}
        colors = {'foreground': {'layers': [host, paint]}, 'background': {'layers': [host]}}
        context = {'sourceUiMode': 'dark', 'targetUiMode': 'light',
                   'adaptationMode': 'color-only', 'reason': 'Synthetic cross-mode boundary test.'}
        samples = {'schemaVersion': 1, 'sourceHash': digest(source), 'actualHash': digest(actual),
                   'policy': 'contextual', 'decisionContext': context,
                   'pairs': [{**self.pair, 'sampleIds': ['body'], 'samples': [{'id': 'body', 'basis': 'Opaque uniform host.',
                              'source': colors, 'actual': colors}]}]}
        return compare_contrast(source, actual, samples, [{**self.pair, 'sampleIds': ['body']}],
                                expected_policy='contextual', expected_context=context)

    def test_faded_body_fails_boundary_while_unchanged_dark_label_is_irrelevant(self):
        self.assertGreater(contrast([.2, .1, .05], [1, .976, .918]), 3)
        self.assertEqual(self.contrast(.16)['status'], 'fail')

    def test_clear_body_passes_and_alpha_reduction_is_not_globally_banned(self):
        self.assertEqual(self.contrast(1)['status'], 'pass')
        self.assertEqual(self.contrast(.8)['status'], 'pass')


if __name__ == '__main__':
    unittest.main()

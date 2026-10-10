from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_contrast_sample_queue import build
from contrast_audit import displayed_color
from theme_audit import digest, snapshot_document


class PrepareContrastSampleQueueTests(unittest.TestCase):
    def fixture(self):
        source = {'schemaVersion': 1, 'rootId': 'page', 'errors': [], 'nodes': [
            {'id': 'page', 'parentId': None, 'children': ['title'],
             'props': {'type': 'FRAME', 'opacity': 1,
                       'fills': [{'type': 'SOLID', 'opacity': 1,
                                  'color': {'r': 1, 'g': 1, 'b': 1}}]}},
            {'id': 'title', 'parentId': 'page', 'children': [],
             'props': {'type': 'TEXT', 'opacity': 1, 'characters': 'Title',
                       'textRuns': {'fills': [{'start': 0, 'end': 5,
                           'value': [{'type': 'SOLID', 'opacity': 1,
                                      'color': {'r': 0, 'g': 0, 'b': 0}}]}]}}},
        ]}
        path = '/nodes/title/props/textRuns/fills/0/value/0/color'
        manifest = {'textRangePlan': {
            'sourceHash': digest(snapshot_document(source)),
            'entries': [{'nodeId': 'title', 'ranges': [
                {'start': 0, 'end': 5, 'channelPaths': [path],
                 'role': 'text.primary', 'hostNodeIds': ['page'],
                 'contrastPairIds': ['text:title:0']}]}]}}
        ledger = {'rules': [{'id': 'contrast-baseline', 'verifier': {
            'policy': 'contextual', 'decisionContext': {'sourceUiMode': 'dark',
                'targetUiMode': 'light', 'adaptationMode': 'color-only',
                'reason': 'Reviewed.'},
            'relationships': [{'id': 'text:title:0', 'kind': 'text',
                'nodeIds': ['title', 'page'], 'sampleIds': ['native-range']}]}}]}
        return source, manifest, ledger

    def test_solid_candidates_still_require_native_review(self):
        source, manifest, ledger = self.fixture()
        result = build(source, deepcopy(source), manifest, ledger)
        self.assertEqual(result['status'], 'needs-review')
        self.assertEqual(result['solidCandidatePairs'], 1)
        row = result['queue'][0]
        self.assertFalse(row['reviewed'])
        self.assertIn('native-host-and-glyph-review', row['needsReview'])
        self.assertEqual(row['candidates']['actual']['background']['layers'][0]['colorPath'],
                         '/nodes/page/props/fills/0/color')

    def test_gradient_foreground_is_not_faked_as_solid(self):
        source, manifest, ledger = self.fixture()
        paint = source['nodes'][1]['props']['textRuns']['fills'][0]['value'][0]
        paint.clear()
        paint.update({'type': 'GRADIENT_LINEAR', 'opacity': 1,
                      'gradientStops': [{'position': 0,
                                         'color': {'r': 0, 'g': 0, 'b': 0}}]})
        manifest['textRangePlan']['sourceHash'] = digest(snapshot_document(source))
        result = build(source, deepcopy(source), manifest, ledger)
        self.assertEqual(result['solidCandidatePairs'], 0)
        self.assertIsNone(result['queue'][0]['candidates']['actual']['foreground'])
        self.assertIn('foreground-gradient-multiple-or-unresolved-composite',
                      result['queue'][0]['needsReview'])

    def test_translucent_solid_uses_verified_opaque_host_layer_candidate(self):
        source, manifest, ledger = self.fixture()
        source['nodes'][1]['props']['textRuns']['fills'][0]['value'][0]['opacity'] = .6
        manifest['textRangePlan']['sourceHash'] = digest(snapshot_document(source))
        result = build(source, deepcopy(source), manifest, ledger)
        candidate = result['queue'][0]['candidates']['source']['foreground']
        self.assertEqual(result['solidCandidatePairs'], 1)
        self.assertEqual(len(candidate['layers']), 2)
        self.assertEqual(candidate['layers'][1]['alphaPaths'],
                         ['/nodes/title/props/textRuns/fills/0/value/0/opacity'])
        self.assertEqual(displayed_color(snapshot_document(source), candidate, {}),
                         [.4, .4, .4])

    def test_translucent_solid_without_simple_host_stays_manual(self):
        source, manifest, ledger = self.fixture()
        source['nodes'][0]['props']['fills'][0]['type'] = 'GRADIENT_LINEAR'
        source['nodes'][1]['props']['textRuns']['fills'][0]['value'][0]['opacity'] = .6
        manifest['textRangePlan']['sourceHash'] = digest(snapshot_document(source))
        result = build(source, deepcopy(source), manifest, ledger)
        self.assertIsNone(result['queue'][0]['candidates']['source']['foreground'])
        self.assertEqual(result['solidCandidatePairs'], 0)

    def test_stale_plan_is_rejected(self):
        source, manifest, ledger = self.fixture()
        manifest['textRangePlan']['sourceHash'] = 'old'
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            build(source, deepcopy(source), manifest, ledger)


if __name__ == '__main__':
    unittest.main()

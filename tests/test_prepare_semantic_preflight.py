from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_semantic_preflight import build
from execution_audit import color_inventory


class PrepareSemanticPreflightTests(unittest.TestCase):
    def source(self):
        def paint(r, g, b):
            return {'type': 'SOLID', 'color': {'r': r, 'g': g, 'b': b}}
        return {'schemaVersion': 1, 'rootId': 'page', 'errors': [], 'nodes': [
            {'id': 'page', 'parentId': None, 'children': ['label', 'icon'],
             'props': {'type': 'FRAME', 'name': 'Page', 'visible': True,
                       'x': 0, 'y': 0, 'width': 414, 'height': 800,
                       'fills': [paint(.1, .1, .1)]}},
            {'id': 'label', 'parentId': 'page', 'children': [],
             'props': {'type': 'TEXT', 'name': 'Label', 'visible': True,
                       'characters': 'Hello', 'fills': [paint(1, 1, 1)],
                       'textRuns': {'fills': [{'start': 0, 'end': 5,
                                              'value': [paint(1, 1, 1)]}]}}},
            {'id': 'icon', 'parentId': 'page', 'children': [],
             'props': {'type': 'VECTOR', 'name': 'Icon', 'visible': True,
                       'fills': [paint(.8, .3, .1)]}},
        ]}

    def manifest(self, source):
        inventory = color_inventory(source)
        entries = []
        for item in inventory['entries']:
            icon = item['nodeId'] == 'icon'
            entries.append({'path': item['path'], 'nodeId': item['nodeId'],
                            'role': 'icon-glyph' if icon else 'text-visible',
                            'disposition': 'change' if icon else 'preserve',
                            'reason': 'Reviewed in native source.', 'ruleId': 'reviewed',
                            **({'target': {'r': 1, 'g': .7, 'b': .2},
                                'recipeId': 'icon', 'sceneId': 'native'} if icon else {})})
        return {'schemaVersion': 1, 'sourceHash': inventory['sourceHash'],
                'themeTransition': 'light-to-light', 'entries': entries}

    def reviewed(self, source):
        h = color_inventory(source)['sourceHash']
        page_path = next(row['path'] for row in color_inventory(source)['entries']
                         if row['nodeId'] == 'page' and '/props/fills/' in row['path'])
        def unit(name):
            return {'id': name + '-unit', 'rootNodeId': name,
                    'basis': 'Reviewed source hierarchy and native screenshot.',
                    'reviewRuleIds': ['hierarchy'], 'extraDependencyNodeIds': []}
        return {'schemaVersion': 1, 'sourceHash': h,
                'iconRootIds': ['icon'], 'neutralIconEvidence': {},
                'mediaCoverIds': [], 'disabledRootIds': [],
                'hiddenRootIds': [], 'stateRootIds': [], 'boundaryRootIds': [],
                'surfaceSystemPlan': {'schemaVersion': 1, 'sourceHash': h,
                    'surfaces': [{'id': 'page-surface', 'nodeId': 'page', 'kind': 'page',
                                  'carrierPaths': [page_path],
                                  'stableRepresentativePath': page_path,
                                  'basis': 'Root page background.'}],
                    'cardBaseGroups': [], 'boundaryReviews': []},
                'visualUnits': {'schemaVersion': 1, 'sourceHash': h,
                                'units': [unit('page'), unit('label'), unit('icon')]}}

    def test_assembles_exact_plans_without_claiming_visual_pass(self):
        source = self.source()
        result = build(source, self.manifest(source), self.reviewed(source))
        self.assertEqual(result['report']['status'], 'ready-for-ledger-and-native-review')
        self.assertEqual(result['report']['textNodes'], 1)
        self.assertEqual(result['report']['iconRoots'], 1)
        self.assertEqual(result['report']['visualCarriers'], 4)
        self.assertEqual(len(result['manifest']['textRangePlan']['entries']), 1)
        self.assertEqual(len(result['textContrastRelationships']), 1)
        self.assertNotIn('ruleLedgerHash', result['manifest'])

    def test_requires_explicit_icons_and_matching_source(self):
        source = self.source()
        reviewed = self.reviewed(source)
        reviewed['iconRootIds'] = []
        with self.assertRaisesRegex(ValueError, 'Icon roots'):
            build(source, self.manifest(source), reviewed)
        reviewed = self.reviewed(source)
        reviewed['sourceHash'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'bind'):
            build(source, self.manifest(source), reviewed)

    def test_cross_mode_needs_explicit_boundaries(self):
        source = self.source()
        manifest = self.manifest(source)
        manifest['themeTransition'] = 'dark-to-light'
        with self.assertRaisesRegex(ValueError, 'boundary roots'):
            build(source, manifest, self.reviewed(source))


if __name__ == '__main__':
    unittest.main()

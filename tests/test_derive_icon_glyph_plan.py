import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import derive_icon_glyph_plan as derive
import execution_audit as audit


class IconGlyphDerivationTests(unittest.TestCase):
    def fixture(self):
        source = {'schemaVersion': 1, 'collectorVersion': 1, 'errors': [],
                  'rootId': 'page', 'nodes': [
            {'id': 'page', 'parentId': None, 'children': ['icon'], 'props': {'type': 'FRAME'}},
            {'id': 'icon', 'parentId': 'page', 'children': ['glyph'], 'props': {
                'type': 'FRAME', 'fills': [{'type': 'SOLID', 'color': {'r': .1, 'g': .2, 'b': .3}}]}},
            {'id': 'glyph', 'parentId': 'icon', 'children': [], 'props': {
                'type': 'VECTOR', 'fills': [{'type': 'SOLID', 'color': {'r': .8, 'g': .7, 'b': .6}}]}}]}
        rows = audit.color_inventory(source)['entries']
        manifest = {'entries': [{**row, 'disposition': 'change' if row['nodeId'] == 'glyph'
                    else 'preserve', 'reason': 'Reviewed visual role'} for row in rows]}
        return source, manifest

    def test_expands_explicit_icon_root(self):
        source, manifest = self.fixture()
        plan = derive.build(source, manifest, ['icon'])
        channels = plan['roots'][0]['channels']
        self.assertEqual([row['part'] for row in channels], ['container', 'glyph'])
        self.assertEqual(audit.icon_glyph_requirements(source, {**manifest,
            'iconGlyphPlan': plan}, {'icon-clarity': {'applicable': True,
            'scopeNodeIds': ['icon']}})['status'], 'pass')

    def test_preserved_glyph_needs_exact_evidence(self):
        source, manifest = self.fixture()
        manifest['entries'][1]['disposition'] = 'preserve'
        with self.assertRaisesRegex(ValueError, 'neutral evidence'):
            derive.build(source, manifest, ['icon'])
        path = manifest['entries'][1]['path']
        plan = derive.build(source, manifest, ['icon'], {path: 'Neutral gray verified on source.'})
        self.assertTrue(plan['roots'][0]['channels'][1]['themeNeutral'])


if __name__ == '__main__':
    unittest.main()

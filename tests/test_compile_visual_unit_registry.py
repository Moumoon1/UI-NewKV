from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compile_visual_unit_registry import build
from execution_audit import color_inventory, visual_units


class CompileVisualUnitRegistryTests(unittest.TestCase):
    def source(self):
        def props(kind, name, value=None, visible=True):
            row = {'type': kind, 'name': name, 'visible': visible}
            if value is not None:
                row['fills'] = [{'type': 'SOLID', 'color': {'r': value, 'g': value, 'b': value}}]
            return row
        return {'schemaVersion': 1, 'rootId': 'page', 'errors': [], 'nodes': [
            {'id': 'page', 'parentId': None, 'children': ['card', 'footer'],
             'props': props('FRAME', 'Page', .2)},
            {'id': 'card', 'parentId': 'page', 'children': ['title', 'hidden'],
             'props': props('FRAME', 'Card', .4)},
            {'id': 'title', 'parentId': 'card', 'children': [],
             'props': props('TEXT', 'Title', .8)},
            {'id': 'hidden', 'parentId': 'card', 'children': [],
             'props': props('RECTANGLE', 'Hidden', .1, False)},
            {'id': 'footer', 'parentId': 'page', 'children': [],
             'props': props('FRAME', 'Footer', .6)},
        ]}

    def manifest(self, source):
        inventory = color_inventory(source)
        return {'schemaVersion': 1, 'sourceHash': inventory['sourceHash'],
                'entries': [{'path': item['path'], 'nodeId': item['nodeId'],
                             'role': 'inactive-stored' if item['inactive'] else 'reviewed-surface',
                             'reason': 'Reviewed source hierarchy and native screenshot.',
                             'ruleId': 'test-rule',
                             'disposition': 'ignore' if item['inactive'] else 'preserve'}
                            for item in inventory['entries']]}

    def declarations(self, source):
        hash_ = color_inventory(source)['sourceHash']
        def unit(unit_id, root):
            return {'id': unit_id, 'rootNodeId': root,
                    'basis': 'Source hierarchy and screenshot independently reviewed.',
                    'reviewRuleIds': ['hierarchy'], 'extraDependencyNodeIds': []}
        return {'schemaVersion': 1, 'sourceHash': hash_,
                'units': [unit('page-unit', 'page'), unit('card-unit', 'card'),
                          unit('footer-unit', 'footer')]}

    def test_assigns_every_stored_path_once_to_deepest_reviewed_root(self):
        source = self.source()
        manifest = self.manifest(source)
        result = build(source, manifest, self.declarations(source), max_active_per_unit=2)
        registry = result['registry']
        self.assertEqual(result['report']['status'], 'ready-for-rule-scope-review')
        self.assertEqual(result['report']['carrierCount'], 5)
        self.assertEqual(result['report']['activeCarrierCount'], 4)
        self.assertEqual(visual_units(source, manifest, registry)['status'], 'pass')
        units = {u['id']: u for u in registry['units']}
        self.assertEqual(len(units['page-unit']['carrierPaths']), 1)
        self.assertEqual(len(units['card-unit']['carrierPaths']), 3)
        self.assertIn('hidden', units['card-unit']['dependencyNodeIds'])
        self.assertEqual(len(units['footer-unit']['carrierPaths']), 1)

    def test_missing_or_overbroad_reviewed_unit_fails_closed(self):
        source = self.source()
        manifest = self.manifest(source)
        decl = self.declarations(source)
        decl['units'] = decl['units'][:1]
        with self.assertRaisesRegex(ValueError, 'too broad'):
            build(source, manifest, decl, max_active_per_unit=2)
        decl = self.declarations(source)
        decl['units'] = decl['units'][1:]
        with self.assertRaisesRegex(ValueError, 'unassigned channel'):
            build(source, manifest, decl)

    def test_rejects_unreviewed_basis_or_stale_source(self):
        source = self.source()
        manifest = self.manifest(source)
        decl = self.declarations(source)
        decl['units'][0]['basis'] = ''
        with self.assertRaisesRegex(ValueError, 'basis'):
            build(source, manifest, decl)
        decl = self.declarations(source)
        decl['sourceHash'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'bind'):
            build(source, manifest, decl)


if __name__ == '__main__':
    unittest.main()

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import derive_material_relations as derive
import execution_audit as audit


class MaterialDerivationTests(unittest.TestCase):
    def fixture(self, alpha=1):
        source = {'schemaVersion': 1, 'collectorVersion': 1, 'errors': [],
                  'rootId': 'root', 'nodes': [{'id': 'root', 'parentId': None,
                  'children': [], 'props': {'type': 'FRAME', 'fills': [{
                      'type': 'GRADIENT_LINEAR', 'gradientStops': [
                          {'position': 0, 'color': {'r': .1, 'g': .1, 'b': .1, 'a': alpha}},
                          {'position': 1, 'color': {'r': .8, 'g': .7, 'b': .6, 'a': 1}}]}]}}]}
        manifest = {'entries': [{**row, 'disposition': 'change', 'role': 'material'}
                                for row in audit.color_inventory(source)['entries']]}
        return source, manifest

    def test_distinct_opaque_stops_get_relation(self):
        source, manifest = self.fixture()
        plan = derive.build(source, manifest)
        self.assertEqual(len(plan['relations']), 1)
        self.assertEqual(len(plan['relations'][0]['members']), 2)

    def test_transparent_terminal_is_composite_exception(self):
        source, manifest = self.fixture(alpha=0)
        plan = derive.build(source, manifest)
        self.assertEqual(plan['relations'], [])
        self.assertIn('transparent fade', plan['exceptions'][0]['reason'])


if __name__ == '__main__':
    unittest.main()

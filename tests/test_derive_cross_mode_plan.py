import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import derive_cross_mode_plan as derive
import execution_audit as audit


class CrossModePlanTests(unittest.TestCase):
    def fixture(self):
        source = {'schemaVersion': 1, 'collectorVersion': 1, 'errors': [], 'rootId': 'root',
                  'nodes': [{'id': 'root', 'parentId': None, 'children': ['fade'],
                             'props': {'type': 'FRAME', 'fills': [{'type': 'SOLID',
                             'color': {'r': .2, 'g': .2, 'b': .2}}]}},
                            {'id': 'fade', 'parentId': 'root', 'children': [],
                             'props': {'type': 'RECTANGLE', 'opacity': .5,
                             'fills': [{'type': 'SOLID', 'color': {'r': .8, 'g': .8, 'b': .8}}]}}]}
        manifest = {'entries': [{**row, 'role': 'atmosphere', 'disposition': 'change'}
                                for row in audit.color_inventory(source)['entries']]}
        return source, manifest

    def test_covers_actual_alpha_and_boundary(self):
        source, manifest = self.fixture()
        plan = derive.build(source, manifest, boundary_roots=['root'])
        result = audit.cross_mode_composite_requirements(source, source,
            {**manifest, 'themeTransition': 'dark-to-light',
             'crossModeCompositePlan': plan},
            {'cross-mode-composite': {'scopeNodeIds': ['root', 'fade']},
             'surface-continuity': {'scopeNodeIds': ['root', 'fade']}})
        self.assertEqual(result['status'], 'pass')

    def test_state_root_requires_state_semantics(self):
        source, manifest = self.fixture()
        with self.assertRaisesRegex(ValueError, 'state role'):
            derive.build(source, manifest, state_roots=['fade'], boundary_roots=['root'])


if __name__ == '__main__':
    unittest.main()

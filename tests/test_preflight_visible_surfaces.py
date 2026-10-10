from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from preflight_visible_surfaces import inspect
from execution_audit import color_inventory


class VisibleSurfaceTests(unittest.TestCase):
    def fixture(self, role, node_type='VECTOR', width=382, height=63):
        source = {'schemaVersion': 1, 'rootId': 'page', 'errors': [], 'nodes': [
            {'id': 'page', 'parentId': None, 'children': ['carrier'],
             'props': {'type': 'FRAME', 'visible': True, 'width': 414, 'height': 800}},
            {'id': 'carrier', 'parentId': 'page', 'children': [], 'props': {
                'type': node_type, 'name': 'Header surface', 'visible': True,
                'width': width, 'height': height, 'fills': [
                    {'type': 'SOLID', 'visible': True, 'opacity': 1,
                     'color': {'r': .2, 'g': .1, 'b': .1}}]}}]}
        entries = [{'path': row['path'], 'nodeId': row['nodeId'], 'role': role,
                    'disposition': 'change'} for row in color_inventory(source)['entries']]
        return source, {'entries': entries}

    def test_large_vector_with_text_recipe_fails(self):
        source, manifest = self.fixture('text')
        result = inspect(source, manifest)
        self.assertEqual(result['status'], 'fail')
        self.assertEqual(result['violations'][0]['nodeId'], 'carrier')

    def test_large_vector_with_surface_recipe_passes(self):
        source, manifest = self.fixture('header')
        self.assertEqual(inspect(source, manifest)['status'], 'pass')

    def test_small_glyph_and_real_text_are_not_misidentified(self):
        for kind, width, height in [('VECTOR', 24, 24), ('TEXT', 382, 63)]:
            source, manifest = self.fixture('text', kind, width, height)
            self.assertEqual(inspect(source, manifest)['status'], 'pass')

    def test_opaque_secondary_surface_requires_surface_role(self):
        source, manifest = self.fixture('secondary')
        self.assertEqual(inspect(source, manifest)['status'], 'fail')


if __name__ == '__main__':
    unittest.main()

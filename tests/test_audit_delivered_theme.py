from pathlib import Path
import sys
import unittest
import copy
import tempfile
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_delivered_theme import _same_rendered_paints, structural_map, _pixels_identical, audit
from PIL import Image


def row(node_id, parent, children):
    return {'id': node_id, 'parentId': parent, 'children': children,
            'props': {'type': 'FRAME', 'name': node_id}}


class DeliveredThemeAuditTests(unittest.TestCase):
    def test_historical_generators_do_not_emit_fixed_node_mutations(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        for name in ('generate_blue_revision_apply_js.py', 'generate_compact_revision_js.py'):
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, str(scripts / name)],
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('Retired task-specific template', result.stderr)

    def delivered_fixture(self, directory):
        source = {'schemaVersion': 1, 'rootId': 'source', 'errors': [], 'nodes': [
            row('source', None, ['hero']), row('hero', 'source', [])]}
        source['nodes'][0]['props'].update(width=320, height=640, fills=[])
        source['nodes'][1]['props'].update(width=320, height=100, fills=[])
        kv = {'schemaVersion': 1, 'rootId': 'kv-source', 'errors': [],
              'nodes': [row('kv-source', None, [])]}
        kv['nodes'][0]['props'].update(name='Asset', width=200, height=100, fills=[])
        final = {'schemaVersion': 1, 'rootId': 'final', 'errors': [], 'nodes': [
            row('final', None, ['kv', 'hero-clone']), row('hero-clone', 'final', []), row('kv', 'final', [])]}
        final['nodes'][0]['props'] = copy.deepcopy(source['nodes'][0]['props'])
        final['nodes'][1]['props'] = copy.deepcopy(source['nodes'][1]['props'])
        final['nodes'][2]['props'] = {**kv['nodes'][0]['props'], 'x': 10, 'y': 5, 'locked': True}
        png = Path(directory) / 'native.png'
        Image.new('RGB', (320, 640), 'white').save(png)
        plan = {'detachInstanceIds': [], 'kvPlacement': {'childIndex': 0, 'x': 10, 'y': 5}}
        return source, copy.deepcopy(source), final, kv, {'entries': []}, plan, png, png

    def test_delivery_uses_actual_canvas_and_frozen_kv_placement(self):
        with tempfile.TemporaryDirectory() as directory:
            result = audit(*self.delivered_fixture(directory))
            self.assertEqual(result['status'], 'pass', result['errors'])
            self.assertTrue(result['kvPlacementChecked'])

    def test_wrong_or_missing_frozen_placement_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.delivered_fixture(directory)
            args[5]['kvPlacement']['x'] = 0
            self.assertEqual(audit(*args)['status'], 'fail')
            args[5].pop('kvPlacement')
            with self.assertRaisesRegex(ValueError, 'kvPlacement'):
                audit(*args)

    def test_matching_screenshots_at_wrong_resolution_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.delivered_fixture(directory)
            Image.new('RGB', (160, 320), 'white').save(args[6])
            self.assertEqual(audit(*args)['status'], 'fail')

    def test_rgb_difference_is_detected_with_identical_opaque_alpha(self):
        a = Image.new('RGBA', (2, 2), (100, 100, 100, 255))
        b = a.copy()
        self.assertTrue(_pixels_identical(a, b))
        b.putpixel((0, 0), (101, 100, 100, 255))
        self.assertFalse(_pixels_identical(a, b))

    def test_alpha_difference_is_also_detected(self):
        a = Image.new('RGBA', (2, 2), (100, 100, 100, 255))
        b = Image.new('RGBA', (2, 2), (100, 100, 100, 254))
        self.assertFalse(_pixels_identical(a, b))

    def test_structural_mapping_skips_only_inserted_kv(self):
        source = {'schemaVersion': 1, 'rootId': 's', 'errors': [],
                  'nodes': [row('s', 'page', ['a', 'b']),
                            row('a', 's', []), row('b', 's', [])]}
        final = {'schemaVersion': 1, 'rootId': 'f', 'errors': [],
                 'nodes': [row('f', 'page', ['x', 'kv', 'y']),
                           row('x', 'f', []), row('kv', 'f', []), row('y', 'f', [])]}
        self.assertEqual(structural_map(source, final, 'f', excluded_roots={'kv'}),
                         {'s': 'f', 'b': 'y', 'a': 'x'})

    def test_delivery_rejects_raster_button_overlay_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            args = list(self.delivered_fixture(directory))
            args[5]['ctaButtonOverlay'] = {'name': '__kv_cta_button_overlay__'}
            with self.assertRaisesRegex(ValueError, 'overlay is forbidden'):
                audit(*args)

    def test_equal_text_paints_ignore_removed_variable_alias(self):
        expected = [{'type': 'SOLID', 'opacity': 1,
                     'color': {'r': .25, 'g': .5, 'b': .75},
                     'boundVariables': {'color': {'id': 'source'}}}]
        actual = [{'type': 'SOLID', 'opacity': 1,
                   'color': {'r': .25, 'g': .5, 'b': .75},
                   'boundVariables': {}}]
        self.assertTrue(_same_rendered_paints(expected, actual))
        actual[0]['opacity'] = .5
        self.assertFalse(_same_rendered_paints(expected, actual))
        actual[0]['opacity'] = 1
        actual[0]['color']['r'] = .2
        self.assertFalse(_same_rendered_paints(expected, actual))


if __name__ == '__main__':
    unittest.main()

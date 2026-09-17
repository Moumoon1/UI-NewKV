import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import contrast_audit as contrast
from theme_audit import digest


class ContrastChecks(unittest.TestCase):
    def setUp(self):
        self.source = {'nodes': {'host': {'props': {'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}]}},
                                 'plate': {'props': {'opacity': .5, 'fills': [
                                     {'type': 'SOLID', 'color': {'r': .4, 'g': .5, 'b': .6}}]}}}}
        self.actual = copy.deepcopy(self.source)
        self.frozen = [{'id': 'plate-host', 'kind': 'surface', 'nodeIds': ['plate', 'host'],
                        'sampleIds': ['center']}]
        host = {'colorPath': '/nodes/host/props/fills/0/color'}
        fg = {'layers': [host, {'colorPath': '/nodes/plate/props/fills/0/color',
                               'alphaPaths': ['/nodes/plate/props/opacity']}]}
        bg = {'layers': [host]}
        self.spec = {'schemaVersion': 1, 'sourceHash': digest(self.source), 'actualHash': digest(self.actual),
                     'pairs': [{**self.frozen[0], 'samples': [{'id': 'center', 'basis': 'Opaque uniform host',
                         'source': {'foreground': fg, 'background': bg},
                         'actual': {'foreground': fg, 'background': bg}}]}]}

    def run_check(self):
        self.spec['actualHash'] = digest(self.actual)
        return contrast.compare_contrast(self.source, self.actual, self.spec, self.frozen)

    def test_equal_passes_and_alpha_is_composited(self):
        result = self.run_check()
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['samples'][0]['colors']['source']['foreground'], [.7, .75, .8])

    def test_lighter_surface_regression_fails_even_if_text_elsewhere_reads(self):
        self.actual['nodes']['plate']['props']['fills'][0]['color'] = {'r': .9, 'g': .95, 'b': 1}
        self.assertEqual(self.run_check()['status'], 'fail')

    def test_improved_surface_passes(self):
        self.actual['nodes']['plate']['props']['fills'][0]['color'] = {'r': .1, 'g': .2, 'b': .3}
        self.assertEqual(self.run_check()['status'], 'pass')

    def test_missing_pair_or_sample_is_not_a_pass(self):
        self.spec['pairs'][0]['samples'] = []
        with self.assertRaises(ValueError): self.run_check()
        self.setUp(); self.frozen.append({'id': 'missing', 'kind': 'state', 'nodeIds': ['plate'],
                                          'sampleIds': ['center']})
        with self.assertRaises(ValueError): self.run_check()

    def test_stale_snapshot_rejected(self):
        self.actual['nodes']['plate']['props']['opacity'] = .25
        with self.assertRaises(ValueError):
            contrast.compare_contrast(self.source, self.actual, self.spec, self.frozen)

    def test_duplicate_alpha_and_transparent_host_rejected(self):
        fg = self.spec['pairs'][0]['samples'][0]['actual']['foreground']
        fg['layers'][1]['alphaPaths'] *= 2
        with self.assertRaises(ValueError): self.run_check()
        self.setUp(); self.actual['nodes']['host']['props']['fills'][0]['color']['a'] = .5
        with self.assertRaises(ValueError): self.run_check()

    def test_every_declared_gradient_sample_must_pass_no_averaging(self):
        second = copy.deepcopy(self.spec['pairs'][0]['samples'][0]); second['id'] = 'edge'
        self.frozen[0]['sampleIds'].append('edge'); self.spec['pairs'][0]['samples'].append(second)
        second['actual']['foreground'] = second['actual']['background']
        self.assertEqual(self.run_check()['status'], 'fail')

    def test_screenshot_hash_and_bounds_are_verified(self):
        from PIL import Image
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'sample.png'; Image.new('RGB', (2, 2), 'white').save(p)
            pixel = {'image': {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()},
                     'xy': [0, 0]}
            self.assertEqual(contrast.displayed_color(self.source, pixel, {}), [1, 1, 1])
            pixel['xy'] = [2, 0]
            with self.assertRaises(ValueError): contrast.displayed_color(self.source, pixel, {})
            pixel['xy'] = [0, 0]; pixel['image']['sha256'] = 'wrong'
            with self.assertRaises(ValueError): contrast.displayed_color(self.source, pixel, {})

    def test_known_black_white_ratio(self):
        self.assertEqual(contrast.contrast([0, 0, 0], [1, 1, 1]), 21)

    def test_non_normal_or_hidden_paint_cannot_impersonate_solid_background(self):
        self.actual['nodes']['plate']['props']['fills'][0]['blendMode'] = 'MULTIPLY'
        with self.assertRaises(ValueError): self.run_check()
        self.setUp(); self.actual['nodes']['plate']['props']['fills'][0]['visible'] = False
        with self.assertRaises(ValueError): self.run_check()

    def test_contrast_can_increase_while_emphasis_order_reverses(self):
        self.source['nodes']['weak'] = copy.deepcopy(self.source['nodes']['plate'])
        self.source['nodes']['weak']['props']['fills'][0]['color'] = {'r': .7, 'g': .8, 'b': .9}
        self.actual = copy.deepcopy(self.source)
        self.actual['nodes']['weak']['props']['fills'][0]['color'] = {'r': .1, 'g': .2, 'b': .3}
        self.spec['sourceHash'] = digest(self.source); self.spec['actualHash'] = digest(self.actual)
        weak = copy.deepcopy(self.spec['pairs'][0]); weak['id'] = 'weak-host'
        weak['nodeIds'] = ['weak', 'host']
        for key in ('source', 'actual'):
            layer = weak['samples'][0][key]['foreground']['layers'][1]
            layer['colorPath'] = layer['colorPath'].replace('plate', 'weak')
            layer['alphaPaths'] = [s.replace('plate', 'weak') for s in layer['alphaPaths']]
        self.spec['pairs'].append(weak)
        self.frozen.append({k:weak[k] for k in ('id', 'kind', 'nodeIds', 'sampleIds')})
        ordinary = self.run_check()
        self.assertEqual(ordinary['status'], 'pass')
        orders = [{'id': 'selected-over-inactive', 'strongerPairId': 'plate-host',
                   'weakerPairId': 'weak-host', 'sampleId': 'center'}]
        self.spec['emphasisOrders'] = orders
        checked = contrast.compare_contrast(self.source, self.actual, self.spec, self.frozen, orders)
        self.assertEqual(checked['status'], 'fail')
        self.assertEqual(checked['emphasisOrders'][0]['status'], 'fail')


if __name__ == '__main__':
    unittest.main()

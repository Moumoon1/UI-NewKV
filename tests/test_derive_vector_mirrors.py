from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from execution_audit import color_inventory
from derive_vector_mirrors import inspect


def fixture():
    old = {'r': .2, 'g': .3, 'b': .4}
    new = {'r': .7, 'g': .6, 'b': .5}
    source = {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
        {'id': 'root', 'parentId': None, 'children': ['icon'], 'props': {'type': 'FRAME'}},
        {'id': 'icon', 'parentId': 'root', 'children': [], 'props': {
            'type': 'VECTOR', 'fills': [{'type': 'SOLID', 'color': old}],
            'vectorNetwork': {'regions': [{'fills': [{'type': 'SOLID', 'color': old}]}]}}}]}
    manifest = {'entries': []}
    for entry in color_inventory(source)['entries']:
        manifest['entries'].append({'path': entry['path'], 'disposition': 'change', 'target': new})
    return source, manifest


class VectorMirrorChecks(unittest.TestCase):
    def test_same_node_fill_sync_requires_final_readback(self):
        source, manifest = fixture()
        result = inspect(source, manifest, {'operations': [{'property': 'fills', 'sourceId': 'icon'}]})
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['mirrorCount'], 1)
        self.assertIn('/props/fills/', result['readbackRequirements'][0]['mirrorPaintPath'])

    def test_wrong_target_or_direct_vector_setter_is_rejected(self):
        source, manifest = fixture()
        wrong = deepcopy(manifest)
        vector = next(x for x in wrong['entries'] if '/props/vectorNetwork/' in x['path'])
        vector['target'] = {'r': 1, 'g': 0, 'b': 0}
        self.assertEqual(inspect(source, wrong, {'operations': []})['status'], 'fail')
        self.assertEqual(inspect(source, manifest, {'operations': [
            {'property': 'vectorNetwork', 'sourceId': 'icon'}]})['status'], 'fail')


if __name__ == '__main__':
    unittest.main()

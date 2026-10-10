import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from preflight_instance_writes import inspect


def fixture():
    return {'rootId': 'root', 'errors': [], 'nodes': [
        {'id': 'root', 'parentId': 'page', 'props': {'type': 'FRAME'}},
        {'id': 'outer', 'parentId': 'root', 'props': {'type': 'INSTANCE'}},
        {'id': 'inner', 'parentId': 'outer', 'props': {'type': 'INSTANCE'}},
        {'id': 'icon', 'parentId': 'inner', 'props': {'type': 'VECTOR'}},
    ]}


class InstanceSetterPreflight(unittest.TestCase):
    def test_nested_vector_network_needs_all_detaches_and_mapping(self):
        plan = {'sourceRootId': 'root', 'operations': [
            {'sourceId': 'icon', 'property': 'vectorNetwork'}]}
        result = inspect(fixture(), plan)
        self.assertEqual(result['status'], 'fail')
        self.assertEqual(result['blockedSetterCount'], 1)
        self.assertEqual(result['errors'][0]['operations'][0]['missingDetaches'],
                         ['inner', 'outer'])
        plan['detachInstanceIds'] = ['outer', 'inner']
        self.assertEqual(inspect(fixture(), plan)['status'], 'fail')
        plan['postDetachMapping'] = 'structural-fingerprint'
        self.assertEqual(inspect(fixture(), plan)['status'], 'pass')

    def test_instance_fill_override_is_not_vector_data(self):
        plan = {'sourceRootId': 'root', 'operations': [
            {'sourceId': 'icon', 'property': 'fills'}]}
        self.assertEqual(inspect(fixture(), plan)['status'], 'pass')

    def test_visual_detach_needs_mapping_and_ancestor_closure(self):
        plan = {'sourceRootId': 'root', 'operations': [],
                'detachInstanceIds': ['inner']}
        result = inspect(fixture(), plan)
        self.assertEqual(result['status'], 'fail')
        self.assertIn('detach-mapping-required', [e['kind'] for e in result['errors']])
        self.assertIn('detach-ancestor-gaps', [e['kind'] for e in result['errors']])
        plan['detachInstanceIds'] = ['outer', 'inner']
        plan['postDetachMapping'] = 'structural-fingerprint'
        self.assertEqual(inspect(fixture(), plan)['status'], 'pass')

    def test_unknown_targets_and_invalid_detaches_fail(self):
        plan = {'sourceRootId': 'root', 'detachInstanceIds': ['icon'],
                'operations': [{'sourceId': 'missing', 'property': 'fills'}]}
        result = inspect(fixture(), plan)
        self.assertEqual(result['unknownTargetCount'], 1)
        self.assertEqual(result['invalidDetachCount'], 1)
        self.assertEqual(result['status'], 'fail')

    def test_empty_binding_key_does_not_justify_vector_write(self):
        source = fixture()
        source['nodes'][-1]['props']['vectorNetwork'] = {
            'regions': [{'fills': [{'color': {'r': 1, 'g': 0, 'b': 0},
                                    'boundVariables': {}}]}]}
        plan = {'sourceRootId': 'root', 'operations': [
            {'sourceId': 'icon', 'property': 'vectorNetwork', 'targets': [-1]}]}
        result = inspect(source, plan)
        self.assertEqual(result['redundantSetterCount'], 1)
        self.assertEqual(result['blockedSetterCount'], 0)
        self.assertEqual(result['status'], 'fail')


if __name__ == '__main__':
    unittest.main()

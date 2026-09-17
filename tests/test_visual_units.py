import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import execution_audit as execution
import theme_audit as audit


def fixture():
    rows = [{'id': 'page', 'parentId': None, 'children': ['tab-a', 'tab-b', 'button'],
             'props': {'type': 'FRAME', 'opacity': 1}}]
    for tab in ('tab-a', 'tab-b'):
        rows.append({'id': tab, 'parentId': 'page', 'children': [tab + '-inner'],
                     'props': {'type': 'VECTOR', 'fills': [{'type': 'SOLID',
                         'color': {'r': 1, 'g': 1, 'b': 1}}]}})
        rows.append({'id': tab + '-inner', 'parentId': tab, 'children': [],
                     'props': {'type': 'FRAME', 'fills': [{'type': 'SOLID',
                         'color': {'r': 1, 'g': 1, 'b': 1}}]}})
    rows.append({'id': 'button', 'parentId': 'page', 'children': [],
                 'props': {'type': 'FRAME', 'fills': [{'type': 'SOLID',
                     'color': {'r': .2, 'g': .3, 'b': .4}}]}})
    source = {'schemaVersion': 1, 'collectorVersion': 1, 'rootId': 'page',
              'capturedAt': '2026-01-01T00:00:00Z', 'errors': [], 'nodes': rows}
    entries = execution.color_inventory(source)['entries']
    manifest = {'schemaVersion': 1, 'sourceHash': audit.digest(audit.snapshot_document(source)),
                'entries': [{**e, 'role': 'surface', 'disposition': 'preserve',
                             'reason': 'Original fixture', 'ruleId': 'clarity'} for e in entries]}
    registry = {'schemaVersion': 1, 'sourceHash': manifest['sourceHash'], 'units': []}
    for name in ('tab-a', 'tab-b', 'button'):
        paths = [e['path'] for e in entries if e['nodeId'] in (name, name + '-inner')]
        registry['units'].append({'id': name, 'basis': 'Source contour and visible continuous surface',
                                  'carrierPaths': paths,
                                  'dependencyNodeIds': [name] + ([name + '-inner'] if name != 'button' else []),
                                  'reviewNodeIds': [name], 'reviewRuleIds': ['clarity', 'hierarchy']})
    relations = {'schemaVersion': 1, 'groups': [{'id': 'continuous-equivalents',
                  'paths': [e['path'] for e in entries if e['nodeId'] != 'button'],
                  'reason': 'Continuous surfaces in equivalent tab instances'}]}
    frozen = {'pairs': [{'id': 'tab-internal', 'kind': 'surface',
                        'nodeIds': ['tab-a', 'tab-a-inner'], 'sampleIds': ['stable']}],
              'emphasisOrders': []}
    return source, manifest, registry, relations, frozen


class VisualUnitChecks(unittest.TestCase):
    def test_missing_inner_surface_fails_even_with_complete_color_manifest(self):
        source, manifest, registry, _, _ = fixture()
        registry['units'][0]['carrierPaths'].pop()
        self.assertEqual(execution.coverage(source, manifest)['status'], 'pass')
        result = execution.visual_units(source, manifest, registry)
        self.assertEqual(result['status'], 'fail')
        self.assertIn('/nodes/tab-a-inner/props/fills/0/color', result['missingCarrierPaths'])

    def test_duplicate_carrier_and_missing_dependency_rejected(self):
        source, manifest, registry, _, _ = fixture()
        bad = copy.deepcopy(registry)
        bad['units'][1]['carrierPaths'].append(bad['units'][0]['carrierPaths'][0])
        with self.assertRaises(ValueError): execution.visual_units(source, manifest, bad)
        bad = copy.deepcopy(registry); bad['units'][0]['dependencyNodeIds'].pop()
        with self.assertRaises(ValueError): execution.visual_units(source, manifest, bad)

    def test_local_change_rechecks_complete_equivalent_tabs_without_unrelated_button(self):
        source, manifest, registry, relations, frozen = fixture()
        result = execution.affected_units(source, manifest, registry, relations, frozen,
            {'changedPaths': ['/nodes/tab-a-inner/props/fills']})
        self.assertEqual(result['affectedUnitIds'], ['tab-a', 'tab-b'])
        self.assertEqual(result['colorRelationIds'], ['continuous-equivalents'])
        self.assertEqual(result['contrastPairIds'], ['tab-internal'])
        self.assertIn('tab-b-inner', result['dependencyNodeIds'])
        self.assertNotIn('button', result['dependencyNodeIds'])

    def test_ancestor_change_invalidates_all_dependent_units(self):
        source, manifest, registry, relations, frozen = fixture()
        result = execution.affected_units(source, manifest, registry, relations, frozen,
                                         {'changedPaths': ['/nodes/page/props/opacity']})
        self.assertEqual(result['affectedUnitIds'], ['button', 'tab-a', 'tab-b'])

    def test_order_edge_expands_closure_transitively(self):
        source, manifest, registry, _, frozen = fixture()
        frozen['pairs'].append({'id': 'button-host', 'kind': 'button',
                                'nodeIds': ['button'], 'sampleIds': ['stable']})
        frozen['emphasisOrders'] = [{'id': 'operation-order', 'strongerPairId': 'button-host',
                                    'weakerPairId': 'tab-internal', 'sampleId': 'stable'}]
        result = execution.affected_units(source, manifest, registry,
            {'schemaVersion': 1, 'groups': []}, frozen,
            {'changedPaths': ['/nodes/tab-a-inner/props/fills/0/color/r']})
        self.assertEqual(result['affectedUnitIds'], ['button', 'tab-a'])
        self.assertEqual(result['emphasisOrderIds'], ['operation-order'])

    def test_scope_and_source_cannot_be_redeclared_to_hide_failure(self):
        source, manifest, registry, _, _ = fixture()
        rules = {name: {'kind': 'visual', 'applicable': True, 'scopeNodeIds': ['button']}
                 for name in ('clarity', 'hierarchy')}
        with self.assertRaises(ValueError): execution.visual_units(source, manifest, registry, rules)
        source['nodes'][1]['props']['fills'][0]['color']['r'] = .5
        with self.assertRaises(ValueError): execution.visual_units(source, manifest, registry)


if __name__ == '__main__':
    unittest.main()

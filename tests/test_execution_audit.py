import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import execution_audit as execution
import theme_audit as audit


def snapshot():
    return {'schemaVersion': 1, 'collectorVersion': 1, 'rootId': 'page',
            'capturedAt': '2026-01-01T00:00:00Z', 'errors': [], 'nodes': [
        {'id': 'page', 'parentId': None, 'children': ['icon'], 'props': {'type': 'FRAME'}},
        {'id': 'icon', 'parentId': 'page', 'children': [], 'props': {'type': 'VECTOR',
         'fills': [{'type': 'SOLID', 'color': {'r': .2, 'g': .3, 'b': .4}}],
         'vectorNetwork': {'regions': [{'fills': [{'type': 'GRADIENT_LINEAR',
             'gradientStops': [{'position': 0, 'color': {'r': .1, 'g': .2, 'b': .3, 'a': 0}},
                               {'position': 1, 'color': {'r': .4, 'g': .5, 'b': .6, 'a': 1}}]}]}]}}}]}


def manifest(source):
    inv = execution.color_inventory(source)
    return {'schemaVersion': 1, 'sourceHash': inv['sourceHash'], 'entries': [
        {**entry, 'role': 'icon.glyph', 'reason': 'Fixture preserved structure', 'ruleId': 'material-layers',
         'disposition': 'preserve'} for entry in inv['entries']]}


class CoverageChecks(unittest.TestCase):
    def test_vector_region_gradient_stop_is_not_silently_missed(self):
        source = snapshot(); plan = manifest(source)
        self.assertEqual(len(plan['entries']), 3)
        plan['entries'].pop()
        result = execution.coverage(source, plan)
        self.assertEqual(result['status'], 'fail')
        self.assertIn('gradientStops/1/color', result['missingPaths'][0])

    def test_visible_channel_cannot_be_ignored_and_inactive_can(self):
        source = snapshot(); plan = manifest(source)
        plan['entries'][0]['disposition'] = 'ignore'
        self.assertEqual(execution.coverage(source, plan)['status'], 'fail')
        plan['entries'][0]['disposition'] = 'preserve'
        plan['entries'][1]['disposition'] = 'ignore'
        self.assertEqual(execution.coverage(source, plan)['status'], 'pass')

    def test_changed_source_duplicate_and_missing_semantics_rejected(self):
        source = snapshot(); plan = manifest(source)
        bad = copy.deepcopy(plan); bad['entries'].append(bad['entries'][0])
        with self.assertRaises(ValueError): execution.coverage(source, bad)
        source['nodes'][1]['props']['fills'][0]['color']['r'] = .9
        with self.assertRaises(ValueError): execution.coverage(source, plan)
        source = snapshot(); plan['entries'][0]['reason'] = ''
        self.assertEqual(execution.coverage(source, plan)['status'], 'fail')

    def test_unchanged_actual_passes_difference_guard_but_fails_completion(self):
        source = snapshot(); plan = manifest(source)
        path = plan['entries'][0]['path']
        target = {'r': .8, 'g': .3, 'b': .4}
        plan['entries'][0].update(disposition='change', target=target, recipeId='rose', sceneId='task')
        policy = {'schemaVersion': 1, 'protectedPaths': [], 'allowedChanges': [
            {'path': path + '/r', 'before': .2, 'after': .8}]}
        self.assertEqual(audit.compare(source, source, policy)['status'], 'pass')
        self.assertEqual(execution.complete(source, source, plan, policy)['status'], 'fail')
        actual = copy.deepcopy(source); actual['nodes'][1]['props']['fills'][0]['color'] = target
        self.assertEqual(execution.complete(source, actual, plan, policy)['status'], 'pass')

    def test_protected_and_unplanned_target_fail(self):
        source = snapshot(); plan = manifest(source)
        plan['entries'][0].update(disposition='change', target={'r': .8, 'g': .3, 'b': .4},
                                  recipeId='rose', sceneId='task')
        policy = {'schemaVersion': 1, 'protectedPaths': [plan['entries'][0]['path']], 'allowedChanges': []}
        self.assertEqual(execution.complete(source, source, plan, policy)['status'], 'fail')

    def test_non_color_planned_write_also_must_complete(self):
        source = snapshot(); plan = manifest(source)
        policy = {'schemaVersion': 1, 'protectedPaths': [], 'allowedChanges': [
            {'path': '/nodes/page/props/x', 'before': audit.MISSING, 'after': 500}]}
        self.assertEqual(execution.complete(source, source, plan, policy)['status'], 'fail')

    def test_hsv_lock_preserves_original_stop_saturation_value_and_alpha(self):
        source = audit.snapshot_document(snapshot())
        actual = copy.deepcopy(source)
        path = '/nodes/icon/props/fills/0/color'
        rule = {'verifier': {'type': 'preserve-hsv', 'paths': [path], 'channels': ['s', 'v', 'a']}}
        # Rotate RGB components: same HSV S/V, different hue.
        actual['nodes']['icon']['props']['fills'][0]['color'] = {'r': .4, 'g': .2, 'b': .3}
        self.assertEqual(execution.verify_rule(source, actual, rule)['status'], 'pass')
        actual['nodes']['icon']['props']['fills'][0]['color']['r'] = .5
        self.assertEqual(execution.verify_rule(source, actual, rule)['status'], 'fail')
        rule['verifier']['type'] = 'preserve-values'
        self.assertEqual(execution.verify_rule(source, actual, rule)['status'], 'fail')
        rule['verifier'] = {'type': 'target-values', 'targets': [{'path': path + '/r', 'expected': .5}]}
        self.assertEqual(execution.verify_rule(source, actual, rule)['status'], 'pass')

    def test_batching_preserves_all_operations_and_rejects_overlap_or_oversize(self):
        ops = [{'path': '/nodes/n' + str(i) + '/props/fills', 'before': [], 'after': []} for i in range(130)]
        result = execution.batch_plan({'batchId': 'expand', 'operations': ops})
        self.assertEqual(len(result['batches']), 3)
        self.assertEqual([op for b in result['batches'] for op in b['operations']], ops)
        with self.assertRaises(ValueError): execution.batch_plan({'operations': ops + [ops[0]]})
        op = {'path': '/nodes/n/props/fills', 'before': [], 'after': ['x' * 2000]}
        with self.assertRaises(ValueError): execution.batch_plan({'operations': [op]}, max_bytes=1024)

    def test_finalizer_recomputes_checks_and_rejects_missing_visual_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            source = snapshot(); plan = manifest(source)
            ledger = {'schemaVersion': 1, 'rules': [
                {'id': name, 'kind': 'machine', 'applicable': True, 'source': 'Fixture', 'acceptance': name}
                for name in sorted(execution.MACHINE_RULES)] + [
                {'id': name, 'kind': 'visual', 'applicable': True, 'scopeNodeIds': ['page', 'icon'],
                 'source': 'Fixture', 'acceptance': name} for name in sorted(execution.VISUAL_RULES)]}
            relationships = [{'id': 'icon-host', 'kind': 'icon', 'nodeIds': ['icon'], 'sampleIds': ['solid']}]
            next(r for r in ledger['rules'] if r['id'] == 'contrast-baseline')['verifier'] = {
                'type': 'contrast-baseline', 'relationships': relationships}
            color_relations = {'schemaVersion': 1, 'groups': []}
            next(r for r in ledger['rules'] if r['id'] == 'color-relations')['verifier'] = {
                'type': 'color-relations', 'groupsHash': audit.digest(color_relations),
                'emptyEvidence': 'Fixture has one carrier; the three stored colors differ.'}
            registry = {'schemaVersion': 1, 'sourceHash': audit.digest(audit.snapshot_document(source)),
                        'units': [{'id': 'icon-unit', 'basis': 'Complete vector fixture and actual host',
                                   'carrierPaths': [e['path'] for e in plan['entries']],
                                   'dependencyNodeIds': ['icon', 'page'], 'reviewNodeIds': ['icon'],
                                   'reviewRuleIds': ['clarity', 'hierarchy']}]}
            next(r for r in ledger['rules'] if r['id'] == 'visual-unit-coverage')['verifier'] = {
                'type': 'visual-unit-coverage', 'registryHash': audit.digest(registry)}
            solid = {'layers': [{'colorPath': '/nodes/icon/props/fills/0/color'}]}
            doc = audit.snapshot_document(source)
            samples = {'schemaVersion': 1, 'sourceHash': audit.digest(doc), 'actualHash': audit.digest(doc),
                       'pairs': [{**relationships[0], 'samples': [{'id': 'solid', 'basis': 'Synthetic host fixture',
                           'source': {'foreground': solid, 'background': solid},
                           'actual': {'foreground': solid, 'background': solid}}]}]}
            plan['ruleLedgerHash'] = audit.digest(ledger)
            for entry in plan['entries']:
                entry['ruleId'] = 'material-layers'
            values = {'sourceBefore': source, 'sourceNow': source, 'cloneNow': source, 'manifest': plan,
                      'policy': {'schemaVersion': 1, 'allowedChanges': [], 'protectedPaths': []},
                      'ruleLedger': ledger, 'contrastSamples': samples, 'colorRelations': color_relations,
                      'visualUnits': registry}
            spec = {'visualScenes': []}
            for key, value in values.items():
                path = p / (key + '.json'); audit.save_json(path, value); spec[key] = str(path)
            result = execution.finalize(spec)
            self.assertEqual(result['status'], 'fail')
            self.assertTrue(result['missingVisualRules'])
            from PIL import Image
            image = p / 'scene.png'; Image.new('RGB', (10, 10), 'white').save(image)
            scene_spec = {'sceneId': 'whole-page', 'reviewScope': 'whole-page', 'dependencyNodeIds': ['page'],
                          'recipe': {'ruleLedgerHash': audit.digest(ledger)}, 'nodeMap': {'page': 'page'},
                          'protectedPaths': [], 'writePaths': [plan['entries'][0]['path']],
                          'reviewRequirements': [{'id': r['id'], 'nodeIds': r['scopeNodeIds'],
                                                  'acceptance': r['acceptance']}
                                                 for r in ledger['rules'] if r['kind'] == 'visual']}
            state = audit.scene_state(source, scene_spec)
            review = {'sceneId': 'whole-page', 'status': 'pass', 'notes': 'Fixture only',
                      'reviewedAt': '2026-01-01T00:00:01Z', 'screenshots': [str(image)],
                      'checks': [{'id': r['id'], 'status': 'pass', 'nodeIds': r['nodeIds'],
                                  'observation': 'Fixture observation', 'comparison': 'Fixture comparison',
                                  'screenshots': [str(image)]} for r in scene_spec['reviewRequirements']]}
            gate = audit.seal_gate(state, review)
            for name, value in (('scene', scene_spec), ('gate', gate)):
                audit.save_json(p / (name + '.json'), value)
            spec['visualScenes'] = [{'spec': str(p / 'scene.json'), 'gate': str(p / 'gate.json')}]
            actual = copy.deepcopy(source); actual['capturedAt'] = '2026-01-01T00:00:02Z'
            audit.save_json(spec['cloneNow'], actual)
            self.assertEqual(execution.finalize(spec)['status'], 'pass')
            missing_contrast = dict(spec); missing_contrast.pop('contrastSamples')
            with self.assertRaises(ValueError): execution.finalize(missing_contrast)
            missing_relations = dict(spec); missing_relations.pop('colorRelations')
            with self.assertRaises(ValueError): execution.finalize(missing_relations)
            missing_units = dict(spec); missing_units.pop('visualUnits')
            with self.assertRaises(ValueError): execution.finalize(missing_units)
            bad_registry = copy.deepcopy(registry)
            bad_registry['units'][0]['carrierPaths'].pop()
            audit.save_json(spec['visualUnits'], bad_registry)
            with self.assertRaises(ValueError): execution.finalize(spec)
            audit.save_json(spec['visualUnits'], registry)
            # Every rule has complete aggregate coverage, but no single scene
            # reviews the unit's clarity and hierarchy together.
            split_scenes = []
            for index, limited_rule in enumerate(('clarity', 'hierarchy')):
                partial = copy.deepcopy(scene_spec)
                partial['sceneId'] = 'split-' + str(index)
                next(r for r in partial['reviewRequirements'] if r['id'] == limited_rule)['nodeIds'] = ['page']
                partial_review = copy.deepcopy(review)
                partial_review['sceneId'] = partial['sceneId']
                next(c for c in partial_review['checks'] if c['id'] == limited_rule)['nodeIds'] = ['page']
                partial_gate = audit.seal_gate(audit.scene_state(source, partial), partial_review)
                scene_path = p / ('split-scene-' + str(index) + '.json')
                gate_path = p / ('split-gate-' + str(index) + '.json')
                audit.save_json(scene_path, partial); audit.save_json(gate_path, partial_gate)
                split_scenes.append({'spec': str(scene_path), 'gate': str(gate_path)})
            split_result = execution.finalize({**spec, 'visualScenes': split_scenes})
            self.assertEqual(split_result['missingVisualRules'], [])
            self.assertEqual(split_result['uncoveredVisualNodes'], {})
            self.assertEqual(split_result['status'], 'fail')
            self.assertEqual(split_result['unreviewedVisualUnits'], ['icon-unit'])
            family_scenes = []
            for index, node in enumerate(('page', 'icon')):
                partial = copy.deepcopy(scene_spec)
                partial['sceneId'] = 'family-' + str(index)
                next(r for r in partial['reviewRequirements']
                     if r['id'] == 'control-family-consistency')['nodeIds'] = [node]
                partial_review = copy.deepcopy(review)
                partial_review['sceneId'] = partial['sceneId']
                next(c for c in partial_review['checks']
                     if c['id'] == 'control-family-consistency')['nodeIds'] = [node]
                gate = audit.seal_gate(audit.scene_state(source, partial), partial_review)
                scene_path = p / ('family-scene-' + str(index) + '.json')
                gate_path = p / ('family-gate-' + str(index) + '.json')
                audit.save_json(scene_path, partial); audit.save_json(gate_path, gate)
                family_scenes.append({'spec': str(scene_path), 'gate': str(gate_path)})
            family_result = execution.finalize({**spec, 'visualScenes': family_scenes})
            self.assertEqual(family_result['uncoveredVisualNodes'], {})
            self.assertEqual(family_result['unreviewedVisualUnits'], [])
            self.assertEqual(family_result['status'], 'fail')
            self.assertTrue(any('control-family' in e['error'] for e in family_result['errors']))
            scene_spec['reviewRequirements'][0]['nodeIds'] = ['page']
            state = audit.scene_state(source, scene_spec)
            review['checks'][0]['nodeIds'] = ['page']
            gate = audit.seal_gate(state, review)
            audit.save_json(p / 'scene.json', scene_spec); audit.save_json(p / 'gate.json', gate)
            self.assertEqual(execution.finalize(spec)['status'], 'fail')
            ledger['rules'].pop()
            audit.save_json(spec['ruleLedger'], ledger)
            with self.assertRaises(ValueError): execution.finalize(spec)


if __name__ == '__main__':
    unittest.main()

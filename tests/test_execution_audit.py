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


class ColorBindingAuditChecks(unittest.TestCase):
    def test_catches_paint_gradient_effect_and_text_style_bindings(self):
        source = snapshot()
        icon = source['nodes'][1]['props']
        icon['fillStyleId'] = 'S:old'
        icon['fills'][0]['boundVariables'] = {'color': {'type': 'VARIABLE_ALIAS', 'id': 'V:old'}}
        icon['vectorNetwork']['regions'][0]['fills'][0]['gradientStops'][1]['boundVariables'] = {
            'color': {'type': 'VARIABLE_ALIAS', 'id': 'V:gradient'}}
        icon['effects'] = [{'type': 'DROP_SHADOW', 'color': {'r': .1, 'g': .2, 'b': .3, 'a': 1},
                            'boundVariables': {'color': {'type': 'VARIABLE_ALIAS', 'id': 'V:shadow'}}}]
        icon['boundVariables'] = {'fills': [{'type': 'VARIABLE_ALIAS', 'id': 'V:old'}],
                                  'itemSpacing': {'type': 'VARIABLE_ALIAS', 'id': 'V:space'}}
        source['nodes'].append({'id': 'label', 'parentId': 'page', 'children': [], 'props': {
            'type': 'TEXT', 'textRuns': {'fillStyleId': [{'start': 0, 'end': 2, 'value': 'S:text'}]}}})
        source['nodes'][0]['children'].append('label')
        result = execution.color_binding_audit(source)
        self.assertEqual(result['status'], 'fail')
        self.assertGreaterEqual(result['residualCount'], 5)
        self.assertFalse(any('itemSpacing' in entry['path'] for entry in result['residualBindings']))

    def test_passes_when_only_noncolor_binding_remains(self):
        source = snapshot()
        source['nodes'][1]['props']['boundVariables'] = {
            'itemSpacing': {'type': 'VARIABLE_ALIAS', 'id': 'V:space'}}
        self.assertEqual(execution.color_binding_audit(source)['status'], 'pass')


class DisplayedContinuityChecks(unittest.TestCase):
    def test_multiple_rules_share_evidence_without_skipping_failed_or_missing_group(self):
        import hashlib
        from PIL import Image
        source = audit.snapshot_document(snapshot())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'native.png'
            image = Image.new('RGB', (2, 1), (128, 128, 128))
            image.putpixel((1, 0), (160, 160, 160)); image.save(path)
            ref = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            values = [{'image': ref, 'xy': xy} for xy in [[0, 0], [1, 0]]]
            rules = {name: {'id': name, 'kind': 'machine', 'applicable': True,
                     'verifier': {'type': 'displayed-relations', 'groups': [
                         {'id': name, 'nodeIds': ['icon'], 'xy': [[0, 0], [1, 0]],
                          'nativePixels': [2, 1], 'maximumChannelDelta': limit}]}}
                     for name, limit in [('wide', 32), ('strict', 1)]}
            evidence = {'sourceHash': audit.digest(source), 'actualHash': audit.digest(source),
                        'groups': [{'id': name, 'source': values, 'actual': values} for name in rules]}
            results = execution.verify_all_displayed_relations(source, source, rules, evidence)
            self.assertEqual(results['wide']['status'], 'pass')
            self.assertEqual(results['strict']['status'], 'fail')
            for groups in [evidence['groups'][:1], evidence['groups'] + evidence['groups'][:1],
                           evidence['groups'] + [{'id': 'undeclared'}]]:
                with self.assertRaises(ValueError):
                    execution.verify_all_displayed_relations(source, source, rules, {**evidence, 'groups': groups})

    def test_lightness_and_color_family_catches_same_hue_but_wrong_weight(self):
        import hashlib
        from PIL import Image
        source = audit.snapshot_document(snapshot())
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            def image_samples(name, colors):
                image = Image.new('RGB', (2, 1)); image.putdata(colors); image.save(p / name)
                ref = {'path': str(p / name), 'sha256': hashlib.sha256((p / name).read_bytes()).hexdigest()}
                return [{'image': ref, 'xy': point} for point in [[0, 0], [1, 0]]]
            group = {'id': 'buttons', 'relationType': 'appearance-family', 'nodeIds': ['icon'],
                     'xy': [[0, 0], [1, 0]], 'nativePixels': [2, 1],
                     'basis': 'Equivalent source button body regions; keep comparable material weight.',
                     'additionalLightnessSpread': 2, 'additionalColorSpreadDeltaE76': 3}
            rule = {'verifier': {'groups': [group]}}
            evidence = {'sourceHash': audit.digest(source), 'actualHash': audit.digest(source),
                        'groups': [{'id': 'buttons', 'source': image_samples('source.png', [(177, 219, 255), (180, 220, 255)]),
                                    'actual': image_samples('actual.png', [(135, 88, 45), (201, 149, 74)])}]}
            result = execution.verify_displayed_relations(source, source, rule, evidence)
            self.assertEqual(result['status'], 'fail')
            self.assertGreater(result['groups'][0]['actual']['lightnessSpread'], result['groups'][0]['limits']['lightnessSpread'])
            # Near-identical dark bodies on a new light page remain valid: absolute
            # source L* is not frozen across the dark-to-light transition.
            evidence['groups'][0]['actual'] = image_samples('actual.png', [(135, 88, 45), (137, 89, 46)])
            self.assertEqual(execution.verify_displayed_relations(source, source, rule, evidence)['status'], 'pass')
            group['additionalLightnessSpread'] = float('inf')
            with self.assertRaises(ValueError): execution.verify_displayed_relations(source, source, rule, evidence)

    def test_equal_gray_but_different_colors_fail_the_family(self):
        import hashlib
        from PIL import Image
        source = audit.snapshot_document(snapshot())
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            values = {}
            for name, colors in [('source', [(128, 128, 128)] * 2),
                                 ('actual', [(38, 128, 204), (153, 102, 51)])]:
                path = p / (name + '.png')
                im = Image.new('RGB', (2, 1)); im.putdata(colors); im.save(path)
                image = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                values[name] = [{'image': image, 'xy': xy} for xy in [[0, 0], [1, 0]]]
            rule = {'verifier': {'groups': [{'id': 'same-gray', 'relationType': 'appearance-family',
                     'basis': 'Comparable main bodies must share both lightness and color family.',
                     'nodeIds': ['icon'], 'xy': [[0, 0], [1, 0]], 'nativePixels': [2, 1],
                     'additionalLightnessSpread': 5, 'additionalColorSpreadDeltaE76': 3}]}}
            evidence = {'sourceHash': audit.digest(source), 'actualHash': audit.digest(source),
                        'groups': [{'id': 'same-gray', **values}]}
            result = execution.verify_displayed_relations(source, source, rule, evidence)
            self.assertLess(result['groups'][0]['actual']['lightnessSpread'], 5)
            self.assertEqual(result['status'], 'fail')

    def test_native_pixels_catch_different_composition_and_require_fresh_binding(self):
        import hashlib
        from PIL import Image
        source = audit.snapshot_document(snapshot())
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            before = Image.new('RGB', (2, 1), (46, 49, 97)); before.save(p / 'source.png')
            actual = Image.new('RGB', (2, 1), (225, 198, 149)); actual.putpixel((1, 0), (234, 225, 202)); actual.save(p / 'actual.png')
            rule = {'verifier': {'groups': [{'id': 'tab-body', 'nodeIds': ['icon'],
                    'xy': [[0, 0], [1, 0]], 'maximumChannelDelta': 1, 'nativePixels': [2, 1]}]}}
            def samples(name):
                image = {'path': str(p / name), 'sha256': hashlib.sha256((p / name).read_bytes()).hexdigest()}
                return [{'image': image, 'xy': point} for point in [[0, 0], [1, 0]]]
            evidence = {'sourceHash': audit.digest(source), 'actualHash': audit.digest(source),
                        'groups': [{'id': 'tab-body', 'source': samples('source.png'), 'actual': samples('actual.png')}]}
            self.assertEqual(execution.verify_displayed_relations(source, source, rule, evidence)['status'], 'fail')
            actual.putpixel((1, 0), (225, 198, 149)); actual.save(p / 'actual.png')
            evidence['groups'][0]['actual'] = samples('actual.png')
            self.assertEqual(execution.verify_displayed_relations(source, source, rule, evidence)['status'], 'pass')
            evidence['actualHash'] = 'stale'
            with self.assertRaises(ValueError): execution.verify_displayed_relations(source, source, rule, evidence)

    def test_continuity_compares_all_points_not_only_the_first_point(self):
        import hashlib
        from PIL import Image
        source = audit.snapshot_document(snapshot())
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'sample.png'
            image = Image.new('RGB', (3, 1)); image.putdata([(100, 100, 100), (101, 100, 100), (99, 100, 100)]); image.save(p)
            ref = {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            points = [[0, 0], [1, 0], [2, 0]]
            values = [{'image': ref, 'xy': point} for point in points]
            rule = {'verifier': {'groups': [{'id': 'joined', 'nodeIds': ['icon'], 'xy': points,
                                            'nativePixels': [3, 1], 'maximumChannelDelta': 1}]}}
            evidence = {'sourceHash': audit.digest(source), 'actualHash': audit.digest(source),
                        'groups': [{'id': 'joined', 'source': values, 'actual': values}]}
            self.assertEqual(execution.verify_displayed_relations(source, source, rule, evidence)['status'], 'fail')


class InteractionRequirementsChecks(unittest.TestCase):
    def fixture(self):
        source = snapshot(); plan = manifest(source)
        plan['entries'][0]['role'] = 'button.material'
        plan['entries'][1]['role'] = 'cta.base'
        plan['entries'][2]['role'] = 'cta.material'
        anchor = {'r': .5, 'g': .6, 'b': .7}
        plan['schemeAnchorContract'] = {'button': anchor}
        for index in (0, 1):
            plan['entries'][index]['disposition'] = 'change'
            plan['entries'][index]['recipeId'] = 'button-primary'
            plan['entries'][index]['sceneId'] = 'buttons'
            plan['entries'][index]['anchorId'] = 'button'
            plan['entries'][index]['target'] = anchor
        return source, plan

    def test_tab_only_visual_scope_and_missing_numeric_relation_fail(self):
        source, plan = self.fixture()
        rules = {'control-family-consistency': {'kind': 'visual', 'applicable': True, 'scopeNodeIds': []}}
        result = execution.interaction_requirements(source, plan, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('omitted' in e['error'] for e in result['errors']))
        self.assertTrue(any('mandatory' in e['error'] for e in result['errors']))

    def test_separate_button_and_cta_groups_cannot_self_certify(self):
        source, plan = self.fixture()
        paths = [e['path'] for e in plan['entries']]
        rules = {'control-family-consistency': {'kind': 'visual', 'applicable': True, 'scopeNodeIds': ['page']},
                 'button-appearance-family': {'kind': 'machine', 'applicable': True,
                    'verifier': {'type': 'displayed-relations', 'groups': [
                        {'relationType': 'appearance-family', 'carrierPaths': [paths[0]]},
                        {'relationType': 'appearance-family', 'carrierPaths': paths[1:]}]}}}
        self.assertEqual(execution.interaction_requirements(source, plan, rules)['status'], 'fail')
        rules['button-appearance-family']['verifier']['groups'] = [
            {'relationType': 'appearance-family', 'carrierPaths': paths, 'nodeIds': ['page']}]
        self.assertEqual(execution.interaction_requirements(source, plan, rules)['status'], 'pass')
        rules['control-family-consistency']['applicable'] = False
        self.assertEqual(execution.interaction_requirements(source, plan, rules)['status'], 'fail')
        rules['control-family-consistency']['applicable'] = True
        rules['button-appearance-family']['verifier']['groups'][0]['carrierPaths'].pop()
        self.assertEqual(execution.interaction_requirements(source, plan, rules)['status'], 'fail')

    def test_split_button_anchor_or_missing_cta_anchor_fails(self):
        source, plan = self.fixture()
        paths = [e['path'] for e in plan['entries']]
        rules = {'control-family-consistency': {'kind': 'visual', 'applicable': True,
                                                'scopeNodeIds': ['page']},
                 'button-appearance-family': {'kind': 'machine', 'applicable': True,
                    'verifier': {'type': 'displayed-relations', 'groups': [
                        {'relationType': 'appearance-family', 'carrierPaths': paths,
                         'nodeIds': ['page']}]}}}
        plan['entries'][1]['target'] = {'r': .9, 'g': .6, 'b': .1}
        result = execution.interaction_requirements(source, plan, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('differs' in e['error'] for e in result['errors']))
        plan['entries'][1]['target'] = plan['schemeAnchorContract']['button']
        plan['entries'][1].pop('anchorId')
        result = execution.interaction_requirements(source, plan, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('anchor channels' in e['error'] for e in result['errors']))


class SchemeAnchorRequirementsChecks(unittest.TestCase):
    def fixture(self):
        plan = manifest(snapshot())
        names = ('background', 'card', 'number', 'icon', 'button', 'tab')
        plan['schemeAnchorContract'] = {}
        entries = []
        for index, name in enumerate(names):
            value = {'r': (index + 1) / 10, 'g': .5, 'b': .9}
            plan['schemeAnchorContract'][name] = value
            entry = copy.deepcopy(plan['entries'][0])
            entry.update(anchorId=name, disposition='change', target=value,
                         recipeId='anchor-' + name, sceneId='anchors')
            entries.append(entry)
        plan['entries'] = entries
        return plan

    def test_all_six_exact_anchor_targets_pass(self):
        result = execution.scheme_anchor_requirements(self.fixture())
        self.assertEqual(result['status'], 'pass')

    def test_tab_cannot_drift_to_button_or_disappear(self):
        plan = self.fixture()
        tab = next(e for e in plan['entries'] if e['anchorId'] == 'tab')
        tab['target'] = plan['schemeAnchorContract']['button']
        result = execution.scheme_anchor_requirements(plan)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any(e.get('anchorId') == 'tab' for e in result['errors']))
        plan = self.fixture()
        plan['entries'] = [e for e in plan['entries'] if e['anchorId'] != 'tab']
        self.assertEqual(execution.scheme_anchor_requirements(plan)['status'], 'fail')


class CoverageChecks(unittest.TestCase):
    def test_vector_region_gradient_stop_is_not_silently_missed(self):
        source = snapshot(); plan = manifest(source)
        self.assertEqual(len(plan['entries']), 3)
        plan['entries'].pop()
        result = execution.coverage(source, plan)
        self.assertEqual(result['status'], 'fail')
        self.assertIn('gradientStops/1/color', result['missingPaths'][0])

    def test_transparent_stop_of_active_gradient_cannot_be_ignored(self):
        source = snapshot(); plan = manifest(source)
        plan['entries'][0]['disposition'] = 'ignore'
        self.assertEqual(execution.coverage(source, plan)['status'], 'fail')
        plan['entries'][0]['disposition'] = 'preserve'
        plan['entries'][1]['disposition'] = 'ignore'
        self.assertEqual(execution.coverage(source, plan)['status'], 'fail')
        self.assertFalse(execution.color_inventory(source)['entries'][1]['inactive'])

    def test_hidden_or_fully_transparent_gradient_remains_inactive(self):
        for mode in ('hidden', 'all-transparent'):
            source = snapshot()
            gradient = source['nodes'][1]['props']['vectorNetwork']['regions'][0]['fills'][0]
            if mode == 'hidden': gradient['visible'] = False
            else: gradient['gradientStops'][1]['color']['a'] = 0
            plan = manifest(source); plan['entries'][1]['disposition'] = 'ignore'
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
            # Finalize must use the frozen contextual policy and still require visual gates.
            verifier = next(r for r in ledger['rules'] if r['id'] == 'contrast-baseline')['verifier']
            context = {'sourceUiMode': 'dark', 'targetUiMode': 'light', 'adaptationMode': 'color-only',
                       'reason': 'Pale host requires a contextual role comparison.'}
            verifier.update(policy='contextual', decisionContext=context)
            samples.update(policy='contextual', decisionContext=context)
            plan['ruleLedgerHash'] = audit.digest(ledger)
            for key, value in [('ruleLedger', ledger), ('contrastSamples', samples), ('manifest', plan)]:
                audit.save_json(spec[key], value)
            contextual = execution.finalize(spec)
            self.assertEqual(contextual['machineChecks']['contrast-baseline']['policy'], 'contextual')
            self.assertEqual(contextual['machineChecks']['contrast-baseline']['samples'][0]['status'], 'measured')
            self.assertEqual(contextual['status'], 'fail')
            for value in (verifier, samples):
                value.pop('policy'); value.pop('decisionContext')
            plan['ruleLedgerHash'] = audit.digest(ledger)
            for key, value in [('ruleLedger', ledger), ('contrastSamples', samples), ('manifest', plan)]:
                audit.save_json(spec[key], value)
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

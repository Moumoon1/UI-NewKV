from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from derive_text_range_plan import build
from execution_audit import color_inventory, text_range_requirements


def fixture():
    white = {'r': 1, 'g': 1, 'b': 1}
    source = {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
        {'id': 'root', 'parentId': None, 'children': ['label'], 'props': {
            'type': 'FRAME', 'visible': True,
            'fills': [{'type': 'SOLID', 'visible': True, 'opacity': 1, 'color': white}]}},
        {'id': 'label', 'parentId': 'root', 'children': [], 'props': {
            'type': 'TEXT', 'visible': True, 'characters': 'AB',
            'textRuns': {'fills': [{'start': 0, 'end': 1, 'value': [
                {'type': 'SOLID', 'color': white}]},
                {'start': 1, 'end': 2, 'value': [{'type': 'SOLID', 'color': white}]}]}}}]}
    inventory = color_inventory(source)
    manifest = {'themeTransition': 'dark-to-light', 'entries': [
        {'path': item['path'], 'disposition': 'change', 'role': 'text.primary'}
        for item in inventory['entries']]}
    return source, manifest


class TextRangeDerivationTests(unittest.TestCase):
    def test_all_ranges_get_exact_channels_hosts_and_contrast_pairs(self):
        source, manifest = fixture()
        plan, pairs = build(source, manifest)
        self.assertEqual(len(plan['entries']), 1)
        self.assertEqual(len(plan['entries'][0]['ranges']), 2)
        self.assertEqual(len(pairs), 2)
        manifest['textRangePlan'] = plan
        rules = {'readability': {'scopeNodeIds': ['label']}}
        result = text_range_requirements(source, manifest, pairs, rules)
        self.assertEqual(result['status'], 'pass')

    def test_missing_painted_host_fails_closed(self):
        source, manifest = fixture()
        source['nodes'][0]['props']['fills'] = []
        with self.assertRaises(ValueError):
            build(source, manifest)

    def test_hidden_paint_in_visible_range_keeps_path_without_mixed_action(self):
        source, manifest = fixture()
        source['nodes'][1]['props']['textRuns']['fills'][0]['value'].insert(0, {
            'type': 'SOLID', 'visible': False, 'opacity': 1,
            'color': {'r': .8, 'g': .1, 'b': .1}})
        manifest['entries'] = [{'path': item['path'],
                                'disposition': 'ignore' if item['inactive'] else 'change',
                                'role': 'inactive-stored' if item['inactive'] else 'text.primary'}
                               for item in color_inventory(source)['entries']]
        plan, pairs = build(source, manifest)
        self.assertEqual(len(plan['entries'][0]['ranges'][0]['channelPaths']), 2)
        manifest['textRangePlan'] = plan
        rules = {'readability': {'scopeNodeIds': ['label']}}
        self.assertEqual(text_range_requirements(source, manifest, pairs, rules)['status'], 'pass')

    def test_planned_hidden_text_has_no_rendered_contrast_pair(self):
        source, manifest = fixture()
        plan, pairs = build(source, manifest, hidden_root_ids=['label'])
        self.assertEqual(plan['entries'], [])
        self.assertEqual(pairs, [])
        manifest['textRangePlan'] = plan
        projected = {'schemaVersion': 1, 'rootId': 'root', 'errors': [],
                     'nodes': [dict(row, props=dict(row['props'])) for row in source['nodes']]}
        projected['nodes'][1]['props']['opacity'] = 0
        rules = {'readability': {'scopeNodeIds': []}}
        self.assertEqual(text_range_requirements(source, manifest, pairs, rules,
                                                 projected)['status'], 'pass')
        projected['nodes'][1]['props']['opacity'] = 1
        self.assertEqual(text_range_requirements(source, manifest, pairs, rules,
                                                 projected)['status'], 'fail')

    def test_zero_alpha_text_needs_no_visible_range_or_hide_operation(self):
        source, manifest = fixture()
        for run in source['nodes'][1]['props']['textRuns']['fills']:
            run['value'][0]['opacity'] = 0
        manifest['entries'] = [{
            'path': item['path'],
            'disposition': 'ignore' if item['inactive'] else 'change',
            'role': 'inactive-stored' if item['inactive'] else 'surface.page',
        } for item in color_inventory(source)['entries']]
        plan, pairs = build(source, manifest)
        self.assertEqual(plan['entries'], [])
        self.assertEqual(pairs, [])
        manifest['textRangePlan'] = plan
        self.assertEqual(text_range_requirements(
            source, manifest, pairs, {'readability': {'scopeNodeIds': []}},
            source)['status'], 'pass')

    def test_exact_half_opacity_disabled_button_is_measured_not_forced_to_three(self):
        source, manifest = fixture()
        source['nodes'][0]['children'] = ['button']
        source['nodes'][1]['parentId'] = 'button'
        source['nodes'].insert(1, {'id': 'button', 'parentId': 'root',
            'children': ['label'], 'props': {'type': 'INSTANCE', 'visible': True,
                'opacity': .5, 'fills': [{'type': 'SOLID', 'visible': True,
                    'opacity': 1, 'color': {'r': .3, 'g': .2, 'b': .1}}]}})
        manifest['entries'] = [{'path': item['path'], 'disposition': 'change',
                                'role': 'text.primary'}
                               for item in color_inventory(source)['entries']]
        plan, pairs = build(source, manifest, [], ['button'])
        self.assertTrue(all(pair['minimumContrast'] is None for pair in pairs))
        manifest['textRangePlan'] = plan
        rules = {'readability': {'scopeNodeIds': ['label']}}
        self.assertEqual(text_range_requirements(source, manifest, pairs, rules)['status'], 'pass')
        broken = [dict(pair, disabledStateRootId='root') for pair in pairs]
        self.assertEqual(text_range_requirements(source, manifest, broken, rules)['status'], 'fail')


if __name__ == '__main__':
    unittest.main()

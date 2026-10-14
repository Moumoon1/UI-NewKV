from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import control_role_preflight as gate


def solid(hex_color):
    return {'type': 'SOLID', 'color': {
        key: int(hex_color[index:index + 2], 16) / 255
        for key, index in (('r', 1), ('g', 3), ('b', 5))}}


def node(parent, children, kind='FRAME', color=None, **props):
    result = {'type': kind, 'visible': True, 'opacity': 1, **props}
    if color:
        result['fills'] = [solid(color)]
    return {'parentId': parent, 'children': children, 'props': result}


class ControlRolePreflightTests(unittest.TestCase):
    def documents(self):
        source = {'nodes': {
            'page': node(None, ['card'], color='#091027'),
            'card': node('page', ['iconUnit', 'tab'], color='#1E214F'),
            'iconUnit': node('card', ['container', 'glyph'], x=0, y=0, width=48, height=48),
            'container': node('iconUnit', [], 'RECTANGLE', '#1C0E59',
                              x=0, y=0, width=48, height=48, opacity=.5),
            'glyph': node('iconUnit', [], 'VECTOR', '#C1C2FF',
                          x=12, y=11, width=24, height=27),
            'tab': node('card', ['tabText'], color='#A4ACEA',
                        x=0, y=50, width=87, height=29),
            'tabText': node('tab', [], 'TEXT', '#102449',
                            x=31, y=6, width=24, height=17),
        }}
        target = {'nodes': {key: {'parentId': value['parentId'],
                                  'children': list(value['children']),
                                  'props': dict(value['props'])}
                            for key, value in source['nodes'].items()}}
        target['nodes']['card']['props']['fills'] = [solid('#286A59')]
        target['nodes']['container']['props']['fills'] = [solid('#835120')]
        target['nodes']['tab']['props']['fills'] = [solid('#4C8D70')]
        target['nodes']['tabText']['props']['fills'] = [solid('#163D2E')]
        return source, target

    def manifest(self, container_role='button.edge'):
        return {'iconGlyphPlan': {'roots': [{'rootNodeId': 'glyph'}]},
                'entries': [{'nodeId': 'container', 'role': container_role,
                             'disposition': 'change'},
                            {'nodeId': 'tab', 'role': 'interaction.tab.selected',
                             'disposition': 'change'}]}

    def test_rejects_button_recipe_on_icon_container(self):
        source, target = self.documents()
        result = gate.inspect(source, target, self.manifest())
        self.assertEqual(result['status'], 'fail')
        self.assertIn('icon-container-role', [issue['kind'] for issue in result['issues']])
        self.assertEqual(result['iconContainers'][0]['containerId'], 'container')

    def test_rejects_selected_tab_and_label_contrast_regression(self):
        source, target = self.documents()
        result = gate.inspect(source, target, self.manifest('icon.container.base'))
        kinds = [issue['kind'] for issue in result['issues']]
        self.assertIn('selected-tab-boundary-regression', kinds)
        self.assertIn('selected-tab-label-regression', kinds)
        self.assertGreater(result['selectedTabs'][0]['sourceBoundaryContrast'],
                           result['selectedTabs'][0]['targetBoundaryContrast'])

    def test_contextual_policy_reports_ratios_without_source_baseline_failure(self):
        source, target = self.documents()
        result = gate.inspect(source, target, self.manifest('icon.container.base'), 'contextual')
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(len(result['selectedTabs']), 1)

    def test_hidden_sibling_is_not_invented_as_visible_container(self):
        source, target = self.documents()
        source['nodes']['container']['props']['visible'] = False
        target['nodes']['container']['props']['visible'] = False
        result = gate.inspect(source, target, self.manifest(), 'contextual')
        self.assertEqual(result['iconContainers'], [])
        self.assertEqual(result['status'], 'pass')

    def test_real_icon_button_requires_explicit_host_evidence(self):
        source, target = self.documents()
        manifest = self.manifest()
        manifest['iconGlyphPlan']['roots'][0]['hostKind'] = 'button'
        self.assertEqual(gate.inspect(source, target, manifest, 'contextual')['status'], 'fail')
        manifest['iconGlyphPlan']['roots'][0]['buttonHostReason'] = 'The carrier itself is the recorded button body.'
        self.assertEqual(gate.inspect(source, target, manifest, 'contextual')['status'], 'pass')


if __name__ == '__main__':
    unittest.main()

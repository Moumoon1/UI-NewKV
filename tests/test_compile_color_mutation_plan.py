from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compile_color_mutation_plan import build
from execution_audit import color_binding_audit, color_inventory
from generate_theme_apply_js import build as build_writer
from theme_audit import digest, snapshot_document


class CompileColorMutationPlanTests(unittest.TestCase):
    def source(self):
        old = {'r': .2, 'g': .1, 'b': .05}
        white = {'r': 1, 'g': 1, 'b': 1}
        return {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
            {'id': 'root', 'parentId': None, 'children': ['label'],
             'props': {'type': 'FRAME', 'name': 'Page', 'width': 414,
                       'fillStyleId': 'S:old',
                       'boundVariables': {'fills': [{'id': 'V:old'}]},
                       'fills': [{'type': 'SOLID', 'visible': True, 'opacity': 1,
                                  'color': old,
                                  'boundVariables': {'color': {'id': 'V:old'}}}]}},
            {'id': 'label', 'parentId': 'root', 'children': [],
             'props': {'type': 'TEXT', 'name': 'Title', 'characters': 'Hi',
                       'fillStyleId': 'S:old',
                       'fills': [{'type': 'SOLID', 'visible': True,
                                  'opacity': 1, 'color': white,
                                  'boundVariables': {}}],
                       'textRuns': {'fills': [{'start': 0, 'end': 2,
                           'value': [{'type': 'SOLID', 'visible': True,
                                      'opacity': .6, 'color': white,
                                      'boundVariables': {}}]}],
                           'fillStyleId': [{'start': 0, 'end': 2, 'value': 'S:old'}]}}},
        ]}

    def kv(self):
        return {'schemaVersion': 1, 'rootId': 'kv', 'errors': [], 'nodes': [
            {'id': 'kv', 'parentId': None, 'children': [],
             'props': {'type': 'FRAME', 'name': 'New KV', 'width': 414}}]}

    def manifest(self, source):
        inventory = color_inventory(source)
        entries = []
        for item in inventory['entries']:
            entries.append({'path': item['path'], 'nodeId': item['nodeId'],
                            'role': 'reviewed-role', 'disposition': 'change',
                            'reason': 'Reviewed in native source.', 'ruleId': 'test',
                            'recipeId': 'test/role', 'sceneId': 'whole-page',
                            'target': {**item['source'], 'r': .6, 'g': .5, 'b': .4}})
        return {'schemaVersion': 1, 'sourceHash': inventory['sourceHash'],
                'entries': entries}

    def options(self, source):
        return {'schemaVersion': 1, 'sourceHash': digest(snapshot_document(source)),
                'kvSourceId': 'kv', 'schemeId': 'test-light',
                'sourceFingerprint': 'frozen-fingerprint'}

    def test_compiles_exact_paint_and_range_ops_and_clears_bindings(self):
        source = self.source()
        manifest = self.manifest(source)
        result = build(source, self.kv(), manifest, self.options(source))
        kinds = [op['kind'] for op in result['writePlan']['operations']]
        self.assertEqual(kinds.count('property'), 2)
        self.assertEqual(kinds.count('text-range'), 1)
        self.assertEqual(color_binding_audit(result['expectedClone'])['status'], 'pass')
        self.assertTrue(all(change['path'].startswith('/nodes/')
                            for change in result['policy']['allowedChanges']))
        self.assertEqual(result['nodeMap'], {'root': 'root', 'label': 'label'})
        self.assertIn('async function applyThemeWriteToClone',
                      build_writer(source, manifest, result['writePlan'], self.kv()))

    def test_explicit_alpha_exceptions_are_projected_not_invented(self):
        source = self.source()
        options = self.options(source)
        options['opacityOps'] = [{'sourceId': 'root', 'property': 'fills',
                                  'paintIndex': 0, 'before': 1, 'after': .2,
                                  'reason': 'Reviewed subtle inner surface.'}]
        options['textPaintAlphaOps'] = [{'sourceId': 'label', 'start': 0, 'end': 2,
                                        'paintIndex': 0, 'before': .6, 'after': 1,
                                        'reason': 'Reviewed readable title.'}]
        result = build(source, self.kv(), self.manifest(source), options)
        rows = {row['id']: row for row in result['expectedClone']['nodes']}
        self.assertEqual(rows['root']['props']['fills'][0]['opacity'], .2)
        self.assertEqual(rows['label']['props']['textRuns']['fills'][0]['value'][0]['opacity'], 1)
        self.assertEqual(result['summary']['opacityOps'], 1)
        self.assertEqual(result['summary']['textPaintAlphaOps'], 1)
        build_writer(source, self.manifest(source), result['writePlan'], self.kv())

    def test_node_opacity_derives_exact_child_path_for_writer(self):
        source = self.source()
        options = self.options(source)
        options['opacityOps'] = [{'sourceId': 'label', 'property': 'opacity',
                                  'before': 1, 'after': 0,
                                  'reason': 'Reviewed old image suppression.'}]
        result = build(source, self.kv(), self.manifest(source), options)
        self.assertEqual(result['writePlan']['opacityOps'][0]['path'], [0])
        self.assertEqual(next(row for row in result['expectedClone']['nodes']
                              if row['id'] == 'label')['props']['opacity'], 0)
        writer = build_writer(source, self.manifest(source), result['writePlan'], self.kv())
        self.assertLess(writer.index('clone.appendChild(kv)'), writer.index('for(const [p,prop,changes,clearStyle,alpha] of D.setters)'))
        self.assertLess(writer.index('kv.locked=true'), writer.index('for(const [p,prop,changes,clearStyle,alpha] of D.setters)'))
        self.assertGreater(writer.index('clone.insertChild(1,kv)'), writer.index('for(const [p,value] of D.opacity)'))

        options['opacityOps'][0]['path'] = [1]
        with self.assertRaisesRegex(ValueError, 'opacity source path mismatch'):
            build(source, self.kv(), self.manifest(source), options)

    def test_missing_manifest_and_stale_options_fail_closed(self):
        source = self.source()
        manifest = self.manifest(source)
        manifest['entries'].pop()
        with self.assertRaises(ValueError):
            build(source, self.kv(), manifest, self.options(source))
        manifest = self.manifest(source)
        options = self.options(source)
        options['sourceHash'] = 'old'
        with self.assertRaises(ValueError):
            build(source, self.kv(), manifest, options)

    def test_opacity_needs_exact_before_and_reason(self):
        source = self.source()
        options = self.options(source)
        options['opacityOps'] = [{'sourceId': 'root', 'property': 'fills',
                                  'paintIndex': 0, 'before': .5, 'after': .2,
                                  'reason': 'Reviewed.'}]
        with self.assertRaises(ValueError):
            build(source, self.kv(), self.manifest(source), options)
        options['opacityOps'][0]['before'] = 1
        options['opacityOps'][0]['reason'] = ''
        with self.assertRaises(ValueError):
            build(source, self.kv(), self.manifest(source), options)

    def test_manifest_cannot_change_color_alpha_without_writer(self):
        source = self.source()
        manifest = self.manifest(source)
        manifest['entries'][0]['target']['a'] = .5
        with self.assertRaises(ValueError):
            build(source, self.kv(), manifest, self.options(source))




class SourcePathOrderTests(unittest.TestCase):
    def test_valid_shuffled_rows_keep_the_same_structural_paths(self):
        from compile_color_mutation_plan import _path_map
        source = {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
            {'id': 'leaf', 'parentId': 'parent', 'children': [], 'props': {'type': 'VECTOR'}},
            {'id': 'parent', 'parentId': 'root', 'children': ['leaf'], 'props': {'type': 'FRAME'}},
            {'id': 'root', 'parentId': None, 'children': ['parent'], 'props': {'type': 'FRAME'}}]}
        self.assertEqual(_path_map(source), {'root': [], 'parent': [0], 'leaf': [0, 0]})


if __name__ == '__main__':
    unittest.main()

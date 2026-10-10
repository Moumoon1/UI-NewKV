import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import execution_audit as audit
import preflight_full
from theme_audit import digest


class PreflightFullTests(unittest.TestCase):
    def test_static_stage_never_claims_full_pass(self):
        result = preflight_full.run({'sourceBefore': '/tmp/nonexistent.json'}, 'static')
        self.assertEqual(result['status'], 'fail')
        self.assertNotIn('contrastSamples', result['missingInputs'])

    def test_missing_inputs_never_become_pass(self):
        result = preflight_full.run({'sourceBefore': '/tmp/nonexistent.json'})
        self.assertEqual(result['status'], 'fail')
        self.assertIn('writePlan', result['missingInputs'])

    def test_channel_coverage_alone_cannot_authorize_write(self):
        source = {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
            {'id': 'root', 'parentId': None, 'children': ['icon', 'label'],
             'props': {'type': 'FRAME', 'visible': True}},
            {'id': 'icon', 'parentId': 'root', 'children': [], 'props': {
                'type': 'VECTOR', 'visible': True, 'fills': [{'type': 'GRADIENT_LINEAR',
                    'gradientStops': [
                        {'position': 0, 'color': {'r': .2, 'g': .3, 'b': .4, 'a': 1}},
                        {'position': 1, 'color': {'r': .8, 'g': .9, 'b': 1, 'a': 1}}]}]}},
            {'id': 'label', 'parentId': 'root', 'children': [], 'props': {
                'type': 'TEXT', 'visible': True, 'characters': 'Hi',
                'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}],
                'textRuns': {'fills': [{'start': 0, 'end': 2, 'value': [
                    {'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}]}]}}}]}
        inventory = audit.color_inventory(source)
        manifest = {'schemaVersion': 1, 'sourceHash': inventory['sourceHash'],
                    'themeTransition': 'dark-to-light', 'entries': [
                        {'path': row['path'], 'role': 'icon.glyph', 'reason': 'Test baseline',
                         'ruleId': 'icon-clarity', 'disposition': 'preserve'}
                        for row in inventory['entries']]}
        self.assertEqual(audit.coverage(source, manifest)['status'], 'pass')
        ledger = {'schemaVersion': 1, 'rules': [
            {'id': name, 'kind': 'machine' if name in audit.MACHINE_RULES else 'visual',
             'applicable': True, 'scopeNodeIds': ['icon']}
            for name in sorted(audit.MACHINE_RULES | audit.VISUAL_RULES)]}
        manifest['ruleLedgerHash'] = digest(ledger)
        inputs = {'sourceBefore': source, 'expectedClone': source, 'manifest': manifest,
                  'writePlan': {'sourceRootId': 'root', 'operations': []},
                  'policy': {'schemaVersion': 1, 'allowedChanges': [], 'protectedPaths': []},
                  'ruleLedger': ledger, 'visualUnits': {}, 'colorRelations': {'groups': []},
                  'contrastSamples': {}, 'materialRelations': {'schemaVersion': 1, 'relations': []},
                  'nodeMap': {}}
        with tempfile.TemporaryDirectory() as temp:
            paths = {}
            for name, value in inputs.items():
                path = Path(temp) / (name + '.json')
                path.write_text(json.dumps(value))
                paths[name] = str(path)
            result = preflight_full.run(paths)
        self.assertEqual(result['status'], 'fail')
        self.assertEqual(result['checks']['frozen-contract']['status'], 'fail')
        self.assertIn('icon-glyph-coverage', result['failedChecks'])
        self.assertIn('cross-mode-composite-coverage', result['failedChecks'])
        self.assertIn('frozen-contract', result['failedChecks'])
        self.assertIn('text-range-coverage', result['failedChecks'])
        self.assertIn('interaction-entry-coverage', result['failedChecks'])


if __name__ == '__main__':
    unittest.main()

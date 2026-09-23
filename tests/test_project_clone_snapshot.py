import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from project_clone_snapshot import project
from snapshot_fingerprint import row_fingerprint


class ProjectCloneSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.before = {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
            {'id': 'root', 'parentId': 'page', 'children': ['card', 'title'], 'props': {'type': 'FRAME'}},
            {'id': 'card', 'parentId': 'root', 'children': [], 'props': {'type': 'FRAME', 'fills': [
                {'type': 'SOLID', 'color': {'r': 1, 'g': 0, 'b': 0}}]}},
            {'id': 'title', 'parentId': 'root', 'children': [], 'props': {'type': 'TEXT', 'fills': [
                {'type': 'SOLID', 'color': {'r': 1, 'g': 0, 'b': 0}}], 'textRuns': {'fills': [
                {'start': 0, 'end': 4, 'value': [{'type': 'SOLID', 'color': {'r': 1, 'g': 0, 'b': 0}}]}]}}}
        ]}

    def test_project_exact_paint_and_text_diffs_without_touching_input(self):
        fills = self.before['nodes'][1]['props']['fills']
        after = copy.deepcopy(fills)
        after[0]['color']['b'] = 1
        text_before = self.before['nodes'][2]['props']['textRuns']['fills'][0]['value']
        text_after = copy.deepcopy(text_before)
        text_after[0]['color']['g'] = 1
        plan = {'schemaVersion': 1, 'operations': [
            {'cloneId': 'card', 'property': 'fills', 'beforeHash': row_fingerprint(fills),
             'afterHash': row_fingerprint(after), 'changes': [{'path': '/0/color/b', 'value': 1}]},
            {'cloneId': 'title', 'property': 'textRuns', 'runs': [
                {'start': 0, 'end': 4, 'beforeHash': row_fingerprint(text_before), 'value': text_after}]}
        ]}
        projected, count = project(self.before, [plan])
        self.assertEqual(count, 2)
        self.assertEqual(projected['nodes'][1]['props']['fills'], after)
        self.assertEqual(projected['nodes'][2]['props']['fills'], text_after)
        self.assertEqual(self.before['nodes'][1]['props']['fills'][0]['color']['b'], 0)

    def test_stale_before_hash_rejected(self):
        plan = {'schemaVersion': 1, 'operations': [
            {'cloneId': 'card', 'property': 'fills', 'beforeHash': 'wrong', 'afterHash': 'other',
             'changes': [{'path': '/0/color/b', 'value': 1}]}
        ]}
        with self.assertRaisesRegex(ValueError, 'before hash conflict'):
            project(self.before, [plan])

    def test_mixed_text_before_requires_full_readback(self):
        self.before['nodes'][2]['props']['textRuns']['fills'] = [
            {'start': 0, 'end': 2, 'value': [{'color': {'r': 1, 'g': 0, 'b': 0}}]},
            {'start': 2, 'end': 4, 'value': [{'color': {'r': 0, 'g': 1, 'b': 0}}]}
        ]
        plan = {'schemaVersion': 1, 'operations': [
            {'cloneId': 'title', 'property': 'textRuns', 'runs': [
                {'start': 0, 'end': 4, 'beforeHash': 'unknown', 'value': []}]}
        ]}
        with self.assertRaisesRegex(ValueError, 'mixed before fills'):
            project(self.before, [plan])


if __name__ == '__main__':
    unittest.main()

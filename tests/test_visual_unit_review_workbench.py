from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from visual_unit_review_workbench import build, _html, _review_queue


class VisualUnitReviewWorkbenchTests(unittest.TestCase):
    def source(self):
        paint = lambda rgb: [{'type': 'SOLID', 'color': dict(zip('rgb', rgb))}]
        return {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
            {'id': 'root', 'parentId': None, 'children': ['card'],
             'props': {'type': 'FRAME', 'name': 'Root', 'visible': True,
                       'width': 414, 'height': 800}},
            {'id': 'card', 'parentId': 'root', 'children': ['label-a', 'label-b'],
             'props': {'type': 'FRAME', 'name': 'Card', 'visible': True,
                       'x': 20, 'y': 100, 'width': 374, 'height': 250,
                       'fills': paint((1, 1, 1))}},
            {'id': 'label-a', 'parentId': 'card', 'children': [],
             'props': {'type': 'TEXT', 'name': 'Button', 'characters': '去发布',
                       'visible': True, 'x': 10, 'y': 20, 'width': 50, 'height': 20,
                       'fills': paint((.3, .2, .1))}},
            {'id': 'label-b', 'parentId': 'card', 'children': [],
             'props': {'type': 'TEXT', 'name': 'Data', 'characters': '199',
                       'visible': True, 'x': 10, 'y': 70, 'width': 50, 'height': 20,
                       'fills': paint((.3, .2, .1))}},
        ]}

    def test_groups_by_visual_unit_and_exact_kind_without_assigning_semantics(self):
        report = build(self.source(), unit_depth=1)
        self.assertEqual(report['status'], 'review-workbench-only')
        self.assertEqual(report['pendingChannels'], 3)
        text_group = next(u for u in report['units'] if u['nodeType'] == 'TEXT')
        self.assertEqual(text_group['pendingCount'], 2)
        self.assertEqual(text_group['bounds'], [20, 100, 374, 250])
        self.assertEqual(len(text_group['candidateRule']['matchedPaths']), 2)
        self.assertNotIn('role', text_group['candidateRule'])
        self.assertEqual({n['text'] for n in text_group['nodes']}, {'去发布', '199'})
        queue = _review_queue(report)
        self.assertIn('3 条', queue)
        self.assertIn('Card', queue)
        self.assertIn('去发布', queue)
        self.assertIn('不能仅凭此摘要复制哈希', queue)

    def test_partial_overlap_disables_candidate_rule(self):
        full = build(self.source(), unit_depth=1)
        text_group = next(u for u in full['units'] if u['nodeType'] == 'TEXT')
        one = [text_group['pendingPaths'][0]]
        partial = build(self.source(), unresolved_paths=one, unit_depth=1)
        group = partial['units'][0]
        self.assertIsNone(group['candidateRule'])
        self.assertEqual(len(group['overlapWithReviewed']), 1)

    def test_adaptive_split_reaches_small_review_units(self):
        report = build(self.source(), max_unit_channels=1)
        self.assertEqual(report['maxUnitChannels'], 1)
        self.assertEqual(report['pendingChannels'], 3)
        self.assertEqual({u['unitId'] for u in report['units']},
                         {'card', 'label-a', 'label-b'})
        self.assertTrue(all(u['pendingCount'] == 1 for u in report['units']))
        with self.assertRaises(ValueError):
            build(self.source(), max_unit_channels=0)

    def test_cross_kind_merge_is_opt_in_and_requires_review(self):
        source = self.source()
        source['nodes'][2]['props']['textRuns'] = {'fills': [
            {'start': 0, 'end': 3, 'value': [{'type': 'SOLID',
             'color': {'r': .3, 'g': .2, 'b': .1}}]}]}
        separate = build(source, unit_depth=1)
        merged = build(source, unit_depth=1, merge_channel_kinds=True)
        self.assertGreater(len(separate['units']), len(merged['units']))
        pair = next(u for u in merged['units'] if u['nodeType'] == 'TEXT')
        self.assertEqual(pair['channelKinds'], ['fill-or-other', 'styled-text'])
        self.assertTrue(pair['crossKind'])
        self.assertNotIn('channelKind', pair['candidateRule']['selector'])
        self.assertEqual(pair['pendingCount'], 3)

    def test_rejects_stale_path_and_escapes_figma_names_in_html(self):
        with self.assertRaises(ValueError):
            build(self.source(), unresolved_paths=['/not-in-source'])
        source = self.source()
        source['nodes'][1]['props']['name'] = '</script><script>alert(1)</script>'
        html = _html(build(source))
        self.assertNotIn('</script><script>alert(1)', html)
        self.assertIn('\\u003c/script>', html)
        self.assertIn("n.paths.join('\\n')", html)


if __name__ == '__main__':
    unittest.main()

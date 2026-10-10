from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from source_channel_triage import build


class SourceChannelTriageTests(unittest.TestCase):
    def source(self):
        return {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
            {'id': 'root', 'parentId': None, 'children': ['card'],
             'props': {'type': 'FRAME', 'name': 'Page', 'visible': True}},
            {'id': 'card', 'parentId': 'root', 'children': ['title', 'hidden'],
             'props': {'type': 'FRAME', 'name': 'Card', 'visible': True,
                       'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}]}},
            {'id': 'title', 'parentId': 'card', 'children': [],
             'props': {'type': 'TEXT', 'name': 'Heading', 'characters': 'Visible title',
                       'visible': True, 'fills': [{'type': 'SOLID',
                       'color': {'r': 0, 'g': 0, 'b': 0}}]}},
            {'id': 'hidden', 'parentId': 'card', 'children': [],
             'props': {'type': 'RECTANGLE', 'name': 'Old overlay', 'visible': False,
                       'fills': [{'type': 'SOLID',
                       'color': {'r': 1, 'g': 0, 'b': 0}}]}},
        ]}

    def test_indexes_exact_active_paths_without_claiming_roles(self):
        report = build(self.source(), 1)
        self.assertEqual(report['activeChannels'], 2)
        self.assertEqual(report['inactiveChannels'], 1)
        self.assertEqual(report['nodesNeedingClassification'], 2)
        self.assertEqual(report['status'], 'review-index-only')
        title = next(row for row in report['nodes'] if row['nodeId'] == 'title')
        self.assertEqual(title['regionId'], 'card')
        self.assertEqual(title['textPreview'], 'Visible title')
        self.assertEqual(title['activeChannelPaths'], ['/nodes/title/props/fills/0/color'])
        self.assertTrue(title['needsSemanticClassification'])

    def test_region_depth_changes_index_not_coverage(self):
        shallow = build(self.source(), 1)
        deep = build(self.source(), 2)
        self.assertEqual(shallow['activeChannels'], deep['activeChannels'])
        self.assertEqual(shallow['regions'][0]['id'], 'card')
        self.assertEqual({row['regionId'] for row in deep['nodes']}, {'card', 'title'})
        with self.assertRaises(ValueError):
            build(self.source(), -1)

    def test_mixed_fill_marker_does_not_break_review_index(self):
        source = self.source()
        source['nodes'][2]['props']['fills'] = 'MIXED'
        report = build(source, 1)
        self.assertEqual(report['activeChannels'], 1)
        self.assertEqual(report['nodesNeedingClassification'], 1)


if __name__ == '__main__':
    unittest.main()

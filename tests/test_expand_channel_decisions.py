from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from execution_audit import color_inventory
from expand_channel_decisions import build, paths_hash


class ExpandChannelDecisionsTests(unittest.TestCase):
    def source(self):
        return {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': [
            {'id': 'root', 'parentId': None, 'children': ['card'],
             'props': {'type': 'FRAME', 'name': 'Page', 'visible': True}},
            {'id': 'card', 'parentId': 'root', 'children': ['button', 'icon', 'hidden'],
             'props': {'type': 'FRAME', 'name': 'Card', 'visible': True,
                       'fills': [{'type': 'SOLID', 'color': {'r': .2, 'g': .1, 'b': .1}}]}},
            {'id': 'button', 'parentId': 'card', 'children': ['label'],
             'props': {'type': 'FRAME', 'name': 'smallButton', 'visible': True,
                       'fills': [{'type': 'SOLID', 'color': {'r': .8, 'g': .3, 'b': .1}}]}},
            {'id': 'label', 'parentId': 'button', 'children': [],
             'props': {'type': 'TEXT', 'name': '去发布', 'characters': '去发布',
                       'visible': True, 'fontSize': 16,
                       'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}],
                       'textRuns': {'fills': [{'start': 0, 'end': 3, 'value': [
                           {'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}]}]}}},
            {'id': 'icon', 'parentId': 'card', 'children': [],
             'props': {'type': 'VECTOR', 'name': 'Coin', 'visible': True,
                       'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': .7, 'b': .2}}]}},
            {'id': 'hidden', 'parentId': 'card', 'children': [],
             'props': {'type': 'VECTOR', 'name': 'Old', 'visible': False,
                       'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': 0, 'b': 0}}]}},
        ]}

    def decisions(self, source, rules):
        return {'schemaVersion': 1, 'sourceHash': color_inventory(source)['sourceHash'],
                'rules': rules}

    def rule(self, rule_id, selector, role, target='#FFF9EA', **extra):
        return {'id': rule_id, 'selector': selector, 'role': role,
                'disposition': 'change', 'reason': 'Reviewed against native source.',
                'ruleId': 'test-rule', 'recipeId': 'test/' + role,
                'sceneId': 'whole-page-1x', 'target': target, **extra}

    def test_unresolved_remains_needs_review_not_fake_pass(self):
        source = self.source()
        report = build(source, self.decisions(source, []))
        self.assertEqual(report['status'], 'needs-review')
        self.assertEqual(len(report['unresolvedPaths']), 5)
        self.assertEqual(report['manifestDraft']['entries'][-1]['disposition'], 'ignore')
        self.assertEqual(report['coverage']['status'], 'fail')
        self.assertTrue(report['suggestedGroups'])
        self.assertEqual(sum(group['matchedCount'] for group in report['suggestedGroups']), 5)

    def test_exact_rules_expand_to_complete_manifest_and_review_lists(self):
        source = self.source()
        paths = {row['path'] for row in color_inventory(source)['entries'] if not row['inactive']}
        rules = [self.rule(str(index), {'path': path}, 'test-color', '#D5B47A')
                 for index, path in enumerate(sorted(paths))]
        report = build(source, self.decisions(source, rules))
        self.assertEqual(report['status'], 'ready-for-semantic-review')
        self.assertEqual(report['coverage']['status'], 'pass')
        self.assertEqual(len(report['textRangeReview']), 1)
        self.assertEqual(len(report['textRangeReview'][0]['runs']), 1)
        self.assertEqual(len(report['iconAndSurfaceReview']), 1)

    def test_broad_rule_requires_exact_match_hash(self):
        source = self.source()
        rules = [self.rule('body', {'nodeType': 'TEXT'}, 'text')]
        report = build(source, self.decisions(source, rules))
        self.assertEqual(report['status'], 'needs-review')
        self.assertEqual(report['ruleMatches'][0]['matchedCount'], 2)
        self.assertIn('matched path set not reviewed', report['invalidRules'][0]['error'])
        rules[0]['reviewedPathsHash'] = paths_hash(report['ruleMatches'][0]['matchedPaths'])
        refreshed = build(source, self.decisions(source, rules))
        self.assertFalse(refreshed['invalidRules'])

    def test_anchor_id_is_projected_for_reviewed_exact_or_grouped_rule(self):
        source = self.source()
        paths = [row['path'] for row in color_inventory(source)['entries']
                 if not row['inactive']]
        exact = self.rule('card-anchor', {'path': paths[0]}, 'card',
                          '#FFF9EA', anchorId='card')
        report = build(source, self.decisions(source, [exact]))
        self.assertFalse(report['invalidRules'])
        self.assertEqual(next(entry for entry in report['manifestDraft']['entries']
                              if entry['path'] == paths[0])['anchorId'], 'card')
        broad = self.rule('broad-anchor', {'nodeType': 'TEXT'}, 'text',
                          '#FFF9EA', anchorId='card')
        report = build(source, self.decisions(source, [broad]))
        self.assertTrue(any('matched path set not reviewed' in error['error']
                            for error in report['invalidRules']))
        broad['reviewedPathsHash'] = paths_hash(report['ruleMatches'][0]['matchedPaths'])
        report = build(source, self.decisions(source, [broad]))
        self.assertFalse(report['invalidRules'])
        self.assertEqual(sum(entry.get('anchorId') == 'card'
                             for entry in report['manifestDraft']['entries']), 2)

    def test_overlaps_need_explicit_exact_path_override(self):
        source = self.source()
        all_paths = [row['path'] for row in color_inventory(source)['entries']
                     if not row['inactive'] and row['nodeId'] in ('button', 'label')]
        broad = self.rule('button-all', {'subtreeId': 'button'}, 'button',
                          reviewedPathsHash=paths_hash(all_paths))
        label_path = next(p for p in all_paths if '/textRuns/' in p)
        exact = self.rule('label', {'path': label_path}, 'on-button')
        report = build(source, self.decisions(source, [broad, exact]))
        self.assertEqual(len(report['conflicts']), 1)
        exact['overrides'] = ['button-all']
        report = build(source, self.decisions(source, [broad, exact]))
        self.assertFalse(report['conflicts'])

    def test_broad_protection_of_editable_action_is_review_risk(self):
        source = self.source()
        paths = [row['path'] for row in color_inventory(source)['entries']
                 if not row['inactive'] and row['nodeId'] in ('button', 'label')]
        rule = {'id': 'protected-card', 'selector': {'subtreeId': 'button'},
                'role': 'protected-marketing-banner', 'disposition': 'preserve',
                'reason': 'Review needed.', 'ruleId': 'test-protection',
                'reviewedPathsHash': paths_hash(paths)}
        report = build(source, self.decisions(source, [rule]))
        self.assertEqual(report['status'], 'needs-review')
        self.assertTrue(report['protectionRisks'])

    def test_exact_protected_channel_has_no_broad_scope_risk(self):
        source = self.source()
        path = next(row['path'] for row in color_inventory(source)['entries']
                    if not row['inactive'] and row['nodeId'] == 'button')
        rule = {'id': 'protected-exact', 'selector': {'path': path},
                'role': 'protected-media-overlay', 'disposition': 'preserve',
                'reason': 'Exact reviewed artwork channel.', 'ruleId': 'test-protection'}
        report = build(source, self.decisions(source, [rule]))
        self.assertFalse(report['protectionRisks'])

    def test_stale_snapshot_or_root_catch_all_rejected(self):
        source = self.source()
        decisions = self.decisions(source, [])
        decisions['sourceHash'] = 'old'
        with self.assertRaises(ValueError):
            build(source, decisions)
        root = self.rule('all', {'subtreeId': 'root'}, 'anything')
        with self.assertRaises(ValueError):
            build(source, self.decisions(source, [root]))


if __name__ == '__main__':
    unittest.main()

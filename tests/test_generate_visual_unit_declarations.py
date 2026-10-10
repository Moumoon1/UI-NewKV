from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_visual_unit_review_workbench as fixture_module
from generate_visual_unit_declarations import build
from visual_unit_review_workbench import build as workbench


class GenerateVisualUnitDeclarationsTests(unittest.TestCase):
    def test_template_lists_roots_but_cannot_pass_as_reviewed(self):
        source = fixture_module.VisualUnitReviewWorkbenchTests().source()
        result = build(source, workbench(source, max_unit_channels=1))
        self.assertEqual(result['status'], 'needs-review')
        self.assertEqual(len(result['units']), 4)
        self.assertEqual({u['rootNodeId'] for u in result['units']},
                         {'root', 'card', 'label-a', 'label-b'})
        self.assertTrue(all(u['basis'] == '' and u['reviewRuleIds'] == []
                            for u in result['units']))
        self.assertTrue(any(u['reviewHint']['pendingPaths'] > 0
                            for u in result['units']))

    def test_stale_workbench_is_rejected(self):
        source = fixture_module.VisualUnitReviewWorkbenchTests().source()
        report = workbench(source)
        report['sourceHash'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'match'):
            build(source, report)


if __name__ == '__main__':
    unittest.main()

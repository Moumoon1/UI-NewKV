import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_figma_region_js import build
from split_region_plan import split_region


class SplitRegionPlanTests(unittest.TestCase):
    def test_only_last_part_reviews_full_region(self):
        plan = {'schemaVersion': 1, 'regionId': 'card', 'oldUiColors': ['#FF0000'],
                'protectedNodeIds': ['badge'], 'operations': [{'cloneId': str(i)} for i in range(61)]}
        parts = split_region(plan)
        self.assertEqual([len(p['operations']) for p in parts], [60, 1])
        self.assertEqual([p['reviewAfter'] for p in parts], [False, True])
        self.assertEqual(parts[0]['oldUiColors'], [])
        self.assertEqual(parts[1]['oldUiColors'], ['#FF0000'])
        self.assertTrue(all(len(build(p)) <= 45000 for p in parts))

    def test_single_oversized_operation_is_rejected_before_figma(self):
        plan = {'schemaVersion': 1, 'regionId': 'card', 'oldUiColors': [],
                'operations': [{'data': 'x' * 50000}]}
        with self.assertRaisesRegex(ValueError, 'single region operation'):
            split_region(plan)


if __name__ == '__main__':
    unittest.main()

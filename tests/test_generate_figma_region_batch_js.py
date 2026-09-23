import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_figma_region_batch_js import build_batch


def plan(region_id):
    return {"schemaVersion": 1, "regionId": region_id, "oldUiColors": [],
            "operations": [], "batchEligibility": {
                "representativeGateStatus": "pass", "independent": True,
                "recipeHash": "recipe", "dependencyHash": "dependency"}}


class GenerateFigmaRegionBatchTests(unittest.TestCase):
    def test_builds_compact_guarded_batch(self):
        program = build_batch([plan("a"), plan("b")])
        self.assertIn("applyAndReviewThemeRegions", program)
        self.assertLessEqual(len(program), 45000)

    def test_requires_multiple_regions(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            build_batch([plan("a")])

    def test_rejects_ungated_or_overlapping_regions_before_figma(self):
        ungated = {**plan("b"), "batchEligibility": {"independent": True}}
        with self.assertRaisesRegex(ValueError, "not eligible"):
            build_batch([plan("a"), ungated])
        left, right = plan("a"), plan("b")
        left["operations"] = [{"cloneId": "same", "property": "fills"}]
        right["operations"] = [{"cloneId": "same", "property": "fills"}]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            build_batch([left, right])


if __name__ == "__main__":
    unittest.main()

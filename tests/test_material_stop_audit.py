import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from material_stop_audit import inspect_metallic_stops
from split_revision_ops import encoded_size, split_operations


def snapshot(node_id, colors):
    return {"nodes": [{"id": node_id, "parentId": None,
                       "props": {"fills": [{"type": "GRADIENT_LINEAR", "visible": True,
                                             "opacity": 1, "gradientStops": [
                                                 {"color": {"r": r, "g": g, "b": b, "a": 1}}
                                                 for r, g, b in colors]}]}}]}


class MaterialStopAuditTests(unittest.TestCase):
    def test_rejects_visible_metallic_gradient_collapse(self):
        source = snapshot("s", [(0.8, 0.4, 0.2), (0.95, 0.7, 0.5)])
        clone = snapshot("c", [(0.3, 0.8, 1.0), (0.3, 0.8, 1.0)])
        result = inspect_metallic_stops(source, clone, {"s": "c"}, ["s"])
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["findings"][0]["reason"], "visible gradient stops collapsed")

    def test_accepts_recolored_but_distinct_material_stops(self):
        source = snapshot("s", [(0.8, 0.4, 0.2), (0.95, 0.7, 0.5)])
        clone = snapshot("c", [(0.2, 0.6, 0.9), (0.7, 0.9, 1.0)])
        result = inspect_metallic_stops(source, clone, {"s": "c"}, ["s"])
        self.assertEqual(result["status"], "pass")


class BatchSplitTests(unittest.TestCase):
    def test_preserves_order_and_stays_within_payload_limit(self):
        operations = [{"id": i, "changes": [{"color": "#abcdef"}]} for i in range(25)]
        batches = split_operations(operations, max_items=8, max_json_bytes=300)
        self.assertEqual([item for batch in batches for item in batch], operations)
        self.assertTrue(all(len(batch) <= 8 and encoded_size(batch) <= 300 for batch in batches))

    def test_rejects_single_oversize_operation(self):
        with self.assertRaises(ValueError):
            split_operations([{"payload": "x" * 1000}], max_json_bytes=200)


if __name__ == "__main__":
    unittest.main()

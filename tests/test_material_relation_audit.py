import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from material_relation_audit import audit_material_relations


def snapshot(rows):
    return {"nodes": [{"id": node_id, "props": {"fills": [{"color": color}]}}
                      for node_id, color in rows]}


def relation(preserve=None):
    item = {"id": "card-top-pair", "unitId": "card-1", "members": [
        {"sourceId": "a", "path": "/fills/0/color", "role": "warm-light"},
        {"sourceId": "b", "path": "/fills/0/color", "role": "cool-light"},
    ]}
    if preserve:
        item["preserve"] = preserve
    return {"schemaVersion": 1, "relations": [item]}


class MaterialRelationAuditTests(unittest.TestCase):
    def setUp(self):
        self.source = snapshot([
            ("a", {"r": 1, "g": .78, "b": .58, "a": 1}),
            ("b", {"r": .72, "g": .9, "b": 1, "a": 1}),
        ])
        self.mapping = {"mapping": {"a": "aa", "b": "bb"}}

    def test_rejects_two_distinct_atmosphere_shapes_collapsing_to_one_color(self):
        target = snapshot([("aa", {"r": .95, "g": .7, "b": 1}),
                           ("bb", {"r": .95, "g": .7, "b": 1})])
        result = audit_material_relations(self.source, target, self.mapping, relation())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["findings"][0]["collapsedAxes"], ["rgb"])

    def test_accepts_same_family_colors_that_remain_distinct(self):
        target = snapshot([("aa", {"r": .95, "g": .7, "b": 1}),
                           ("bb", {"r": .72, "g": .58, "b": 1})])
        result = audit_material_relations(self.source, target, self.mapping, relation())
        self.assertEqual(result["status"], "pass")

    def test_saturation_role_can_be_protected_explicitly(self):
        source = snapshot([("a", {"r": .92, "g": .92, "b": .86}),
                           ("b", {"r": .5, "g": 1, "b": .05})])
        target = snapshot([("aa", {"r": .6, "g": .3, "b": 1}),
                           ("bb", {"r": .3, "g": .6, "b": 1})])
        result = audit_material_relations(source, target, self.mapping,
                                          relation(["rgb", "saturation"]))
        self.assertEqual(result["status"], "fail")
        self.assertIn("saturation", result["findings"][0]["collapsedAxes"])

    def test_flatten_exception_requires_a_reason(self):
        plan = relation()
        plan["relations"][0]["allowFlatten"] = True
        with self.assertRaisesRegex(ValueError, "allowFlattenReason"):
            audit_material_relations(self.source, self.source, {"a": "a", "b": "b"}, plan)


if __name__ == "__main__":
    unittest.main()

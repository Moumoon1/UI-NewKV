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

    def test_repeated_metal_stop_roles_cannot_split_or_lose_alternation(self):
        dark = {"r": .05, "g": .08, "b": .12, "a": 1}
        light = {"r": .9, "g": .95, "b": 1, "a": 1}
        source_rows = [(str(i), dark if i % 2 == 0 else light) for i in range(8)]
        target_rows = [("t" + str(i), ({"r": .2, "g": .45, "b": .9, "a": 1}
                                      if i >= 2 else
                                      {"r": .8, "g": .9, "b": 1, "a": 1}))
                       for i in range(8)]
        source = snapshot(source_rows); target = snapshot(target_rows)
        mapping = {str(i): "t" + str(i) for i in range(8)}
        plan = {"schemaVersion": 1, "relations": [{"id": "metal-ring", "unitId": "icon",
                "members": [{"sourceId": str(i), "path": "/fills/0/color", "role": "stop-" + str(i)}
                            for i in range(8)]}]}
        result = audit_material_relations(source, target, mapping, plan)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["findings"][0]["roleGroupErrors"])

    def test_repeated_metal_stop_roles_may_change_palette_but_keep_groups(self):
        dark = {"r": .05, "g": .08, "b": .12, "a": 1}
        light = {"r": .9, "g": .95, "b": 1, "a": 1}
        blue_dark = {"r": .15, "g": .35, "b": .7, "a": 1}
        blue_light = {"r": .75, "g": .86, "b": 1, "a": 1}
        source = snapshot([(str(i), dark if i % 2 == 0 else light) for i in range(8)])
        target = snapshot([("t" + str(i), blue_dark if i % 2 == 0 else blue_light) for i in range(8)])
        plan = {"schemaVersion": 1, "relations": [{"id": "metal-ring", "members": [
            {"sourceId": str(i), "path": "/fills/0/color"} for i in range(8)]}]}
        self.assertEqual(audit_material_relations(source, target,
                         {str(i): "t" + str(i) for i in range(8)}, plan)["status"], "pass")


if __name__ == "__main__":
    unittest.main()

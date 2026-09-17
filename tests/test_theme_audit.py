import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import theme_audit as audit
from render_views import render_regions, render_views


def snapshot():
    return {"schemaVersion": 1, "collectorVersion": 1, "rootId": "page",
            "capturedAt": "2026-01-01T00:00:00Z", "errors": [], "nodes": [
        {"id": "page", "parentId": "figma-page", "children": ["card", "other"],
         "props": {"type": "FRAME", "x": 0, "fills": [{"color": {"r": 1}}]}},
        {"id": "card", "parentId": "page", "children": ["button", "protected"],
         "props": {"type": "FRAME", "opacity": 1}},
        {"id": "button", "parentId": "card", "children": [],
         "props": {"type": "VECTOR", "fills": [{"color": {"r": 0.2}}],
                   "vectorNetwork": {"vertices": [{"x": 0, "y": 0}],
                                     "regions": [{"fills": [{"color": {"r": 0.2}}]}]}}},
        {"id": "protected", "parentId": "card", "children": [],
         "props": {"type": "TEXT", "characters": "1", "fills": [{"color": {"r": 0.8}}]}},
        {"id": "other", "parentId": "page", "children": [],
         "props": {"type": "TEXT", "characters": "Other", "opacity": 1}},
    ]}


BUTTON = "/nodes/button/props/fills/0/color/r"
PROTECTED = "/nodes/protected/props/fills"


def policy(changes=None, protected=None):
    return {"schemaVersion": 1, "allowedChanges": changes or [], "protectedPaths": protected or []}


def spec():
    return {"sceneId": "task-card", "dependencyNodeIds": ["card"],
            "recipe": {"button": "red"}, "nodeMap": {"source-card": "card"},
            "protectedPaths": [PROTECTED], "writePaths": [BUTTON],
            "reviewRequirements": [{"id": name, "acceptance": "Fixture acceptance",
                                    "nodeIds": ["button", "card"]}
                                   for name in ("theme-consistency", "clarity", "hierarchy")]}


class StructuralChecks(unittest.TestCase):
    def test_unchanged_source_passes(self):
        self.assertEqual(audit.compare(snapshot(), snapshot(), policy())["status"], "pass")

    def test_root_translation_only_and_no_geometry_bypass(self):
        before, clone = snapshot(), snapshot()
        mapping = {n["id"]: "clone-" + n["id"] for n in before["nodes"]}
        clone["rootId"] = mapping[clone["rootId"]]
        for row in clone["nodes"]:
            row["id"] = mapping[row["id"]]
            row["parentId"] = mapping.get(row["parentId"], row["parentId"])
            row["children"] = [mapping[i] for i in row["children"]]
        clone["nodes"][0]["props"]["x"] = 700
        p = policy([{"path": "/nodes/page/props/x", "before": 0, "after": 700}])
        self.assertEqual(audit.compare(before, clone, p, mapping)["status"], "pass")
        clone["nodes"][2]["props"]["vectorNetwork"]["vertices"][0]["x"] = 5
        self.assertEqual(audit.compare(before, clone, p, mapping)["status"], "fail")

    def test_region_paint_permission_does_not_allow_geometry(self):
        before, after = snapshot(), snapshot()
        net = after["nodes"][2]["props"]["vectorNetwork"]
        net["regions"][0]["fills"][0]["color"]["r"] = 0.7
        p = policy([{"path": "/nodes/button/props/vectorNetwork/regions/0/fills/0/color/r",
                     "before": 0.2, "after": 0.7}])
        self.assertEqual(audit.compare(before, after, p)["status"], "pass")
        net["vertices"][0]["y"] = 2
        self.assertEqual(audit.compare(before, after, p)["status"], "fail")

    def test_protection_beats_allowlist(self):
        a, b = snapshot(), snapshot()
        b["nodes"][3]["props"]["fills"][0]["color"]["r"] = 0.1
        p = policy([{"path": PROTECTED + "/0/color/r", "before": 0.8, "after": 0.1}], [PROTECTED])
        result = audit.compare(a, b, p)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(len(result["protectedChanges"]), 1)

    def test_source_color_change_cannot_be_ignored(self):
        a, b = snapshot(), snapshot()
        b["nodes"][2]["props"]["fills"][0]["color"]["r"] = 0.7
        self.assertEqual(audit.compare(a, b, policy())["status"], "fail")

    def test_adding_layer_is_not_silently_normalized_away(self):
        a, b = snapshot(), snapshot()
        b["nodes"][1]["children"].append("extra")
        b["nodes"].append({"id": "extra", "parentId": "card", "children": [], "props": {"type": "RECTANGLE"}})
        self.assertEqual(audit.compare(a, b, policy())["status"], "fail")

    def test_reordered_children_fail(self):
        a, b = snapshot(), snapshot()
        b["nodes"][1]["children"].reverse()
        self.assertEqual(audit.compare(a, b, policy())["status"], "fail")

    def test_missing_and_duplicate_mapping_rejected(self):
        for mapping in ({"page": "page"}, {n["id"]: "same" for n in snapshot()["nodes"]}):
            with self.assertRaises(ValueError):
                audit.compare(snapshot(), snapshot(), policy(), mapping)

    def test_incomplete_snapshot_rejected(self):
        for mutation in (lambda s: s["errors"].append({"error": "denied"}),
                         lambda s: s["nodes"].pop(),
                         lambda s: s["nodes"][1]["children"].append("card")):
            s = snapshot(); mutation(s)
            with self.assertRaises(ValueError):
                audit.snapshot_document(s)

    def test_typo_in_protection_path_rejected(self):
        with self.assertRaises(ValueError):
            audit.compare(snapshot(), snapshot(), policy(protected=["/nodes/missing/props/fills"]))

    def test_boolean_is_not_number(self):
        self.assertFalse(audit.equal(True, 1))


class ColorRelationChecks(unittest.TestCase):
    def setUp(self):
        self.before = snapshot()
        for row in self.before["nodes"]:
            row["props"]["fills"] = [{"color": {"r": 1, "g": 1, "b": 1}}]
        self.after = copy.deepcopy(self.before)
        self.spec = {"schemaVersion": 1, "groups": [{"id": "joined-surface",
            "reason": "Vector tab and Frame content form one white surface",
            "paths": ["/nodes/card/props/fills/0/color", "/nodes/button/props/fills/0/color"]}]}

    def test_catches_same_white_split_by_node_type(self):
        self.after["nodes"][1]["props"]["fills"][0]["color"] = {"r": 1, "g": .98, "b": .95}
        self.after["nodes"][2]["props"]["fills"][0]["color"] = {"r": 1, "g": .91, "b": .87}
        result = audit.color_relations(self.before, self.after, self.spec)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["groups"][0]["sourceEquivalent"])
        self.assertFalse(result["groups"][0]["targetEquivalent"])

    def test_equivalent_colors_allow_state_alpha_and_float_rounding(self):
        self.after["nodes"][1]["props"]["fills"][0]["color"] = {"r": .7, "g": .3, "b": .2}
        self.after["nodes"][2]["props"]["fills"][0]["color"] = {"r": .699999988, "g": .3, "b": .2, "a": .6}
        self.assertEqual(audit.color_relations(self.before, self.after, self.spec)["status"], "pass")

    def test_distinct_original_colors_cannot_be_declared_equivalent(self):
        self.before["nodes"][1]["props"]["fills"][0]["color"]["g"] = .8
        self.assertEqual(audit.color_relations(self.before, self.after, self.spec)["status"], "fail")

    def test_empty_missing_partial_color_and_duplicate_member_rejected(self):
        for paths in (["/nodes/missing/props/fills/0/color", self.spec["groups"][0]["paths"][0]],
                      ["/nodes/card/props/fills/0/color/r", "/nodes/button/props/fills/0/color/r"],
                      [self.spec["groups"][0]["paths"][0]] * 2):
            bad = copy.deepcopy(self.spec); bad["groups"][0]["paths"] = paths
            with self.assertRaises(ValueError):
                audit.color_relations(self.before, self.after, bad)
        with self.assertRaises(ValueError):
            audit.color_relations(self.before, self.after, {"schemaVersion": 1, "groups": []})

    def test_clone_mapping_used_for_color_paths(self):
        mapping = {n["id"]: "clone-" + n["id"] for n in self.before["nodes"]}
        self.after["rootId"] = mapping[self.after["rootId"]]
        for row in self.after["nodes"]:
            row["id"] = mapping[row["id"]]
            row["parentId"] = mapping.get(row["parentId"], row["parentId"])
            row["children"] = [mapping[i] for i in row["children"]]
        self.assertEqual(audit.color_relations(self.before, self.after, self.spec, mapping)["status"], "pass")


class RecoveryChecks(unittest.TestCase):
    def setUp(self):
        self.ops = [{"path": BUTTON, "before": 0.2, "after": 0.7},
                    {"path": "/nodes/other/props/opacity", "before": 1, "after": 0.8}]
        self.batch = {"schemaVersion": 1, "batchId": "trial-1", "operations": self.ops}
        self.policy = policy(self.ops, [PROTECTED])

    def test_partial_success_only_retries_pending(self):
        s = snapshot(); s["nodes"][2]["props"]["fills"][0]["color"]["r"] = 0.7
        result = audit.recover_batch(s, self.batch, self.policy)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["completedPaths"], [BUTTON])
        self.assertEqual(result["pendingOperations"], [self.ops[1]])

    def test_user_change_blocks_rebase(self):
        s = snapshot(); s["nodes"][2]["props"]["fills"][0]["color"]["r"] = 0.9
        result = audit.recover_batch(s, self.batch, self.policy)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["pendingOperations"])
        self.assertEqual(len(result["conflicts"]), 1)

    def test_figma_float_rounding_is_complete_but_protection_remains_exact(self):
        s = snapshot(); s["nodes"][2]["props"]["fills"][0]["color"]["r"] = 0.699999988079071
        result = audit.recover_batch(s, self.batch, self.policy)
        self.assertEqual(result["completedPaths"], [BUTTON])
        self.assertEqual(audit.compare(snapshot(), s, self.policy)["status"], "pass")
        self.assertEqual(audit.compare(snapshot(), s, policy())["status"], "fail")
        self.policy["protectedPaths"].append(BUTTON)
        self.assertEqual(audit.compare(snapshot(), s, self.policy)["status"], "fail")

    def test_outside_allowlist_is_not_executable(self):
        result = audit.recover_batch(snapshot(), self.batch, policy())
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["pendingOperations"])

    def test_whole_paint_write_preserves_protected_channel(self):
        before = [{"color": {"r": 0.2}, "opacity": 1}]
        after = [{"color": {"r": 0.7}, "opacity": 1}]
        s = snapshot(); s["nodes"][2]["props"]["fills"] = before
        op = {"path": "/nodes/button/props/fills", "before": before, "after": after}
        p = policy([self.ops[0]], ["/nodes/button/props/fills/0/opacity"])
        result = audit.recover_batch(s, {"schemaVersion": 1, "batchId": "b", "operations": [op]}, p)
        self.assertEqual(result["status"], "ready")
        after[0]["opacity"] = 0.4
        result = audit.recover_batch(s, {"schemaVersion": 1, "batchId": "b", "operations": [op]}, p)
        self.assertEqual(result["status"], "blocked")

    def test_overlapping_operations_rejected(self):
        self.batch["operations"].append({"path": "/nodes/button/props/fills", "before": [], "after": []})
        with self.assertRaises(ValueError):
            audit.recover_batch(snapshot(), self.batch, self.policy)


class GateChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "scene.png"
        from PIL import Image
        Image.new("RGB", (10, 10), "red").save(self.image)
        self.review = {"sceneId": "task-card", "status": "pass", "notes": "Fixture review only",
                       "reviewedAt": "2026-01-01T00:00:01Z", "screenshots": [str(self.image)]}
        self.review["checks"] = [{"id": requirement["id"], "status": "pass",
                                  "observation": "Fixture observation", "comparison": "Fixture host comparison",
                                  "nodeIds": requirement["nodeIds"], "screenshots": [str(self.image)]}
                                 for requirement in spec()["reviewRequirements"]]
        self.state = audit.scene_state(snapshot(), spec())
        self.gate = audit.seal_gate(self.state, self.review)

    def fresh(self, s=None, specification=None):
        s = s or snapshot()
        s["capturedAt"] = "2026-01-01T00:00:02Z"
        return audit.scene_state(s, specification or spec())

    def test_current_gate_passes_but_pre_review_readback_rejected(self):
        self.assertEqual(audit.check_gate(self.fresh(), self.gate)["status"], "pass")
        self.assertEqual(audit.check_gate(self.state, self.gate)["status"], "stale")

    def test_shared_background_and_ancestor_changes_invalidate(self):
        for index, key, value in ((0, "fills", [{"color": {"r": 0}}]), (1, "opacity", 0.5)):
            s = snapshot(); s["nodes"][index]["props"][key] = value
            self.assertEqual(audit.check_gate(self.fresh(s), self.gate)["status"], "stale")

    def test_recipe_mapping_and_scope_changes_invalidate(self):
        for key, value in (("recipe", {"button": "blue"}), ("nodeMap", {"different-source": "card"}),
                           ("writePaths", ["/nodes/button/props/fills"]), ("protectedPaths", [])):
            sp = spec(); sp[key] = value
            self.assertEqual(audit.check_gate(self.fresh(specification=sp), self.gate)["status"], "stale")

    def test_unrelated_region_does_not_invalidate(self):
        s = snapshot(); s["nodes"][4]["props"]["characters"] = "Updated unrelated text"
        self.assertEqual(audit.check_gate(self.fresh(s), self.gate)["status"], "pass")

    def test_changed_evidence_invalidates(self):
        self.image.write_bytes(b"changed")
        self.assertEqual(audit.check_gate(self.fresh(), self.gate)["status"], "stale")

    def test_missing_evidence_and_failed_review_do_not_seal(self):
        self.review["status"] = "fail"
        with self.assertRaises(ValueError):
            audit.seal_gate(self.state, self.review)
        self.review["status"] = "pass"; self.image.unlink()
        with self.assertRaises(ValueError):
            audit.seal_gate(self.state, self.review)

    def test_non_image_file_cannot_be_screenshot_evidence(self):
        self.image.write_text('{"status":"pass"}')
        with self.assertRaises(ValueError):
            audit.seal_gate(self.state, self.review)

    def test_missing_dependencies_are_not_silently_skipped(self):
        sp = spec(); sp["dependencyNodeIds"] = ["nonexistent"]
        with self.assertRaises(ValueError):
            audit.scene_state(snapshot(), sp)

    def test_summary_only_missing_failed_and_unobserved_checks_do_not_seal(self):
        for modify in (lambda r: r.pop("checks"),
                       lambda r: r["checks"].pop(),
                       lambda r: r["checks"][0].update(status="unknown"),
                       lambda r: r["checks"][0].update(nodeIds=["button"]),
                       lambda r: r["checks"][0].update(screenshots=[]),
                       lambda r: r["checks"][0].update(comparison="")):
            review = copy.deepcopy(self.review); modify(review)
            with self.assertRaises(ValueError):
                audit.seal_gate(self.state, review)

    def test_changed_acceptance_invalidates_and_legacy_gate_is_stale(self):
        sp = spec(); sp["reviewRequirements"][0]["acceptance"] = "Changed rule"
        self.assertEqual(audit.check_gate(self.fresh(specification=sp), self.gate)["status"], "stale")
        gate = copy.deepcopy(self.gate); gate.pop("checks")
        self.assertEqual(audit.check_gate(self.fresh(), gate)["status"], "stale")

    def test_requirements_cannot_omit_baseline_or_observed_context(self):
        sp = spec(); sp["reviewRequirements"].pop()
        with self.assertRaises(ValueError):
            audit.scene_state(snapshot(), sp)
        sp = spec(); sp["reviewRequirements"][0]["nodeIds"] = ["other"]
        with self.assertRaises(ValueError):
            audit.scene_state(snapshot(), sp)


class ArtifactChecks(unittest.TestCase):
    def test_cli_diff_has_meaningful_exit_status_and_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            a, b = snapshot(), snapshot()
            b["nodes"][4]["props"]["characters"] = "Wrong text"
            for name, value in (("a", a), ("b", b), ("policy", policy())):
                audit.save_json(p / (name + ".json"), value)
            result = subprocess.run([sys.executable, str(Path(audit.__file__)), "diff",
                                     str(p / "a.json"), str(p / "b.json"), str(p / "policy.json"),
                                     "--out", str(p / "result.json")], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(audit.read_json(p / "result.json")["status"], "fail")

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "bad.json"; p.write_text('{"x": 1, "x": 2}')
            with self.assertRaises(ValueError): audit.read_json(p)

    def test_views_preserve_real_background_and_reject_transparent_input(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); source = p / "source.png"
            Image.new("RGB", (400, 600), "#993300").save(source)
            before = source.read_bytes()
            manifest = render_views(source, p / "views")
            self.assertEqual(before, source.read_bytes())
            self.assertEqual(manifest["sourcePixels"], [400, 600])
            with Image.open(p / "views" / "thumbnail.png") as image:
                self.assertEqual(image.size, (240, 360))
            with Image.open(p / "views" / "color.png") as image:
                self.assertEqual(image.getpixel((0, 0)), (153, 51, 0))
            Image.new("RGBA", (10, 10), (255, 0, 0, 0)).save(source)
            with self.assertRaises(ValueError): render_views(source, p / "invalid")

    def test_regions_preserve_source_pixels_without_extra_remote_exports(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); source = p / "whole.png"
            image = Image.new("RGB", (400, 600), "#993300")
            image.putpixel((10, 20), (1, 2, 3)); image.save(source)
            before = source.read_bytes()
            result = render_regions(source, p / "regions", {"button": [10, 20, 100, 50]})
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(result["button"]["cropPixels"], [10, 20, 110, 70])
            with Image.open(p / "regions/button/color.png") as crop:
                self.assertEqual(crop.size, (100, 50)); self.assertEqual(crop.getpixel((0, 0)), (1, 2, 3))
            for regions in ({"../unsafe": [0, 0, 10, 10]}, {"bad": [399, 599, 10, 10]}):
                with self.assertRaises(ValueError): render_regions(source, p / "regions", regions)
            source = p / "regions/button/color.png"
            with self.assertRaises(ValueError): render_regions(source, p / "regions", {"button": [0, 0, 10, 10]})


class SceneNumericFingerprintTests(unittest.TestCase):
    def state(self, value):
        return {"schemaVersion": 1, "sceneId": "numeric",
                "capturedAt": "2026-01-01T00:00:00Z",
                "payload": {"context": {"value": value}}}

    def test_json_integer_float_formats_are_equivalent(self):
        self.assertEqual(audit.state_hash(self.state([1, 0, {"alpha": 1}])),
                         audit.state_hash(self.state([1.0, -0.0, {"alpha": 1.0}])))

    def test_real_numeric_changes_still_invalidate(self):
        self.assertNotEqual(audit.state_hash(self.state(1)),
                            audit.state_hash(self.state(1.0000001)))

    def test_boolean_is_not_numeric_one(self):
        self.assertNotEqual(audit.state_hash(self.state(True)),
                            audit.state_hash(self.state(1)))


if __name__ == "__main__":
    unittest.main()

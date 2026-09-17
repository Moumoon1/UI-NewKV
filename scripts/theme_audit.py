#!/usr/bin/env python3
"""Offline, fail-closed checks for KV theme adaptation. Never writes to Figma."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone


MISSING = {"$missing": True}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))


def save_json(path, value):
    """Atomic replacement of one local artifact; not a Figma transaction."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, encoding="utf-8") as f:
        temporary = Path(f.name)
        try:
            f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def escape(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def parts(path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("expected nonempty JSON pointer")
    return [v.replace("~1", "/").replace("~0", "~") for v in path[1:].split("/")]


def overlaps(a, b):
    aa, bb = parts(a), parts(b)
    return aa[:len(bb)] == bb or bb[:len(aa)] == aa


def at(document, path):
    value = document
    for part in parts(path):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return MISSING
    return value


def equal(a, b):
    # bool must not compare equal to numeric 0/1. JSON numeric 1 and 1.0 are equivalent.
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isfinite(a) and math.isfinite(b) and a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    return a == b


def target_equal(actual, target):
    """Allow tiny Figma float readback rounding only for an authorized target.

    Baseline differences and protected channels remain exact comparisons.
    """
    if equal(actual, target):
        return True
    if isinstance(actual, bool) or isinstance(target, bool):
        return False
    if isinstance(actual, (int, float)) and isinstance(target, (int, float)):
        return math.isclose(actual, target, rel_tol=0, abs_tol=1e-6)
    if isinstance(actual, dict) and isinstance(target, dict):
        return actual.keys() == target.keys() and all(target_equal(actual[k], target[k]) for k in actual)
    if isinstance(actual, list) and isinstance(target, list):
        return len(actual) == len(target) and all(target_equal(a, b) for a, b in zip(actual, target))
    return False


def differences(before, after, path=""):
    if equal(before, after):
        return []
    result = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            p = path + "/" + escape(key)
            if key not in before or key not in after:
                result.append({"path": p, "before": before.get(key, MISSING), "after": after.get(key, MISSING)})
            else:
                result.extend(differences(before[key], after[key], p))
    elif isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        for i, (a, b) in enumerate(zip(before, after)):
            result.extend(differences(a, b, path + "/" + str(i)))
    else:
        # Array insertions/removals are atomic: never silently shift paint/range indices.
        result.append({"path": path, "before": before, "after": after})
    return result


def snapshot_document(snapshot):
    if snapshot.get("schemaVersion") != 1 or snapshot.get("errors") != []:
        raise ValueError("snapshot version mismatch or incomplete reads")
    rows = snapshot.get("nodes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("snapshot has no nodes")
    nodes = {}
    for row in rows:
        if not isinstance(row.get("id"), str) or row["id"] in nodes:
            raise ValueError("missing or duplicate node ID")
        if not isinstance(row.get("props"), dict) or not isinstance(row.get("children"), list):
            raise ValueError("invalid node record")
        if not isinstance(row.get("parentId"), (str, type(None))):
            raise ValueError("invalid parent ID")
        if "type" not in row["props"]:
            raise ValueError("node type missing")
        nodes[row["id"]] = {k: row[k] for k in ("parentId", "children", "props")}
    root = snapshot.get("rootId")
    if root not in nodes:
        raise ValueError("snapshot root missing")
    seen = set()
    def visit(node_id):
        if node_id in seen:
            raise ValueError("cycle or duplicate child")
        seen.add(node_id)
        for child in nodes[node_id]["children"]:
            if child not in nodes or nodes[child]["parentId"] != node_id:
                raise ValueError("incomplete or inconsistent subtree")
            visit(child)
    visit(root)
    if seen != set(nodes):
        raise ValueError("snapshot has disconnected nodes")
    return {"nodes": nodes}


def mapped_document(before, after, mapping):
    if before.get("collectorVersion") != after.get("collectorVersion"):
        raise ValueError("collector versions differ; rebuild comparable snapshots")
    source, clone = snapshot_document(before), snapshot_document(after)
    if mapping is None:
        if before["rootId"] != after["rootId"]:
            raise ValueError("different roots require explicit source-to-clone mapping")
        return source, clone
    if set(mapping) != set(source["nodes"]) or len(set(mapping.values())) != len(mapping):
        raise ValueError("mapping must cover every source node with unique target IDs")
    if mapping[before["rootId"]] != after["rootId"]:
        raise ValueError("root mapping mismatch")
    inverse = {v: k for k, v in mapping.items()}
    normalized = {}
    for node_id, row in clone["nodes"].items():
        key = inverse.get(node_id, node_id)
        if key in normalized or (node_id not in inverse and key in source["nodes"]):
            raise ValueError("unmapped clone ID collides with source namespace")
        normalized[key] = {"parentId": inverse.get(row["parentId"], row["parentId"]),
                           "children": [inverse.get(c, c) for c in row["children"]],
                           "props": row["props"]}
    return source, {"nodes": normalized}


def color_relations(before, after, spec, mapping=None):
    """Check declared RGB equivalence classes, not visual quality or coverage.

    Paths use source IDs and point to RGB(A) objects. Alpha and gradient
    geometry are deliberately separate: equal base colors can have different
    state opacity. Existing structural/visual checks still apply.
    """
    source, target = mapped_document(before, after, mapping)
    groups = spec.get("groups")
    if spec.get("schemaVersion") != 1 or not isinstance(groups, list) or not groups:
        raise ValueError("color relations require nonempty groups")
    seen, results = set(), []

    def rgb_at(document, path):
        value = at(document, path)
        if not isinstance(value, dict) or not set(value) in ({"r", "g", "b"}, {"r", "g", "b", "a"}):
            raise ValueError("relation path must point to an RGB(A) object: " + path)
        for channel in value.values():
            if isinstance(channel, bool) or not isinstance(channel, (int, float)) or not math.isfinite(channel) or not 0 <= channel <= 1:
                raise ValueError("invalid color channel: " + path)
        return {k: value[k] for k in ("r", "g", "b")}

    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("relation group must be an object")
        name, paths = group.get("id"), group.get("paths")
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError("relation IDs must be nonempty and unique")
        seen.add(name)
        if not isinstance(group.get("reason"), str) or not group["reason"].strip():
            raise ValueError("relation needs original semantic/continuity evidence")
        if not isinstance(paths, list) or len(paths) < 2 or any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
            raise ValueError("relation requires at least two unique color paths")
        original = [rgb_at(source, p) for p in paths]
        actual = [rgb_at(target, p) for p in paths]
        comparison = group.get("comparison", "float")
        if comparison not in ("float", "srgb8"):
            raise ValueError("unknown color relation comparison: " + str(comparison))
        def same_rgb(a, b):
            if comparison == "srgb8":
                return all(math.floor(a[k] * 255 + .5) == math.floor(b[k] * 255 + .5) for k in "rgb")
            return target_equal(a, b)
        source_same = all(same_rgb(original[0], v) for v in original[1:])
        target_same = all(same_rgb(actual[0], v) for v in actual[1:])
        results.append({"id": name, "status": "pass" if source_same and target_same else "fail",
                        "sourceEquivalent": source_same, "targetEquivalent": target_same,
                        "comparison": comparison,
                        "maxTargetChannelDelta": max(abs(v[k] - actual[0][k]) for v in actual for k in "rgb"),
                        "paths": paths, "sourceRGB": original, "targetRGB": actual})
    return {"status": "pass" if all(g["status"] == "pass" for g in results) else "fail",
            "relationsHash": digest(spec), "groups": results}


def policy_check(policy):
    if policy.get("schemaVersion") != 1:
        raise ValueError("policy version mismatch")
    allowed = policy.get("allowedChanges")
    protected = policy.get("protectedPaths")
    if not isinstance(allowed, list) or not isinstance(protected, list):
        raise ValueError("policy needs allowedChanges and protectedPaths lists")
    seen = set()
    for change in allowed:
        if set(change) != {"path", "before", "after"}:
            raise ValueError("allowed changes require exact path/before/after")
        parts(change["path"])
        if change["path"] in seen:
            raise ValueError("duplicate allowed path")
        seen.add(change["path"])
    for path in protected:
        parts(path)
    return {c["path"]: c for c in allowed}, protected


def assess_changes(changes, policy):
    allowed, protected = policy_check(policy)
    blocked, unexpected = [], []
    for change in changes:
        if any(overlaps(change["path"], p) for p in protected):
            blocked.append(change)
        expected = allowed.get(change["path"])
        if not expected or not equal(change["before"], expected["before"]) or not target_equal(change["after"], expected["after"]):
            unexpected.append(change)
    return {"status": "fail" if blocked or unexpected else "pass", "changes": changes,
            "protectedChanges": blocked, "unexpectedChanges": unexpected}


def compare(before, after, policy, mapping=None):
    a, b = mapped_document(before, after, mapping)
    _, protected = policy_check(policy)
    for path in protected:
        if at(a, path) == MISSING:
            raise ValueError("protection path missing from baseline: " + path)
    return assess_changes(differences(a, b), policy)


def recover_batch(snapshot, batch, policy):
    """Classify atomic writes from fresh readback; never rebase an unexpected value."""
    doc = snapshot_document(snapshot)
    _, protected = policy_check(policy)
    for path in protected:
        if at(doc, path) == MISSING:
            raise ValueError("protection path missing from fresh readback: " + path)
    if batch.get("schemaVersion") != 1 or not batch.get("batchId") or not batch.get("operations"):
        raise ValueError("batch needs version, batchId and nonempty operations")
    operations = batch["operations"]
    paths = []
    planned = []
    for op in operations:
        if set(op) != {"path", "before", "after"}:
            raise ValueError("operation needs exact path/before/after")
        path = op["path"]
        tokens = parts(path)
        if len(tokens) < 4 or tokens[0] != "nodes" or tokens[2] != "props":
            raise ValueError("batch recovery supports existing node property writes only")
        if any(overlaps(path, other) for other in paths):
            raise ValueError("overlapping operations must be coalesced into one atomic write")
        if op["before"] == MISSING or op["after"] == MISSING:
            raise ValueError("structural operations require separate recovery")
        paths.append(path)
        planned.extend(differences(op["before"], op["after"], path))
    guard = assess_changes(planned, policy)
    pending, done, conflicts = [], [], []
    for op in operations:
        current = at(doc, op["path"])
        if current == MISSING:
            conflicts.append({**op, "current": current})
        elif target_equal(current, op["after"]):
            done.append(op["path"])
        elif equal(current, op["before"]):
            pending.append(op)
        else:
            conflicts.append({**op, "current": current})
    ready = guard["status"] == "pass" and not conflicts
    return {"status": "ready" if ready else "blocked", "batchId": batch["batchId"],
            "completedPaths": done, "pendingOperations": pending if ready else [],
            "conflicts": conflicts, "guard": guard}


def scene_state(snapshot, spec):
    nodes = snapshot_document(snapshot)["nodes"]
    required = ("sceneId", "dependencyNodeIds", "recipe", "nodeMap", "protectedPaths", "writePaths", "reviewRequirements")
    if any(key not in spec for key in required) or not spec["dependencyNodeIds"]:
        raise ValueError("incomplete scene specification")
    if not spec["sceneId"] or not spec["recipe"] or not spec["nodeMap"] or not spec["writePaths"]:
        raise ValueError("empty scene recipe, mapping or write scope")
    chosen = set()
    def subtree(node_id):
        if node_id not in nodes:
            raise ValueError("missing dependency: " + node_id)
        if node_id in chosen:
            return
        chosen.add(node_id)
        for child in nodes[node_id]["children"]:
            subtree(child)
    for seed in spec["dependencyNodeIds"]:
        subtree(seed)
    for seed in list(chosen):
        parent = nodes[seed]["parentId"]
        while parent in nodes:
            chosen.add(parent)
            parent = nodes[parent]["parentId"]
    for path in spec["protectedPaths"] + spec["writePaths"]:
        tokens = parts(path)
        if len(tokens) < 2 or tokens[0] != "nodes" or tokens[1] not in chosen or at({"nodes": nodes}, path) == MISSING:
            raise ValueError("scope path outside observed dependencies: " + path)
    if any(target not in chosen for target in spec["nodeMap"].values()):
        raise ValueError("scene mapping target outside observed dependencies")
    requirements = spec["reviewRequirements"]
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("predeclared visual review requirements required")
    ids = set()
    for requirement in requirements:
        name = requirement.get("id")
        if not isinstance(name, str) or not name.strip() or name in ids:
            raise ValueError("missing/duplicate review requirement ID")
        ids.add(name)
        if not isinstance(requirement.get("acceptance"), str) or not requirement["acceptance"].strip():
            raise ValueError("review requirement needs concrete acceptance")
        if not isinstance(requirement.get("nodeIds"), list) or not requirement["nodeIds"] or not set(requirement["nodeIds"]) <= chosen:
            raise ValueError("review requirement nodes outside observed context")
    if not {"theme-consistency", "clarity", "hierarchy"} <= ids:
        raise ValueError("theme-consistency, clarity and hierarchy reviews required")
    return {"schemaVersion": 1, "sceneId": spec["sceneId"],
            "capturedAt": snapshot["capturedAt"],
            "payload": {"recipe": spec["recipe"], "nodeMap": spec["nodeMap"],
                        "protectedPaths": sorted(spec["protectedPaths"]),
                        "writePaths": sorted(spec["writePaths"]),
                        "dependencyNodeIds": sorted(spec["dependencyNodeIds"]),
                        "reviewRequirements": requirements,
                        "reviewScope": spec.get("reviewScope", "local"),
                        "rootId": snapshot["rootId"],
                        "context": {i: nodes[i] for i in sorted(chosen)}}}


def timestamp(value):
    time = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if time.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return time


def state_hash(state):
    if state.get("schemaVersion") != 1 or not state.get("sceneId") or not state.get("payload"):
        raise ValueError("invalid scene state")
    timestamp(state["capturedAt"])
    # Figma has one Number type. JSON templates may contain 1.0 where a fresh
    # collector emits 1; equal()/differences() already treat these as identical.
    # Canonicalize integral floats for scene fingerprints only; keep the frozen
    # source/manifest/ledger digest contract unchanged.
    def numeric(value):
        if isinstance(value, float) and math.isfinite(value) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [numeric(v) for v in value]
        if isinstance(value, dict):
            return {k: numeric(v) for k, v in value.items()}
        return value
    return digest(numeric({"sceneId": state["sceneId"], "payload": state["payload"]}))


def evidence_records(paths):
    if not paths:
        raise ValueError("screenshot evidence required")
    result = []
    for path in paths:
        p = Path(path).resolve()
        if not p.is_file() or p.stat().st_size == 0:
            raise ValueError("missing/empty evidence: " + str(p))
        data = p.read_bytes()
        if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")
                or data.startswith((b"GIF87a", b"GIF89a"))
                or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")):
            raise ValueError("evidence is not a recognized raster screenshot: " + str(p))
        result.append({"path": str(p), "sha256": hashlib.sha256(data).hexdigest()})
    return result


def validate_visual_checks(state, review):
    requirements = state["payload"].get("reviewRequirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("legacy scene without review requirements must be reviewed again")
    checks = review.get("checks")
    if not isinstance(checks, list):
        raise ValueError("per-requirement visual checks required; summary notes are insufficient")
    indexed = {}
    screenshots = set(review.get("screenshots", []))
    for check in checks:
        name = check.get("id")
        if not name or name in indexed:
            raise ValueError("missing/duplicate visual check")
        indexed[name] = check
    if set(indexed) != {r["id"] for r in requirements}:
        raise ValueError("visual checks must cover exactly the predeclared requirements")
    for requirement in requirements:
        check = indexed[requirement["id"]]
        if check.get("status") != "pass":
            raise ValueError("failed or unknown visual check cannot seal gate")
        if not all(isinstance(check.get(k), str) and check[k].strip() for k in ("observation", "comparison")):
            raise ValueError("actual observation and contextual comparison required")
        if not isinstance(check.get("nodeIds"), list) or not set(requirement["nodeIds"]) <= set(check["nodeIds"]):
            raise ValueError("review omitted required nodes")
        if not set(check["nodeIds"]) <= set(state["payload"]["context"]):
            raise ValueError("review nodes outside observed context")
        if not isinstance(check.get("screenshots"), list) or not check["screenshots"] or not set(check["screenshots"]) <= screenshots:
            raise ValueError("per-check screenshot evidence required")
    return checks


def seal_gate(state, review):
    fingerprint = state_hash(state)
    if review.get("status") != "pass" or review.get("sceneId") != state["sceneId"] or not review.get("notes"):
        raise ValueError("an explicit, matching visual pass with notes is required")
    reviewed = timestamp(review["reviewedAt"])
    if not timestamp(state["capturedAt"]) <= reviewed <= datetime.now(timezone.utc):
        raise ValueError("review must follow readback and cannot be in the future")
    checks = validate_visual_checks(state, review)
    return {"schemaVersion": 1, "stateHashVersion": 2, "sceneId": state["sceneId"], "status": "pass",
            "stateHash": fingerprint, "reviewedAt": review["reviewedAt"],
            "notes": review["notes"],
            "checks": [{**c, "screenshots": [str(Path(p).resolve()) for p in c["screenshots"]]} for c in checks],
            "evidence": evidence_records(review.get("screenshots"))}


def check_gate(state, gate):
    valid = (gate.get("schemaVersion") == 1 and gate.get("status") == "pass"
             and state.get("sceneId") == gate.get("sceneId")
             and state_hash(state) == gate.get("stateHash"))
    valid = valid and timestamp(state["capturedAt"]) >= timestamp(gate["reviewedAt"])
    evidence = gate.get("evidence", [])
    try:
        valid = valid and bool(evidence) and evidence_records([e["path"] for e in evidence]) == evidence
    except (ValueError, KeyError, TypeError, OSError):
        valid = False
    if valid:
        # Old summary-only gates cannot be reused after upgrading the contract.
        try:
            validate_visual_checks(state, {"checks": gate.get("checks"),
                                           "screenshots": [e["path"] for e in evidence]})
        except (ValueError, KeyError, TypeError):
            valid = False
    return {"status": "pass" if valid else "stale", "sceneId": state["sceneId"],
            "stateHash": state_hash(state)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    diff = sub.add_parser("diff", help="compare snapshots against exact allowed changes")
    diff.add_argument("before"); diff.add_argument("after"); diff.add_argument("policy")
    diff.add_argument("--map", dest="mapping")
    relations = sub.add_parser("color-relations", help="check declared source RGB equivalence classes")
    relations.add_argument("before"); relations.add_argument("after"); relations.add_argument("spec")
    relations.add_argument("--map", dest="mapping")
    batch = sub.add_parser("recover", help="classify partial writes from a fresh snapshot")
    batch.add_argument("snapshot"); batch.add_argument("batch"); batch.add_argument("policy")
    state = sub.add_parser("scene-state", help="collect scene dependencies and all ancestors")
    state.add_argument("snapshot"); state.add_argument("spec")
    for name in ("seal-gate", "check-gate"):
        p = sub.add_parser(name)
        p.add_argument("state"); p.add_argument("record")
    for p in (diff, relations, batch, state, *[sub.choices[n] for n in ("seal-gate", "check-gate")]):
        p.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        if args.command == "diff":
            result = compare(read_json(args.before), read_json(args.after), read_json(args.policy),
                             read_json(args.mapping) if args.mapping else None)
        elif args.command == "color-relations":
            result = color_relations(read_json(args.before), read_json(args.after), read_json(args.spec),
                                     read_json(args.mapping) if args.mapping else None)
        elif args.command == "recover":
            result = recover_batch(read_json(args.snapshot), read_json(args.batch), read_json(args.policy))
        elif args.command == "scene-state":
            result = scene_state(read_json(args.snapshot), read_json(args.spec))
        else:
            fn = seal_gate if args.command == "seal-gate" else check_gate
            result = fn(read_json(args.state), read_json(args.record))
        save_json(args.out, result)
        print(json.dumps({"status": result.get("status", "recorded"), "output": args.out}))
        return 0 if result.get("status") in (None, "pass", "ready") else 1
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        save_json(args.out, {"status": "error", "error": str(exc)})
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

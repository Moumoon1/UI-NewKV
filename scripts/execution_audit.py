#!/usr/bin/env python3
"""Coverage, completion, batching and timings. Offline; never edits Figma."""
import argparse
import colorsys
from collections import Counter
import math
import sys

from theme_audit import (MISSING, at, canonical, compare, digest, equal, escape,
                         check_gate, color_relations, mapped_document, overlaps, parts, policy_check, scene_state,
                         read_json, save_json, snapshot_document, target_equal)
from contrast_audit import compare_contrast


def color_inventory(snapshot):
    doc = snapshot_document(snapshot)
    entries = []

    def scan(value, path, node_id, inactive):
        if isinstance(value, dict):
            if all(k in value for k in ('r', 'g', 'b')):
                if not all(type(value[k]) in (int, float) and math.isfinite(value[k])
                           and 0 <= value[k] <= 1 for k in ('r', 'g', 'b')):
                    raise ValueError('invalid RGB: ' + path)
                entries.append({'path': path, 'nodeId': node_id, 'source': value,
                                'inactive': inactive or value.get('a') == 0})
                return
            hidden = inactive or value.get('visible') is False or value.get('opacity') == 0
            for key, child in value.items():
                scan(child, path + '/' + escape(key), node_id, hidden)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                scan(child, path + '/' + str(i), node_id, inactive)

    def visit(node_id, inactive=False):
        row = doc['nodes'][node_id]
        props = row['props']
        hidden = inactive or props.get('visible') is False or props.get('opacity') == 0
        base = '/nodes/' + escape(node_id) + '/props/'
        for key in ('fills', 'strokes', 'effects', 'vectorNetwork', 'textDecorationColor'):
            if key in props:
                scan(props[key], base + key, node_id, hidden)
        for key in ('fills', 'textDecorationColor'):
            if key in props.get('textRuns', {}):
                scan(props['textRuns'][key], base + 'textRuns/' + key, node_id, hidden)
        for child in row['children']:
            visit(child, hidden)

    visit(snapshot['rootId'])
    return {'schemaVersion': 1, 'sourceHash': digest(doc), 'entries': entries,
            'count': len(entries), 'note': 'Stored channels, not inferred semantic or raster coverage.'}


def coverage(snapshot, manifest):
    inventory = color_inventory(snapshot)
    if manifest.get('schemaVersion') != 1 or manifest.get('sourceHash') != inventory['sourceHash']:
        raise ValueError('manifest does not match complete source snapshot')
    expected = {e['path']: e for e in inventory['entries']}
    entries = manifest.get('entries')
    if not isinstance(entries, list):
        raise ValueError('manifest entries required')
    actual = {}
    errors = []
    for entry in entries:
        path = entry.get('path')
        parts(path)
        if path in actual:
            raise ValueError('duplicate manifest channel: ' + path)
        actual[path] = entry
        if not all(isinstance(entry.get(k), str) and entry[k].strip()
                   for k in ('role', 'reason', 'ruleId')):
            errors.append({'path': path, 'error': 'role/reason/ruleId required'})
        disposition = entry.get('disposition')
        if disposition not in ('change', 'preserve', 'ignore'):
            errors.append({'path': path, 'error': 'unknown disposition'})
        if disposition == 'ignore' and path in expected and not expected[path]['inactive']:
            errors.append({'path': path, 'error': 'visible channel cannot be silently ignored'})
        if disposition == 'change':
            target = entry.get('target')
            if not isinstance(target, dict) or not all(k in target for k in ('r', 'g', 'b')):
                errors.append({'path': path, 'error': 'target RGB required'})
            elif not all(type(target[k]) in (int, float) and math.isfinite(target[k])
                         and 0 <= target[k] <= 1 for k in ('r', 'g', 'b')):
                errors.append({'path': path, 'error': 'invalid target RGB'})
            elif path in expected and target_equal(target, expected[path]['source']):
                errors.append({'path': path, 'error': 'unchanged color needs an explicit preserve reason'})
            if not all(isinstance(entry.get(k), str) and entry[k].strip()
                       for k in ('recipeId', 'sceneId')):
                errors.append({'path': path, 'error': 'changed channel needs recipe and representative scene'})
    missing, extra = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
    return {'status': 'fail' if missing or extra or errors else 'pass',
            'sourceHash': inventory['sourceHash'], 'manifestHash': digest(manifest),
            'expected': len(expected), 'classified': len(expected.keys() & actual.keys()),
            'missingPaths': missing, 'extraPaths': extra, 'errors': errors,
            'dispositions': dict(Counter(e.get('disposition') for e in entries))}


def complete(before, after, manifest, policy, mapping=None):
    cover = coverage(before, manifest)
    source, actual = mapped_document(before, after, mapping)
    allowed, protected = policy_check(policy)
    guard = compare(before, after, policy, mapping)
    incomplete, invalid = [], []
    for path, change in allowed.items():
        if not equal(at(source, path), change['before']):
            invalid.append({'path': path, 'error': 'planned before differs from source baseline'})
        if not target_equal(at(actual, path), change['after']):
            incomplete.append({'path': path, 'actual': at(actual, path), 'target': change['after']})
    known_paths = {e['path'] for e in color_inventory(before)['entries']}
    for entry in manifest['entries']:
        path = entry['path']
        if path not in known_paths:
            continue
        disposition = entry.get('disposition')
        if disposition == 'change' and any(overlaps(path, p) for p in protected):
            invalid.append({'path': path, 'error': 'protected channel classified as change'})
        target = entry.get('target') if disposition == 'change' else at(source, path)
        if not target_equal(at(actual, path), target):
            incomplete.append({'path': path, 'actual': at(actual, path), 'target': target})
        # Keep intended changes tied to the predeclared exact allow-list, even if omitted in Figma.
        if disposition == 'change':
            from theme_audit import differences, assess_changes
            permission = assess_changes(differences(at(source, path), target, path), policy)
            if permission['status'] != 'pass':
                invalid.append({'path': path, 'error': 'target not authorized in policy'})
    return {'status': 'pass' if cover['status'] == guard['status'] == 'pass'
            and not incomplete and not invalid else 'fail',
            'coverage': cover, 'propertyGuard': guard, 'incompleteTargets': incomplete,
            'invalidPlan': invalid, 'actualHash': digest(actual),
            'note': 'Machine completion only; visual review and semantic mapping are still required.'}


def batch_plan(batch, max_operations=64, max_bytes=48000):
    if max_operations < 1 or max_bytes < 1024 or not isinstance(batch.get('operations'), list):
        raise ValueError('positive operation limit and byte limit >=1024 required')
    groups, current = [], []
    for op in batch['operations']:
        if set(op) != {'path', 'before', 'after'} or op['before'] == MISSING or op['after'] == MISSING:
            raise ValueError('batch planner supports atomic existing-property writes only')
        parts(op['path'])
        if any(overlaps(op['path'], prev['path']) for prev in batch['operations'][:sum(map(len, groups)) + len(current)]):
            raise ValueError('overlapping operations')
        trial = current + [op]
        payload = {'schemaVersion': 1, 'batchId': 'planned', 'operations': trial}
        if len(trial) > max_operations or len(canonical(payload).encode()) > max_bytes:
            if not current:
                raise ValueError('one atomic operation exceeds payload limit; cannot split it')
            groups.append(current)
            current = [op]
            if len(canonical({**payload, 'operations': current}).encode()) > max_bytes:
                raise ValueError('one atomic operation exceeds payload limit; cannot split it')
        else:
            current = trial
    if current:
        groups.append(current)
    prefix = batch.get('batchId', 'batch')
    return {'status': 'pass', 'operationCount': len(batch['operations']),
            'batches': [{'schemaVersion': 1, 'batchId': prefix + '-' + str(i), 'operations': ops}
                        for i, ops in enumerate(groups)],
            'note': 'Batch only within one phase and validated scene group; these are not write permissions.'}


MACHINE_RULES = {'source-unchanged', 'clone-allowed-differences', 'color-coverage', 'plan-complete',
                 'contrast-baseline', 'color-relations', 'visual-unit-coverage'}
VISUAL_RULES = {'kv-fit', 'theme-consistency', 'clarity', 'hierarchy', 'button-salience',
                'cta-salience', 'icon-clarity', 'readability', 'material-layers',
                'surface-discernibility', 'state-discernibility', 'control-family-consistency'}


def visual_units(source, manifest, registry, rules=None):
    """Require a primary visual unit for every inventoried color channel.

    Membership is authored from source evidence, never guessed from RGB/name.
    Ancestors are read dependencies, not extra write permission.
    """
    doc = snapshot_document(source)
    if registry.get('schemaVersion') != 1 or registry.get('sourceHash') != digest(doc):
        raise ValueError('visual units must bind the source snapshot')
    coverage_result = coverage(source, manifest)
    if coverage_result['status'] != 'pass':
        raise ValueError('complete classified manifest required before visual units')
    units = registry.get('units')
    if not isinstance(units, list) or not units:
        raise ValueError('nonempty visual units required')
    known = {e['path'] for e in manifest['entries']}
    assigned, indexed = {}, {}
    for unit in units:
        name = unit.get('id')
        if not isinstance(name, str) or not name.strip() or name in indexed:
            raise ValueError('missing/duplicate visual unit ID')
        if not isinstance(unit.get('basis'), str) or not unit['basis'].strip():
            raise ValueError('visual unit needs original structure/rendering evidence')
        for key in ('carrierPaths', 'dependencyNodeIds', 'reviewNodeIds', 'reviewRuleIds'):
            values = unit.get(key)
            if (not isinstance(values, list) or not values or
                    any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values)):
                raise ValueError('nonempty unique visual unit ' + key + ' required')
        if not set(unit['dependencyNodeIds']) <= doc['nodes'].keys():
            raise ValueError('missing visual unit dependency')
        if not set(unit['reviewNodeIds']) <= set(unit['dependencyNodeIds']):
            raise ValueError('visual review roots must belong to unit dependencies')
        dependencies = set(unit['dependencyNodeIds'])
        carrier_nodes = set()
        for path in unit['carrierPaths']:
            if path not in known or path in assigned:
                raise ValueError('unknown or multiply assigned visual carrier: ' + path)
            node = parts(path)[1]
            if node not in dependencies:
                raise ValueError('visual carrier outside its unit dependencies: ' + path)
            assigned[path] = name; carrier_nodes.add(node)
        for node in list(dependencies):
            parent = doc['nodes'][node]['parentId']
            while parent in doc['nodes']:
                dependencies.add(parent)
                parent = doc['nodes'][parent]['parentId']
        if rules is not None:
            for rule_id in unit['reviewRuleIds']:
                rule = rules.get(rule_id, {})
                if rule.get('kind') != 'visual' or not rule.get('applicable'):
                    raise ValueError('visual unit references absent/inapplicable visual rule')
                if not set(unit['reviewNodeIds']) <= set(rule['scopeNodeIds']):
                    raise ValueError('visual unit roots outside frozen visual rule scope')
        indexed[name] = {**unit, 'dependencies': sorted(dependencies),
                         'carrierNodeIds': sorted(carrier_nodes)}
    missing = sorted(known - assigned.keys())
    return {'status': 'fail' if missing else 'pass', 'missingCarrierPaths': missing,
            'unitCount': len(units), 'registryHash': digest(registry), 'units': indexed}


def affected_units(source, manifest, registry, relations, frozen, changes):
    """Compute the relation closure to recheck after any local correction."""
    result = visual_units(source, manifest, registry)
    if result['status'] != 'pass':
        return result
    changed = changes.get('changedPaths')
    if (not isinstance(changed, list) or not changed or
            any(not isinstance(p, str) for p in changed) or len(set(changed)) != len(changed)):
        raise ValueError('unique source-namespace changedPaths required')
    nodes = snapshot_document(source)['nodes']
    for path in changed:
        tokens = parts(path)
        if len(tokens) < 3 or tokens[0] != 'nodes' or tokens[1] not in nodes or tokens[2] != 'props':
            raise ValueError('changed path must identify an existing source node property')
    units = result['units']
    owner = {p: name for name, u in units.items() for p in u['carrierPaths']}
    node_owners = {}
    for name, unit in units.items():
        for node in set(unit['carrierNodeIds']) | set(unit['reviewNodeIds']):
            node_owners.setdefault(node, set()).add(name)
    pairs = frozen['pairs'] if isinstance(frozen, dict) else frozen
    orders = frozen.get('emphasisOrders', []) if isinstance(frozen, dict) else []
    edges = []
    for group in relations['groups']:
        if not set(group['paths']) <= owner.keys():
            raise ValueError('color relation includes an unregistered carrier')
        edges.append(('color', group['id'], {owner[p] for p in group['paths']}))
    pair_edges = {}
    for pair in pairs:
        if not set(pair['nodeIds']) <= nodes.keys():
            raise ValueError('contrast pair contains missing source node')
        members = set().union(*(node_owners.get(n, set()) for n in pair['nodeIds']))
        if not members:
            raise ValueError('contrast pair has no registered visual unit')
        pair_edges[pair['id']] = members
        edges.append(('contrast', pair['id'], members))
    for order in orders:
        members = pair_edges[order['strongerPairId']] | pair_edges[order['weakerPairId']]
        edges.append(('order', order['id'], members))
    affected = {name for name, u in units.items()
                if any(parts(p)[1] in u['dependencies'] for p in changed)}
    pending = True
    while pending:
        before = set(affected)
        for _, _, members in edges:
            if members & affected:
                affected.update(members)
        pending = before != affected
    return {'status': 'pass', 'registryHash': result['registryHash'],
            'affectedUnitIds': sorted(affected),
            'colorRelationIds': sorted(i for k, i, m in edges if k == 'color' and m & affected),
            'contrastPairIds': sorted(i for k, i, m in edges if k == 'contrast' and m & affected),
            'emphasisOrderIds': sorted(i for k, i, m in edges if k == 'order' and m & affected),
            'requiredReviewRuleIds': sorted({r for n in affected for r in units[n]['reviewRuleIds']}),
            'dependencyNodeIds': sorted({d for n in affected for d in units[n]['dependencies']}),
            'note': 'Invalidates affected gates; includes read-only/protected members, never grants writes.'}


def verify_rule(source, actual, rule):
    verifier = rule.get('verifier', {})
    kind = verifier.get('type')
    failures = []
    if kind in ('preserve-values', 'preserve-hsv'):
        paths = verifier.get('paths')
        if not isinstance(paths, list) or not paths or len(set(paths)) != len(paths):
            raise ValueError('nonempty unique verifier paths required')
        channels = verifier.get('channels')
        if kind == 'preserve-hsv' and (not isinstance(channels, list) or not channels
                                      or not set(channels) <= {'s', 'v', 'a'}):
            raise ValueError('HSV verifier channels must be s/v/a')
        for path in paths:
            baseline, value = at(source, path), at(actual, path)
            if baseline == MISSING or value == MISSING:
                failures.append({'path': path, 'error': 'missing value'})
                continue
            if kind == 'preserve-values':
                valid = equal(baseline, value)
            else:
                def hsv(color):
                    if not isinstance(color, dict) or not all(k in color for k in ('r', 'g', 'b')):
                        raise ValueError('HSV verifier requires RGB color objects')
                    h, s, v = colorsys.rgb_to_hsv(color['r'], color['g'], color['b'])
                    return {'s': s, 'v': v, 'a': color.get('a', 1)}
                left, right = hsv(baseline), hsv(value)
                valid = all(target_equal(left[c], right[c]) for c in channels)
            if not valid:
                failures.append({'path': path, 'source': baseline, 'actual': value})
    elif kind == 'target-values':
        targets = verifier.get('targets')
        if not isinstance(targets, list) or not targets:
            raise ValueError('nonempty declared target values required')
        for target in targets:
            path = target['path']; value = at(actual, path)
            if value == MISSING or not target_equal(value, target['expected']):
                failures.append({'path': path, 'actual': value, 'expected': target['expected']})
    else:
        raise ValueError('unsupported machine verifier: ' + str(kind))
    return {'status': 'fail' if failures else 'pass', 'failures': failures}


def finalize(spec):
    """Recompute machine checks and match fresh scene gates to the frozen rule ledger."""
    source = read_json(spec['sourceBefore'])
    source_now = read_json(spec['sourceNow'])
    actual = read_json(spec['cloneNow'])
    plan = read_json(spec['manifest'])
    policy = read_json(spec['policy'])
    mapping = read_json(spec['nodeMap']) if spec.get('nodeMap') else None
    ledger = read_json(spec['ruleLedger'])
    if ledger.get('schemaVersion') != 1 or not isinstance(ledger.get('rules'), list):
        raise ValueError('rule ledger required')
    rules = {}
    source_ids = set(snapshot_document(source)['nodes'])
    for rule in ledger['rules']:
        name = rule.get('id')
        if not isinstance(name, str) or not name or name in rules:
            raise ValueError('missing/duplicate ledger rule ID')
        if rule.get('kind') not in ('machine', 'visual') or type(rule.get('applicable')) is not bool:
            raise ValueError('rule kind and explicit applicability required')
        if not all(isinstance(rule.get(k), str) and rule[k].strip() for k in ('acceptance', 'source')):
            raise ValueError('rule source and concrete acceptance required')
        if not rule['applicable'] and not rule.get('notApplicableEvidence'):
            raise ValueError('not-applicable needs predeclared evidence')
        if rule['kind'] == 'visual' and rule['applicable']:
            scope = rule.get('scopeNodeIds')
            if not isinstance(scope, list) or not scope or not set(scope) <= source_ids:
                raise ValueError('visual rule requires existing source scopeNodeIds')
        rules[name] = rule
    if not (MACHINE_RULES | VISUAL_RULES) <= rules.keys():
        raise ValueError('baseline rules cannot be omitted')
    for name in MACHINE_RULES:
        if rules[name]['kind'] != 'machine' or not rules[name]['applicable']:
            raise ValueError('baseline machine rules cannot be skipped')
    for name in VISUAL_RULES:
        if rules[name]['kind'] != 'visual':
            raise ValueError('baseline visual rule kind mismatch')
    for name in ('kv-fit', 'theme-consistency', 'clarity', 'hierarchy', 'readability'):
        if not rules[name]['applicable']:
            raise ValueError('whole-page baseline visual rule cannot be skipped')
    ledger_hash = digest(ledger)
    if plan.get('ruleLedgerHash') != ledger_hash:
        raise ValueError('manifest must bind the frozen rule ledger')
    if any(entry['ruleId'] not in rules for entry in plan['entries']):
        raise ValueError('manifest references an undeclared rule')
    done = complete(source, actual, plan, policy, mapping)
    source_guard = compare(source, source_now, {'schemaVersion': 1, 'allowedChanges': [], 'protectedPaths': []})
    machine = {'source-unchanged': source_guard, 'clone-allowed-differences': done['propertyGuard'],
               'color-coverage': done['coverage'], 'plan-complete': done}
    relation_rule = rules['color-relations'].get('verifier', {})
    if not spec.get('colorRelations') or relation_rule.get('type') != 'color-relations':
        raise ValueError('frozen colorRelations are required, including after local corrections')
    relations = read_json(spec['colorRelations'])
    if relation_rule.get('groupsHash') != digest(relations):
        raise ValueError('color relations differ from frozen groups')
    if not relations.get('groups') and not relation_rule.get('emptyEvidence'):
        raise ValueError('empty color relations require predeclared source evidence')
    machine['color-relations'] = (color_relations(source, actual, relations, mapping)
                                  if relations.get('groups') else
                                  {'status': 'pass', 'groupCount': 0,
                                   'notApplicableEvidence': relation_rule['emptyEvidence']})
    source_doc, actual_doc = mapped_document(source, actual, mapping)
    unit_rule = rules['visual-unit-coverage'].get('verifier', {})
    if not spec.get('visualUnits') or unit_rule.get('type') != 'visual-unit-coverage':
        raise ValueError('frozen visualUnits are required for full and local runs')
    registry = read_json(spec['visualUnits'])
    if unit_rule.get('registryHash') != digest(registry):
        raise ValueError('visual units differ from the frozen registry')
    unit_result = visual_units(source, plan, registry, rules)
    machine['visual-unit-coverage'] = unit_result
    contrast_rule = rules['contrast-baseline'].get('verifier', {})
    if contrast_rule.get('type') != 'contrast-baseline' or not spec.get('contrastSamples'):
        raise ValueError('frozen contrast relationships and fresh contrastSamples required')
    machine['contrast-baseline'] = compare_contrast(
        source_doc, actual_doc, read_json(spec['contrastSamples']), contrast_rule.get('relationships'),
        contrast_rule.get('emphasisOrders', []))
    for rule in rules.values():
        if rule['kind'] == 'machine' and rule['applicable'] and rule['id'] not in machine:
            machine[rule['id']] = verify_rule(source_doc, actual_doc, rule)
    reviewed, gate_results, unit_reviews = {}, [], set()
    errors = []
    whole_page_reviewed = False
    family_rule = rules['control-family-consistency']
    family_compared = not family_rule['applicable']
    for scene in spec.get('visualScenes', []):
        scene_spec, gate = read_json(scene['spec']), read_json(scene['gate'])
        if scene_spec.get('recipe', {}).get('ruleLedgerHash') != ledger_hash:
            errors.append({'sceneId': scene_spec.get('sceneId'), 'error': 'scene uses stale or missing rules'})
            continue
        state = scene_state(actual, scene_spec)
        result = check_gate(state, gate)
        gate_results.append(result)
        if result['status'] != 'pass':
            continue
        context = set(state['payload']['context'])
        requirements = {r['id']: r for r in scene_spec['reviewRequirements']}
        family_requirement = requirements.get('control-family-consistency', {})
        family_nodes = {mapping.get(n, n) if mapping else n
                        for n in family_rule.get('scopeNodeIds', [])}
        if (family_rule['applicable'] and
                family_requirement.get('acceptance') == family_rule['acceptance'] and
                family_nodes <= set(family_requirement.get('nodeIds', []))):
            family_compared = True
        for unit_id, unit in unit_result['units'].items():
            clone_ids = lambda ids: {mapping.get(n, n) if mapping else n for n in ids}
            if (clone_ids(unit['dependencies']) <= context and
                    all(rule_id in requirements and
                        requirements[rule_id]['acceptance'] == rules[rule_id]['acceptance'] and
                        clone_ids(unit['reviewNodeIds']) <= set(requirements[rule_id]['nodeIds'])
                        for rule_id in unit['reviewRuleIds'])):
                unit_reviews.add(unit_id)
        if scene_spec.get('reviewScope') == 'whole-page':
            if set(state['payload']['context']) != set(snapshot_document(actual)['nodes']):
                errors.append({'sceneId': scene_spec['sceneId'], 'error': 'whole-page scene has incomplete context'})
            elif any(r['id'] == 'hierarchy' and actual['rootId'] in r['nodeIds']
                     for r in scene_spec['reviewRequirements']):
                whole_page_reviewed = True
        for requirement in scene_spec['reviewRequirements']:
            name = requirement['id']
            rule = rules.get(name)
            if not rule or rule['kind'] != 'visual' or not rule['applicable'] or requirement['acceptance'] != rule['acceptance']:
                errors.append({'sceneId': scene_spec['sceneId'], 'ruleId': name, 'error': 'review differs from frozen acceptance'})
            else:
                reviewed.setdefault(name, set()).update(requirement['nodeIds'])
    missing = sorted(name for name, rule in rules.items()
                     if rule['kind'] == 'visual' and rule['applicable'] and name not in reviewed)
    uncovered = {name: sorted({mapping.get(n, n) if mapping else n for n in rule['scopeNodeIds']}
                             - reviewed.get(name, set()))
                 for name, rule in rules.items() if rule['kind'] == 'visual' and rule['applicable']}
    uncovered = {name: nodes for name, nodes in uncovered.items() if nodes}
    if not whole_page_reviewed:
        errors.append({'error': 'fresh whole-page hierarchy review required; local passes are insufficient'})
    unreviewed_units = sorted(unit_result['units'].keys() - unit_reviews)
    if unreviewed_units:
        errors.append({'error': 'visual unit lacks a fresh complete-context review',
                       'unitIds': unreviewed_units})
    if not family_compared:
        errors.append({'error': 'fresh cross-region control-family comparison required; separate local passes are insufficient'})
    passed = all(v['status'] == 'pass' for v in machine.values()) and all(g['status'] == 'pass' for g in gate_results)
    return {'status': 'pass' if passed and not missing and not uncovered and not errors else 'fail',
            'ruleLedgerHash': ledger_hash, 'machineChecks': machine, 'visualGates': gate_results,
            'missingVisualRules': missing, 'uncoveredVisualNodes': uncovered, 'errors': errors,
            'unreviewedVisualUnits': unreviewed_units,
            'note': 'Verifies recorded coverage and evidence freshness, not the truth of an artistic judgment.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    inv = subs.add_parser('inventory'); inv.add_argument('source')
    cov = subs.add_parser('coverage'); cov.add_argument('source'); cov.add_argument('manifest')
    done = subs.add_parser('complete')
    for field in ('source', 'actual', 'manifest', 'policy'):
        done.add_argument(field)
    done.add_argument('--map', dest='mapping')
    batch = subs.add_parser('batch-plan'); batch.add_argument('batch')
    batch.add_argument('--max-operations', type=int, default=64)
    batch.add_argument('--max-bytes', type=int, default=48000)
    final = subs.add_parser('finalize'); final.add_argument('spec')
    impact = subs.add_parser('impact', help='compute visual-unit closure before a local correction')
    for field in ('source', 'manifest', 'registry', 'relations', 'relationships', 'changes'):
        impact.add_argument(field)
    for sub in (inv, cov, done, batch, final, impact):
        sub.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'inventory':
            result = color_inventory(read_json(args.source))
        elif args.command == 'coverage':
            result = coverage(read_json(args.source), read_json(args.manifest))
        elif args.command == 'complete':
            result = complete(read_json(args.source), read_json(args.actual), read_json(args.manifest),
                              read_json(args.policy), read_json(args.mapping) if args.mapping else None)
        elif args.command == 'batch-plan':
            result = batch_plan(read_json(args.batch), args.max_operations, args.max_bytes)
        elif args.command == 'impact':
            result = affected_units(*(read_json(getattr(args, field)) for field in
                                      ('source', 'manifest', 'registry', 'relations', 'relationships', 'changes')))
        else:
            result = finalize(read_json(args.spec))
        save_json(args.out, result)
        print(canonical({'status': result.get('status', 'recorded'), 'output': args.out}))
        return 0 if result.get('status', 'pass') == 'pass' else 1
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        save_json(args.out, {'status': 'error', 'error': str(exc)})
        print(canonical({'status': 'error', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())

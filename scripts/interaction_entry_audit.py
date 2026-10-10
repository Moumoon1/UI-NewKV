"""Check source-authored entry obligations independently of target color roles.

This checks recorded coverage, not whether a human correctly recognized every
entry. Native host review and contrast_audit remain mandatory.
"""
import math

from theme_audit import digest, parts, snapshot_document


def inspect(source, manifest, ledger):
    # Lazy import keeps execution_audit's finalizer able to call this module.
    from execution_audit import color_inventory

    doc = snapshot_document(source)
    nodes = doc['nodes']
    inventory = ledger.get('sourceInteractions')
    errors = []

    def fail(message):
        errors.append(message)

    def within(node, root):
        seen = set()
        while node in nodes and node not in seen:
            if node == root:
                return True
            seen.add(node)
            node = nodes[node]['parentId']
        return False

    def visible(node):
        seen = set()
        while node in nodes and node not in seen:
            seen.add(node)
            props = nodes[node]['props']
            if props.get('visible') is False or props.get('opacity', 1) == 0:
                return False
            node = nodes[node]['parentId']
        return True

    if (not isinstance(inventory, dict) or inventory.get('schemaVersion') != 1 or
            inventory.get('sourceHash') != digest(doc)):
        return {'status': 'fail', 'errors': ['source-bound sourceInteractions inventory required']}
    if not inventory.get('sourceReviewEvidence'):
        fail('whole-source review evidence required, including icon-only entries')
    entries = inventory.get('entries')
    exclusions = inventory.get('nonInteractiveText')
    if not isinstance(entries, list) or not isinstance(exclusions, list):
        return {'status': 'fail', 'errors': ['entries and nonInteractiveText lists required']}
    source_colors = {e['path']: e for e in color_inventory(source)['entries'] if not e['inactive']}
    target_colors = {e['path']: e for e in manifest.get('entries', [])}
    rules = {r['id']: r for r in ledger.get('rules', [])}
    relationships = rules.get('contrast-baseline', {}).get('verifier', {}).get('relationships', [])
    pairs = {p['id']: p for p in relationships}
    texts = {n for n, row in nodes.items() if row['props'].get('type') == 'TEXT' and visible(n)}
    covered_text = set()
    roots = set()
    used_pairs = set()

    for entry in entries:
        if not isinstance(entry, dict):
            fail('each source entry must be an object')
            continue
        root, host = entry.get('rootId'), entry.get('hostId')
        if root not in nodes or host not in nodes or root == host or root in roots:
            fail('entry needs unique existing root and distinct host')
            continue
        roots.add(root)
        if not visible(root) or not visible(host):
            fail(root + ': entry and host must be source-visible')
        if entry.get('priority') not in {'primary', 'secondary', 'tertiary'} or not entry.get('sourceEvidence'):
            fail(root + ': original priority and source evidence required')
        affordance = entry.get('affordance')
        if affordance not in {'filled', 'outline', 'text', 'icon'}:
            fail(root + ': original affordance must be explicit')
        content = entry.get('textNodeIds', [])
        if (not isinstance(content, list) or len(content) != len(set(content)) or
                not set(content) <= texts or covered_text & set(content) or
                any(not within(n, root) for n in content)):
            fail(root + ': missing, duplicate or unrelated entry text')
            continue
        covered_text.update(content)
        paths = entry.get('carrierPaths', [])
        if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
            fail(root + ': actual affordance carrier paths required')
            continue
        carriers = set()
        for path in paths:
            source_color = source_colors.get(path)
            target = target_colors.get(path, {})
            if not source_color or not within(source_color['nodeId'], root):
                fail(root + ': carrier is not a visible source channel inside entry')
                continue
            node = source_color['nodeId']
            carriers.add(node)
            segments = parts(path)
            kind = nodes[node]['props'].get('type')
            if affordance in {'filled', 'outline'}:
                channel = 'fills' if affordance == 'filled' else 'strokes'
                if kind == 'TEXT' or len(segments) < 4 or segments[3] != channel:
                    fail(root + ': body/boundary cannot be replaced by text or effects')
                prefixes = ('button.', 'cta.', 'interaction.', 'protected-hero-controls')
            else:
                prefixes = ('button.', 'cta.', 'interaction.', 'icon.', 'text.', 'protected-hero-controls')
            if not str(target.get('role', '')).startswith(prefixes):
                fail(root + ': functional carrier reclassified as non-interactive decoration/surface')
        if affordance in {'filled', 'outline'}:
            channel = 'fills' if affordance == 'filled' else 'strokes'
            required_paths = {p for p, color in source_colors.items()
                              if color['nodeId'] in carriers and parts(p)[3] == channel}
            if not required_paths <= set(paths):
                fail(root + ': all visible body paints/stops required; a highlight alone is insufficient')
        pair_id = entry.get('boundaryPairId')
        pair = pairs.get(pair_id, {})
        if not pair_id or pair_id in used_pairs:
            fail(root + ': independent boundary relationship required per entry')
        used_pairs.add(pair_id)
        if (pair.get('kind') not in {'button', 'icon', 'text'} or
                (affordance in {'filled', 'outline'} and pair.get('kind') != 'button') or
                not carriers or not carriers | {host} <= set(pair.get('nodeIds', []))):
            fail(root + ': relationship must compare affordance carriers with real host, not label alone')
        limits = [(pair.get('minimumContrast'), 1), (pair.get('minimumDeltaE'), 0)]
        if not any(type(v) in (int, float) and math.isfinite(v) and v > floor for v, floor in limits):
            fail(root + ': nonzero authored boundary threshold required')
        if not pair.get('sampleIds') or not entry.get('boundaryBasis'):
            fail(root + ': source-based boundary acceptance and samples required')
        hosts = {host}
        if affordance in {'filled', 'outline'}:
            adjacent = entry.get('adjacentHostIds')
            comparisons = entry.get('boundaryComparisons')
            if (not isinstance(adjacent, list) or not adjacent or
                    any(not isinstance(h, str) or h not in nodes or h == root or not visible(h)
                        for h in adjacent) or len(set(adjacent)) != len(adjacent) or
                    host not in adjacent or not entry.get('adjacentHostEvidence')):
                fail(root + ': explicit review of all adjacent visible hosts required')
                adjacent = [host]
            hosts = set(adjacent)
            if not isinstance(comparisons, list):
                fail(root + ': boundary comparisons required for every adjacent host')
                comparisons = []
            reviewed_hosts = []
            gradient = any(paint.get('type', '').startswith('GRADIENT')
                           for n in carriers for paint in nodes[n]['props'].get(channel, []))
            for comparison in comparisons:
                if not isinstance(comparison, dict):
                    fail(root + ': boundary comparison must be an object')
                    continue
                neighbor, relationship = comparison.get('hostId'), comparison.get('pairId')
                if not isinstance(neighbor, str) or not isinstance(relationship, str):
                    fail(root + ': boundary comparison needs host and pair IDs')
                    continue
                candidate = pairs.get(relationship, {})
                responsibilities = comparison.get('sampleResponsibilities', {})
                if neighbor not in hosts or neighbor in reviewed_hosts:
                    fail(root + ': boundary comparison host missing, duplicate or unrelated')
                reviewed_hosts.append(neighbor)
                if ((neighbor == host and relationship != pair_id) or
                        (neighbor != host and relationship in used_pairs) or
                        not relationship or candidate.get('kind') != 'button' or
                        not carriers | {neighbor} <= set(candidate.get('nodeIds', []))):
                    fail(root + ': independent body-to-neighbor relationship required')
                used_pairs.add(relationship)
                limits = [(candidate.get('minimumContrast'), 1), (candidate.get('minimumDeltaE'), 0)]
                if not any(type(v) in (int, float) and math.isfinite(v) and v > floor for v, floor in limits):
                    fail(root + ': adjacent boundary needs authored acceptance threshold')
                required = {'body', 'edge'} if affordance == 'filled' else {'edge'}
                if gradient and affordance == 'filled':
                    required.add('weakest-body')
                if (not isinstance(responsibilities, dict) or
                        any(not isinstance(value, str) for value in responsibilities.values()) or
                        set(responsibilities) != set(candidate.get('sampleIds', [])) or
                        not required <= set(responsibilities.values()) or
                        not comparison.get('basis')):
                    fail(root + ': boundary samples must cover body, edge and gradient weakest-body as applicable')
            if set(reviewed_hosts) != hosts:
                fail(root + ': missing boundary comparison for an adjacent host')
            review_id = entry.get('visualReviewRuleId')
            review = rules.get(review_id, {})
            if (review_id != 'entry-review:' + root or review.get('kind') != 'visual' or
                    review.get('applicable') is not True or not review.get('acceptance') or
                    not {root} | hosts <= set(review.get('scopeNodeIds', []))):
                fail(root + ': dedicated local visual review rule required for entry and adjacent hosts')
        for name in ('button-salience', 'hierarchy'):
            rule = rules.get(name, {})
            if (rule.get('kind') != 'visual' or rule.get('applicable') is not True or
                    not {root} | hosts <= set(rule.get('scopeNodeIds', []))):
                fail(root + ': entry and host omitted from ' + name)

    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            fail('each static text exclusion must be an object')
            continue
        ids = exclusion.get('nodeIds', [])
        if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or
                not set(ids) <= texts or covered_text & set(ids) or not exclusion.get('reason')):
            fail('non-interactive text exclusion needs unique source text and reviewed reason')
            continue
        covered_text.update(ids)
    if covered_text != texts:
        fail('visible source text missing interaction review: ' + ', '.join(sorted(texts - covered_text)))
    return {'status': 'fail' if errors else 'pass', 'entryCount': len(entries), 'errors': errors,
            'note': 'Recorded source obligations only; semantic truth and native hierarchy review are not automated.'}

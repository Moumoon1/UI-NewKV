from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from execution_audit import color_inventory
from surface_system_audit import discover, inspect, _boundary_group_geometry_valid, _box
from theme_audit import digest, snapshot_document


class SurfaceSystemAuditTests(unittest.TestCase):
    def test_group_wrapper_origin_is_not_counted_twice_for_child_box(self):
        doc = {'nodes': {
            'root': {'parentId': None, 'props': {'type': 'FRAME', 'x': 0, 'y': 0,
                                              'width': 400, 'height': 800}},
            'group': {'parentId': 'root', 'props': {'type': 'GROUP', 'x': 20, 'y': 40,
                                                  'width': 100, 'height': 100}},
            'child': {'parentId': 'group', 'props': {'type': 'RECTANGLE', 'x': 25, 'y': 50,
                                                  'width': 40, 'height': 30}}}}
        self.assertEqual(_box(doc, 'child', 'root'), (25, 50, 65, 80))
        self.assertEqual(_box(doc, 'group', 'root'), (20, 40, 120, 140))
        doc['nodes']['group']['props']['type'] = 'FRAME'
        self.assertEqual(_box(doc, 'child', 'root'), (45, 90, 85, 120))

    def test_root_edge_requires_nearest_native_pixels_and_explicit_basis(self):
        candidate = {'kind': 'clip-edge', 'rootLocalEdge': {
            'side': 'right', 'coordinate': 400, 'span': [0, 800]}}
        group = {'nativePixels': [400, 800], 'xy': [[398, 120], [399, 120]],
                 'samplingMode': 'root-edge-inward',
                 'samplingBasis': 'Exterior is outside the clipped native PNG.'}
        self.assertTrue(_boundary_group_geometry_valid(candidate, group, (0, 0, 400, 800)))
        for wrong in ([[1, 120], [2, 120]], [[399, 120], [401, 120]]):
            self.assertFalse(_boundary_group_geometry_valid(
                candidate, {**group, 'xy': wrong}, (0, 0, 400, 800)))
        self.assertFalse(_boundary_group_geometry_valid(
            candidate, {**group, 'samplingBasis': ''}, (0, 0, 400, 800)))

    def test_fractional_root_bottom_uses_available_inward_pixels(self):
        candidate = {'kind': 'clip-edge', 'rootLocalEdge': {
            'side': 'bottom', 'coordinate': 799.5, 'span': [0, 400]}}
        group = {'nativePixels': [400, 800], 'xy': [[200, 797], [200, 798]],
                 'samplingMode': 'root-edge-inward',
                 'samplingBasis': 'The last pixel is partially clipped; use two fully covered inward rows.'}
        self.assertTrue(_boundary_group_geometry_valid(candidate, group, (0, 0, 400, 800)))
        group['xy'] = [[200, 798], [200, 799]]
        self.assertFalse(_boundary_group_geometry_valid(candidate, group, (0, 0, 400, 800)))

    def test_root_edge_mode_cannot_replace_internal_cross_boundary_sampling(self):
        candidate = {'kind': 'clip-edge', 'rootLocalEdge': {
            'side': 'right', 'coordinate': 380, 'span': [100, 220]}}
        group = {'nativePixels': [400, 800], 'xy': [[378, 130], [379, 130]],
                 'samplingMode': 'root-edge-inward', 'samplingBasis': 'Claimed edge.'}
        self.assertFalse(_boundary_group_geometry_valid(candidate, group, (0, 0, 400, 800)))
        candidate['rootLocalEdge'] = {'side': 'bottom', 'coordinate': 800, 'span': [0, 400]}
        group['xy'] = [[200, 798], [200, 799]]
        self.assertTrue(_boundary_group_geometry_valid(candidate, group, (0, 0, 400, 800)))

    def fixture(self, clipped=False, terminal=False, inner=False,
                inner_box=(20, 70, 80, 12)):
        def solid(rgb):
            return {'type': 'SOLID', 'visible': True, 'opacity': 1,
                    'color': dict(zip('rgb', rgb))}

        children = ['h5'] if terminal else ['income', 'task']
        nodes = [{'id': 'root', 'parentId': None, 'children': children,
                  'props': {'type': 'FRAME', 'name': 'Root', 'visible': True,
                            'x': 0, 'y': 0, 'width': 400, 'height': 800,
                            'fills': [solid((.93, .85, .70))]}}]
        parent = 'root'
        if terminal:
            nodes.append({'id': 'h5', 'parentId': 'root', 'children': ['income', 'task'],
                          'props': {'type': 'FRAME', 'name': 'H5', 'visible': True,
                                    'x': 0, 'y': 0, 'width': 400, 'height': 770,
                                    'fills': [solid((.93, .85, .70))]}})
            parent = 'h5'
        income_children = ([] + (['clip-child'] if clipped else []) +
                           (['inner-container'] if inner else []))
        nodes.extend([
            {'id': 'income', 'parentId': parent, 'children': income_children,
             'props': {'type': 'FRAME', 'name': 'Income', 'visible': True,
                       'clipsContent': clipped, 'x': 20, 'y': 100, 'width': 360, 'height': 120,
                       'fills': [solid((1, .98, .92))]}},
            {'id': 'task', 'parentId': parent, 'children': [],
             'props': {'type': 'FRAME', 'name': 'Task', 'visible': True,
                       'x': 20, 'y': 250, 'width': 360, 'height': 180,
                       'fills': [solid((1, .98, .92))]}},
        ])
        if clipped:
            nodes.append({'id': 'clip-child', 'parentId': 'income', 'children': [],
                          'props': {'type': 'RECTANGLE', 'name': 'Entry carrier', 'visible': True,
                                    'x': 300, 'y': 10, 'width': 100, 'height': 50,
                                    'fills': [solid((.8, .5, .2))]}})
        if inner:
            inner_x, inner_y, inner_width, inner_height = inner_box
            nodes.append({'id': 'inner-container', 'parentId': 'income', 'children': [],
                          'props': {'type': 'RECTANGLE', 'name': 'Inner grouping surface',
                                    'visible': True, 'x': inner_x, 'y': inner_y,
                                    'width': inner_width, 'height': inner_height,
                                    'fills': [solid((.96, .93, .85))]}})
        source = {'schemaVersion': 1, 'rootId': 'root', 'errors': [], 'nodes': nodes}
        actual = deepcopy(source)
        inventory = color_inventory(source)
        entries = []
        for row in inventory['entries']:
            entries.append({'path': row['path'], 'nodeId': row['nodeId'],
                            'role': 'surface', 'reason': 'Fixture', 'ruleId': 'clarity',
                            'disposition': 'preserve'})

        paths = {row['nodeId']: row['path'] for row in inventory['entries']
                 if '/props/fills/' in row['path']}
        surfaces = [{
            'id': 'root-surface', 'nodeId': 'root', 'kind': 'page',
            'carrierPaths': [paths['root']], 'stableRepresentativePath': paths['root'],
            'basis': 'Root page background.'
        }]
        if terminal:
            surfaces.append({
                'id': 'h5-surface', 'nodeId': 'h5', 'kind': 'page',
                'carrierPaths': [paths['h5']], 'stableRepresentativePath': paths['h5'],
                'hostSurfaceId': 'root-surface', 'boundaryRelationshipId': 'h5-root',
                'basis': 'H5 surface inside root.'})
            card_host = 'h5-surface'
        else:
            card_host = 'root-surface'
        for node_id in ('income', 'task'):
            surfaces.append({
                'id': node_id + '-surface', 'nodeId': node_id, 'kind': 'card',
                'carrierPaths': [paths[node_id]], 'stableRepresentativePath': paths[node_id],
                'hostSurfaceId': card_host, 'boundaryRelationshipId': node_id + '-host',
                'basis': 'Peer card stable base.'})
        plan = {'schemaVersion': 1, 'sourceHash': inventory['sourceHash'],
                'surfaces': surfaces,
                'cardBaseGroups': [{'id': 'peer-cards',
                                    'surfaceIds': ['income-surface', 'task-surface'],
                                    'additionalDeltaE': 1,
                                    'basis': 'Source cards use the same stable base.'}],
                'boundaryReviews': []}
        manifest = {'schemaVersion': 1, 'sourceHash': inventory['sourceHash'],
                    'themeTransition': 'light-to-light', 'entries': entries,
                    'surfaceSystemPlan': plan}
        host_id = 'h5' if terminal else 'root'
        relationships = [
            {'id': 'income-host', 'kind': 'surface', 'nodeIds': ['income', host_id],
             'sampleIds': ['income'], 'minimumDeltaE': 3},
            {'id': 'task-host', 'kind': 'surface', 'nodeIds': ['task', host_id],
             'sampleIds': ['task'], 'minimumDeltaE': 3},
        ]
        if terminal:
            relationships.append({'id': 'h5-root', 'kind': 'surface',
                                  'nodeIds': ['h5', 'root'], 'sampleIds': ['h5'],
                                  'minimumDeltaE': 3})
        rules = {'contrast-baseline': {'verifier': {'relationships': relationships}}}
        return source, actual, manifest, rules, paths

    def proxy_fixture(self):
        source, actual, manifest, rules, paths = self.fixture(inner=True)
        surface = {'id': 'proxy-surface', 'nodeId': 'inner-container',
                   'carrierPaths': [paths['inner-container']],
                   'basis': 'Source layer borrows its local background appearance.'}
        manifest['surfaceSystemPlan']['surfaces'].append(surface)
        surface.update(kind='proxy', hostSurfaceId='income-surface',
                       appearanceGroupIds=['host-proxy'], visualReviewRuleId='host-proxy-review')
        for entry in manifest['entries']:
            if entry['nodeId'] == 'inner-container': entry['role'] = 'surface.proxy'
        rules['host-proxy-pixels'] = {'kind': 'machine', 'applicable': True,
            'verifier': {'type': 'displayed-relations', 'groups': [{
                'id': 'host-proxy', 'relationType': 'surface-linked-appearance',
                'basis': 'Source layer visually continues its local background.',
                'targetBasis': 'surface-recipe', 'anchorPath': paths['income'],
                'carrierPaths': [paths['inner-container']], 'anchorPointIndex': 0,
                'nodeIds': ['income', 'inner-container'], 'xy': [[0, 0], [1, 0]],
                'nativePixels': [2, 1]}]}}
        rules['host-proxy-review'] = {'kind': 'visual', 'applicable': True,
            'scopeNodeIds': ['income', 'inner-container'],
            'acceptance': 'Native complete unit preserves its source background dependency.'}
        return source, actual, manifest, rules, paths, surface

    def test_background_dependency_has_no_shape_specific_requirement(self):
        source, actual, manifest, rules, _, _ = self.proxy_fixture()
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'pass')

    def test_proxy_dependencies_cover_each_real_host(self):
        source, actual, manifest, rules, paths, surface = self.proxy_fixture()
        surface['hostSurfaceIds'] = ['income-surface', 'root-surface']
        rules['host-proxy-review']['scopeNodeIds'].append('root')
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'fail')
        group = deepcopy(rules['host-proxy-pixels']['verifier']['groups'][0])
        group.update(id='second-host-proxy', anchorPath=paths['root'],
                     nodeIds=['root', 'inner-container'])
        rules['host-proxy-pixels']['verifier']['groups'].append(group)
        surface['appearanceGroupIds'].append('second-host-proxy')
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'pass')

    def test_proxy_cannot_be_reclassified_as_decorative_emphasis(self):
        source, actual, manifest, rules, _, surface = self.proxy_fixture()
        surface['kind'] = 'decoration'
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'fail')

    def test_proxy_dependency_rejects_missing_wrong_or_independent_binding(self):
        for defect in ('missing', 'wrong-host', 'wrong-anchor', 'scheme-anchor', 'missing-path', 'visual'):
            with self.subTest(defect=defect):
                source, actual, manifest, rules, paths, surface = self.proxy_fixture()
                group = rules['host-proxy-pixels']['verifier']['groups'][0]
                if defect == 'missing': surface.pop('appearanceGroupIds')
                if defect == 'wrong-host': surface['hostSurfaceId'] = 'missing'
                if defect == 'wrong-anchor': group['anchorPath'] = paths['task']
                if defect == 'scheme-anchor':
                    next(e for e in manifest['entries'] if e['nodeId'] == 'inner-container')['anchorId'] = 'icon'
                if defect == 'missing-path': group['carrierPaths'] = []
                if defect == 'visual': rules.pop('host-proxy-review')
                self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'fail')

    def test_peer_card_base_divergence_fails(self):
        source, actual, manifest, rules, paths = self.fixture()
        for node in actual['nodes']:
            if node['id'] == 'income':
                node['props']['fills'][0]['color'] = {'r': .97, 'g': .90, 'b': .75}
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('diverged' in row['error'] for row in result['errors']))

    def test_equal_peer_card_bases_pass(self):
        source, actual, manifest, rules, _ = self.fixture()
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'pass')

    def test_omitted_semantic_surface_fails(self):
        source, actual, manifest, rules, _ = self.fixture()
        manifest['surfaceSystemPlan']['surfaces'] = [row for row in
            manifest['surfaceSystemPlan']['surfaces'] if row['nodeId'] != 'income']
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('omitted' in row['error'] for row in result['errors']))

    def test_clipped_paint_requires_frozen_native_pixel_group(self):
        source, actual, manifest, rules, paths = self.fixture(clipped=True)
        found = discover(source)
        self.assertIn('clip:income:right',
                      [row['id'] for row in found['clipBoundaryCandidates']])
        manifest['surfaceSystemPlan']['surfaces'].append({
            'id': 'entry-carrier', 'nodeId': 'clip-child', 'kind': 'interaction',
            'carrierPaths': [paths['clip-child']],
            'basis': 'Existing functional entry carrier inside the card.'})
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertIn('clip:income:right', result['errors'][-1]['missingCandidateIds'])
        manifest['surfaceSystemPlan']['boundaryReviews'] = [{
            'candidateId': 'clip:income:right', 'decision': 'fade',
            'displayedGroupId': 'income-clip-right',
            'basis': 'The internal clipped carrier must fade without a hard rectangle.'}]
        rules['surface-continuity'] = {'applicable': True, 'verifier': {
            'type': 'displayed-relations', 'groups': [{
                'id': 'income-clip-right', 'nodeIds': ['income', 'clip-child'],
                'xy': [[379, 130], [381, 130]], 'nativePixels': [400, 800],
                'maximumChannelDelta': 8}]}}
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'pass')

    def test_adjacent_painted_units_require_source_topology_pixels(self):
        source, actual, manifest, rules, _ = self.fixture()
        for doc in (source, actual):
            next(node for node in doc['nodes'] if node['id'] == 'task')['props']['y'] = 220
        source_hash = digest(snapshot_document(source))
        manifest['sourceHash'] = source_hash
        manifest['surfaceSystemPlan']['sourceHash'] = source_hash
        candidate_id = 'adjacent:root:income:task'
        found = discover(source)
        self.assertIn(candidate_id, [row['id'] for row in found['boundaryCandidates']])
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertIn(candidate_id, result['errors'][-1]['missingCandidateIds'])
        manifest['surfaceSystemPlan']['boundaryReviews'] = [{
            'candidateId': candidate_id, 'decision': 'continuous',
            'displayedGroupId': 'income-task-join',
            'basis': 'The two painted source units meet at this edge.'}]
        group = {'id': 'income-task-join', 'relationType': 'source-topology',
                 'nodeIds': ['income', 'task'], 'xy': [[50, 219], [50, 221]],
                 'nativePixels': [400, 800], 'maximumChannelDelta': 16}
        rules['surface-continuity'] = {'applicable': True, 'verifier': {
            'type': 'displayed-relations', 'groups': [group]}}
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'pass')
        group['xy'] = [[50, 100], [50, 101]]
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'fail')

    def test_clipped_boundary_rejects_placeholder_coordinates_and_loose_delta(self):
        source, actual, manifest, rules, paths = self.fixture(clipped=True)
        manifest['surfaceSystemPlan']['surfaces'].append({
            'id': 'entry-carrier', 'nodeId': 'clip-child', 'kind': 'interaction',
            'carrierPaths': [paths['clip-child']],
            'basis': 'Existing functional entry carrier inside the card.'})
        manifest['surfaceSystemPlan']['boundaryReviews'] = [{
            'candidateId': 'clip:income:right', 'decision': 'fade',
            'displayedGroupId': 'income-clip-right',
            'basis': 'The clipped decoration must fade at its actual right edge.'}]
        group = {'id': 'income-clip-right', 'nodeIds': ['income', 'clip-child'],
                 'xy': [[1, 1], [2, 1]], 'nativePixels': [400, 800],
                 'maximumChannelDelta': 8}
        rules['surface-continuity'] = {'applicable': True, 'verifier': {
            'type': 'displayed-relations', 'groups': [group]}}
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('discovered edge' in row['error'] for row in result['errors']))
        group['xy'] = [[379, 130], [381, 130]]
        group['maximumChannelDelta'] = 48
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('tight native' in row['error'] for row in result['errors']))

    def test_manifest_surface_role_cannot_be_downgraded_to_decoration(self):
        source, actual, manifest, rules, paths = self.fixture(inner=True)
        manifest['surfaceSystemPlan']['surfaces'].append({
            'id': 'inner-surface', 'nodeId': 'inner-container', 'kind': 'decoration',
            'carrierPaths': [paths['inner-container']],
            'basis': 'Incorrect downgrade used by the regression fixture.'})
        next(row for row in manifest['entries']
             if row['path'] == paths['inner-container'])['role'] = 'surface.container'
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('conflicts with surfaceSystemPlan' in row['error']
                            for row in result['errors']))

    def test_source_same_card_and_chrome_base_cannot_split_in_target(self):
        source, actual, manifest, rules, paths = self.fixture(inner=True)
        source_card = next(row for row in source['nodes'] if row['id'] == 'income')
        source_chrome = next(row for row in source['nodes'] if row['id'] == 'inner-container')
        source_chrome['props']['fills'][0]['color'] = deepcopy(
            source_card['props']['fills'][0]['color'])
        actual_chrome = next(row for row in actual['nodes'] if row['id'] == 'inner-container')
        actual_chrome['props']['fills'][0]['color'] = {'r': .92, 'g': .86, 'b': .68}
        source_hash = digest(snapshot_document(source))
        manifest['sourceHash'] = source_hash
        manifest['surfaceSystemPlan']['sourceHash'] = source_hash
        manifest['surfaceSystemPlan']['surfaces'].append({
            'id': 'title-chrome', 'nodeId': 'inner-container', 'kind': 'chrome',
            'carrierPaths': [paths['inner-container']],
            'basis': 'Title chrome whose source base is continuous with the card.'})
        next(row for row in manifest['entries']
             if row['path'] == paths['inner-container'])['role'] = 'card.chrome'
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('source-identical card' in row['error']
                            for row in result['errors']))
        actual_chrome['props']['fills'][0]['color'] = deepcopy(
            next(row for row in actual['nodes'] if row['id'] == 'income')
            ['props']['fills'][0]['color'])
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'pass')

    def test_page_terminal_requires_frozen_native_pixel_group(self):
        source, actual, manifest, rules, _ = self.fixture(terminal=True)
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('terminal:h5:bottom' in row.get('missingCandidateIds', [])
                            for row in result['errors']))

    def test_every_visible_card_descendant_fill_requires_classification(self):
        source, actual, manifest, rules, paths = self.fixture(inner=True)
        found = discover(source)
        self.assertIn('inner-container',
                      [row['nodeId'] for row in found['paintedCandidates']])
        result = inspect(source, actual, manifest, rules)
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any('inner-container' in row.get('nodeIds', [])
                            for row in result['errors']))
        manifest['surfaceSystemPlan']['surfaces'].append({
            'id': 'inner-surface', 'nodeId': 'inner-container', 'kind': 'container',
            'carrierPaths': [paths['inner-container']],
            'stableRepresentativePath': paths['inner-container'],
            'hostSurfaceId': 'income-surface',
            'boundaryRelationshipId': 'inner-income',
            'basis': 'Visible grouping container inside the income card.'})
        relation = {'id': 'inner-income', 'kind': 'surface',
                    'nodeIds': ['inner-container', 'income'],
                    'sampleIds': ['inner-center'],
                    'minimumDeltaE': 4, 'maximumDeltaE': 9}
        rules['contrast-baseline']['verifier']['relationships'].append(relation)
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'pass')
        relation['minimumDeltaE'] = 3
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'fail')
        relation['minimumDeltaE'] = 4
        relation.pop('maximumDeltaE')
        self.assertEqual(inspect(source, actual, manifest, rules)['status'], 'fail')

    def test_card_geometry_reports_coverage_and_common_content_insets(self):
        source, actual, manifest, rules, _ = self.fixture(
            inner=True, inner_box=(16, 16, 328, 80))
        result = inspect(source, actual, manifest, rules)
        evidence = next(row for row in result['candidateGeometryEvidence']
                        if row['nodeId'] == 'inner-container')['cardGeometry']
        self.assertAlmostEqual(evidence['widthRatio'], 328 / 360)
        self.assertAlmostEqual(evidence['areaRatio'], 328 * 80 / (360 * 120))
        self.assertEqual(evidence['insetsPx']['left'], 16)
        self.assertEqual(evidence['insetsPx']['right'], 16)
        self.assertEqual(evidence['commonInsetMatchesPx']['left'], 16)
        self.assertTrue(evidence['symmetricHorizontalInset'])


if __name__ == '__main__':
    unittest.main()

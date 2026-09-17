const test = require('node:test');
const assert = require('node:assert/strict');
const { snapshotThemeTree } = require('../scripts/figma_snapshot.js');

test('includes hidden descendants, restores settings, never loads fonts or edits', async () => {
  let fontLoads = 0;
  const page = {id: 'p'};
  const hidden = {id: 'hidden', type: 'RECTANGLE', visible: false, fills: []};
  const root = {id: 'r', type: 'FRAME', parent: page, children: [hidden], x: 1};
  hidden.parent = root;
  const api = {skipInvisibleInstanceChildren: true,
    getNodeByIdAsync: async () => {
      assert.equal(api.skipInvisibleInstanceChildren, false);
      return root;
    }, loadFontAsync: async () => { fontLoads++; }};
  const snapshot = await snapshotThemeTree(api, 'r');
  assert.equal(api.skipInvisibleInstanceChildren, true);
  assert.equal(snapshot.nodes.length, 2);
  assert.deepEqual(snapshot.errors, []);
  assert.equal(snapshot.nodes[1].props.visible, false);
  assert.equal(fontLoads, 0);
  assert.equal(root.x, 1);
});

test('property failure is explicit and traversal settings are restored', async () => {
  const root = {id: 'r', type: 'FRAME', children: []};
  Object.defineProperty(root, 'fills', {get: () => { throw Error('denied'); }});
  const api = {skipInvisibleInstanceChildren: true, getNodeByIdAsync: async () => root};
  const snapshot = await snapshotThemeTree(api, 'r');
  assert.equal(snapshot.errors.length, 1);
  assert.equal(snapshot.errors[0].property, 'fills');
  assert.equal(api.skipInvisibleInstanceChildren, true);
});

test('one text read keeps typography independent of color splits', async () => {
  let reads = 0;
  const root = {id: 't', type: 'TEXT', characters: 'AB', getStyledTextSegments: fields => {
    reads++;
    return [0, 1].map(i => ({start: i, end: i + 1, ...Object.fromEntries(fields.map(f =>
      [f, f === 'fills' ? [{color: {r: i}}] : f === 'fontName' ? {family: 'Example', style: 'Regular'} : 12]))}));
  }};
  const result = await snapshotThemeTree({skipInvisibleInstanceChildren: false, getNodeByIdAsync: async () => root}, 't');
  assert.equal(reads, 1);
  assert.equal(result.nodes[0].props.textRuns.fills.length, 2);
  assert.deepEqual(result.nodes[0].props.textRuns.fontName, [{start: 0, end: 2, value: {family: 'Example', style: 'Regular'}}]);
});

test('missing roots and failed instance reads do not produce silent success', async () => {
  const missing = await snapshotThemeTree({skipInvisibleInstanceChildren: false, getNodeByIdAsync: async () => null}, 'r');
  assert.equal(missing.errors.length, 1);
  const node = {id: 'i', type: 'INSTANCE', getMainComponentAsync: async () => { throw Error('unavailable'); }};
  const failed = await snapshotThemeTree({skipInvisibleInstanceChildren: false, getNodeByIdAsync: async () => node}, 'i');
  assert.equal(failed.errors[0].property, 'mainComponentId');
});

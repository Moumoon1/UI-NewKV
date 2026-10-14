from pathlib import Path
import sys
import json
import shutil
import subprocess
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_theme_apply_js import build


class GenerateThemeApplyTests(unittest.TestCase):
    def fixture(self):
        source = {'rootId': 'root', 'nodes': [
            {'id': 'root', 'children': ['outer'], 'props': {'type': 'FRAME'}},
            {'id': 'outer', 'children': ['inner'], 'props': {'type': 'INSTANCE'}},
            {'id': 'inner', 'children': [], 'props': {'type': 'INSTANCE'}}]}
        plan = {'sourceRootId': 'root', 'kvSourceId': 'kv', 'operations': [],
                'detachInstanceIds': ['inner', 'outer'],
                'postDetachMapping': 'structural-fingerprint'}
        kv = {'rootId': 'kv', 'errors': [], 'nodes': [{'id': 'kv'}]}
        return source, {'entries': []}, plan, kv

    def test_detaches_are_emitted_parent_first(self):
        source, manifest, plan, kv = self.fixture()
        program = build(source, manifest, plan, kv)
        self.assertIn('"detach":[[0],[0,0]]', program)
        self.assertIn('detachedCount', program)

    def test_detach_requires_structural_mapping(self):
        source, manifest, plan, kv = self.fixture()
        del plan['postDetachMapping']
        with self.assertRaisesRegex(ValueError, 'structural-fingerprint'):
            build(source, manifest, plan, kv)

    def test_cloned_kv_is_locked_and_read_back(self):
        source, manifest, plan, kv = self.fixture()
        program = build(source, manifest, plan, kv)
        self.assertIn('kv.locked=true', program)
        self.assertIn('kvLocked:kv.locked', program)

    def test_baked_raster_button_cannot_gain_an_overlay(self):
        source, manifest, plan, kv = self.fixture()
        plan['ctaButtonOverlay'] = {'name': '__kv_cta_button_overlay__'}
        with self.assertRaisesRegex(ValueError, 'overlay is forbidden'):
            build(source, manifest, plan, kv)

    def test_styled_text_alpha_is_written_and_read_back(self):
        source, manifest, plan, kv = self.fixture()
        source['nodes'][2]['children'] = ['label']
        source['nodes'].append({'id': 'label', 'children': [], 'props': {
            'type': 'TEXT', 'textRuns': {'fills': [{'start': 0, 'end': 2,
                'value': [{'type': 'SOLID', 'opacity': .6,
                           'color': {'r': 1, 'g': 1, 'b': 1}}]}]}}})
        plan['operations'] = [{'kind': 'text-range', 'sourceId': 'label',
            'path': [0, 0, 0], 'start': 0, 'end': 2,
            'before': [{'type': 'SOLID', 'opacity': .6}],
            'after': [{'type': 'SOLID', 'opacity': 1}]}]
        program = build(source, manifest, plan, kv)
        self.assertIn('"text":[[[0,0,0],0,2,[],[[0,1]]]]', program)
        self.assertIn('styled text readback alpha mismatch', program)

    @unittest.skipUnless(shutil.which('node'), 'Node needed for generated writer behavior')
    def test_one_fill_range_across_different_fonts_is_written_without_font_changes(self):
        source, manifest, plan, kv = self.fixture()
        plan['detachInstanceIds'] = []
        source['nodes'][2]['children'] = ['label']
        fill = [{'type': 'SOLID', 'opacity': .6, 'color': {'r': 1, 'g': 1, 'b': 1}}]
        source['nodes'].append({'id': 'label', 'children': [], 'props': {
            'type': 'TEXT', 'textRuns': {'fills': [{'start': 0, 'end': 12, 'value': fill}]}}})
        plan['operations'] = [{'kind': 'text-range', 'sourceId': 'label',
            'path': [0, 0, 0], 'start': 0, 'end': 12,
            'before': fill, 'after': [{**fill[0], 'opacity': 1}]}]
        program = build(source, manifest, plan, kv)
        harness = r'''
const assert=require('node:assert/strict');let paints=__FILL__,writes=[];
const fonts=['Medium','Regular','Medium'];
const label={id:'label',type:'TEXT',getStyledTextSegments(fields){
 if(fields.includes('fontName'))return [[0,2],[2,3],[3,12]].map(([start,end],i)=>({start,end,fills:paints,fontName:fonts[i]}));
 return [{start:0,end:12,fills:paints}];
},setRangeFills(start,end,value){writes.push([start,end]);paints=value;}};
const inner={children:[label]},outer={children:[inner]};
const clone={width:414,children:[outer],appendChild(n){this.children.push(n)},insertChild(i,n){this.children.splice(this.children.indexOf(n),1);this.children.splice(i,0,n)}};
const figma={skipInvisibleInstanceChildren:true,getNodeByIdAsync:async()=>({type:'FRAME',width:414,clone(){return {id:'kv-clone',width:414,height:389,findAll:()=>[]}}})};
(async()=>{const receipt=await applyThemeWriteToClone(figma,clone);assert.equal(receipt.status,'pass');assert.deepEqual(writes,[[0,12]]);assert.equal(paints[0].opacity,1);assert.deepEqual(fonts,['Medium','Regular','Medium']);assert.equal(figma.skipInvisibleInstanceChildren,true);})().catch(e=>{console.error(e);process.exit(1)});
'''.replace('__FILL__', json.dumps(fill))
        result = subprocess.run([shutil.which('node'), '-e', program + harness],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

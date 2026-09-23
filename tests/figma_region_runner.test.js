const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ctx=vm.createContext({});
for(const name of ['snapshot_fingerprint.js','figma_apply_color_diff.js','figma_region_runner.js'])
  vm.runInContext(fs.readFileSync('scripts/'+name,'utf8'),ctx);

test('one region call writes, reads back, screens old colors and screenshots',async()=>{
 let screenshots=0;
 const n={id:'card',visible:true,fills:[{type:'SOLID',color:{r:1,g:0,b:0}}],screenshot:async()=>{screenshots++}};
 const after=[{type:'SOLID',color:{r:0,g:0,b:1}}];
 const plan={schemaVersion:1,regionId:'card',oldUiColors:['#FF0000'],operations:[{cloneId:'card',property:'fills',beforeHash:ctx.snapshotRowFingerprint(n.fills),afterHash:ctx.snapshotRowFingerprint(after),changes:[{path:'/0/color/r',value:0},{path:'/0/color/b',value:1}]}]};
 const figma={skipInvisibleInstanceChildren:true,getNodeByIdAsync:async()=>n};
 const result=await ctx.applyAndReviewThemeRegion(figma,plan);
 assert.equal(result.status,'visual-review');assert.equal(result.write.readbackCount,1);
 assert.equal(result.oldColorScreen.hitCount,0);assert.equal(screenshots,1);assert.equal(figma.skipInvisibleInstanceChildren,true);
});
test('old editable colors are reported, not silently removed',async()=>{
 const n={id:'card',visible:true,fills:[{type:'SOLID',color:{r:1,g:0,b:0}}],screenshot:async()=>{}};
 const result=await ctx.applyAndReviewThemeRegion({skipInvisibleInstanceChildren:false,getNodeByIdAsync:async()=>n},
  {schemaVersion:1,regionId:'card',oldUiColors:['#FF0000'],operations:[]});
 assert.equal(result.status,'old-color-review');assert.equal(result.oldColorScreen.hitCount,1);
 assert.equal(result.oldColorScreen.hits[0].nodeId,'card');
});
test('write conflicts stop region review without a misleading screenshot',async()=>{
 let screenshots=0;const n={id:'card',fills:[{type:'SOLID',color:{r:1,g:0,b:0}}],screenshot:async()=>{screenshots++}};
 const result=await ctx.applyAndReviewThemeRegion({getNodeByIdAsync:async()=>n},
  {schemaVersion:1,regionId:'card',oldUiColors:[],operations:[{cloneId:'card',property:'fills',beforeHash:'wrong',afterHash:'other',changes:[]}]});
 assert.equal(result.status,'needs-recovery');assert.equal(screenshots,0);
});
test('intermediate technical part does not screenshot or declare region reviewed',async()=>{
 let screenshots=0;const n={id:'card',visible:true,fills:[],screenshot:async()=>{screenshots++}};
 const result=await ctx.applyAndReviewThemeRegion({getNodeByIdAsync:async()=>n},
  {schemaVersion:1,regionId:'card',oldUiColors:[],operations:[],reviewAfter:false});
 assert.equal(result.status,'writing');assert.equal(screenshots,0);
});
test('sibling overlay is screened and screenshot can use an ancestor context',async()=>{
 let screenshotId=null;
 const card={id:'card',visible:true,fills:[]};
 const overlay={id:'overlay',visible:true,fills:[{type:'SOLID',color:{r:1,g:0,b:0}}]};
 const page={id:'page',screenshot:async()=>{screenshotId='page'}};
 const nodes=new Map([card,overlay,page].map(x=>[x.id,x]));
 const result=await ctx.applyAndReviewThemeRegion({skipInvisibleInstanceChildren:true,getNodeByIdAsync:async id=>nodes.get(id)},
  {schemaVersion:1,regionId:'card',scopeNodeIds:['card','overlay'],screenshotNodeId:'page',oldUiColors:['#FF0000'],operations:[]});
 assert.equal(result.oldColorScreen.hitCount,1);assert.equal(result.oldColorScreen.hits[0].nodeId,'overlay');
 assert.equal(screenshotId,'page');
});
test('region runner rejects writes outside declared scope or into protected node',async()=>{
 const card={id:'card',visible:true,fills:[],screenshot:async()=>{}};
 const figma={getNodeByIdAsync:async()=>card};
 const base={schemaVersion:1,regionId:'card',oldUiColors:[],operations:[{cloneId:'other'}]};
 await assert.rejects(ctx.applyAndReviewThemeRegion(figma,base),/outside declared region/);
 await assert.rejects(ctx.applyAndReviewThemeRegion(figma,{...base,operations:[{cloneId:'card'}],protectedNodeIds:['card']}),/protected node/);
});
test('excluded subtree cannot be written or counted as an old UI color',async()=>{
 const kvChild={id:'kv-child',visible:true,fills:[{type:'SOLID',color:{r:1,g:0,b:0}}]};
 const kv={id:'kv',visible:true,fills:[],children:[kvChild]};
 const card={id:'card',visible:true,fills:[],children:[kv],screenshot:async()=>{}};
 const nodes=new Map([card,kv,kvChild].map(x=>[x.id,x]));
 const figma={skipInvisibleInstanceChildren:true,getNodeByIdAsync:async id=>nodes.get(id)};
 const base={schemaVersion:1,regionId:'card',oldUiColors:['#FF0000'],excludedSubtreeRootIds:['kv'],operations:[]};
 const result=await ctx.applyAndReviewThemeRegion(figma,base);
 assert.equal(result.status,'visual-review');
 assert.equal(result.oldColorScreen.hitCount,0);
 assert.deepEqual(Array.from(result.excludedSubtreeRootIds),['kv']);
 await assert.rejects(ctx.applyAndReviewThemeRegion(figma,{...base,operations:[{cloneId:'kv-child'}]}),/outside declared region/);
});

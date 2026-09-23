const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ctx=vm.createContext({});
for(const name of ['snapshot_fingerprint.js','figma_apply_color_diff.js','figma_region_runner.js','figma_multi_region_runner.js'])
  vm.runInContext(fs.readFileSync('scripts/'+name,'utf8'),ctx);

function plan(id){return {schemaVersion:1,regionId:id,oldUiColors:[],operations:[],batchEligibility:{representativeGateStatus:'pass',independent:true,recipeHash:'r',dependencyHash:'d'}}}

test('independent gated regions review in one guarded call',async()=>{
 const nodes=new Map(['a','b'].map(id=>[id,{id,visible:true,fills:[],screenshot:async()=>{}}]));
 const result=await ctx.applyAndReviewThemeRegions({getNodeByIdAsync:async id=>nodes.get(id)},[plan('a'),plan('b')]);
 assert.equal(result.status,'visual-review');assert.equal(result.completedRegions,2);
});

test('batch stops before later regions after a review issue',async()=>{
 let bScreens=0;
 const nodes=new Map([
  ['a',{id:'a',visible:true,fills:[{type:'SOLID',color:{r:1,g:0,b:0}}],screenshot:async()=>{}}],
  ['b',{id:'b',visible:true,fills:[],screenshot:async()=>{bScreens++}}],
 ]);
 const first={...plan('a'),oldUiColors:['#FF0000']};
 const result=await ctx.applyAndReviewThemeRegions({getNodeByIdAsync:async id=>nodes.get(id)},[first,plan('b')]);
 assert.equal(result.status,'stopped-for-review');assert.equal(result.results.length,1);assert.equal(bScreens,0);
});

test('batch rejects regions without frozen eligibility evidence',async()=>{
 await assert.rejects(ctx.applyAndReviewThemeRegions({},[plan('a'),{...plan('b'),batchEligibility:{independent:true}}]),/not eligible/);
});

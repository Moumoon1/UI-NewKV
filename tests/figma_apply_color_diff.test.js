const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync('scripts/snapshot_fingerprint.js','utf8')+'\n'+fs.readFileSync('scripts/figma_apply_color_diff.js','utf8'),ctx);
const hash=ctx.snapshotRowFingerprint;
const api=n=>({getNodeByIdAsync:async id=>id===n.id?n:null});
const op=(n,key,after,changes)=>({cloneId:n.id,property:key,beforeHash:hash(n[key]),afterHash:hash(after),changes});
test('scalar opacity replacement works',async()=>{
 const n={id:'a',opacity:.4};const result=await ctx.applyDeclaredColorDiff(api(n),[op(n,'opacity',.65,[{path:'',value:.65}])]);assert.equal(n.opacity,.65);assert.equal(result.readbackCount,1);
});
test('paint diff retains geometry, alpha and hidden layers',async()=>{
 const n={id:'a',fills:[{type:'SOLID',visible:true,opacity:.4,color:{r:.1,g:.2,b:.3}},{type:'SOLID',visible:false,color:{r:1,g:0,b:0}}]};
 const after=structuredClone(n.fills);after[0].color.g=.8;await ctx.applyDeclaredColorDiff(api(n),[op(n,'fills',after,[{path:'/0/color/g',value:.8}])]);assert.equal(JSON.stringify(n.fills),JSON.stringify(after));
});
test('full before conflict rejects write',async()=>{
 const n={id:'a',opacity:.4};const plan=op(n,'opacity',.65,[{path:'',value:.65}]);n.opacity=.5;await assert.rejects(ctx.applyDeclaredColorDiff(api(n),[plan]),/before conflict/);assert.equal(n.opacity,.5);
});
test('derived already completed property is skipped',async()=>{
 const n={id:'a',opacity:.4};const plan=op(n,'opacity',.65,[{path:'',value:.65}]);n.opacity=.65;const result=await ctx.applyDeclaredColorDiff(api(n),[plan]);assert.equal(result.mutatedNodeIds.length,0);
});
test('vector region colors use async API and keep topology',async()=>{
 const network={vertices:[{x:3,y:4}],segments:[],regions:[{fills:[{type:'SOLID',color:{r:.1,g:.2,b:.3}}]}]};let calls=0;const n={id:'a',vectorNetwork:network,setVectorNetworkAsync:async value=>{calls++;n.vectorNetwork=value;}};const after=structuredClone(network);after.regions[0].fills[0].color.r=.7;await ctx.applyDeclaredColorDiff(api(n),[op(n,'vectorNetwork',after,[{path:'/regions/0/fills/0/color/r',value:.7}])]);assert.equal(calls,1);assert.equal(JSON.stringify(n.vectorNetwork.vertices),JSON.stringify(network.vertices));
});
test('mixed text ranges use range fill API without typography calls',async()=>{
 const before=[{type:'SOLID',color:{r:.1,g:.2,b:.3}}];const after=[{type:'SOLID',color:{r:.7,g:.2,b:.3}}];let count=0,current=before;const n={id:'a',type:'TEXT',fontName:'unchanged',getRangeFills:()=>current,setRangeFills:(start,end,value)=>{assert.equal(start,2);assert.equal(end,5);assert.equal(JSON.stringify(value),JSON.stringify(after));current=value;count++;}};const result=await ctx.applyDeclaredColorDiff(api(n),[{cloneId:'a',property:'textRuns',runs:[{start:2,end:5,value:after,beforeHash:hash(before)}]}]);assert.equal(count,1);assert.equal(result.readbackCount,1);assert.equal(n.fontName,'unchanged');
});
test('bound paint rebound fails in the same write call',async()=>{
 const original=[{type:'SOLID',color:{r:.1,g:.2,b:.3}}];let current=original;
 const n={id:'a',get fills(){return current},set fills(_value){current=original}};
 const after=structuredClone(original);after[0].color.r=.7;
 await assert.rejects(ctx.applyDeclaredColorDiff(api(n),[op(n,'fills',after,[{path:'/0/color/r',value:.7}])]),/after conflict/);
});
test('mixed text rebound fails in the same write call',async()=>{
 const before=[{type:'SOLID',color:{r:.1,g:.2,b:.3}}];const after=[{type:'SOLID',color:{r:.7,g:.2,b:.3}}];
 const n={id:'a',getRangeFills:()=>before,setRangeFills:()=>{}};
 await assert.rejects(ctx.applyDeclaredColorDiff(api(n),[{cloneId:'a',property:'textRuns',runs:[{start:0,end:2,value:after,beforeHash:hash(before)}]}]),/after conflict range/);
});
test('partial failure exposes only fully read-back prior nodes',async()=>{
 const a={id:'a',opacity:.4},b={id:'b',opacity:.2};
 const operations=[op(a,'opacity',.7,[{path:'',value:.7}]),{...op(b,'opacity',.6,[{path:'',value:.6}]),beforeHash:'wrong'}];
 await assert.rejects(ctx.applyDeclaredColorDiff({getNodeByIdAsync:async id=>id==='a'?a:b},operations),error=>{
  assert.equal(error.message,'before conflict b opacity');assert.equal(JSON.stringify(error.verifiedCompletedNodeIds),'["a"]');return true;
 });
});
test('local variable alias removal deletes the property rather than storing a sentinel',async()=>{
 const n={id:'a',fills:[{type:'SOLID',color:{r:.1,g:.2,b:.3},boundVariables:{color:{type:'VARIABLE_ALIAS',id:'v'}}}]};
 const after=structuredClone(n.fills);delete after[0].boundVariables.color;after[0].color.r=.7;
 await ctx.applyDeclaredColorDiff(api(n),[op(n,'fills',after,[{path:'/0/boundVariables/color',value:{$missing:true}},{path:'/0/color/r',value:.7}])]);
 assert.equal('color' in n.fills[0].boundVariables,false);assert.equal(n.fills[0].color.r,.7);
});
test('mixed text recovery skips completed ranges and rejects conflicts before writes',async()=>{
 const before=[{type:'SOLID',color:{r:.1,g:.2,b:.3}}];const after=[{type:'SOLID',color:{r:.7,g:.2,b:.3}}];let calls=0;
 const n={id:'a',getRangeFills:()=>after,setRangeFills:()=>{calls++;}};
 const plan={cloneId:'a',property:'textRuns',runs:[{start:0,end:2,value:after,beforeHash:hash(before)}]};
 const result=await ctx.applyDeclaredColorDiff(api(n),[plan]);assert.equal(calls,0);assert.equal(result.mutatedNodeIds.length,0);
 n.getRangeFills=()=>[{type:'SOLID',color:{r:.5,g:.2,b:.3}}];await assert.rejects(ctx.applyDeclaredColorDiff(api(n),[plan]),/before conflict/);assert.equal(calls,0);
});

const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {execFileSync}=require('node:child_process');

const context=vm.createContext({atob});
for(const name of ['figma_snapshot.js','snapshot_fingerprint.js',
                   'figma_snapshot_transport.js','figma_final_review.js'])
  vm.runInContext(fs.readFileSync('scripts/'+name,'utf8'),context);

test('final review preserves snapshot and requests separate native screenshot',async()=>{
  const page={id:'page',type:'PAGE'};
  const source={id:'source',type:'FRAME',name:'source',parent:page,children:[],
                visible:true,width:100,height:200};
  const clone={id:'clone',type:'FRAME',name:'clone',parent:page,children:[],
               visible:true,width:100,height:200,x:300,y:0,
               exportAsync:async()=>new Uint8Array([137,80,78,71])};
  const kv={id:'kv',type:'FRAME',parent:clone,locked:true};
  const nodes={source,clone,kv},writes=[];
  const figma={currentPage:page,skipInvisibleInstanceChildren:false,
    getNodeByIdAsync:async id=>nodes[id],
    io:{write:(name,bytes)=>writes.push({name,bytes})}};
  const sourceSnapshot=await context.snapshotThemeTree(figma,'source');
  const fingerprint=context.snapshotRowFingerprint(sourceSnapshot.nodes.map(context.snapshotRowFingerprint));
  const result=await context.captureThemeFinalReview(figma,'source','clone','kv',fingerprint);
  assert.equal(result.status,'captured');
  assert.equal(result.imageBlockCount,1);
  assert.deepEqual(writes.map(w=>w.name),['theme-final-snapshot.png']);
  assert(Buffer.from(writes[0].bytes).includes(Buffer.from('KVSS1')));
  assert.equal(result.screenshotRequired.nodeId,'clone');
});

test('generated code stays within Figma script budget',()=>{
  const code=execFileSync('python3',['scripts/generate_figma_final_review_js.py',
      'source','clone','kv','1234567890abcdef'],{encoding:'utf8'});
  assert(code.length<45000);
  assert(code.includes('return await captureThemeFinalReview(figma'));
});

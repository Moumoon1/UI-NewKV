const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const vm=require('node:vm');
const {execFileSync}=require('node:child_process');

const context=vm.createContext({atob});
for(const name of ['figma_snapshot.js','snapshot_fingerprint.js','figma_staged_preview.js'])
  vm.runInContext(fs.readFileSync('scripts/'+name,'utf8'),context);

function fixture(){
  const page={id:'page',type:'PAGE',children:[],appendChild(node){
    const old=this.children.indexOf(node);if(old>=0)this.children.splice(old,1);
    this.children.push(node);node.parent=this;
  }};
  const source={id:'source',type:'FRAME',name:'source',parent:page,
    children:[],visible:true,width:100,height:200,x:0,y:0,
    clone(){const copy={id:'preview',type:'FRAME',name:this.name,parent:page,
      children:[],visible:true,width:100,height:200,x:0,y:0,
      remove(){const index=page.children.indexOf(this);if(index>=0)page.children.splice(index,1)}};
      page.children.splice(page.children.indexOf(this)+1,0,copy);return copy}};
  page.children.push(source);
  const figma={currentPage:page,skipInvisibleInstanceChildren:false,
    getNodeByIdAsync:async id=>page.children.find(node=>node.id===id)??null};
  return {page,source,figma};
}

test('staged preview can be captured then precisely cleaned',async()=>{
  const {page,figma}=fixture();
  const baseline=await context.snapshotThemeTree(figma,'source');
  const fingerprint=context.snapshotRowFingerprint(baseline.nodes.map(context.snapshotRowFingerprint));
  const started=await context.startStagedThemePreview(figma,'source',fingerprint,'plan-1',
    async()=>({status:'pass'}));
  assert.equal(started.status,'awaiting-screenshot');
  assert.equal(page.children.length,2);
  assert.equal(page.children[1].name,'__kv_theme_preview__plan-1');
  const finished=await context.finishStagedThemePreview(figma,'source',started.cloneId,
    fingerprint,'plan-1',started.childIdsBefore);
  assert.equal(finished.status,'pass');
  assert.equal(finished.temporaryCloneRemoved,true);
  assert.deepEqual(page.children.map(node=>node.id),['source']);
});

test('failed plan cleans itself without external screenshot or cleanup',async()=>{
  const {page,figma}=fixture();
  const baseline=await context.snapshotThemeTree(figma,'source');
  const fingerprint=context.snapshotRowFingerprint(baseline.nodes.map(context.snapshotRowFingerprint));
  const started=await context.startStagedThemePreview(figma,'source',fingerprint,'plan-2',
    async()=>{throw new Error('setter rejected')});
  assert.equal(started.status,'fail');
  assert.equal(started.temporaryCloneRemoved,true);
  assert.deepEqual(page.children.map(node=>node.id),['source']);
});

test('cleanup refuses an unmarked or mismatched Frame',async()=>{
  const {page,figma}=fixture();
  const baseline=await context.snapshotThemeTree(figma,'source');
  const fingerprint=context.snapshotRowFingerprint(baseline.nodes.map(context.snapshotRowFingerprint));
  const started=await context.startStagedThemePreview(figma,'source',fingerprint,'plan-3',
    async()=>({status:'pass'}));
  await assert.rejects(context.finishStagedThemePreview(figma,'source',started.cloneId,
    fingerprint,'different-plan',started.childIdsBefore),/marker mismatch/);
  assert.equal(page.children.length,2);
});

test('generated start and finish programs stay within Figma budget',()=>{
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'kv-preview-test-'));
  try{
    const apply=path.join(directory,'apply.js');
    fs.writeFileSync(apply,'async function applyThemeWriteToClone(){return {status:"pass"}}');
    const start=execFileSync('python3',['scripts/generate_figma_staged_preview_js.py','start',
      'source','1234567890abcdef','plan','--apply-js',apply],{encoding:'utf8'});
    const finish=execFileSync('python3',['scripts/generate_figma_staged_preview_js.py','finish',
      'source','preview','1234567890abcdef','plan','--child-ids-json','["source"]'],{encoding:'utf8'});
    assert(start.length<45000&&finish.length<45000);
    assert(start.includes('startStagedThemePreview'));
    assert(start.includes('rightEdge+256'));
    assert(finish.includes('finishStagedThemePreview'));
  }finally{fs.rmSync(directory,{recursive:true,force:true})}
});

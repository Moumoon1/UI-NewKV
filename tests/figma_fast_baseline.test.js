const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {spawnSync,execFileSync}=require('node:child_process');
const ctx=vm.createContext({atob});
for(const name of ['figma_snapshot.js','snapshot_fingerprint.js','figma_source_preflight.js','figma_snapshot_transport.js'])
  vm.runInContext(fs.readFileSync('scripts/'+name,'utf8'),ctx);

function example(){
 const white={r:1,g:1,b:1};
 return {schemaVersion:1,rootId:'root',capturedAt:'2026-09-22T00:00:00.000Z',errors:[],nodes:[
  {id:'root',parentId:'page',children:['card'],props:{type:'FRAME',name:'Page',visible:true}},
  {id:'card',parentId:'root',children:['title'],props:{type:'FRAME',name:'Card',visible:true,
   fills:[{type:'GRADIENT_LINEAR',gradientStops:[{color:white,boundVariables:{color:{id:'var-1',type:'VARIABLE_ALIAS'}}},{color:{r:.2,g:.3,b:.4}}]}],fillStyleId:'style-1'}},
  {id:'title',parentId:'card',children:[],props:{type:'TEXT',name:'Title',visible:true,
   fills:[{type:'SOLID',color:{r:.3,g:.3,b:.4}}],textRuns:{fills:[{start:0,end:2,value:[{type:'SOLID',color:{r:.3,g:.3,b:.4}}]}],fillStyleId:[{start:0,end:2,value:'style-text'}]}}}
 ]};
}
test('one full scan returns compact region, channel and binding risks',()=>{
 const summary=ctx.summarizeThemeSource(example());
 assert.equal(summary.status,'pass');assert.equal(summary.counts.nodes,3);assert.equal(summary.counts.channels,4);
 assert.equal(summary.regions.find(x=>x.id==='card').channels,4);
 assert(summary.bindingGroups.some(x=>x.kind==='variable'&&x.instances===1));
 assert(summary.bindingGroups.some(x=>x.value==='style-text'));
 assert(JSON.stringify(summary).length<16000);
});
test('binding detail truncation is explicit rather than silently hidden',()=>{
 const snapshot=example();
 snapshot.nodes[1].props.fills=Array.from({length:80},(_,i)=>({type:'SOLID',color:{r:.2,g:.3,b:.4},boundVariables:{color:{id:'var-'+i}}}));
 const summary=ctx.summarizeThemeSource(snapshot,5000);
 assert.equal(summary.counts.bindingGroups,82);
 assert(summary.omittedBindingGroups>0);
 assert(JSON.stringify(summary).length<=5000);
});
test('generated baseline code stays under plugin limit and has one capture',()=>{
 const code=execFileSync('python3',['scripts/generate_figma_baseline_js.py','frame:1'],{encoding:'utf8'});
 assert(code.length<45000);assert(code.includes('return await captureThemeBaseline(figma,"frame:1"'));
});
test('generated baseline program captures once and emits decodable artifact',async()=>{
 const program=execFileSync('python3',['scripts/generate_figma_baseline_js.py','frame:1'],{encoding:'utf8'});
 let reads=0,artifact;
 const root={id:'frame:1',type:'FRAME',name:'Source',children:[],visible:true,fills:[{type:'SOLID',color:{r:.2,g:.3,b:.4}}]};
 const figma={skipInvisibleInstanceChildren:true,getNodeByIdAsync:async()=>{reads++;return root},io:{write:(_name,bytes)=>{artifact=bytes}}};
 const summary=await vm.runInNewContext('(async()=>{'+program+'})()',{figma,atob});
 assert.equal(reads,1);assert.equal(summary.counts.nodes,1);assert.equal(summary.counts.channels,1);
 const check=spawnSync('python3',['-c','import sys;sys.path.insert(0,"scripts");from decode_theme_snapshot_png import decode_transport;print(decode_transport(sys.stdin.buffer.read())["rootId"])'],{input:Buffer.from(artifact),encoding:'utf8'});
 assert.equal(check.status,0,check.stderr);assert.equal(check.stdout.trim(),'frame:1');
});
test('binary artifact round trips through Python and detects corruption',()=>{
 const snapshot=example();snapshot.nodes[1].props.note='金属反射 '.repeat(3000);
 const artifact=ctx.packThemeSnapshotPng(snapshot);
 const roundtrip=spawnSync('python3',['-c','import sys,json;sys.path.insert(0,"scripts");from decode_theme_snapshot_png import decode_transport;d=decode_transport(sys.stdin.buffer.read());print(json.dumps({"rootId":d["rootId"],"nodes":len(d["nodes"]),"note":d["nodes"][1]["props"]["note"]},ensure_ascii=False))'],{input:Buffer.from(artifact.bytes),encoding:'utf8'});
 assert.equal(roundtrip.status,0,roundtrip.stderr);const decoded=JSON.parse(roundtrip.stdout);
 assert.equal(decoded.note,snapshot.nodes[1].props.note);assert.equal(decoded.nodes,3);
 const damaged=Buffer.from(artifact.bytes);damaged[damaged.length-2]^=1;
 const reject=spawnSync('python3',['-c','import sys;sys.path.insert(0,"scripts");from decode_theme_snapshot_png import decode_transport;decode_transport(sys.stdin.buffer.read())'],{input:damaged,encoding:'utf8'});
 assert.notEqual(reject.status,0);assert.match(reject.stderr,/mismatch|invalid|exceeds/);
});
test('read errors block export before the image write',async()=>{
 let written=false;const bad={id:'root',type:'FRAME',children:[]};Object.defineProperty(bad,'fills',{get(){throw Error('denied')}});
 const figma={skipInvisibleInstanceChildren:false,getNodeByIdAsync:async()=>bad,io:{write(){written=true}}};
 await assert.rejects(ctx.captureThemeBaseline(figma,'root'),/read errors/);assert.equal(written,false);
});
test('broken component set metadata is recorded while visible paints remain audited',async()=>{
 let artifact;
 const child={id:'instance',type:'INSTANCE',name:'Icon',children:[],visible:true,fills:[{type:'SOLID',color:{r:1,g:0,b:0}}],getMainComponentAsync:async()=>null};
 Object.defineProperty(child,'componentProperties',{get(){throw Error('Component set for node has existing errors')}});
 const root={id:'root',type:'FRAME',name:'Page',children:[child],visible:true};child.parent=root;
 const figma={skipInvisibleInstanceChildren:false,getNodeByIdAsync:async()=>root,io:{write(_name,bytes){artifact=bytes}}};
 const summary=await ctx.captureThemeBaseline(figma,'root');
 assert.equal(summary.counts.readErrors,0);
 assert.equal(summary.counts.unavailableFields,1);
 assert.equal(summary.counts.channels,1);
 assert.equal(summary.unavailableFields[0].id,'instance');
 const decoded=spawnSync('python3',['-c','import sys,json;sys.path.insert(0,"scripts");from decode_theme_snapshot_png import decode_transport;d=decode_transport(sys.stdin.buffer.read());print(json.dumps(d["nodes"][1]["props"]["componentProperties"]))'],{input:Buffer.from(artifact),encoding:'utf8'});
 assert.equal(decoded.status,0,decoded.stderr);
 assert.match(decoded.stdout,/\$unavailable/);
});

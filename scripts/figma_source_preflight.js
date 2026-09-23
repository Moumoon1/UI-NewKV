/* Load figma_snapshot.js and snapshot_fingerprint.js first.
 * Full traversal stays inside Figma; only a bounded diagnostic summary returns.
 * This is a preflight, not a replacement for the write/final audit.
 */
function summarizeThemeSource(snapshot, maxChars=16000) {
  if (!snapshot || !Array.isArray(snapshot.nodes)) throw new Error('complete snapshot required');
  const rows=new Map(snapshot.nodes.map(n=>[n.id,n]));
  if(rows.size!==snapshot.nodes.length||!rows.has(snapshot.rootId))throw new Error('duplicate or missing source node');
  const regionFor=new Map();
  function region(id){
    if(regionFor.has(id))return regionFor.get(id);
    const row=rows.get(id);if(!row)throw new Error('unknown node '+id);
    if(id===snapshot.rootId)return snapshot.rootId;
    if(row.parentId===snapshot.rootId){regionFor.set(id,id);return id;}
    const result=region(row.parentId);regionFor.set(id,result);return result;
  }
  const regionStats=new Map(),colors=new Map(),bindingGroups=new Map();
  let channels=0,inactiveChannels=0,images=0,texts=0,instances=0;
  function stat(id){const key=region(id);if(!regionStats.has(key))regionStats.set(key,{id:key,name:rows.get(key)?.props?.name||'',nodes:0,channels:0,inactiveChannels:0,images:0});return regionStats.get(key);}
  function binding(nodeId,path,value){
    const signature=JSON.stringify(value);
    const kind=path.includes('StyleId')?'style':'variable';
    const key=kind+'|'+path.replace(/\/\d+(?=\/|$)/g,'/*')+'|'+signature;
    if(!bindingGroups.has(key))bindingGroups.set(key,{kind,path:path.replace(/\/\d+(?=\/|$)/g,'/*'),value,instances:0,sampleNodeIds:[]});
    const group=bindingGroups.get(key);group.instances++;if(group.sampleNodeIds.length<3&&!group.sampleNodeIds.includes(nodeId))group.sampleNodeIds.push(nodeId);
  }
  function walk(value,nodeId,path,hidden,grad=false){
    if(!value||typeof value!=='object')return;
    if(Array.isArray(value)){for(let i=0;i<value.length;i++)walk(value[i],nodeId,path+'/'+i,hidden,grad);return;}
    if(Object.hasOwn(value,'r')&&Object.hasOwn(value,'g')&&Object.hasOwn(value,'b')){
      channels++;const s=stat(nodeId);s.channels++;
      if(hidden||(value.a===0&&!grad)){inactiveChannels++;s.inactiveChannels++;}
      const k=[value.r,value.g,value.b].map(x=>Math.round(x*255).toString(16).padStart(2,'0')).join('').toUpperCase();colors.set(k,(colors.get(k)||0)+1);return;
    }
    const localHidden=hidden||value.visible===false||value.opacity===0;
    const gradient=grad||String(value.type||'').startsWith('GRADIENT_');
    for(const [key,child] of Object.entries(value)){
      const next=path+'/'+key;
      if(key==='boundVariables'&&child&&Object.keys(child).length)binding(nodeId,next,child);
      if(key.endsWith('StyleId')&&typeof child==='string'&&child)binding(nodeId,next,child);
      walk(child,nodeId,next,localHidden,gradient);
    }
  }
  const hiddenById=new Map();
  function isHidden(id){if(hiddenById.has(id))return hiddenById.get(id);const row=rows.get(id);const parent=row.parentId&&rows.has(row.parentId)?isHidden(row.parentId):false;const h=parent||row.props?.visible===false||row.props?.opacity===0;hiddenById.set(id,h);return h;}
  for(const row of snapshot.nodes){
    const s=stat(row.id);s.nodes++;
    if(row.props?.type==='TEXT')texts++;
    if(row.props?.type==='INSTANCE')instances++;
    const hidden=isHidden(row.id);
    for(const key of ['fills','strokes','effects','vectorNetwork','textDecorationColor']){
      if(key in row.props){const value=row.props[key];
        if(Array.isArray(value)){const count=value.filter(x=>x&&x.type==='IMAGE').length;images+=count;s.images+=count;}
        walk(value,row.id,'props/'+key,hidden);
      }
    }
    for(const key of ['fills','textDecorationColor'])if(key in (row.props?.textRuns||{}))walk(row.props.textRuns[key],row.id,'props/textRuns/'+key,hidden);
    for(const run of row.props?.textRuns?.fillStyleId||[])if(typeof run.value==='string'&&run.value)binding(row.id,'props/textRuns/fillStyleId',run.value);
    for(const key of ['boundVariables','fillStyleId','strokeStyleId','effectStyleId','textStyleId'])if(key in row.props)walk({[key]:row.props[key]},row.id,'props',hidden);
  }
  const fullHash=snapshotRowFingerprint(snapshot.nodes.map(snapshotRowFingerprint));
  const result={schemaVersion:1,status:snapshot.errors?.length?'fail':'pass',rootId:snapshot.rootId,capturedAt:snapshot.capturedAt,
    fullTreeFingerprint:fullHash,counts:{nodes:snapshot.nodes.length,channels,inactiveChannels,images,texts,instances,bindingGroups:bindingGroups.size,readErrors:snapshot.errors?.length||0,unavailableFields:snapshot.unavailableFields?.length||0},
    errors:snapshot.errors||[],unavailableFields:snapshot.unavailableFields||[],regions:[...regionStats.values()].sort((a,b)=>b.channels-a.channels),
    topColors:[...colors].sort((a,b)=>b[1]-a[1]).slice(0,24).map(([hex,count])=>({hex:'#'+hex,count})),
    bindingGroups:[...bindingGroups.values()].sort((a,b)=>b.instances-a.instances),omittedBindingGroups:0};
  while(JSON.stringify(result).length>maxChars&&result.bindingGroups.length){result.bindingGroups.pop();result.omittedBindingGroups++;}
  if(JSON.stringify(result).length>maxChars)throw new Error('preflight exceeds return budget even without binding detail');
  return result;
}
async function inspectThemeSource(figma,rootId){
  const t0=Date.now();const snapshot=await snapshotThemeTree(figma,rootId);
  const summary=summarizeThemeSource(snapshot);summary.timingMs={captureAndSummarize:Date.now()-t0};
  return summary;
}
if(typeof module!=='undefined')module.exports={summarizeThemeSource,inspectThemeSource};

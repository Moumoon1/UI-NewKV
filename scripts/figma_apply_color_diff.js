/* Load snapshot_fingerprint.js first. Caller supplies a phase-scoped frozen plan.
 * Diff transport preserves full Paint arrays/topology and checks all before fields.
 * afterHash allows already completed derived vector region colors to be skipped.
 */
async function applyDeclaredColorDiff(figma, ops) {
const mutated=[];let readbackCount=0;
function serial(v){if(typeof v==="symbol")return {$mixed:true};if(v===undefined)return {$undefined:true};if(Array.isArray(v))return v.map(serial);if(v&&typeof v==="object")return Object.fromEntries(Object.keys(v).map(k=>[k,serial(v[k])]));return v;}
try{
for(const op of ops){
 const n=await figma.getNodeByIdAsync(op.cloneId);if(!n)throw new Error("missing "+op.cloneId);
 if(op.property==="textRuns"){
  const pending=[];
  for(const run of op.runs){const hash=snapshotRowFingerprint(serial(n.getRangeFills(run.start,run.end)));if(hash===snapshotRowFingerprint(run.value))continue;if(hash!==run.beforeHash)throw new Error("before conflict range "+n.id);pending.push(run);}
  if(!pending.length)continue;
  const originalName=n.name,originalAutoRename=n.autoRename;
  for(const run of pending)n.setRangeFills(run.start,run.end,run.value);
  if(n.name!==originalName&&originalAutoRename!==true)n.name=originalName;
  for(const run of pending){readbackCount++;if(snapshotRowFingerprint(serial(n.getRangeFills(run.start,run.end)))!==snapshotRowFingerprint(run.value))throw new Error("after conflict range "+n.id+" "+run.start+":"+run.end);}
 }else{
  let current=serial(n[op.property]);const currentHash=snapshotRowFingerprint(current);if(currentHash===op.afterHash)continue;if(currentHash!==op.beforeHash)throw new Error("before conflict "+n.id+" "+op.property);
  for(const change of op.changes){if(change.path===""){current=change.value;continue;}const path=change.path.split("/").slice(1).map(k=>k.replace(/~1/g,"/").replace(/~0/g,"~"));let obj=current;for(const k of path.slice(0,-1))obj=obj[k];const key=path.at(-1);if(change.value&&typeof change.value==="object"&&change.value.$missing===true){if(Array.isArray(obj))throw new Error("array deletion requires a full declared property replacement");delete obj[key];}else obj[key]=change.value;}
  if(op.property==="vectorNetwork")await n.setVectorNetworkAsync(current);else n[op.property]=current;
  readbackCount++;
  if(snapshotRowFingerprint(serial(n[op.property]))!==op.afterHash)throw new Error("after conflict "+n.id+" "+op.property);
 }
 mutated.push(n.id);
}
}catch(error){error.verifiedCompletedNodeIds=[...new Set(mutated)];throw error;}
return {mutatedNodeIds:[...new Set(mutated)],operationCount:ops.length,readbackCount,capturedAt:new Date().toISOString()};
}

/* Load snapshot_fingerprint.js first. Caller supplies a phase-scoped frozen plan.
 * Diff transport preserves full Paint arrays/topology and checks all before fields.
 * afterHash allows already completed derived vector region colors to be skipped.
 */
async function applyDeclaredColorDiff(figma, ops) {
const mutated=[];
function serial(v){if(typeof v==="symbol")return {$mixed:true};if(v===undefined)return {$undefined:true};if(Array.isArray(v))return v.map(serial);if(v&&typeof v==="object")return Object.fromEntries(Object.keys(v).map(k=>[k,serial(v[k])]));return v;}
for(const op of ops){
 const n=await figma.getNodeByIdAsync(op.cloneId);if(!n)throw new Error("missing "+op.cloneId);
 if(op.property==="textRuns"){
  for(const run of op.runs)if(snapshotRowFingerprint(serial(n.getRangeFills(run.start,run.end)))!==run.beforeHash)throw new Error("before conflict range "+n.id);
  for(const run of op.runs)n.setRangeFills(run.start,run.end,run.value);
 }else{
  let current=serial(n[op.property]);const currentHash=snapshotRowFingerprint(current);if(currentHash===op.afterHash)continue;if(currentHash!==op.beforeHash)throw new Error("before conflict "+n.id+" "+op.property);
  for(const change of op.changes){if(change.path===""){current=change.value;continue;}const path=change.path.split("/").slice(1);let obj=current;for(const k of path.slice(0,-1))obj=obj[k];obj[path.at(-1)]=change.value;}
  if(op.property==="vectorNetwork")await n.setVectorNetworkAsync(current);else n[op.property]=current;
 }
 mutated.push(n.id);
}
return {mutatedNodeIds:[...new Set(mutated)],operationCount:ops.length,capturedAt:new Date().toISOString()};
}

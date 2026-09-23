/* Load snapshot_fingerprint.js and figma_apply_color_diff.js first.
 * One region call: guarded writes, immediate readback, compact old-color screen,
 * and one native screenshot. The screen is not a semantic final audit.
 */
async function applyAndReviewThemeRegion(figma,plan){
 if(plan.schemaVersion!==1||!plan.regionId||!Array.isArray(plan.operations)||!Array.isArray(plan.oldUiColors))throw new Error('invalid region plan');
 if(plan.oldUiColors.some(x=>!/^#[0-9A-Fa-f]{6}$/.test(x)))throw new Error('oldUiColors must be exact #RRGGBB values');
 const t0=Date.now(),scopeIds=plan.scopeNodeIds||[plan.regionId],scope=[],protectedIds=new Set(plan.protectedNodeIds||[]),excludedRoots=new Set(plan.excludedSubtreeRootIds||[]);
 for(const id of scopeIds){const node=await figma.getNodeByIdAsync(id);if(!node)throw new Error('scope node missing before writes: '+id);scope.push(node);}
 const priorSkip=figma.skipInvisibleInstanceChildren,allowed=new Set();
 try{figma.skipInvisibleInstanceChildren=false;const stack=[...scope];while(stack.length){const n=stack.pop();if(allowed.has(n.id)||excludedRoots.has(n.id))continue;allowed.add(n.id);if('children'in n)stack.push(...n.children);}}finally{figma.skipInvisibleInstanceChildren=priorSkip;}
 for(const op of plan.operations){if(!allowed.has(op.cloneId))throw new Error('write outside declared region: '+op.cloneId);if(protectedIds.has(op.cloneId))throw new Error('write to protected node: '+op.cloneId);}
 let write;
 try{write=await applyDeclaredColorDiff(figma,plan.operations);}catch(error){return {status:'needs-recovery',regionId:plan.regionId,error:String(error),verifiedCompletedNodeIds:error.verifiedCompletedNodeIds||[],note:'Some earlier operations may have completed; inspect/read back before retrying.'};}
 if(plan.reviewAfter===false)return {status:'writing',regionId:plan.regionId,write,timingMs:{total:Date.now()-t0},note:'Technical batch complete; final region screenshot and old-color screen still required.'};
 const screenshotNode=await figma.getNodeByIdAsync(plan.screenshotNodeId||plan.regionId);
 if(!screenshotNode)return {status:'needs-review',regionId:plan.regionId,error:'screenshot node missing after writes',write};
 const previousSkip=figma.skipInvisibleInstanceChildren;const old=new Set(plan.oldUiColors.map(x=>String(x).toUpperCase()));
 const hits=[];let hitCount=0,scannedNodes=0,readError=null;
 function scan(value,node,path){
  if(!value||typeof value!=='object')return;
  if(Array.isArray(value)){for(let i=0;i<value.length;i++)scan(value[i],node,path+'/'+i);return;}
  if(value.visible===false||value.opacity===0)return;
  if(['r','g','b'].every(k=>typeof value[k]==='number')){
   if(value.a===0)return;
   const hex='#'+['r','g','b'].map(k=>Math.round(value[k]*255).toString(16).padStart(2,'0')).join('').toUpperCase();
   if(old.has(hex)){hitCount++;if(hits.length<60)hits.push({nodeId:node.id,path,hex,protected:protectedIds.has(node.id)});}return;
  }
  for(const [key,child] of Object.entries(value))scan(child,node,path+'/'+key);
 }
 try{
  figma.skipInvisibleInstanceChildren=false;const stack=[...scope],seen=new Set();
  while(stack.length){const n=stack.pop();if(n.visible===false||n.opacity===0||seen.has(n.id)||excludedRoots.has(n.id))continue;seen.add(n.id);scannedNodes++;
   for(const key of ['fills','strokes','effects','vectorNetwork','textDecorationColor'])if(key in n)scan(n[key],n,key);
   if(n.type==='TEXT')for(const segment of n.getStyledTextSegments(['fills']))scan(segment.fills,n,'textRuns/fills/'+segment.start);
   if('children'in n)stack.push(...[...n.children].reverse());
  }
 }catch(error){readError=String(error);}finally{figma.skipInvisibleInstanceChildren=previousSkip;}
 if(readError)return {status:'needs-review',regionId:plan.regionId,error:readError,write,scannedNodes};
 let screenshotError=null;try{await screenshotNode.screenshot();}catch(error){screenshotError=String(error);}
 return {status:screenshotError?'needs-review':hitCount?'old-color-review':'visual-review',regionId:plan.regionId,write,
  oldColorScreen:{hitCount,hits,omittedHits:hitCount-hits.length},scannedNodes,excludedSubtreeRootIds:[...excludedRoots],screenshotError,
  timingMs:{total:Date.now()-t0},note:'Machine readback and old-color screen are not a final visual or semantic pass.'};
}
if(typeof module!=='undefined')module.exports={applyAndReviewThemeRegion};

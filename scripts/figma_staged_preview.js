/* Full-page native preview when image blocks cannot carry a tall 1:1 PNG.
 * Start returns a precisely marked temporary Frame. The orchestrator must
 * capture it with get_screenshot and call finish in a finally block. No
 * delivery write may begin while a preview Frame remains on the page.
 * Requires figma_snapshot.js and snapshot_fingerprint.js.
 */
const THEME_PREVIEW_PREFIX='__kv_theme_preview__';
async function startStagedThemePreview(figma,sourceId,sourceFingerprint,planHash,applyToClone){
 const source=await figma.getNodeByIdAsync(sourceId);
 if(!source||source.type!=='FRAME'||source.parent?.type!=='PAGE')
  throw new Error('source must be a top-level Frame');
 const page=source.parent;
 if(figma.currentPage.id!==page.id)await figma.setCurrentPageAsync(page);
 const baseline=await snapshotThemeTree(figma,sourceId);
 if(baseline.errors.length)throw new Error('source read errors');
 const actual=snapshotRowFingerprint(baseline.nodes.map(snapshotRowFingerprint));
 if(actual!==sourceFingerprint)throw new Error('source fingerprint changed');
 const childIdsBefore=page.children.map(node=>node.id);
 let clone=null;
 try{
  clone=source.clone();
  if(clone.parent?.id!==page.id)throw new Error('clone was not inserted beside source');
  clone.name=THEME_PREVIEW_PREFIX+planHash;
  const rightEdge=Math.max(...page.children.filter(node=>node!==clone&&node.type==='FRAME'&&
   node.y<source.y+source.height&&node.y+node.height>source.y).map(node=>node.x+node.width));
  clone.x=rightEdge+256;clone.y=source.y;
  const receipt=await applyToClone(figma,clone);
  if(!receipt||receipt.status!=='pass')throw new Error('write plan failed: '+JSON.stringify(receipt));
  const snapshot=await snapshotThemeTree(figma,clone.id);
  if(snapshot.errors.length)throw new Error('preview snapshot read errors');
  return {schemaVersion:1,status:'awaiting-screenshot',sourceId,sourceFingerprint,
   planHash,cloneId:clone.id,pageId:page.id,childIdsBefore,writeReceipt:receipt,
   previewFingerprint:snapshotRowFingerprint(snapshot.nodes.map(snapshotRowFingerprint)),
   previewNodeCount:snapshot.nodes.length,width:clone.width,height:clone.height,
   createdAt:new Date().toISOString()};
 }catch(error){
  if(clone)clone.remove();
  if(JSON.stringify(page.children.map(node=>node.id))!==JSON.stringify(childIdsBefore))
   throw new Error('preview failed and cleanup did not restore page: '+error);
  return {schemaVersion:1,status:'fail',temporaryCloneRemoved:true,error:String(error),
   errorStack:String(error?.stack||error).slice(0,2400),
   sourceId,sourceFingerprint,planHash};
 }
}
async function finishStagedThemePreview(figma,sourceId,cloneId,sourceFingerprint,
                                        planHash,childIdsBefore){
 const source=await figma.getNodeByIdAsync(sourceId);
 const clone=await figma.getNodeByIdAsync(cloneId);
 if(!source||!clone||source.parent?.type!=='PAGE'||clone.parent?.id!==source.parent.id)
  throw new Error('exact preview/source siblings not found');
 if(clone.name!==THEME_PREVIEW_PREFIX+planHash)
  throw new Error('preview marker mismatch; refusing removal');
 const page=source.parent;
 if(figma.currentPage.id!==page.id)await figma.setCurrentPageAsync(page);
 clone.remove();
 const childIdsAfter=page.children.map(node=>node.id);
 if(JSON.stringify(childIdsAfter)!==JSON.stringify(childIdsBefore))
  throw new Error('preview removal did not restore original page child order');
 const sourceNow=await snapshotThemeTree(figma,sourceId);
 if(sourceNow.errors.length||
    snapshotRowFingerprint(sourceNow.nodes.map(snapshotRowFingerprint))!==sourceFingerprint)
  throw new Error('source changed during preview');
 return {schemaVersion:1,status:'pass',temporaryCloneRemoved:true,
  sourceId,cloneId,sourceFingerprint,planHash,pageChildOrderRestored:true,
  completedAt:new Date().toISOString()};
}

/* Load figma_snapshot.js, snapshot_fingerprint.js and
 * figma_snapshot_transport.js first. This call emits one KVSS image block
 * for the lossless clone snapshot. Retrieve the 1:1 full-page visual with
 * get_screenshot as a separate evidence call after this succeeds.
 * Source visual evidence is the Phase 1 screenshot already saved locally;
 * 1:1 review crops are derived from the whole-page PNG.
 */
async function captureThemeFinalReview(figma, sourceId, cloneId, kvCloneId,
                                       expectedSourceFingerprint,
                                       snapshotFileName='theme-final-snapshot.png') {
  const source = await figma.getNodeByIdAsync(sourceId);
  const clone = await figma.getNodeByIdAsync(cloneId);
  const kv = await figma.getNodeByIdAsync(kvCloneId);
  if (!source || !clone || !kv) throw new Error('final review target missing');
  if (!source.parent || source.parent.type !== 'PAGE' || source.parent.id !== clone.parent?.id)
    throw new Error('source and clone are not siblings on a page');
  if (figma.currentPage.id !== source.parent.id)
    await figma.setCurrentPageAsync(source.parent);

  const sourceSnapshot = await snapshotThemeTree(figma, sourceId);
  const cloneSnapshot = await snapshotThemeTree(figma, cloneId);
  if (sourceSnapshot.errors.length || cloneSnapshot.errors.length)
    throw new Error('final snapshot read errors');
  const sourceFingerprint = snapshotRowFingerprint(sourceSnapshot.nodes.map(snapshotRowFingerprint));
  if (sourceFingerprint !== expectedSourceFingerprint)
    throw new Error('source changed: ' + sourceFingerprint);
  const cloneFingerprint = snapshotRowFingerprint(cloneSnapshot.nodes.map(snapshotRowFingerprint));
  const artifact = packThemeSnapshotPng(cloneSnapshot);
  figma.io.write(snapshotFileName,artifact.bytes);
  return {schemaVersion:1,status:'captured',sourceId,cloneId,kvCloneId,
    sourceFingerprint,cloneFingerprint,
    sourceNodes:sourceSnapshot.nodes.length,cloneNodes:cloneSnapshot.nodes.length,
    kvLocked:kv.locked,kvParentId:kv.parent?.id??null,
    clonePosition:{x:clone.x,y:clone.y},
    transport:{fileName:snapshotFileName,kind:artifact.kind,rawBytes:artifact.rawBytes,
               packedBytes:artifact.packedBytes,checksum:artifact.checksum},
    screenshotRequired:{nodeId:cloneId,width:clone.width,height:clone.height,scale:1},
    imageBlockCount:1,capturedAt:new Date().toISOString()};
}

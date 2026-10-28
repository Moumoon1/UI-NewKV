/* A stateless, read-only transport. Each row is verified against one frozen manifest.
 * Parts read only their listed nodes. No persistent Figma cache or canvas writes.
 */
async function planThemeSnapshotChunks(figma, rootId, pageId, maxRawChars=1500000, sourceCheck=null) {
  await figma.setCurrentPageAsync(await figma.getNodeByIdAsync(pageId));
  const started=Date.now();let sourceProof;
  if(sourceCheck){
    const source=await snapshotThemeTree(figma,sourceCheck.rootId);
    const fingerprint=snapshotRowFingerprint(source.nodes.map(snapshotRowFingerprint));
    if(source.errors.length||fingerprint!==sourceCheck.fingerprint)throw Error('original source changed');
    sourceProof={rootId:source.rootId,fingerprint,nodes:source.nodes.length,capturedAt:source.capturedAt};
  }
  const snapshot=await snapshotThemeTree(figma,rootId);
  if(snapshot.errors.length)throw Error('snapshot planning read errors');
  const rows=snapshot.nodes.map(n=>[n.id,snapshotRowFingerprint(n)]);
  const chunks=[];let indices=[],size=0;
  for(let i=0;i<snapshot.nodes.length;i++){
    const chars=JSON.stringify(snapshot.nodes[i]).length;
    if(chars>maxRawChars){chunks.push([i]);continue;}
    if(indices.length && size+chars>maxRawChars){chunks.push(indices);indices=[];size=0;}
    indices.push(i);size+=chars;
  }
  if(indices.length)chunks.push(indices);
  const {nodes,...snapshotMeta}=snapshot;
  const manifest={transportDocument:'manifest',version:1,pageId,rootId,snapshotMeta,rows,chunks,
    fullTreeFingerprint:snapshotRowFingerprint(rows.map(r=>r[1])),planningMs:Date.now()-started};
  if(sourceProof)manifest.sourceProof=sourceProof;
  manifest.manifestHash=snapshotRowFingerprint(manifest);
  if(JSON.stringify(manifest).length>17500)throw Error('snapshot manifest exceeds text response budget');
  return manifest;
}
async function readThemeSnapshotChunk(figma, request, maxArtifactBytes=700000) {
  const {partIndex,manifestHash,rootId,pageId,nodeIds,expectedRowsFingerprint}=request;
  if(!Number.isInteger(partIndex)||!nodeIds.length)throw Error('invalid part request');
  await figma.setCurrentPageAsync(await figma.getNodeByIdAsync(pageId));
  const started=Date.now();
  const snapshot=await snapshotThemeTree(figma,rootId,nodeIds);
  if(snapshot.errors.length)throw Error('part read errors');
  if(snapshotRowFingerprint(snapshot.nodes.map(snapshotRowFingerprint))!==expectedRowsFingerprint)
    throw Error('source changed at part '+partIndex);
  const document={transportDocument:'part',version:1,manifestHash,
    partIndex,rootId,capturedAt:snapshot.capturedAt,nodes:snapshot.nodes};
  const readMs=Date.now()-started,artifact=packThemeSnapshotPng(document);
  if(artifact.bytes.length>maxArtifactBytes)throw Error('part exceeds tested artifact budget: '+partIndex+' '+artifact.bytes.length);
  figma.io.write('theme-snapshot-part-'+partIndex+'.png',artifact.bytes);
  return {status:'captured',partIndex,manifestHash,nodes:snapshot.nodes.length,
    rawBytes:artifact.rawBytes,packedBytes:artifact.packedBytes,checksum:artifact.checksum,
    readMs,packMs:Date.now()-started-readMs,totalMs:Date.now()-started};
}

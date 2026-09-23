/* Load figma_snapshot.js, snapshot_fingerprint.js and figma_source_preflight.js first.
 * One full capture, one integrity-checked binary image artifact. The image channel
 * is a transport compatibility path, not a screenshot or visual evidence.
 */
const THEME_TRANSPORT_PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII=';
function utf8Bytes(value){const raw=unescape(encodeURIComponent(value));const out=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);return out;}
function themeTransportHash(bytes){let a=2166136261,b=5381;for(const x of bytes){a=Math.imul(a^x,16777619)>>>0;b=(Math.imul(b,33)^x)>>>0;}return [a,b];}
function packThemeBytes(raw){
 const out=[],recent=new Map();let i=0;
 while(i<raw.length){
  const key=(raw[i]<<24)|(raw[i+1]<<16)|(raw[i+2]<<8)|raw[i+3];
  const prev=i+3<raw.length?recent.get(key):undefined;let n=0;
  if(prev!==undefined&&i-prev<=65535)while(n<255&&i+n<raw.length&&raw[prev+n]===raw[i+n])n++;
  if(n>=7){const dist=i-prev;out.push(0,dist>>8,dist&255,n);for(let j=0;j<n;j++)if(i+j+3<raw.length)recent.set((raw[i+j]<<24)|(raw[i+j+1]<<16)|(raw[i+j+2]<<8)|raw[i+j+3],i+j);i+=n;}
  else{const c=raw[i];if(c===0)out.push(0,0,0,0);else out.push(c);if(i+3<raw.length)recent.set(key,i);i++;}
 }
 return new Uint8Array(out);
}
function packThemeSnapshotPng(snapshot){
 const raw=utf8Bytes(JSON.stringify(snapshot));if(raw.length>100000000)throw new Error('snapshot too large for one artifact');
 const packed=packThemeBytes(raw),png=atob(THEME_TRANSPORT_PNG),header=new Uint8Array(21),view=new DataView(header.buffer),hash=themeTransportHash(raw);
 for(let i=0;i<5;i++)header[i]='KVSS1'.charCodeAt(i);
 view.setUint32(5,raw.length,false);view.setUint32(9,packed.length,false);view.setUint32(13,hash[0],false);view.setUint32(17,hash[1],false);
 const bytes=new Uint8Array(png.length+header.length+packed.length);for(let i=0;i<png.length;i++)bytes[i]=png.charCodeAt(i);
 bytes.set(header,png.length);bytes.set(packed,png.length+header.length);
 return {bytes,rawBytes:raw.length,packedBytes:packed.length,checksum:hash.map(n=>n.toString(16).padStart(8,'0')).join('')};
}
async function captureThemeBaseline(figma,rootId,fileName='theme-source-snapshot.png',pageId=null){
 const t0=Date.now();
 if(pageId){const page=await figma.getNodeByIdAsync(pageId);if(!page||page.type!=='PAGE')throw new Error('declared page missing: '+pageId);await figma.setCurrentPageAsync(page);}
 const snapshot=await snapshotThemeTree(figma,rootId);
 if(snapshot.errors.length)throw new Error('source snapshot has '+snapshot.errors.length+' read errors');
 const summary=summarizeThemeSource(snapshot),tCapture=Date.now();
 const artifact=packThemeSnapshotPng(snapshot),tPack=Date.now();
 figma.io.write(fileName,artifact.bytes);
 return {...summary,transport:{kind:'kvss1-png',fileName,rawBytes:artifact.rawBytes,packedBytes:artifact.packedBytes,checksum:artifact.checksum},timingMs:{captureAndSummarize:tCapture-t0,pack:tPack-tCapture,total:Date.now()-t0}};
}
if(typeof module!=='undefined')module.exports={utf8Bytes,themeTransportHash,packThemeBytes,packThemeSnapshotPng,captureThemeBaseline};

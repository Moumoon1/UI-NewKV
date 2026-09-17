/* Full live collection, compact transport verification. IDs/order/properties all hash. */
function snapshotRowFingerprint(value) {
 let a=2166136261,b=5381;
 function token(s){for(let i=0;i<s.length;i++){a=Math.imul(a^s.charCodeAt(i),16777619)>>>0;b=(Math.imul(b,33)^s.charCodeAt(i))>>>0;}}
 function walk(v){
  if(v===null){token('L');return;}
  if(typeof v==='boolean'){token(v?'T':'F');return;}
  if(typeof v==='number'){if(!Number.isFinite(v))throw new Error('nonfinite');const buf=new ArrayBuffer(8);new DataView(buf).setFloat64(0,v===0?0:v,false);token('N'+Array.from(new Uint8Array(buf),x=>x.toString(16).padStart(2,'0')).join(''));return;}
  if(typeof v==='string'){token('S'+v.length+':'+v);return;}
  if(Array.isArray(v)){token('A'+v.length+':');for(const x of v)walk(x);return;}
  const keys=Object.keys(v).sort();token('O'+keys.length+':');for(const k of keys){walk(k);walk(v[k]);}
 }
 walk(value);return a.toString(16).padStart(8,'0')+b.toString(16).padStart(8,'0');
}

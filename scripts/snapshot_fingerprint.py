"""Verify full live snapshot row fingerprints, then reconstruct from exact templates.

The proof contains actual collector timestamps/errors and every row hash. Templates
are not marked fresh unless the live collector matched every ID/order/property.
This optimizes transport only: it never skips full collection or allows mismatches.
"""
import struct, copy

def row_fingerprint(value):
    a,b=2166136261,5381
    def token(s):
        nonlocal a,b
        data=s.encode('utf-16-le',errors='surrogatepass')
        for i in range(0,len(data),2):
            c=data[i]|data[i+1]<<8;a=((a^c)*16777619)&0xffffffff;b=((b*33)^c)&0xffffffff
    def walk(v):
        if v is None:token('L')
        elif isinstance(v,bool):token('T' if v else 'F')
        elif isinstance(v,(int,float)):token('N'+struct.pack('>d',0 if v==0 else v).hex())
        elif isinstance(v,str):token('S'+str(len(v.encode('utf-16-le',errors='surrogatepass'))//2)+':'+v)
        elif isinstance(v,list):
            token('A'+str(len(v))+':')
            for x in v:walk(x)
        elif isinstance(v,dict):
            keys=sorted(v,key=lambda s:s.encode('utf-16-be',errors='surrogatepass'));token('O'+str(len(keys))+':')
            for k in keys:walk(k);walk(v[k])
        else:raise ValueError('unsupported value')
    walk(value);return f'{a:08x}{b:08x}'

def verify_template(template,proof):
    if proof['errors'] or proof['mismatches'] or proof.get('mismatchCount',0) or proof['rootId']!=template['rootId'] or proof['nodeCount']!=len(template['nodes']):raise ValueError('live collection did not match template')
    expected=[row_fingerprint(n) for n in template['nodes']]
    if proof['verifiedTemplateHash']!=row_fingerprint(expected):raise ValueError('wrong template proof')
    out=copy.deepcopy(template);out['capturedAt']=proof['capturedAt'];out['errors']=proof['errors']
    return out

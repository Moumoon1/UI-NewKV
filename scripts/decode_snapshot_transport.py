#!/usr/bin/env python3
"""Decode verified lossless UTF-16 LZ snapshot parts; never accept missing chunks."""
import argparse, array, base64, json, sys
from pathlib import Path

def decode_parts(parts):
    parts = sorted(parts, key=lambda p: p['part'])
    first = parts[0]
    if [p['part'] for p in parts] != list(range(first['partCount'])):
        raise ValueError('missing or duplicate transport parts')
    for p in parts:
        for key in ('contentHash', 'rawLength', 'packedLength', 'partCount'):
            if p[key] != first[key]: raise ValueError('source changed during capture')
        if p.get('errors'): raise ValueError('capture errors')
    encoded = ''.join(p['data'] for p in parts)
    if len(encoded) != first['packedLength']: raise ValueError('truncated transport')
    packed = array.array('H'); packed.frombytes(base64.b64decode(encoded).decode('utf-8').encode('utf-16-le'))
    if sys.byteorder != 'little': packed.byteswap()
    out = array.array('H'); i = 0
    while i < len(packed):
        if packed[i] != 126: out.append(packed[i]); i += 1; continue
        if packed[i+1] == 126: out.append(126); i += 2; continue
        end = i+1
        while packed[end] != 126: end += 1
        token = ''.join(chr(x) for x in packed[i+1:end]); distance, length = (int(x,36) for x in token.split('.'))
        if distance <= 0 or distance > len(out): raise ValueError('invalid backreference')
        for _ in range(length): out.append(out[-distance])
        i = end+1
    a,b = 2166136261,5381
    for c in out:
        a = ((a ^ c)*16777619)&0xffffffff; b = ((b*33)^c)&0xffffffff
    if f'{a:x}:{b:x}:{len(out)}' != first['contentHash']: raise ValueError('integrity hash mismatch')
    if sys.byteorder != 'little': out.byteswap()
    result = json.loads(out.tobytes().decode('utf-16-le'))
    interval = [min(p['capturedAt'] for p in parts),max(p['capturedAt'] for p in parts)]
    if 'snapshot' in result: result['snapshot']['capturedAt'] = interval[1]
    return result, interval

if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory'); args=ap.parse_args(); root=Path(args.directory)
    result,interval=decode_parts([json.loads(p.read_text()) for p in root.glob('source-part-*.json')])
    (root/'source-before.json').write_text(json.dumps(result['snapshot'],ensure_ascii=False))
    (root/'kv-node.json').write_text(json.dumps(result['kv'],ensure_ascii=False))
    (root/'capture-interval.json').write_text(json.dumps({'interval':interval,'contentStable':True}))
    print({'nodes':len(result['snapshot']['nodes']),'interval':interval})

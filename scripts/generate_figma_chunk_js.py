#!/usr/bin/env python3
"""Generate manifest or exact-row part calls without a persistent Figma cache."""
import argparse
import json
from pathlib import Path
from transport_codec import zlib_helper
from snapshot_fingerprint import row_fingerprint


def build_manifest(root_id, page_id, source_check=None):
    return build('planThemeSnapshotChunks', [root_id, page_id,1500000,source_check], compress=False)


def build_part(manifest, index):
    frozen=dict(manifest);expected=frozen.pop('manifestHash')
    if row_fingerprint(frozen)!=expected:
        raise ValueError('manifest integrity mismatch')
    rows=[manifest['rows'][i] for i in manifest['chunks'][index]]
    request={k:manifest[k] for k in ['rootId','pageId','manifestHash']}
    request.update(partIndex=index,nodeIds=[r[0] for r in rows],
                   expectedRowsFingerprint=row_fingerprint([r[1] for r in rows]))
    return build('readThemeSnapshotChunk', [request], compress=True)


def build(function, args, compress):
    root = Path(__file__).parent
    names = ['figma_snapshot.js', 'snapshot_fingerprint.js', 'figma_snapshot_chunks.js']
    program = (zlib_helper() if compress else '')
    if compress:
        names.insert(2, 'figma_snapshot_transport.js')
    helpers=[]
    for name in names:
        helper=(root/name).read_text()
        if name=='figma_snapshot_chunks.js':
            marker='async function readThemeSnapshotChunk'
            plan,part=helper.split(marker,1)
            helper=marker+part if compress else plan
        helpers.append(helper)
    program += '\n'.join(helpers)
    program += '\nreturn await ' + function + '(figma,' + ','.join(
        json.dumps(a, ensure_ascii=False, separators=(',', ':')) for a in args) + ');\n'
    if len(program) > 45000:
        raise ValueError('chunk program exceeds Figma request budget')
    return program


if __name__ == '__main__':
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('manifest');p.add_argument('root');p.add_argument('page')
    p.add_argument('--source-id');p.add_argument('--source-fingerprint')
    p=sub.add_parser('part');p.add_argument('manifest',type=Path);p.add_argument('index',type=int)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if a.command=='manifest':
        if bool(a.source_id)!=bool(a.source_fingerprint):ap.error('source ID and fingerprint must be given together')
        check={'rootId':a.source_id,'fingerprint':a.source_fingerprint} if a.source_id else None
        code=build_manifest(a.root,a.page,check)
    else:code=build_part(json.loads(a.manifest.read_text()),a.index)
    a.out.write_text(code);print(json.dumps({'path':str(a.out),'characters':len(code)}))

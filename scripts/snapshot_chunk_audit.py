"""Validate stateless transport parts against one immutable full-tree manifest."""
import argparse
import json
from pathlib import Path
from snapshot_fingerprint import row_fingerprint
from decode_theme_snapshot_png import validate_snapshot


def validate_manifest(manifest):
    frozen=dict(manifest); expected=frozen.pop('manifestHash',None)
    if manifest.get('transportDocument')!='manifest' or manifest.get('version')!=1:
        raise ValueError('invalid manifest format')
    if row_fingerprint(frozen)!=expected:
        raise ValueError('manifest integrity mismatch')
    if manifest['snapshotMeta'].get('rootId')!=manifest['rootId'] or manifest['snapshotMeta'].get('errors'):
        raise ValueError('manifest source metadata mismatch or read errors')
    rows=manifest['rows'];ids=[r[0] for r in rows]
    if len(ids)!=len(set(ids)) or manifest['rootId'] not in ids:
        raise ValueError('manifest duplicate IDs or missing root')
    coverage=[i for c in manifest['chunks'] for i in c]
    if not all(manifest['chunks']) or sorted(coverage)!=list(range(len(rows))):
        raise ValueError('manifest must cover every row exactly once')
    if row_fingerprint([r[1] for r in rows])!=manifest['fullTreeFingerprint']:
        raise ValueError('manifest tree fingerprint mismatch')


def validate_part(part, manifest, index):
    validate_manifest(manifest)
    if (part.get('transportDocument')!='part' or part.get('version')!=1
            or part.get('manifestHash')!=manifest['manifestHash']
            or part.get('partIndex')!=index or part.get('rootId')!=manifest['rootId']):
        raise ValueError('part identity mismatch')
    expected=[manifest['rows'][i] for i in manifest['chunks'][index]]
    rows=part.get('nodes',[])
    if len(rows)!=len(expected):
        raise ValueError('part row count mismatch')
    for row,(node_id,fingerprint) in zip(rows,expected):
        if row.get('id')!=node_id or row_fingerprint(row)!=fingerprint:
            raise ValueError('part row changed: '+node_id)
    return part


def assemble(manifest, parts):
    validate_manifest(manifest)
    indexes=[p.get('partIndex') for p in parts]
    if sorted(indexes)!=list(range(len(manifest['chunks']))):
        raise ValueError('missing or duplicate parts')
    rows=[None]*len(manifest['rows'])
    for p in parts:
        i=p['partIndex'];validate_part(p,manifest,i)
        for destination,row in zip(manifest['chunks'][i],p['nodes']):
            rows[destination]=row
    snapshot={**manifest['snapshotMeta'],'nodes':rows}
    validate_snapshot(json.dumps(snapshot,ensure_ascii=False).encode())
    if row_fingerprint([row_fingerprint(r) for r in rows])!=manifest['fullTreeFingerprint']:
        raise ValueError('assembled fingerprint mismatch')
    by_id={r['id']:r for r in rows}
    seen=set()
    def visit(node_id):
        if node_id in seen:raise ValueError('cycle or duplicate child')
        seen.add(node_id)
        for child in by_id[node_id]['children']:
            if child not in by_id or by_id[child]['parentId']!=node_id:
                raise ValueError('incomplete parent/child graph')
            visit(child)
    visit(snapshot['rootId'])
    if len(seen)!=len(rows):raise ValueError('disconnected snapshot nodes')
    return snapshot


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path)
    ap.add_argument('parts',type=Path,nargs='+');ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();m=json.loads(a.manifest.read_text());parts=[json.loads(p.read_text()) for p in a.parts]
    result=assemble(m,parts);temp=a.out.with_name(a.out.name+'.partial')
    temp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')));temp.replace(a.out)
    print(json.dumps({'status':'pass','rootId':result['rootId'],'nodes':len(result['nodes']),
                      'fullTreeFingerprint':m['fullTreeFingerprint'],'parts':len(parts),
                      'captureInterval':[min(p['capturedAt'] for p in parts),max(p['capturedAt'] for p in parts)]}))

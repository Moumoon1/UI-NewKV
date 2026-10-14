#!/usr/bin/env python3
"""Compile a frozen color manifest into a compact Figma clone-apply function.

The emitted function is for a disposable preview and the eventual single
commit alike. It never writes vectorNetwork directly; mirrored vector colors
are checked after writable Paint setters run.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from theme_audit import parts


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


TOKEN_CODES = {'gradientStops': 'g', 'color': 'c', 'regions': 'r',
               'fills': 'f', 'strokes': 's', 'value': 'v'}


def encoded_path(tokens):
    return '.'.join(TOKEN_CODES.get(token, token) for token in tokens)


def build(source, manifest, write_plan, kv_source):
    if write_plan.get('ctaButtonOverlay') is not None:
        raise ValueError('raster CTA button overlay is forbidden; keep baked image pixels unchanged')
    if write_plan.get('sourceRootId') != source.get('rootId'):
        raise ValueError('write plan source mismatch')
    if write_plan.get('kvSourceId') != kv_source.get('rootId') or kv_source.get('errors'):
        raise ValueError('fresh KV subtree snapshot required')
    node_rows = {row['id']: row for row in source['nodes']}
    paths = {op['sourceId']: op['path'] for op in write_plan['operations']}
    node_paths = {source['rootId']: []}
    for row in source['nodes']:
        base = node_paths.get(row['id'])
        if base is not None:
            node_paths.update({child: base + [index]
                               for index, child in enumerate(row['children'])})
    detach_ids = write_plan.get('detachInstanceIds') or []
    if detach_ids and write_plan.get('postDetachMapping') != 'structural-fingerprint':
        raise ValueError('instance detach requires structural-fingerprint mapping')
    if len(detach_ids) != len(set(detach_ids)) or any(
            node_id not in node_paths or
            node_rows[node_id]['props'].get('type') != 'INSTANCE'
            for node_id in detach_ids):
        raise ValueError('invalid or duplicate instance detach target')
    detach_paths = sorted((node_paths[node_id] for node_id in detach_ids),
                          key=lambda path: (len(path), path))
    colors = []
    color_index = {}

    def color_id(target):
        value = tuple(target[key] for key in 'rgb')
        if value not in color_index:
            color_index[value] = len(colors)
            colors.append(''.join(f'{round(channel * 16777215):06x}' for channel in value))
        return color_index[value]

    paint_changes = defaultdict(list)
    range_changes = defaultdict(list)
    vector_checks = defaultdict(list)
    for entry in manifest['entries']:
        if entry['disposition'] != 'change':
            continue
        tokens = parts(entry['path'])
        if tokens[:1] != ['nodes'] or tokens[2] != 'props':
            raise ValueError('invalid color manifest path')
        node_id, prop = tokens[1], tokens[3]
        if node_id not in node_rows:
            raise ValueError('unknown color node')
        index = color_id(entry['target'])
        if prop in ('fills', 'strokes'):
            paint_changes[(node_id, prop)].append([encoded_path(tokens[4:]), index])
        elif prop == 'textRuns' and tokens[4] == 'fills':
            range_changes[(node_id, int(tokens[5]))].append([encoded_path(tokens[7:]), index])
        elif prop == 'vectorNetwork':
            vector_checks[node_id].append([encoded_path(tokens[4:]), index])
        else:
            raise ValueError('unsupported changed color path: ' + entry['path'])

    setters = []
    for op in write_plan['operations']:
        node_id = op['sourceId']
        if op['kind'] != 'property':
            continue
        prop = op['property']
        if prop not in ('fills', 'strokes'):
            raise ValueError('unsupported property setter: ' + prop)
        setters.append([op['path'], prop, paint_changes.pop((node_id, prop), []),
                        bool(node_rows[node_id]['props'].get(
                            'fillStyleId' if prop == 'fills' else 'strokeStyleId'))])
    if paint_changes:
        raise ValueError('changed Paint lacks a frozen setter: ' + str(list(paint_changes)[:3]))

    text_ops = []
    for op in write_plan['operations']:
        if op['kind'] != 'text-range':
            continue
        node_id = op['sourceId']
        runs = node_rows[node_id]['props'].get('textRuns', {}).get('fills') or []
        matches = [index for index, run in enumerate(runs)
                   if run['start'] == op['start'] and run['end'] == op['end']]
        if len(matches) != 1:
            raise ValueError('text range cannot map to one source segment: ' + node_id)
        index = matches[0]
        alpha = [[i, new.get('opacity', 1)] for i, (old, new) in
                 enumerate(zip(op['before'], op['after']))
                 if old.get('opacity', 1) != new.get('opacity', 1)]
        text_ops.append([op['path'], op['start'], op['end'],
                         range_changes.pop((node_id, index), []), alpha])
    if range_changes:
        raise ValueError('changed styled text has no setter: ' + str(list(range_changes)[:3]))

    node_opacity = []
    paint_opacity = defaultdict(list)
    for op in write_plan.get('opacityOps', []):
        if op.get('property') == 'fills':
            paint_opacity[op['sourceId']].append([op['paintIndex'], op['after']])
        else:
            node_opacity.append([op['path'], op['after']])
    for node_id, rows in paint_opacity.items():
        matches = [op for op in setters if op[0] == paths.get(node_id) and op[1] == 'fills']
        if len(matches) != 1:
            raise ValueError('fill opacity change lacks a Paint setter: ' + node_id)
        matches[0].append(rows)
    vector = [[paths[node_id], rows] for node_id, rows in vector_checks.items()]
    if any(node_id not in paths for node_id in vector_checks):
        raise ValueError('vector mirror cannot map to source node path')

    data = {'colors': colors, 'setters': setters, 'text': text_ops,
            'opacity': node_opacity, 'vector': vector,
            'detach': detach_paths,
            'kvId': kv_source['rootId'], 'kvNodeCount': len(kv_source['nodes'])}
    transition = write_plan.get('kvTransitionOverlay')
    if transition is not None:
        if (not isinstance(transition, dict) or
                transition.get('name') != '__kv_theme_transition__' or
                transition.get('insertIndex') != 2 or
                any(type(transition.get(key)) not in (int, float)
                    for key in ('x', 'y', 'width', 'height')) or
                transition['x'] != 0 or transition['width'] != source['nodes'][0]['props']['width'] or
                transition['height'] <= 0 or transition['y'] < 0 or
                transition['y'] + transition['height'] > kv_source['nodes'][0]['props']['height'] or
                not isinstance(transition.get('color'), dict) or
                any(type(transition['color'].get(key)) not in (int, float) or
                    not 0 <= transition['color'][key] <= 1 for key in 'rgb')):
            raise ValueError('invalid independent KV transition overlay')
        data['transition'] = transition
    program = r'''async function applyThemeWriteToClone(figma,clone){
const D=__DATA__;
const previousSkip=figma.skipInvisibleInstanceChildren;
figma.skipInvisibleInstanceChildren=false;
try{
function node(p){let n=clone;for(const i of p){if(!n.children||!n.children[i])throw Error('missing mapped clone child '+p.join('.')+' at '+i+' under '+n.id+'/'+n.type);n=n.children[i];}return n;}
function copy(x,label){const raw=JSON.stringify(x);if(raw===undefined)throw Error('unserializable Paint '+label+' type='+typeof x);return JSON.parse(raw);}
function clean(x){if(Array.isArray(x)){x.forEach(clean);return;}if(x&&typeof x==='object'){delete x.boundVariables;for(const v of Object.values(x))clean(v);}}
function steps(path){const names={g:'gradientStops',c:'color',r:'regions',f:'fills',s:'strokes',v:'value'};return path.split('.').map(t=>names[t]||Number(t));}
function rgb(index){const h=D.colors[index];return [0,1,2].map(i=>parseInt(h.slice(6*i,6*i+6),16)/16777215);}
function writeColor(base,path,index){let x=base;for(const step of steps(path))x=x[step];if(!x)throw Error('color path missing');const c=rgb(index);x.r=c[0];x.g=c[1];x.b=c[2];}
function sameColor(base,path,index){let x=base;for(const step of steps(path))x=x?.[step];const c=rgb(index);return !!x&&Math.abs(x.r-c[0])<1e-5&&Math.abs(x.g-c[1])<1e-5&&Math.abs(x.b-c[2])<1e-5;}
const kvSource=await figma.getNodeByIdAsync(D.kvId);
if(!kvSource||kvSource.type!=='FRAME'||kvSource.width!==clone.width)throw Error('KV source changed or not same-width Frame');
const kv=kvSource.clone();clone.appendChild(kv);kv.x=0;kv.y=0;
const kvCount=1+kv.findAll().length;if(kvCount!==D.kvNodeCount)throw Error('KV clone subtree count mismatch');
kv.locked=true;if(!kv.locked)throw Error('KV locked subtree readback mismatch');
// Append preserves every original source child path during UI setters.
let detachedCount=0;
for(const p of D.detach){const n=node(p);if(n.type!=='INSTANCE')throw Error('detach path is not an instance '+p.join('.'));const children=n.children.length;const d=n.detachInstance();if(!d||d.children.length!==children)throw Error('detach changed child structure '+p.join('.'));detachedCount++;}
const cached=new Map();
for(const [p] of D.text){const key=p.join('.');if(cached.has(key))continue;const n=node(p);if(n.type!=='TEXT')throw Error('styled range target not text');cached.set(key,n.getStyledTextSegments(['fills']));}
let setters=0,rangeSetters=0,opacitySetters=0,colorsChecked=0;
for(const [p,prop,changes,clearStyle,alpha] of D.setters){
 const n=node(p);if(n[prop]===undefined)throw Error('missing writable Paint property '+n.id+'/'+prop);
 const paints=copy(n[prop],n.id+'/'+prop);clean(paints);
 for(const [path,index] of changes)writeColor(paints,path,index);
 for(const [i,value] of alpha||[])paints[i].opacity=value;
 if(clearStyle){const style=prop==='fills'?'fillStyleId':'strokeStyleId';if(n[style])n[style]='';}
 n[prop]=paints;setters++;
 for(const [path,index] of changes){if(!sameColor(n[prop],path,index))throw Error('Paint readback mismatch '+n.id+'/'+prop);colorsChecked++;}
}
for(const [p,start,end,changes,alpha] of D.text){
 const n=node(p),segs=cached.get(p.join('.'));
 const found=segs.filter(s=>s.start===start&&s.end===end);
 if(found.length!==1)throw Error('styled text segment mismatch '+n.id+'/'+start);
 // A Paint-only range write must not require loading unavailable source fonts.
 if(found[0].fills===undefined)throw Error('styled segment missing fills '+n.id+'/'+start);
 const paints=copy(found[0].fills,n.id+'/range:'+start);clean(paints);
 for(const [path,index] of changes)writeColor(paints,path,index);
 for(const [i,value] of alpha)paints[i].opacity=value;
 n.setRangeFills(start,end,paints);rangeSetters++;
 const after=n.getStyledTextSegments(['fills']).filter(s=>s.end>start&&s.start<end);
 let cursor=start;
 for(const segment of after){
  if(segment.start>cursor)throw Error('styled text readback gap '+n.id);
  for(const [path,index] of changes){if(!sameColor(segment.fills,path,index))throw Error('styled text readback color mismatch '+n.id);colorsChecked++;}
  for(const [i,value] of alpha){if(Math.abs(segment.fills[i].opacity-value)>1e-5)throw Error('styled text readback alpha mismatch '+n.id);}
  cursor=Math.max(cursor,segment.end);
 }
 if(cursor<end)throw Error('styled text readback range missing '+n.id);
}
for(const [p,value] of D.opacity){const n=node(p);n.opacity=value;opacitySetters++;if(Math.abs(n.opacity-value)>1e-5)throw Error('node opacity readback mismatch '+n.id);}
let vectorChecked=0;
for(const [p,changes] of D.vector){const n=node(p),network=n.vectorNetwork;for(const [path,index] of changes){if(!sameColor(network,path,index))throw Error('derived vector mirror mismatch '+n.id);vectorChecked++;}}
clone.insertChild(1,kv);
let transitionId=null;
if(D.transition){
 const t=D.transition,fade=figma.createRectangle();
 clone.insertChild(t.insertIndex,fade);fade.name=t.name;
 fade.x=t.x;fade.y=t.y;fade.resize(t.width,t.height);
 const c=t.color;
 fade.fills=[{type:'GRADIENT_LINEAR',gradientTransform:[[0,1,0],[-1,0,1]],
  gradientStops:[{position:0,color:{...c,a:0}},{position:1,color:{...c,a:1}}]}];
 fade.locked=true;transitionId=fade.id;
 if(fade.x!==t.x||fade.y!==t.y||fade.width!==t.width||fade.height!==t.height||!fade.locked)
  throw Error('KV transition overlay readback mismatch');
}
return {status:'pass',setters,rangeSetters,opacitySetters,colorsChecked,vectorChecked,detachedCount,
 kvCloneId:kv.id,kvNodeCount:kvCount,kvLocked:kv.locked,kvPosition:[kv.x,kv.y],kvSize:[kv.width,kv.height],transitionId};
}finally{figma.skipInvisibleInstanceChildren=previousSkip;}
}'''
    return program.replace('__DATA__', compact(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'manifest', 'write_plan', 'kv_source'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    values = [json.loads(getattr(args, name).read_text()) for name in
              ('source', 'manifest', 'write_plan', 'kv_source')]
    program = build(*values)
    args.out.write_text(program)
    print(json.dumps({'characters': len(program), 'output': str(args.out)}))


if __name__ == '__main__':
    main()

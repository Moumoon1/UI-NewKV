#!/usr/bin/env python3
"""Compile a frozen color manifest into a compact Figma clone-apply function.

The emitted function is for a disposable preview and the eventual single
commit alike. It never writes vectorNetwork directly; mirrored vector colors
are checked after writable Paint setters run.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path

from theme_audit import equal, parts


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


TOKEN_CODES = {'gradientStops': 'g', 'color': 'c', 'regions': 'r',
               'fills': 'f', 'strokes': 's', 'value': 'v'}


def encoded_path(tokens):
    return '.'.join(TOKEN_CODES.get(token, token) for token in tokens)


def normalize_kv_placement(source, placement=None):
    """Freeze the exact existing parent and insertion order of the intact KV."""
    spec = deepcopy(placement if placement is not None else
                    {'childIndex': 1, 'x': 0, 'y': 0})
    rows = {row['id']: row for row in source['nodes']}
    parent_id = spec.get('parentSourceId', source['rootId'])
    paths, pending = {source['rootId']: []}, [source['rootId']]
    while pending:
        current = pending.pop()
        for index, child in enumerate(rows[current]['children']):
            paths[child] = paths[current] + [index]
            pending.append(child)
    if (parent_id not in paths or
            (parent_id != source['rootId'] and rows[parent_id]['props'].get('type') != 'FRAME') or
            type(spec.get('childIndex')) is not int or
            not 0 <= spec['childIndex'] <= len(rows[parent_id]['children']) or
            any(type(spec.get(k)) not in (int, float) or not math.isfinite(spec[k])
                for k in ('x', 'y'))):
        raise ValueError('kvPlacement needs an existing Frame parent, childIndex, x and y')
    if 'parentPath' in spec and spec['parentPath'] != paths[parent_id]:
        raise ValueError('kvPlacement parent path differs from source')
    return {**spec, 'parentSourceId': parent_id, 'parentPath': paths[parent_id]}


def normalize_geometry_ops(source, operations):
    """Validate exact user-authorized y/height changes and derive their paths.

    Transform translations and GROUP descendants in the same Frame coordinate
    space are deterministic readback obligations, never additional setters.
    """
    if not isinstance(operations, list):
        raise ValueError('geometryOps must be an explicit list')
    if not operations:
        return []
    rows = {row['id']: row for row in source['nodes']}
    paths, pending = {source['rootId']: []}, [source['rootId']]
    while pending:
        node_id = pending.pop()
        for index, child in enumerate(rows[node_id]['children']):
            if child in paths:
                raise ValueError('geometry source graph has a duplicate child')
            paths[child] = paths[node_id] + [index]
            pending.append(child)
    required = {'sourceId', 'property', 'before', 'after', 'reason', 'userAuthorization'}
    allowed = required | {'path', 'derivedRelativeTransform', 'derivedNodeTranslations'}
    seen, result = set(), []

    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)

    def translation(node_id, after):
        props = rows[node_id]['props']
        before = props.get('y')
        if not finite(before) or not finite(after):
            raise ValueError('derived GROUP translation requires finite source y')
        value = {'sourceId': node_id, 'path': paths[node_id], 'before': before, 'after': after}
        if 'relativeTransform' in props:
            transform = props['relativeTransform']
            if (not isinstance(transform, list) or len(transform) != 2 or
                    any(not isinstance(row, list) or len(row) != 3 or
                        any(not finite(v) for v in row) for row in transform) or
                    not equal(transform[1][2], before)):
                raise ValueError('geometry y must match the source relativeTransform translation')
            target = deepcopy(transform)
            target[1][2] = after
            value['derivedRelativeTransform'] = {'before': deepcopy(transform), 'after': target}
        return value

    for operation in operations:
        if (not isinstance(operation, dict) or not required <= operation.keys() or
                set(operation) - allowed):
            raise ValueError('geometry operation requires exact source/property/before/after/reason/userAuthorization')
        node_id, prop = operation['sourceId'], operation['property']
        if node_id not in paths or prop not in ('y', 'height'):
            raise ValueError('geometry operation only supports an exact source y or height')
        if any(not isinstance(operation[key], str) or not operation[key].strip()
               for key in ('reason', 'userAuthorization')):
            raise ValueError('geometry operation needs a reason and explicit user authorization')
        key = (node_id, prop)
        if key in seen:
            raise ValueError('duplicate geometry operation')
        seen.add(key)
        before, after = operation['before'], operation['after']
        props = rows[node_id]['props']
        if (not finite(before) or not finite(after) or
                not equal(props.get(prop), before) or equal(before, after)):
            raise ValueError('geometry before mismatch, nonfinite value or unchanged operation')
        if prop == 'height' and (before <= 0 or after <= 0 or
                                 not finite(props.get('width')) or props['width'] <= 0):
            raise ValueError('height geometry requires positive dimensions')
        if 'path' in operation and operation['path'] != paths[node_id]:
            raise ValueError('geometry source path mismatch')
        normalized = {key: deepcopy(operation[key]) for key in required}
        normalized['path'] = paths[node_id]
        if prop == 'y':
            own_translation = translation(node_id, after)
            if 'derivedRelativeTransform' in own_translation:
                normalized['derivedRelativeTransform'] = own_translation['derivedRelativeTransform']
            if props.get('type') == 'GROUP':
                delta = after - before
                descendants, stack = [], list(reversed(rows[node_id]['children']))
                boundaries = {'FRAME', 'INSTANCE', 'COMPONENT', 'COMPONENT_SET', 'SECTION'}
                while stack:
                    child_id = stack.pop()
                    if (child_id, 'y') in seen:
                        raise ValueError('geometry operations overlap a derived GROUP translation')
                    seen.add((child_id, 'y'))
                    child = rows[child_id]
                    child_y = child['props'].get('y')
                    if not finite(child_y):
                        raise ValueError('derived GROUP child has no finite y')
                    descendants.append(translation(child_id, child_y + delta))
                    if child['props'].get('type') not in boundaries:
                        stack.extend(reversed(child['children']))
                normalized['derivedNodeTranslations'] = descendants
        if ('derivedRelativeTransform' in operation and
                not equal(operation['derivedRelativeTransform'], normalized.get('derivedRelativeTransform'))):
            raise ValueError('geometry derived relativeTransform mismatch')
        if ('derivedNodeTranslations' in operation and
                not equal(operation['derivedNodeTranslations'], normalized.get('derivedNodeTranslations'))):
            raise ValueError('geometry derived GROUP translations mismatch')
        result.append(normalized)
    return result


def normalize_export_bounds(source, expected, value):
    """Freeze native overflow bounds for an explicitly resized page."""
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {'source', 'target', 'basis'} or
            not isinstance(value['basis'], str) or not value['basis'].strip()):
        raise ValueError('exportBounds needs exact source/target native bounds and basis')
    for side in ('source', 'target'):
        bounds = value[side]
        if (not isinstance(bounds, dict) or set(bounds) != {'x', 'y', 'width', 'height'} or
                any(type(bounds[k]) not in (int, float) or not math.isfinite(bounds[k]) for k in bounds) or
                bounds['width'] <= 0 or bounds['height'] <= 0):
            raise ValueError('invalid native export bounds')
    before = next(row['props'] for row in source['nodes'] if row['id'] == source['rootId'])
    after = next(row['props'] for row in expected['nodes'] if row['id'] == expected['rootId'])
    if (any(not equal(value['source'][key], value['target'][key]) for key in ('x', 'y', 'width')) or
            not equal(value['target']['height'] - value['source']['height'],
                      after['height'] - before['height'])):
        raise ValueError('native export bounds must retain origin/width and declared page height delta')
    return deepcopy(value)


def build(source, manifest, write_plan, kv_source):
    if write_plan.get('ctaButtonOverlay') is not None:
        raise ValueError('raster CTA button overlay is forbidden; keep baked image pixels unchanged')
    if write_plan.get('sourceRootId') != source.get('rootId'):
        raise ValueError('write plan source mismatch')
    if write_plan.get('kvSourceId') != kv_source.get('rootId') or kv_source.get('errors'):
        raise ValueError('fresh KV subtree snapshot required')
    geometry_ops = normalize_geometry_ops(source, write_plan.get('geometryOps', []))
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

    kv_props = kv_source['nodes'][0].get('props') or {}
    kv_images = [paint.get('imageHash') for paint in kv_props.get('fills') or []
                 if paint.get('type') == 'IMAGE' and paint.get('visible', True)]
    data = {'colors': colors, 'setters': setters, 'text': text_ops,
            'opacity': node_opacity, 'vector': vector,
            'geometry': [[op['path'], op['property'], op['before'], op['after'],
                          op.get('derivedRelativeTransform'),
                          [[row['path'], row['before'], row['after']]
                           for row in op.get('derivedNodeTranslations', [])]] for op in geometry_ops],
            'detach': detach_paths,
            'kvId': kv_source['rootId'], 'kvNodeCount': len(kv_source['nodes']),
            'kvPlacement': normalize_kv_placement(source, write_plan.get('kvPlacement')),
            'kvImageHashes': kv_images if kv_props.get('type') == 'RECTANGLE' else None}
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
function geometryEqual(actual,wanted){return typeof actual==='number'&&Number.isFinite(actual)&&Math.abs(actual-wanted)<=1e-6;}
function sameTransform(actual,wanted){return Array.isArray(actual)&&actual.length===2&&actual.every((row,i)=>Array.isArray(row)&&row.length===3&&row.every((v,j)=>geometryEqual(v,wanted[i][j])));}
const kvSource=await figma.getNodeByIdAsync(D.kvId);
if(!kvSource||!['FRAME','RECTANGLE'].includes(kvSource.type)||kvSource.width!==clone.width)throw Error('KV source changed or not same-width Frame/Rectangle');
if(D.kvImageHashes&&(!Array.isArray(kvSource.fills)||JSON.stringify(kvSource.fills.filter(p=>p.type==='IMAGE'&&p.visible!==false).map(p=>p.imageHash))!==JSON.stringify(D.kvImageHashes)))throw Error('KV source image Paint changed');
const kv=kvSource.clone();clone.appendChild(kv);kv.x=0;kv.y=0;
const kvCount=1+(('findAll' in kv)?kv.findAll().length:0);if(kvCount!==D.kvNodeCount)throw Error('KV clone subtree count mismatch');
kv.locked=true;if(!kv.locked)throw Error('KV locked subtree readback mismatch');
// Append preserves every original source child path during UI setters.
let detachedCount=0;
for(const p of D.detach){const n=node(p);if(n.type!=='INSTANCE')throw Error('detach path is not an instance '+p.join('.'));const children=n.children.length;const d=n.detachInstance();if(!d||d.children.length!==children)throw Error('detach changed child structure '+p.join('.'));detachedCount++;}
let geometrySetters=0,derivedGeometryChecked=0;
for(const [p,prop,before,after,transform,derived] of D.geometry){
 const n=node(p);if(!geometryEqual(n[prop],before))throw Error('geometry before mismatch '+n.id+'/'+prop);
 if(transform&&!sameTransform(n.relativeTransform,transform.before))throw Error('geometry transform before mismatch '+n.id);
 const descendants=derived.map(([path,oldY,newY])=>{
  const child=node(path),t=copy(child.relativeTransform,'GROUP descendant transform '+child.id);
  if(!geometryEqual(child.y,oldY)||!sameTransform(t,t)||!geometryEqual(t[1][2],oldY))throw Error('GROUP descendant before mismatch '+child.id);
  t[1][2]=newY;
  return {child,newY,t,x:child.x,width:child.width,height:child.height};
 });
 const oldX=n.x,oldY=n.y,oldWidth=n.width,oldHeight=n.height;
 if(prop==='height'){
  if(!('resizeWithoutConstraints' in n)||typeof n.resizeWithoutConstraints!=='function')throw Error('height geometry setter unavailable '+n.id);
  n.resizeWithoutConstraints(oldWidth,after);
 }else if(prop==='y'){n.y=after;}else{throw Error('unsupported geometry property '+prop);}
 if(!geometryEqual(n[prop],after)||!geometryEqual(n.width,oldWidth)||!geometryEqual(n.x,oldX)||
    (prop==='y'&&!geometryEqual(n.height,oldHeight))||(prop==='height'&&!geometryEqual(n.y,oldY)))
  throw Error('geometry readback mismatch '+n.id+'/'+prop);
 if(transform&&!sameTransform(n.relativeTransform,transform.after))throw Error('geometry transform readback mismatch '+n.id);
 for(const item of descendants){const {child,newY,t,x,width,height}=item;
  if(!geometryEqual(child.y,newY)||!geometryEqual(child.x,x)||!geometryEqual(child.width,width)||!geometryEqual(child.height,height)||
    !sameTransform(child.relativeTransform,t))throw Error('GROUP descendant readback mismatch '+child.id);
  derivedGeometryChecked++;
 }
 geometrySetters++;
}
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
const kp=D.kvPlacement,kpNode=node(kp.parentPath);
kpNode.insertChild(kp.childIndex,kv);kv.x=kp.x;kv.y=kp.y;
if(kpNode.children[kp.childIndex]!==kv||kv.x!==kp.x||kv.y!==kp.y)throw Error('KV placement readback mismatch');
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
return {status:'pass',setters,rangeSetters,opacitySetters,geometrySetters,derivedGeometryChecked,colorsChecked,vectorChecked,detachedCount,
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

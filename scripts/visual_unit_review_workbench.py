#!/usr/bin/env python3
"""Build a visual, path-exact review workbench from one frozen Figma snapshot.

The output is evidence and candidate rule scopes, never semantic decisions or
a PASS. The native screenshot is copied unchanged beside the local HTML.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import shutil

from execution_audit import color_inventory
from expand_channel_decisions import _channel_kind, _hex, _match, paths_hash
from theme_audit import snapshot_document


def _multiply(left, right):
    a, b, c = left[0]
    d, e, f = left[1]
    g, h, i = right[0]
    j, k, l = right[1]
    return [[a * g + b * j, a * h + b * k, a * i + b * l + c],
            [d * g + e * j, d * h + e * k, d * i + e * l + f]]


def _bounds(nodes, root_id):
    cache = {}

    def transform(node_id):
        if node_id in cache:
            return cache[node_id]
        row = nodes[node_id]
        props = row['props']
        if node_id == root_id:
            result = [[1, 0, 0], [0, 1, 0]]
        else:
            parent = row['parentId']
            if parent not in nodes:
                raise ValueError('disconnected node: ' + node_id)
            local = props.get('relativeTransform')
            if not local:
                local = [[1, 0, props.get('x') or 0],
                         [0, 1, props.get('y') or 0]]
            # Some imported component descendants expose x/y in their
            # component parent's coordinate space, repeated at several
            # wrapper levels. Do not add that same offset repeatedly.
            parent_props = nodes[parent]['props']
            px, py = parent_props.get('x') or 0, parent_props.get('y') or 0
            cw, ch = props.get('width') or 0, props.get('height') or 0
            pw, ph = parent_props.get('width') or 0, parent_props.get('height') or 0
            cx, cy = props.get('x') or 0, props.get('y') or 0
            if (cx + cw > pw + 1 or cy + ch > ph + 1) and (
                    px - 1 <= cx <= px + pw + 1 and py - 1 <= cy <= py + ph + 1):
                local = [[local[0][0], local[0][1], local[0][2] - px],
                         [local[1][0], local[1][1], local[1][2] - py]]
            result = _multiply(transform(parent), local)
        cache[node_id] = result
        return result

    result = {}
    for node_id, row in nodes.items():
        t = transform(node_id)
        w, h = row['props'].get('width') or 0, row['props'].get('height') or 0
        corners = [(t[0][0] * x + t[0][1] * y + t[0][2],
                    t[1][0] * x + t[1][1] * y + t[1][2])
                   for x, y in ((0, 0), (w, 0), (0, h), (w, h))]
        xs, ys = zip(*corners)
        result[node_id] = [round(min(xs), 2), round(min(ys), 2),
                           round(max(xs) - min(xs), 2),
                           round(max(ys) - min(ys), 2)]
    return result


def build(source, unresolved_paths=None, unit_depth=3, max_unit_channels=None,
          merge_channel_kinds=False):
    if unit_depth < 1:
        raise ValueError('unit depth must be at least one')
    if max_unit_channels is not None and max_unit_channels < 1:
        raise ValueError('max unit channels must be positive')
    doc = snapshot_document(source)
    nodes, root_id = doc['nodes'], source['rootId']
    inventory = color_inventory(source)
    active = {item['path']: item for item in inventory['entries'] if not item['inactive']}
    if unresolved_paths is None:
        unresolved_paths = set(active)
    else:
        unresolved_paths = set(unresolved_paths)
        unknown = unresolved_paths - set(active)
        if unknown:
            raise ValueError('unresolved paths absent from active inventory: ' + str(len(unknown)))
    ancestry = {}
    for node_id in nodes:
        chain, cursor, seen = [], node_id, set()
        while cursor in nodes:
            if cursor in seen:
                raise ValueError('parent cycle')
            seen.add(cursor)
            chain.append(cursor)
            if cursor == root_id:
                break
            cursor = nodes[cursor]['parentId']
        if chain[-1] != root_id:
            raise ValueError('disconnected node: ' + node_id)
        ancestry[node_id] = chain
    bounds = _bounds(nodes, root_id)
    pending_by_ancestor = defaultdict(int)
    for path in unresolved_paths:
        for ancestor in ancestry[active[path]['nodeId']]:
            pending_by_ancestor[ancestor] += 1
    buckets = defaultdict(list)
    for path in unresolved_paths:
        item = active[path]
        chain = list(reversed(ancestry[item['nodeId']]))
        if max_unit_channels is None:
            unit_id = chain[min(unit_depth, len(chain) - 1)]
        else:
            unit_id = next((ancestor for ancestor in chain[1:]
                            if pending_by_ancestor[ancestor] <= max_unit_channels),
                           item['nodeId'])
        kind, source_hex = _channel_kind(path), _hex(item['source'])
        bucket_kind = None if merge_channel_kinds else kind
        buckets[(unit_id, nodes[item['nodeId']]['props'].get('type'), bucket_kind, source_hex)].append(item)
    units = []
    for (unit_id, node_type, kind, source_hex), items in buckets.items():
        selector = {'subtreeId': unit_id, 'nodeType': node_type,
                    'sourceHex': source_hex}
        if kind is not None:
            selector['channelKind'] = kind
        matched = sorted(item['path'] for item in active.values()
                         if _match(selector, item, nodes, ancestry))
        pending = sorted(item['path'] for item in items)
        # A candidate may include already-reviewed paths. Never present its hash
        # as a safe new rule until the reviewer handles that overlap explicitly.
        safe_candidate = matched == pending
        node_rows = []
        for node_id in sorted({item['nodeId'] for item in items}):
            props = nodes[node_id]['props']
            own_items = [item for item in items if item['nodeId'] == node_id]
            text = props.get('characters') or ''
            text_runs = []
            for index, run in enumerate((props.get('textRuns') or {}).get('fills') or []):
                text_runs.append({'index': index, 'start': run.get('start'),
                                  'end': run.get('end'),
                                  'text': text[run.get('start') or 0:run.get('end') or 0]})
            node_rows.append({'nodeId': node_id, 'name': props.get('name', ''),
                              'type': props.get('type'), 'bounds': bounds[node_id],
                              'text': text[:160], 'textRuns': text_runs,
                              'paths': sorted(item['path'] for item in own_items),
                              'hasImageFill': any(isinstance(p, dict) and p.get('type') == 'IMAGE'
                                                  for p in props.get('fills') or []),
                              'isMask': bool(props.get('isMask'))})
        chain = list(reversed(ancestry[unit_id]))
        region_id = chain[min(2, len(chain) - 1)]
        channel_kinds = sorted({_channel_kind(item['path']) for item in items})
        units.append({'unitId': unit_id, 'unitName': nodes[unit_id]['props'].get('name', ''),
                      'regionId': region_id, 'regionName': nodes[region_id]['props'].get('name', ''),
                      'ancestry': [{'id': n, 'name': nodes[n]['props'].get('name', '')}
                                   for n in chain],
                      'bounds': bounds[unit_id], 'sourceHex': source_hex,
                      'nodeType': node_type, 'channelKind': kind or '+'.join(channel_kinds),
                      'channelKinds': channel_kinds, 'crossKind': len(channel_kinds) > 1,
                      'pendingCount': len(pending), 'pendingPaths': pending,
                      'candidateRule': ({'selector': selector,
                                         'reviewedPathsHash': paths_hash(matched),
                                         'matchedPaths': matched} if safe_candidate else None),
                      'overlapWithReviewed': sorted(set(matched) - set(pending)),
                      'nodes': node_rows})
    units.sort(key=lambda u: (u['bounds'][1], u['bounds'][0], u['regionId'],
                              u['unitId'], u['nodeType'], u['channelKind'], u['sourceHex']))
    return {'schemaVersion': 1, 'status': 'review-workbench-only',
            'sourceHash': inventory['sourceHash'], 'rootId': root_id,
            'sourceSize': [nodes[root_id]['props'].get('width'),
                           nodes[root_id]['props'].get('height')],
            'activeChannels': len(active), 'pendingChannels': len(unresolved_paths),
            'unitDepth': unit_depth if max_unit_channels is None else None,
            'maxUnitChannels': max_unit_channels,
            'mergeChannelKinds': merge_channel_kinds, 'units': units,
            'note': 'No role, target, protection or visual PASS is inferred. Review every member and exception.'}


def _html(report):
    data = json.dumps(report, ensure_ascii=False).replace('<', '\\u003c')
    return '''<!doctype html><html lang="zh"><meta charset="utf-8">
<title>Figma 视觉单元颜色审查</title>
<style>
body{margin:0;font:13px/1.5 system-ui,sans-serif;color:#252525;background:#f4f4f1}
header{position:sticky;top:0;z-index:3;background:white;padding:12px 16px;border-bottom:1px solid #ddd}
main{display:grid;grid-template-columns:minmax(430px,1fr) 420px;height:calc(100vh - 66px)}
#list{overflow:auto;padding:12px}#viewer{overflow:auto;background:#d8d8d4;padding:16px}
#canvas{position:relative;width:414px;margin:auto}#canvas img{display:block;width:100%}
#box{position:absolute;border:2px solid #eb5c32;background:#eb5c3226;pointer-events:none;box-sizing:border-box}
article{background:white;border:1px solid #ddd;border-radius:8px;margin:0 0 8px;padding:10px;cursor:pointer}
article.selected{border-color:#eb5c32;box-shadow:0 0 0 1px #eb5c32}
summary{font-weight:650}.muted{color:#666}.warn{color:#a53c18}
code{font-size:11px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f3;padding:8px}
.swatch{display:inline-block;width:12px;height:12px;border:1px solid #777;vertical-align:-2px}
input{min-width:330px;padding:6px;border:1px solid #ccc;border-radius:5px}
</style><header><strong>逐视觉单元审查 · 非自动分类</strong>　<span id="count"></span>　
<input id="filter" placeholder="按区域、节点、文字、路径筛选"></header>
<main><section id="list"></section><section id="viewer"><div id="canvas"><img src="source-native.png"><div id="box"></div></div></section></main>
<script>
const report=__DATA__, list=document.querySelector('#list'), viewer=document.querySelector('#viewer');
const box=document.querySelector('#box'), filter=document.querySelector('#filter');
document.querySelector('#count').textContent=`${report.pendingChannels} 待审通道 / ${report.units.length} 组`;
document.querySelector('#canvas').style.width=report.sourceSize[0]+'px';
function show(u,card){document.querySelectorAll('article').forEach(x=>x.classList.remove('selected'));
card.classList.add('selected');let [x,y,w,h]=u.bounds;
Object.assign(box.style,{left:x+'px',top:y+'px',width:w+'px',height:h+'px'});
viewer.scrollTop=Math.max(0,y-80);}
function render(){list.replaceChildren();let q=filter.value.toLowerCase();for(const u of report.units){
let hay=[u.regionName,u.unitName,u.unitId,u.sourceHex,...u.nodes.flatMap(n=>[n.name,n.text,...n.paths])].join(' ').toLowerCase();if(q&&!hay.includes(q))continue;
let card=document.createElement('article');let title=document.createElement('summary');
let swatch=document.createElement('span');swatch.className='swatch';swatch.style.background=u.sourceHex;title.append(swatch);
title.append(document.createTextNode(` ${u.regionName} › ${u.unitName} · ${u.nodeType}/${u.channelKind} ${u.sourceHex} · ${u.pendingCount} 条`));
card.append(title);let detail=document.createElement('details');let sum=document.createElement('summary');sum.textContent=`${u.nodes.length} 个节点 · ${u.unitId} · ${u.bounds.join(', ')}`;detail.append(sum);
let body=document.createElement('div');let note=document.createElement('p');note.className='muted';note.textContent='候选规则仅在完整成员逐个确认后可用；不包含角色、目标色或保护结论。';body.append(note);
if(u.overlapWithReviewed.length){let p=document.createElement('p');p.className='warn';p.textContent=`与已审规则重叠 ${u.overlapWithReviewed.length} 条，须先拆分或显式覆写`;body.append(p)}
if(u.crossKind){let p=document.createElement('p');p.className='warn';p.textContent=`包含 ${u.channelKinds.join('、')}，须分别确认它们是同一视觉职责；必要时拆分规则。`;body.append(p)}
for(const n of u.nodes){let p=document.createElement('p');let strong=document.createElement('strong');strong.textContent=`${n.name} [${n.type}] ${n.nodeId}`;p.append(strong);
if(n.text)p.append(document.createElement('br'),document.createTextNode(n.text));
if(n.textRuns.length)p.append(document.createElement('br'),document.createTextNode('文字区间 '+JSON.stringify(n.textRuns)));
if(n.hasImageFill||n.isMask)p.append(document.createElement('br'),document.createTextNode(`IMAGE=${n.hasImageFill} mask=${n.isMask}`));
let pre=document.createElement('pre');pre.textContent=n.paths.join('\\n');p.append(pre);body.append(p)}
let pre=document.createElement('pre');pre.textContent=JSON.stringify(u.candidateRule||{overlapWithReviewed:u.overlapWithReviewed},null,2);body.append(pre);detail.append(body);card.append(detail);
card.addEventListener('click',()=>show(u,card));list.append(card)}}filter.addEventListener('input',render);render();
</script></html>'''.replace('__DATA__', data)


def _review_queue(report):
    """Compact navigation; not a replacement for inspecting every member."""
    lines = ['# 视觉单元审查队列', '',
             f"原稿 `{report['rootId']}`；待审 {report['pendingChannels']} 条，"
             f"分为 {len(report['units'])} 组。此索引不包含语义结论。", '']
    by_region = defaultdict(list)
    for index, unit in enumerate(report['units'], 1):
        by_region[(unit['regionId'], unit['regionName'])].append((index, unit))
    for (_, region_name), units in by_region.items():
        lines.extend([f'## {region_name} · {sum(u["pendingCount"] for _, u in units)} 条', '',
                      '| # | 单元 | 类型 / 通道 | 旧色 | 条数 | 文字/节点预览 |',
                      '|---:|---|---|---|---:|---|'])
        for index, unit in units:
            preview = '；'.join((n['text'] or n['name'])[:30] for n in unit['nodes'][:3])
            fields = [str(index), unit['unitName'],
                      unit['nodeType'] + ' / ' + unit['channelKind'],
                      unit['sourceHex'], str(unit['pendingCount']), preview]
            safe = [re.sub(r'[\r\n|]+', ' ', str(value)) for value in fields]
            lines.append('| ' + ' | '.join(safe) + ' |')
        lines.extend(['', '每组须打开 `index.html` 或 `review-units.json` 核对完整成员、'
                      '原生图位置、精确路径与例外；不能仅凭此摘要复制哈希。', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('native_png', type=Path)
    parser.add_argument('--decision-report', type=Path,
                        help='Optional same-source expander report; focus unresolved paths')
    parser.add_argument('--unit-depth', type=int, default=3)
    parser.add_argument('--max-unit-channels', type=int,
                        help='Adaptively descend hierarchy until each review unit has at most N pending channels')
    parser.add_argument('--merge-channel-kinds', action='store_true',
                        help='Show same-hex Paint/text/vector channels together; reviewer must check each kind')
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.source.read_text())
    unresolved = None
    if args.decision_report:
        previous = json.loads(args.decision_report.read_text())
        if previous.get('sourceHash') != color_inventory(source)['sourceHash']:
            raise ValueError('decision report source hash mismatch')
        unresolved = previous['unresolvedPaths']
    report = build(source, unresolved, args.unit_depth, args.max_unit_channels,
                   args.merge_channel_kinds)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.native_png, args.out_dir / 'source-native.png')
    (args.out_dir / 'review-units.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (args.out_dir / 'review-queue.md').write_text(_review_queue(report))
    (args.out_dir / 'index.html').write_text(_html(report))
    print(json.dumps({'status': report['status'], 'pending': report['pendingChannels'],
                      'units': len(report['units']), 'output': str(args.out_dir)}))


if __name__ == '__main__':
    main()

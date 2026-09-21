#!/usr/bin/env python3
"""Generate compact guarded recolor code from frozen current/target templates."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["trial", "expand"])
    parser.add_argument("current")
    parser.add_argument("target")
    parser.add_argument("operations")
    args = parser.parse_args()
    current = json.loads(Path(args.current).read_text())
    target = json.loads(Path(args.target).read_text())
    operations = json.loads(Path(args.operations).read_text())
    before_index = {row["id"]: row for row in current["nodes"]}
    after_index = {row["id"]: row for row in target["nodes"]}

    def collect_colors(before, after, out):
        if isinstance(before, dict) and isinstance(after, dict):
            if all(key in before and key in after for key in ("r", "g", "b")):
                left = [before[key] for key in ("r", "g", "b")]
                right = [after[key] for key in ("r", "g", "b")]
                if left != right:
                    pair = {"before": left, "after": right}
                    if pair not in out:
                        out.append(pair)
                return
            for key in before.keys() & after.keys():
                collect_colors(before[key], after[key], out)
        elif isinstance(before, list) and isinstance(after, list):
            for left, right in zip(before, after):
                collect_colors(left, right, out)

    property_targets = []
    text_targets = []
    for operation in operations:
        if operation["property"] == "textRuns":
            text_targets.append({"id": operation["cloneId"], "runs": operation["runs"]})
            continue
        before = before_index[operation["cloneId"]]["props"][operation["property"]]
        after = after_index[operation["cloneId"]]["props"][operation["property"]]
        colors = []
        collect_colors(before, after, colors)
        if not colors:
            raise RuntimeError(f"non-color property change in compact revision: {operation['cloneId']} {operation['property']}")
        property_targets.append({
            "id": operation["cloneId"],
            "property": operation["property"],
            "beforeHash": operation["beforeHash"],
            "afterHash": operation["afterHash"],
            "colors": colors,
        })

    scripts = Path(__file__).parent
    print((scripts / "snapshot_fingerprint.js").read_text())
    print("const propertyTargets=" + json.dumps(property_targets, ensure_ascii=False, separators=(",", ":")) + ";")
    print("const textTargets=" + json.dumps(text_targets, ensure_ascii=False, separators=(",", ":")) + ";")
    print(
        """
function serial(v){if(typeof v==='symbol')return {$mixed:true};if(v===undefined)return {$undefined:true};if(Array.isArray(v))return v.map(serial);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).map(k=>[k,serial(v[k])]));return v;}
function recolor(value,pairs){
 if(Array.isArray(value))return value.map(v=>recolor(v,pairs));
 if(value&&typeof value==='object'){
  if(['r','g','b'].every(k=>k in value)){
   const pair=pairs.find(p=>Math.abs(value.r-p.before[0])<1e-6&&Math.abs(value.g-p.before[1])<1e-6&&Math.abs(value.b-p.before[2])<1e-6);
   if(pair)return {...value,r:pair.after[0],g:pair.after[1],b:pair.after[2]};
  }
  return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,recolor(v,pairs)]));
 }
 return value;
}
const mutated=[];
figma.skipInvisibleInstanceChildren=false;
const revisionRoot=await figma.getNodeByIdAsync('1237:6621');
if(!revisionRoot)throw new Error('missing revision root');
for(const target of propertyTargets){
 const node=(await figma.getNodeByIdAsync(target.id))||revisionRoot.findOne(n=>n.id===target.id);if(!node)throw new Error('missing '+target.id);
 const current=serial(node[target.property]);const hash=snapshotRowFingerprint(current);
 if(hash===target.afterHash)continue;
 if(hash!==target.beforeHash)throw new Error('before conflict '+target.id+' '+target.property);
 const next=recolor(current,target.colors);
 if(snapshotRowFingerprint(next)!==target.afterHash)throw new Error('compact transform mismatch '+target.id+' '+target.property);
 if(target.property==='vectorNetwork')await node.setVectorNetworkAsync(next);else node[target.property]=next;
 mutated.push(node.id);
}
for(const target of textTargets){
 const node=(await figma.getNodeByIdAsync(target.id))||revisionRoot.findOne(n=>n.id===target.id);if(!node||node.type!=='TEXT')throw new Error('missing text '+target.id);
 for(const run of target.runs){
  const current=serial(node.getRangeFills(run.start,run.end));const hash=snapshotRowFingerprint(current);const after=snapshotRowFingerprint(run.value);
  if(hash===after)continue;
  if(hash!==run.beforeHash)throw new Error('before conflict text '+target.id);
  node.setRangeFills(run.start,run.end,run.value);mutated.push(node.id);
 }
}
"""
    )
    if args.phase == "trial":
        print(
            """
const image=await figma.getNodeByIdAsync('1237:6623');
const fade=await figma.getNodeByIdAsync('1237:6624');
if(!image||!fade||!('resize' in image)||!('resize' in fade))throw new Error('missing Hero fit carriers');
if(Math.abs(image.width-414)>1e-6||Math.abs(image.height-349.5)>1e-6)throw new Error('unexpected KV carrier geometry');
if(Math.abs(fade.x)>1e-6||Math.abs(fade.y-328)>1e-6||Math.abs(fade.width-414)>1e-6||Math.abs(fade.height-32)>1e-6)throw new Error('unexpected bottom fade geometry');
image.resize(414,360);fade.y=300;fade.resize(414,60);mutated.push(image.id,fade.id);
"""
        )
    print("return {mutatedNodeIds:[...new Set(mutated)],propertyCount:propertyTargets.length,textCount:textTargets.length,capturedAt:new Date().toISOString()};")


if __name__ == "__main__":
    main()

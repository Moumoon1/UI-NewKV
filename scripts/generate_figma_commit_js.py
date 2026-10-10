#!/usr/bin/env python3
"""Generate one guarded, atomic Figma delivery write using a previewed plan."""
import argparse
import json
from pathlib import Path


def build(source_id, fingerprint, plan_hash, apply_js, *, expected_nodes,
          expected_receipt, delivery_name):
    directory = Path(__file__).parent
    program = '\n'.join((directory / name).read_text() for name in (
        'figma_snapshot.js', 'snapshot_fingerprint.js'))
    program += '\n' + Path(apply_js).read_text() + '\n'
    args = json.dumps({'sourceId': source_id, 'sourceFingerprint': fingerprint,
                       'planHash': plan_hash, 'expectedNodes': expected_nodes,
                       'expectedReceipt': expected_receipt,
                       'deliveryName': delivery_name}, ensure_ascii=False,
                      separators=(',', ':'))
    program += '''\nasync function commitThemeOnce(figma,C){
 const source=await figma.getNodeByIdAsync(C.sourceId);
 if(!source||source.type!=='FRAME'||source.parent?.type!=='PAGE')
  throw Error('source must be a top-level Frame');
 const page=source.parent;
 if(figma.currentPage.id!==page.id)await figma.setCurrentPageAsync(page);
 if(page.children.some(n=>n.name.startsWith('__kv_theme_preview__')))
  throw Error('temporary preview remains on delivery page');
 const sourceBefore=await snapshotThemeTree(figma,C.sourceId);
 if(sourceBefore.errors.length)throw Error('source snapshot read errors');
 const before=snapshotRowFingerprint(sourceBefore.nodes.map(snapshotRowFingerprint));
 if(before!==C.sourceFingerprint)throw Error('source fingerprint changed');
 const childIdsBefore=page.children.map(n=>n.id);
 const rightEdge=Math.max(...page.children.filter(n=>n.type==='FRAME'&&
  n.y<source.y+source.height&&n.y+n.height>source.y).map(n=>n.x+n.width));
 let clone=null;
 try{
  clone=source.clone();
  if(clone.parent?.id!==page.id)throw Error('clone was not inserted beside source');
  const receipt=await applyThemeWriteToClone(figma,clone);
  if(!receipt||receipt.status!=='pass')throw Error('write receipt failed');
  for(const [key,value] of Object.entries(C.expectedReceipt))
   if(receipt[key]!==value)throw Error('write receipt mismatch '+key);
  if(receipt.kvLocked!==true)throw Error('KV subtree is not locked');
  clone.name=C.deliveryName;
  clone.x=rightEdge+256;clone.y=source.y;
  const delivered=await snapshotThemeTree(figma,clone.id);
  if(delivered.errors.length||delivered.nodes.length!==C.expectedNodes)
   throw Error('delivered snapshot structure mismatch');
  const sourceAfter=await snapshotThemeTree(figma,C.sourceId);
  if(sourceAfter.errors.length||
     snapshotRowFingerprint(sourceAfter.nodes.map(snapshotRowFingerprint))!==C.sourceFingerprint)
   throw Error('source changed during delivery');
  const childIdsAfter=page.children.map(n=>n.id);
  if(childIdsAfter.length!==childIdsBefore.length+1||
     childIdsAfter.filter(id=>id!==clone.id).length!==childIdsBefore.length||
     JSON.stringify(childIdsAfter.filter(id=>id!==clone.id))!==JSON.stringify(childIdsBefore)||
     childIdsAfter.filter(id=>id===clone.id).length!==1)throw Error('page child order changed');
  return {schemaVersion:1,status:'committed',sourceId:C.sourceId,
   sourceFingerprint:C.sourceFingerprint,planHash:C.planHash,
   cloneId:clone.id,kvCloneId:receipt.kvCloneId,
   clonePosition:{x:clone.x,y:clone.y},
   cloneSize:[clone.width,clone.height],nodeCount:delivered.nodes.length,
   cloneFingerprint:snapshotRowFingerprint(delivered.nodes.map(snapshotRowFingerprint)),
   writeReceipt:receipt,pageChildOrderPreserved:true,
   committedAt:new Date().toISOString()};
 }catch(error){
  if(clone)clone.remove();
  if(JSON.stringify(page.children.map(n=>n.id))!==JSON.stringify(childIdsBefore))
   throw Error('delivery failed and exact cleanup failed: '+String(error));
  return {schemaVersion:1,status:'fail',temporaryCloneRemoved:true,
   sourceId:C.sourceId,planHash:C.planHash,error:String(error)};
 }
}
return await commitThemeOnce(figma,''' + args + ''');\n'''
    if len(program) > 45000:
        raise ValueError('commit program exceeds 45,000-character safety budget')
    return program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_id')
    parser.add_argument('source_fingerprint')
    parser.add_argument('plan_hash')
    parser.add_argument('--apply-js', type=Path, required=True)
    parser.add_argument('--expected-nodes', type=int, required=True)
    parser.add_argument('--expected-receipt-json', required=True)
    parser.add_argument('--delivery-name', required=True)
    args = parser.parse_args()
    print(build(args.source_id, args.source_fingerprint, args.plan_hash,
                args.apply_js, expected_nodes=args.expected_nodes,
                expected_receipt=json.loads(args.expected_receipt_json),
                delivery_name=args.delivery_name), end='')


if __name__ == '__main__':
    main()

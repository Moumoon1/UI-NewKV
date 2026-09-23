/* Load figma_region_runner.js first. This batches only independent, already
 * gated regions. Each region still performs its own guarded write, readback,
 * old-color screen, and screenshot before the next region starts.
 */
async function applyAndReviewThemeRegions(figma,plans){
 if(!Array.isArray(plans)||plans.length<2)throw new Error('multi-region batch needs at least two plans');
 const regionIds=new Set(),writeKeys=new Set();
 for(const plan of plans){
  if(regionIds.has(plan.regionId))throw new Error('duplicate regionId: '+plan.regionId);regionIds.add(plan.regionId);
  const gate=plan.batchEligibility||{};
  if(gate.representativeGateStatus!=='pass'||gate.independent!==true||!gate.recipeHash||!gate.dependencyHash)
   throw new Error('region is not eligible for guarded batching: '+plan.regionId);
  if(plan.reviewAfter===false)throw new Error('batched region must review in the same call: '+plan.regionId);
  for(const op of plan.operations||[]){const key=op.cloneId+'\u0000'+op.property;if(writeKeys.has(key))throw new Error('overlapping region write: '+key);writeKeys.add(key);}
 }
 const results=[];
 for(const plan of plans){
  const result=await applyAndReviewThemeRegion(figma,plan);results.push(result);
  if(result.status!=='visual-review')return {status:'stopped-for-review',completedRegions:results.length-1,results};
 }
 return {status:'visual-review',completedRegions:results.length,results};
}
if(typeof module!=='undefined')module.exports={applyAndReviewThemeRegions};

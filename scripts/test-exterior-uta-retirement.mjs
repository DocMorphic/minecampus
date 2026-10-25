// Geometric regression for the three native UTA fragments and unsupported return.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {retiresPhotoSurface} from '../minecraft/exterior/service/photo-facades.mjs';
const dir=process.argv[2]??'dist-minecraft/exterior';
const plans=JSON.parse(fs.readFileSync(dir+'/photo-facades.json')).plans;
const plan=plans.find(p=>p.id==='DEBY_LOD2_5323191');
const coverage=JSON.parse(fs.readFileSync(new URL('../minecraft/exterior/photos/uta-photo-coverage-study.json',import.meta.url))).metrics[0];
const walls=plan.walls.map((w,i)=>({...w,accepted:coverage.walls[i].coverage>=.8&&coverage.walls[i].unfilled===0&&coverage.walls[i].maxFillDistance<=2}));
assert.deepEqual(walls.map(w=>w.accepted),[false,true,true,true,true,true]);
const photo={patches:[{...plan,walls,roofCache:new Map()}]};
const fixtures=JSON.parse(fs.readFileSync(new URL('../minecraft/exterior/photos/reactor-south-exterior-research.json',import.meta.url))).nativeFragmentMeasurements;
let removedSamples=0,preservedSamples=0;
for(const f of fixtures){
 assert.ok(retiresPhotoSurface(photo,...f.point),'recorded visible fragment hit');removedSamples++;
 for(let a=0;a<=10;a++)for(let b=0;b<=10-a;b++){
  const weights=[a/10,b/10,1-(a+b)/10],p=[0,1,2].map(k=>f.vertices.reduce((s,v,i)=>s+v[k]*weights[i],0));
  assert.ok(retiresPhotoSurface(photo,...p),'sampled native fragment triangle');removedSamples++;
 }
}
for(const [i,w]of walls.entries()){
 const s=(w.bounds[0][0]+w.bounds[1][0])/2,y=(w.bounds[0][1]+w.bounds[1][1])/2;
 const p=[w.anchor[0]+s*w.direction[0],y,w.anchor[2]+s*w.direction[2]];
 // East return and east wall adjoin protected survey neighbours. Their
 // photography may render, but this plan must not erase that neighbour's mesh.
 const owned=[2,4,5].includes(i);
 assert.equal(retiresPhotoSurface(photo,...p),owned,'survey wall '+i);
 if(owned)removedSamples++;else preservedSamples++;
}
for(const p of [[300,66,-40],[330,66,-40],[315,75,-40],[315,59,-40]]){assert.equal(retiresPhotoSurface(photo,...p),false,'outside owned envelope');preservedSamples++;}
const unavailable={patches:[]};for(const f of fixtures){assert.equal(retiresPhotoSurface(unavailable,...f.point),false);preservedSamples++;}
console.log(JSON.stringify({status:'PASS: measured fragment samples owned by supported walls; unsupported return, exterior controls and unavailable-source fallback preserved',removedSamples,preservedSamples,qualification:'Uses recorded coverage to test geometry ownership. Live imagery coverage and native appearance must be checked separately.'},null,2));

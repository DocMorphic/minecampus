#!/usr/bin/env node
// Compare complete affected collision packets using the packaged service code.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const [serviceRoot,baseline,dataRoot='dist-minecraft/exterior']=process.argv.slice(2);
if(!serviceRoot||!baseline)throw Error('Usage: test-exterior-cyclotron-annex.mjs <service-root> <baseline-data> [candidate-data]');
const at=n=>import(pathToFileURL(path.resolve(serviceRoot,'src',n)).href);
const {Frame}=await at('geo.mjs'),{voxelizeArea}=await at('voxel.mjs'),{attachSurveySurface}=await at('minecampus-survey.mjs');
const m=JSON.parse(fs.readFileSync(path.join(dataRoot,'manifest.json'))),count=16*16*96;
function scene(directory){const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>new Uint8Array(count)};attachSurveySurface(service,directory,{voxelizeArea});return service;}
const before=scene(baseline),after=scene(dataRoot),rows=[],changes=[],pairs={},transitionExamples={};let identical=0,changedCodes=0,changedProfiles=0,occupancyChanges=0;
for(const shift of [0,2]){
 const frame=new Frame(m.origin[0],m.origin[1],m.origin[2]-shift);
 for(let cx=10;cx<=13;cx++)for(let cz=-6;cz<=-3;cz++){
  const a=before.campusCollisionPacket(frame,cx,cz,48+shift,96),b=after.campusCollisionPacket(frame,cx,cz,48+shift,96);
  if(a.equals(b)){identical++;rows.push({cx,cz,shift,identical:true});continue;}
  let differences=0;
  for(let i=0;i<count;i++)if(a[i]!==b[i]){
   changedCodes++;differences++;const key=a[i]+'->'+b[i];pairs[key]=(pairs[key]??0)+1;
   const point={x:cx*16+i%16,y:48+shift+Math.floor(i/256),z:cz*16+Math.floor(i/16)%16,before:a[i],after:b[i]};
   (transitionExamples[key]??=[]);if(transitionExamples[key].length<8)transitionExamples[key].push(point);
   assert.ok(key==='4->6'||key==='255->0','Unexpected material/occupancy transition '+key);
   const bounds=m.tiles.find(t=>t.runtimeId===1000030054).bounds;
   assert.ok(point.x>=bounds[0][0]-4&&point.x<=bounds[1][0]+4&&point.z>=bounds[0][2]-4&&point.z<=bounds[1][2]+4&&point.y-shift>=bounds[0][1]-1&&point.y-shift<=bounds[1][1]+1,'Change outside annex envelope guard');
   const empty=v=>v===0||v===255; if(empty(a[i])!==empty(b[i]))occupancyChanges++;
   if(changes.length<60)changes.push({x:cx*16+i%16,y:48+shift+Math.floor(i/256),z:cz*16+Math.floor(i/16)%16,before:a[i],after:b[i]});
  }
  if(!a.subarray(count).equals(b.subarray(count)))changedProfiles++;
  rows.push({cx,cz,shift,identical:false,differences});
 }
}
assert.equal(changedProfiles,0,'Unrelated fine collision profiles changed');
assert.equal(occupancyChanges,0,'Known solid occupancy changed');
const result={status:changedCodes||changedProfiles?'PASS: bounded stone-to-plaster changes and provider-to-air cleanup only; v92 migration required':'PASS: all 32 complete collision packets are identical at both datums',packets:32,identicalPackets:identical,changedCodes,changedProfilePackets:changedProfiles,occupancyChanges,materialTransitions:pairs,transitionExamples,examples:changes,rows};
process.stdout.write(JSON.stringify(result,null,2)+'\n');

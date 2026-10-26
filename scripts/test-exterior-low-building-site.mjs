#!/usr/bin/env node
// Compare complete affected collision packets using the packaged service code.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const [serviceRoot,baseline,dataRoot='dist-minecraft/exterior']=process.argv.slice(2);
if(!serviceRoot||!baseline)throw Error('Usage: test-exterior-low-building-site.mjs <service-root> <baseline-data> [candidate-data]');
const at=n=>import(pathToFileURL(path.resolve(serviceRoot,'src',n)).href);
const {Frame}=await at('geo.mjs'),{voxelizeArea}=await at('voxel.mjs'),{attachSurveySurface}=await at('minecampus-survey.mjs');
const m=JSON.parse(fs.readFileSync(path.join(dataRoot,'manifest.json'))),count=16*16*96;
function scene(directory){const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>new Uint8Array(count)};attachSurveySurface(service,directory,{voxelizeArea});return service;}
const before=scene(baseline),after=scene(dataRoot),rows=[],changes=[],pairs={},transitionExamples={};let identical=0,changedCodes=0,changedProfiles=0,occupancyChanges=0;
for(const shift of [0,2]){
 const frame=new Frame(m.origin[0],m.origin[1],m.origin[2]-shift);
 for(let cx=8;cx<=13;cx++)for(let cz=-6;cz<=1;cz++){
  const a=before.campusCollisionPacket(frame,cx,cz,48+shift,96),b=after.campusCollisionPacket(frame,cx,cz,48+shift,96);
  if(a.equals(b)){identical++;rows.push({cx,cz,shift,identical:true});continue;}
  let differences=0;
  for(let i=0;i<count;i++)if(a[i]!==b[i]){
   changedCodes++;differences++;const key=a[i]+'->'+b[i];pairs[key]=(pairs[key]??0)+1;
   const point={x:cx*16+i%16,y:48+shift+Math.floor(i/256),z:cz*16+Math.floor(i/16)%16,before:a[i],after:b[i]};
   (transitionExamples[key]??=[]);if(transitionExamples[key].length<8)transitionExamples[key].push(point);
   assert.ok((a[i]===255&&b[i]===0)||((a[i]===255||a[i]===0)&&b[i]>0&&b[i]!==255),'Unexpected removal of known solid or material transition '+key);
   const site=m.architecture.lowBuildingSite,stack=site.stack;
   const shaft=Math.hypot(point.x+.5-stack.baseMC[0],point.z+.5-stack.baseMC[2])<4 && point.y-shift>=stack.baseMC[1]-2 && point.y-shift<stack.topMC[1]+2;
   const court=point.x>=159&&point.x<=181&&point.z>=-34&&point.z<=-8&&point.y-shift>=60&&point.y-shift<=71;
   assert.ok(shaft||court,'Change outside reconstructed stack/courtyard');
   if(b[i]>0&&b[i]!==255)assert.ok(shaft,'New solid outside stack '+JSON.stringify(point));
   const empty=v=>v===0||v===255; if(empty(a[i])!==empty(b[i]))occupancyChanges++;
   if(changes.length<60)changes.push({x:cx*16+i%16,y:48+shift+Math.floor(i/256),z:cz*16+Math.floor(i/16)%16,before:a[i],after:b[i]});
  }
  if(!a.subarray(count).equals(b.subarray(count))){
   changedProfiles++;
   const profiles=p=>{assert.equal(p.toString('ascii',count,count+4),'MCSP');const out=new Map();for(let j=count+8;j<p.length;j+=4)out.set(p.readUInt16LE(j),p.readUInt16LE(j+2));return out;};
   const pa=profiles(a),pb=profiles(b);
   for(const i of new Set([...pa.keys(),...pb.keys()]))if(pa.get(i)!==pb.get(i)){
    const x=cx*16+i%16,z=cz*16+Math.floor(i/16)%16,y=48+Math.floor(i/256),stack=m.architecture.lowBuildingSite.stack;
    assert.ok(Math.hypot(x+.5-stack.baseMC[0],z+.5-stack.baseMC[2])<3&&y>=stack.baseMC[1]-2&&y<=stack.topMC[1]+2,'Fine profile changed outside stack');
    assert.ok(!pa.has(i)&&pb.has(i)&&b[i]===4,'Existing fine profile changed or removed');
   }
  }
  rows.push({cx,cz,shift,identical:false,differences});
 }
}
// All profile differences were checked against the new stack above.
// Added solid cells must lie within the stack bound checked above.
const result={status:changedCodes||changedProfiles?'PASS: bounded new stack solids and source cleanup; no known-solid removals; new fine profiles limited to stack; v94 migration required':'PASS: all 96 complete collision packets are identical at both datums',packets:96,identicalPackets:identical,changedCodes,changedProfilePackets:changedProfiles,occupancyChanges,materialTransitions:pairs,transitionExamples,examples:changes,rows};
process.stdout.write(JSON.stringify(result,null,2)+'\n');

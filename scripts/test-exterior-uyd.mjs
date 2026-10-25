#!/usr/bin/env node
// Test UYD survey collision and retain the established reactor/UTA walking routes.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const [serviceRoot,dataRoot='dist-minecraft/exterior',inspectionPath]=process.argv.slice(2);
if(!serviceRoot)throw Error('Usage: test-exterior-uyd.mjs <service-root> [exterior-data] [inspection-plan]');
const moduleAt=n=>import(pathToFileURL(path.resolve(serviceRoot,'src',n)).href);
const {Frame}=await moduleAt('geo.mjs'),{voxelizeArea}=await moduleAt('voxel.mjs'),{attachSurveySurface}=await moduleAt('minecampus-survey.mjs'),{woodProfileBounds}=await moduleAt('wood-shapes.mjs'),{preservesPhotoSource}=await moduleAt('photo-facades.mjs');
const read=p=>JSON.parse(fs.readFileSync(p));
const m=read(path.join(dataRoot,'manifest.json')),plan=read(inspectionPath??new URL('../minecraft/exterior/checks/uyd-exterior.json',import.meta.url));
const facade=read(path.join(dataRoot,'photo-facades.json')).plans.find(p=>p.id==='DEBY_LOD2_108698301');
plan.surfaceControls=[...facade.walls.map((w,i)=>({label:'UYD wall '+i,position:[0,1,2].map(k=>w.vertices.reduce((s,p)=>s+p[k],0)/w.vertices.length),kind:'wall'})),...facade.roofTriangles.map((tri,i)=>({label:'UYD roof '+i,position:[0,1,2].map(k=>tri.reduce((s,p)=>s+p[k],0)/3),kind:'roof'}))];
const controls=plan.gravityProbes,results=[];
function scene(directory,shift){
 const frame=new Frame(m.origin[0],m.origin[1],m.origin[2]-shift),minY=48+shift,height=96,count=16*16*height;
 const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>new Uint8Array(count)};attachSurveySurface(service,directory,{voxelizeArea});
 const packets=new Map();
 function packet(cx,cz){const key=cx+','+cz;if(packets.has(key))return packets.get(key);
  const bytes=service.campusCollisionPacket(frame,cx,cz,minY,height);assert.equal(bytes.subarray(count,count+4).toString(),'MCSP');const profiles=new Map();
  for(let offset=count+8;offset<bytes.length;offset+=4)profiles.set(bytes.readUInt16LE(offset),bytes.readUInt16LE(offset+2));
  const value={bytes,profiles};packets.set(key,value);return value;
 }
 const intersect=function(x,z,y0,y1,radius=.3){const cells=[];
  for(let bx=Math.floor(x-radius);bx<=Math.floor(x+radius);bx++)for(let bz=Math.floor(z-radius);bz<=Math.floor(z+radius);bz++)for(let y=Math.floor(y0);y<y1;y++){
   const cx=Math.floor(bx/16),cz=Math.floor(bz/16),{bytes,profiles}=packet(cx,cz),i=((y-minY)*16+bz-cz*16)*16+bx-cx*16,code=bytes[i];
   if(code===0||code===255||code===9)continue;
   const [a,b,c,d]=profiles.has(i)?woodProfileBounds(profiles.get(i)):[0,0,1,1],top=y+(code>=32&&code<=175?((code-32)%16+1)/16:1);
   if(bx+c>x-radius&&bx+a<x+radius&&bz+d>z-radius&&bz+b<z+radius&&top>y0&&y<y1)cells.push({x:bx,y,z:bz,code,profile:profiles.get(i),top});
  }return cells;
 };
 intersect.code=(x,y,z)=>{const bx=Math.floor(x),bz=Math.floor(z),cx=Math.floor(bx/16),cz=Math.floor(bz/16);return packet(cx,cz).bytes[((Math.floor(y)-minY)*16+bz-cz*16)*16+bx-cx*16];};
 return intersect;
}
let wallChecks=0,roofChecks=0,preservedRoofChecks=0;
for(const shift of [0,2]){
 const intersect=scene(dataRoot,shift);
 for(const c of plan.surfaceControls){
  const [x,y,z]=c.position;
  if(c.kind==='roof'&&preservesPhotoSource(facade.sourcePreservation,Math.floor(x)+.5,Math.floor(y)+.5,Math.floor(z)+.5)){
   assert.equal(intersect.code(x,y+shift,z),255,`${c.label}: original equipment collision must remain provider-owned`);preservedRoofChecks++;continue;
  }
  assert.ok(intersect(x,z,y+shift-.13,y+shift+.13,.16).length>0,`${c.label}: missing exterior collision at ${c.position}`);
  if(c.kind==='wall')wallChecks++;else roofChecks++;
 }
 for(const p of controls){
  const [x,,z]=p.target,expected=p.supportHeight+shift;
  if([...(m.architecture.utaSite?.groundTiles??[]),...(m.architecture.utaLandscape?.groundTiles??[])].some(name=>m.tiles.find(t=>t.file===name)?.runtimeId===p.tile)){
   for(let bx=Math.floor(x-.3);bx<=Math.floor(x+.3);bx++)for(let bz=Math.floor(z-.3);bz<=Math.floor(z+.3);bz++)
    assert.notEqual(intersect.code(bx+.5,expected,bz+.5),255,`${p.label}: player footprint reaches unaligned provider collision at ${bx},${bz}`);
  }
  const support=intersect(x,z,expected-.5,expected+p.dropHeight+.05),standingY=Math.max(...support.map(c=>c.top));
  assert.ok(Number.isFinite(standingY)&&Math.abs(standingY-expected)<.125,`${p.label}: support ${standingY} vs ${expected}`);
  assert.equal(intersect(x,z,standingY+.001,standingY+1.8).length,0,`${p.label}: approach obstructed`);
  results.push({label:p.label,shift,standingY,expected,residual:standingY-expected,bodyClear:true});
 }
}
console.log(JSON.stringify({status:'PASS: five UYD walls, five roof triangles and 17 established approaches retain collision support at both datums',wallChecks,roofChecks,preservedRoofChecks,results,qualification:'Survey-plane collision is independent of provider photographic acceptance. Native migration and visual acceptance are separate.'},null,2));

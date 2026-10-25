#!/usr/bin/env node
// The actual service must clear the projected approach and retain roof/glazing collision.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const [serviceRoot,dataRoot='dist-minecraft/exterior',baselineRoot]=process.argv.slice(2);
if(!serviceRoot)throw Error('Usage: test-exterior-atom-west-entrance.mjs <service-root> [exterior-data] [prior-data]');
const moduleAt=n=>import(pathToFileURL(path.resolve(serviceRoot,'src',n)).href);
const {Frame}=await moduleAt('geo.mjs'),{voxelizeArea}=await moduleAt('voxel.mjs'),{attachSurveySurface}=await moduleAt('minecampus-survey.mjs'),{woodProfileBounds}=await moduleAt('wood-shapes.mjs');
const read=p=>JSON.parse(fs.readFileSync(p));
const m=read(path.join(dataRoot,'manifest.json')),plan=read(new URL('../minecraft/exterior/checks/atom-ei-west-entrance.json',import.meta.url)),data=read(path.join(dataRoot,'atom-ei-west-entrance-surfaces.json'));
const controls=plan.gravityProbes.filter(p=>p.westEntrance),results=[],before=[];
function scene(directory,shift){
 const frame=new Frame(m.origin[0],m.origin[1],m.origin[2]-shift),minY=48+shift,height=96,count=16*16*height;
 const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>new Uint8Array(count)};attachSurveySurface(service,directory,{voxelizeArea});
 const packets=new Map();
 function packet(cx,cz){const key=cx+','+cz;if(packets.has(key))return packets.get(key);
  const bytes=service.campusCollisionPacket(frame,cx,cz,minY,height);assert.equal(bytes.subarray(count,count+4).toString(),'MCSP');const profiles=new Map();
  for(let offset=count+8;offset<bytes.length;offset+=4)profiles.set(bytes.readUInt16LE(offset),bytes.readUInt16LE(offset+2));
  const value={bytes,profiles};packets.set(key,value);return value;
 }
 return function intersect(x,z,y0,y1,radius=.3){const cells=[];
  for(let bx=Math.floor(x-radius);bx<=Math.floor(x+radius);bx++)for(let bz=Math.floor(z-radius);bz<=Math.floor(z+radius);bz++)for(let y=Math.floor(y0);y<y1;y++){
   const cx=Math.floor(bx/16),cz=Math.floor(bz/16),{bytes,profiles}=packet(cx,cz),i=((y-minY)*16+bz-cz*16)*16+bx-cx*16,code=bytes[i];
   if(code===0||code===255||code===9)continue;
   const [a,b,c,d]=profiles.has(i)?woodProfileBounds(profiles.get(i)):[0,0,1,1],top=y+(code>=32&&code<=175?((code-32)%16+1)/16:1);
   if(bx+c>x-radius&&bx+a<x+radius&&bz+d>z-radius&&bz+b<z+radius&&top>y0&&y<y1)cells.push({x:bx,y,z:bz,code,profile:profiles.get(i),top});
  }return cells;
 };
}
let glassChecks=0,roofChecks=0;
for(const shift of [0,2]){
 const intersect=scene(dataRoot,shift),old=baselineRoot?scene(baselineRoot,shift):null;
 for(const p of controls){
  const [x,,z]=p.target,expected=p.supportHeight+shift;
  assert.equal(intersect(x,z,expected+p.dropHeight+.001,expected+p.dropHeight+1.8).length,0,`${p.label}: drop starts inside roof collision`);
  const support=intersect(x,z,expected-.5,expected+p.dropHeight+.05),standingY=Math.max(...support.map(c=>c.top));
  assert.ok(Number.isFinite(standingY)&&Math.abs(standingY-expected)<.125,`${p.label}: support ${standingY} vs ${expected}`);
  assert.equal(intersect(x,z,standingY+.001,standingY+1.8).length,0,`${p.label}: approach obstructed`);
  results.push({label:p.label,shift,standingY,expected,residual:standingY-expected,bodyClear:true});
  if(old&&p.label.endsWith('outer entry'))before.push({label:p.label,shift,obstructingCells:old(x,z,standingY+.001,standingY+1.8).length});
  const roofY=data.roofPlane[0]*x+data.roofPlane[1]*z+data.roofPlane[2]+shift;
  assert.ok(intersect(x,z,roofY-.1,roofY+.1,.04).length>0,`${p.label}: opaque roof lost collision`);roofChecks++;
 }
 for(const c of data.glassControls){
  const [x,y,z]=c.position;
  assert.ok(intersect(x,z,y+shift-.03,y+shift+.03,.04).length>0,`Missing glazing collision at ${c.position}`);glassChecks++;
 }
}
if(baselineRoot)assert.ok(before.filter(p=>p.obstructingCells>0).length>=2,'No former false wall obstruction reproduced');
console.log(JSON.stringify({status:'PASS: open west approach at both datums; roof and glazing remain solid',results,priorFalseWalls:before,glassChecks,roofChecks,qualification:'Packaged-service code preflight; native migration and visual review are separate.'},null,2));

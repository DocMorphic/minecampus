#!/usr/bin/env node
// Run the actual packaged service against the native courtyard walking controls.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const [serviceRoot,dataRoot='dist-minecraft/exterior']=process.argv.slice(2);
if(!serviceRoot)throw Error('Usage: node scripts/test-exterior-mlz-collision.mjs <extracted-service-directory> [exterior-data-directory]');
const moduleAt=n=>import(pathToFileURL(path.resolve(serviceRoot,'src',n)).href);
const {Frame}=await moduleAt('geo.mjs'),{voxelizeArea}=await moduleAt('voxel.mjs'),{attachSurveySurface}=await moduleAt('minecampus-survey.mjs'),{woodProfileBounds}=await moduleAt('wood-shapes.mjs');
const m=JSON.parse(fs.readFileSync(path.join(dataRoot,'manifest.json'))),plan=JSON.parse(fs.readFileSync(new URL('../minecraft/exterior/checks/mlz-courtyard-ground.json',import.meta.url)));
const results=[],wallControls=[];
for(const tile of m.tiles.filter(t=>t.profile==='mlz-exterior')){
 const b=fs.readFileSync(path.join(dataRoot,tile.file)),n=b.readInt32LE(32),v=[];
 for(let i=0;i<n;i++)v.push([0,1,2].map(k=>b.readFloatLE(48+i*20+k*4)));
 for(let i=0;i<v.length;i+=3){
  const p=[0,1,2].map(k=>(v[i][k]+v[i+1][k]+v[i+2][k])/3);
  if(p[1]>65&&p[1]<68){wallControls.push({file:tile.file,point:p});break;}
 }
}
assert.equal(wallControls.length,3);
for(const shift of [0,2]){
 const frame=new Frame(m.origin[0],m.origin[1],m.origin[2]-shift),minY=48+shift,height=96,count=16*16*height;
 const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>new Uint8Array(count)};attachSurveySurface(service,dataRoot,{voxelizeArea});
 const packets=new Map();
 function packet(cx,cz){const key=cx+','+cz;if(packets.has(key))return packets.get(key);
  const bytes=service.campusCollisionPacket(frame,cx,cz,minY,height);assert.equal(bytes.subarray(count,count+4).toString(),'MCSP');const profiles=new Map();
  for(let offset=count+8;offset<bytes.length;offset+=4)profiles.set(bytes.readUInt16LE(offset),bytes.readUInt16LE(offset+2));
  const value={bytes,profiles};packets.set(key,value);return value;
 }
 function intersect(x,z,y0,y1,radius=.3){const cells=[];
  for(let bx=Math.floor(x-radius);bx<=Math.floor(x+radius);bx++)for(let bz=Math.floor(z-radius);bz<=Math.floor(z+radius);bz++)for(let y=Math.floor(y0);y<y1;y++){
   const cx=Math.floor(bx/16),cz=Math.floor(bz/16),{bytes,profiles}=packet(cx,cz),i=((y-minY)*16+bz-cz*16)*16+bx-cx*16,code=bytes[i];
   if(code===0||code===255||code===9)continue;
   const [a,b,c,d]=profiles.has(i)?woodProfileBounds(profiles.get(i)):[0,0,1,1],top=y+(code>=32&&code<=175?((code-32)%16+1)/16:1);
   if(bx+c>x-radius&&bx+a<x+radius&&bz+d>z-radius&&bz+b<z+radius&&top>y0&&y<y1)cells.push({x:bx,y,z:bz,code,profile:profiles.get(i),top});
  }return cells;
 }
 for(const p of plan.gravityProbes){
  const [x,,z]=p.target,expected=p.supportHeight+shift;
  const support=intersect(x,z,expected-1,expected+3.5),standingY=Math.max(...support.map(c=>c.top));
  const residual=standingY-expected,limit=p.maxSupportError??.125;
  assert.ok(Number.isFinite(standingY)&&Math.abs(residual)<limit,`${p.label}: standing ${standingY}, expected ${expected}, residual ${residual}`);
  const blockers=intersect(x,z,standingY+.001,standingY+1.8);assert.equal(blockers.length,0,`${p.label}: ${JSON.stringify(blockers)}`);
  results.push({label:p.label,shift,standingY,expected,residual,bodyClear:true});
 }
 for(const wall of wallControls){const [x,y,z]=wall.point;assert.ok(intersect(x,z,y+shift-.05,y+shift+.05,.08).length>0,wall.file+' lost visible wall collision');}
}
console.log(JSON.stringify({status:'PASS: all nine native standing/body controls at both datums, with retained collision on all three MLZ buildings',results,wallControls,qualification:'Actual packaged service and sparse shapes. Native migration, walking and visual checks remain required.'},null,2));

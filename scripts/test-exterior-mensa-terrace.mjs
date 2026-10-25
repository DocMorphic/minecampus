#!/usr/bin/env node
// Exercise the actual packaged voxelizer and survey service, using the retained
// terrace route controls. No server, credentials or saved world is opened.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const serviceRoot=process.argv[2],dataRoot=process.argv[3]??'dist-minecraft/exterior';
if(!serviceRoot)throw Error('Usage: node scripts/test-exterior-mensa-terrace.mjs <extracted-service-directory> [exterior-data-directory]');
const moduleAt=name=>import(pathToFileURL(path.resolve(serviceRoot,'src',name)).href);
const {Frame}=await moduleAt('geo.mjs'),{voxelizeArea}=await moduleAt('voxel.mjs'),{attachSurveySurface}=await moduleAt('minecampus-survey.mjs');
const manifest=JSON.parse(fs.readFileSync(path.join(dataRoot,'manifest.json')));
const plan=JSON.parse(fs.readFileSync(new URL('../minecraft/exterior/checks/mensa-terrace.json',import.meta.url)));
const controls=plan.gravityProbes.filter(p=>p.tile===1_000_050_038);
assert.equal(controls.length,3);
const results=[];
for(const shift of [0,2]){
 const frame=new Frame(manifest.origin[0],manifest.origin[1],manifest.origin[2]-shift);
 const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>new Uint8Array(24576)};
 attachSurveySurface(service,dataRoot,{voxelizeArea});
 const minY=48+shift,height=96,packets=new Map();
 function at(x,y,z){
  const cx=Math.floor(x/16),cz=Math.floor(z/16),key=cx+','+cz;
  if(!packets.has(key))packets.set(key,service.campusCollision(frame,cx,cz,minY,height));
  return packets.get(key)[((y-minY)*16+z-cz*16)*16+x-cx*16];
 }
 for(const p of controls){
  const [x,,z]=p.target,expected=p.supportHeight+shift,tops=[];
  for(let xx=Math.floor(x-.3);xx<=Math.floor(x+.3);xx++)for(let zz=Math.floor(z-.3);zz<=Math.floor(z+.3);zz++)for(let yy=Math.floor(expected)-2;yy<=Math.floor(expected)+2;yy++){
   const code=at(xx,yy,zz);
   if(code>=32&&code<=175)tops.push(yy+((code-32)%16+1)/16);
   else if(code>=1&&code<=9)tops.push(yy+1);
  }
  const standingY=Math.max(...tops),residual=standingY-expected;
  assert.ok(Number.isFinite(standingY)&&Math.abs(residual)<.063,`${p.label}: standing ${standingY}, encoded mesh support ${expected}, residual ${residual}`);
  results.push({label:p.label,shift,standingY,expected,residual});
 }
}
console.log(JSON.stringify({status:'PASS: three surveyed terrace standing controls at both save datums',qualification:'Actual packaged voxelization; native migration, body clearance and visual review are separate checks.',results},null,2));

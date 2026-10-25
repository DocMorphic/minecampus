import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {attachSurveySurface} from './survey-surface.mjs';

const origin={lat:48.265,lon:11.671,h0:519.7618173672081};
test('column-centre collision is restricted to listed Physics ground assets',t=>{
 let meshes;
 const names=['physics.ect','core.ect','building.ect','tree.ect','woodland.ect','laboratory.ect','site.ect','physics-ii.ect','wsi.ect','znn.ect','riverbank.ect','znn-west.ect','cala.ect','lmu.ect','lmu-courtyard.ect','lmu-east.ect'];
 const kinds=['ground','ground','reconstruction','vegetation','ground','ground','ground','ground','ground','ground','ground','ground','ground','ground','ground','ground'];
 const tiles=names.map((file,i)=>({file,kind:kinds[i],runtimeId:100+i,bounds:[[0,0,0],[16,4,16]]}));
 const {service,dir}=fixture(t,null,{tiles,architecture:{physicsISite:{groundTiles:['physics.ect','building.ect']},physicsWoodland:{groundTiles:['woodland.ect']},physicsNewLaboratory:{groundTiles:['laboratory.ect']},physicsLaboratorySite:{groundTiles:['site.ect']},physicsII:{groundTiles:['physics-ii.ect']},physicsWSI:{groundTiles:['wsi.ect']},physicsZNN:{groundTiles:['znn.ect']},riverbank:{groundTiles:['riverbank.ect']},physicsZNNWest:{groundTiles:['znn-west.ect']},physicsCALA:{groundTiles:['cala.ect']},physicsLMU:{groundTiles:['lmu.ect']},physicsLMUCourtyard:{groundTiles:['lmu-courtyard.ect']},physicsLMUEast:{groundTiles:['lmu-east.ect']}}},
   {voxelizeArea:(_frame,assets)=>{meshes=assets;return {vox:new Uint8Array(16*16*8)};}});
 for(const name of names)fs.writeFileSync(path.join(dir,name),tile([[0,1,0],[16,1,0],[0,1,16]]));
 service.campusCollision({...origin,mcToEcef:(x,y,z)=>[x,y,z]},0,0,0,8);
 assert.deepEqual(meshes.map(m=>m.primitives[0].campusHeightfield),[true,false,false,true,true,true,true,true,true,true,true,true,true,true,true]);
});
function tile(positions){
 const b=Buffer.alloc(32+16+positions.length*20+4);b.write('ECT1');b.writeInt32LE(1,4);b.writeInt32LE(positions.length,32);b.writeInt32LE(1,36);b.writeInt32LE(1,40);b.fill(255,44,48);
 positions.forEach((p,i)=>[...p,.25,.75].forEach((n,j)=>b.writeFloatLE(n,48+i*20+j*4)));b.set([12,34,56,255],b.length-4);return b;
}
function fixture(t,bytes,extra={},deps,sourceTiles=[],loader){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-survey-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,0,z]);
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),attribution:'BVV CC BY 4.0',tiles:[],terrainGuide:{width:3,height:3,points},walls:[{points:[[10,0,3],[10,10,3],[10,10,17],[10,0,17]]}],...extra}));
 const service={renderSelect:async()=>({tiles:sourceTiles,attribution:[]}),renderTile:loader??(async()=>bytes),chunk:async(_frame,_cx,_cz,_minY,span)=>new Uint8Array(16*16*span)};const check=attachSurveySurface(service,dir,deps);return {service,check,dir};
}
test('survey removes source ground while retaining texture bytes and triangle header integrity',async t=>{
 const {service,check}=fixture(t,tile([[4,.4,4],[8,.8,4],[4,.5,8]]));const b=await service.renderTile(origin,1_100_000_007);
 assert.equal(b.readInt32LE(32),0);assert.equal(b.length,52);assert.deepEqual([...b.subarray(-4)],[12,34,56,255]);assert.equal(check.stats().removedSourceTriangles,1);
});
test('photo facade positions stay intact outside an explicit replacement footprint',async t=>{
 const {service}=fixture(t,tile([[9.4,5,5],[9.4,8,5],[9.4,5,8]]));const b=await service.renderTile(origin,1_100_000_007);
 assert.ok(Math.abs(b.readFloatLE(48)-9.4)<1e-5);assert.equal(b.readFloatLE(52),5);assert.equal(b.readFloatLE(60),.25);assert.equal(b.readFloatLE(64),.75);assert.deepEqual([...b.subarray(-4)],[12,34,56,255]);
});
test('unrelated regions, roof equipment and distant geometry retain original positions',async t=>{
 const bytes=tile([[7,12,5],[7,15,5],[7,12,8]]);const {service}=fixture(t,bytes);
 assert.deepEqual(await service.renderTile(origin,1_100_000_007),bytes);
 assert.deepEqual(await service.renderTile({...origin,lat:49},7),bytes);
 assert.deepEqual(await service.renderSelect({...origin,lat:49},[0,0,0]),{tiles:[],attribution:[]});
});
test('provider misses remain misses',async t=>{const {service}=fixture(t,null);assert.equal(await service.renderTile(origin,1_100_000_007),null);});

test('survey sampling reaches all mesh edges without extrapolating beyond coverage',async t=>{
 for(const points of [
  [[19.5,.4,4],[20,.4,4],[19.5,.4,5]],
  [[0,.4,4],[.5,.4,4],[0,.4,5]],
  [[4,.4,0],[5,.4,0],[4,.4,.5]],
  [[4,.4,19.5],[5,.4,19.5],[4,.4,20]]
 ]){
  const {service}=fixture(t,tile(points));
  assert.equal((await service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 }
 const outside=tile([[20.01,.4,4],[20.5,.4,4],[20.01,.4,5]]);
 const {service}=fixture(t,outside);
 assert.deepEqual(await service.renderTile(origin,1_100_000_007),outside);
 const high=fixture(t,tile([[19.5,18,4],[20,18,4],[19.5,18,5]]),{
  surfaceGuide:{width:3,height:3,heights:Array(9).fill(7),tolerance:3}
 });
 assert.equal((await high.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const mask=Buffer.alloc(400);for(let row=0;row<20;row++)mask[row*20+19]=1;
 const wall=tile([[19.5,3,4],[19.5,5,4],[19.5,3,5]]);
 const protectedEdge=fixture(t,wall,{protectionGrid:{width:20,height:20,metresPerPixel:1,data:mask.toString('base64')}});
 assert.deepEqual(await protectedEdge.service.renderTile(origin,1_100_000_007),wall);
});

test('outdoor cleanup removes low floating debris while keeping surveyed building faces',async t=>{
 const mask=Buffer.alloc(20*20);for(let row=0;row<20;row++)for(let col=9;col<13;col++)mask[row*20+col]=1;
 const extra={protectionGrid:{width:20,height:20,metresPerPixel:1,data:mask.toString('base64')}};
 const outside=fixture(t,tile([[4,3,4],[5,4,4],[4,3,5]]),extra);
 assert.equal((await outside.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const facade=fixture(t,tile([[10,3,4],[10,4,4],[10,3,5]]),extra);
 assert.equal((await facade.service.renderTile(origin,1_100_000_007)).readInt32LE(32),3);
});
test('survey cleanup preserves low geometry beyond its coverage and preserves UV/texture data',async t=>{
 const bytes=tile([[25,3,4],[26,4,4],[25,3,5]]);
 const {service}=fixture(t,bytes,{protectionGrid:{width:20,height:20,metresPerPixel:1,data:Buffer.alloc(400).toString('base64')}});
 assert.deepEqual(await service.renderTile(origin,1_100_000_007),bytes);
});
test('vegetation masks remove the old canopy only within its surveyed footprint and height interval',async t=>{
 const extra={replacements:[{ring:[[3,3],[8,3],[8,8],[3,8]],y0:2,y1:12,kind:'vegetation'}]};
 const {service}=fixture(t,tile([[4,8,4],[5,9,4],[4,8,5]]),extra);
 assert.equal((await service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const high=fixture(t,tile([[4,18,4],[5,19,4],[4,18,5]]),extra);
 assert.equal((await high.service.renderTile(origin,1_100_000_007)).readInt32LE(32),3);
});

test('replacement removes a source triangle straddling the reconstruction boundary',async t=>{
 const extra={replacements:[{ring:[[3,3],[8,3],[8,8],[3,8]],y0:2,y1:12}]};
 const {service}=fixture(t,tile([[2,8,4],[4,9,4],[2,8,5]]),extra);
 assert.equal((await service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
});

test('DOM survey envelope rejects detached overhead source fragments without removing supported roof geometry',async t=>{
 const extra={surfaceGuide:{width:3,height:3,heights:Array(9).fill(7),tolerance:3}};
 const floating=fixture(t,tile([[4,18,4],[5,19,4],[4,18,5]]),extra);
 assert.equal((await floating.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const supported=fixture(t,tile([[4,7,4],[5,8,4],[4,7,5]]),extra);
 assert.equal((await supported.service.renderTile(origin,1_100_000_007)).readInt32LE(32),3);
});

test('survey clipping uses the save datum consistently when the world origin height differs',async t=>{
 const raw=tile([[4,9,4],[5,9,4],[4,9,5]]);raw.writeDoubleLE(2,16);
 const {service}=fixture(t,raw,{surfaceGuide:{width:3,height:3,heights:Array(9).fill(7),tolerance:3}});
 const result=await service.renderTile({...origin,h0:origin.h0-2},1_100_000_007);
 assert.equal(result.readInt32LE(32),3);assert.equal(result.readDoubleLE(16),2);
 const ground=tile([[4,.4,4],[5,.4,4],[4,.4,5]]);ground.writeDoubleLE(2,16);
 const other=fixture(t,ground);
 assert.equal((await other.service.renderTile({...origin,h0:origin.h0-2},1_100_000_007)).readInt32LE(32),0);
});

test('source fringe cleanup preserves neighbouring surveyed building and roof footprints',async t=>{
 const mask=Buffer.alloc(400);for(let row=0;row<20;row++)for(let col=9;col<13;col++)mask[row*20+col]=1;
 const extra={protectionGrid:{width:20,height:20,metresPerPixel:1,data:mask.toString('base64')},replacements:[{kind:'architecture-fringe',ring:[[2,2],[18,2],[18,18],[2,18]],y0:0,y1:30}]};
 const facade=fixture(t,tile([[10,8,4],[10,9,4],[10,8,5]]),extra);
 assert.equal((await facade.service.renderTile(origin,1_100_000_007)).readInt32LE(32),3);
 const orphan=fixture(t,tile([[4,8,4],[5,9,4],[4,8,5]]),extra);
 assert.equal((await orphan.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
});

test('the reconstructed outdoor layer retires high scan remnants while retaining neighbouring architecture',async t=>{
 const mask=Buffer.alloc(400);for(let row=0;row<20;row++)for(let col=9;col<13;col++)mask[row*20+col]=1;
 const extra={protectionGrid:{width:20,height:20,metresPerPixel:1,data:mask.toString('base64')}};
 const branch=fixture(t,tile([[4,18,4],[5,19,4],[4,18,5]]),extra);
 assert.equal((await branch.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const building=fixture(t,tile([[10,18,4],[10,19,4],[10,18,5]]),extra);
 assert.equal((await building.service.renderTile(origin,1_100_000_007)).readInt32LE(32),3);
});

test('airborne photographic startup waits for readiness, preserves old tiles and uses save datum without mutating source',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-photo-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const wall={anchor:[3,4,5],direction:[1,0,0],normal:[0,0,1],bounds:[[0,4],[4,8]],rings:[[[0,4],[4,4],[4,8],[0,8]]],vertices:[[3,4,5],[7,4,5],[7,8,5],[3,8,5]],indices:[0,1,2,0,2,3]};
 const occluded={...wall,anchor:[3,4,15],bounds:[[0,4],[4,24]],rings:[[[0,4],[4,4],[4,24],[0,24]]],vertices:[[3,4,15],[7,4,15],[7,24,15],[3,24,15]]};
 const plan={id:'test-building',runtimeId:1_000_050_000,roofFile:'roof.ect',bounds:[[3,4,5],[7,24,17]],walls:[wall,occluded],retirement:[{ring:[[2,4],[8,4],[8,18],[2,18]],holes:[]}]};
 fs.writeFileSync(path.join(dir,'photo-facades.json'),JSON.stringify({plans:[plan]}));fs.writeFileSync(path.join(dir,'roof.ect'),tile([[3,8,5],[7,8,5],[3,8,7]]));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,0,z]);
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),attribution:'survey',tiles:[],terrainGuide:{width:3,height:3,points},photoFacades:{file:'photo-facades.json'}}));
 const frame={...origin,h0:origin.h0-2},source=tile([[3.2,7,5.4],[6,7,5.4],[3.2,9,5.4]]);
 const positions=new Float64Array([3,6,5.2,7,6,5.2,7,10,5.2,3,10,5.2]),snapshot=positions.slice();
 const prim={positions,uvs:new Float32Array([0,1,1,1,1,0,0,0]),indices:new Uint32Array([0,1,2,0,2,3])};
 const service={client:{},meshesFor:async()=>[{copyright:'test provider',primitives:[prim]}],renderSelect:async()=>({tiles:[{id:7,parent:0,chain:[],fine:true}],pending:0,attribution:[]}),renderTile:async()=>source};
 attachSurveySurface(service,dir,{collectRegionTiles:async()=>[{}],mcPositions:(frame,p)=>p.positions,sampleColor:(p,u,v,out)=>out.splice(0,3,60,90,120)});
 assert.deepEqual(await service.renderTile(frame,1_200_000_007),source); // Cache before facade preparation.
 const initial=await service.renderSelect(frame,[5,160,6]);assert.equal(initial.pending,1);assert.equal(initial.tiles[0].id,1_100_000_007);
 let result;
 for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,5));result=await service.renderSelect(frame,[5,160,6]);if(result.pending===0)break;}
 assert.equal(result.pending,0);assert.ok(result.tiles.some(t=>t.id===1_000_050_000));assert.ok(result.tiles.some(t=>t.id===1_200_000_007));assert.ok(result.attribution.includes('test provider'));
 const descending=await service.renderSelect(frame,[5,6,6]);assert.deepEqual(descending.tiles,result.tiles);assert.equal(descending.pending,0);
 assert.deepEqual(positions,snapshot);
 // Only one sixth of the building's wall area is observed. Its good face must
 // still appear; the larger occluded face must not be synthesized.
 const baked=await service.renderTile(frame,1_000_050_000);assert.equal(baked.readFloatLE(52),6);assert.equal(baked.readInt32LE(4),2);
 assert.equal((await service.renderTile(frame,1_200_000_007)).readInt32LE(32),0);
 assert.deepEqual(await service.renderTile(frame,1_100_000_007),source);
 // A structural facade replaces the only photographed wall. It must not get
 // a second flat photographic sheet across its newly recessed glazing, while
 // retaining source retirement and the public roof even with no usable faces.
 wall.reconstructed=true;
 fs.writeFileSync(path.join(dir,'photo-facades.json'),JSON.stringify({plans:[plan]}));
 const manualService={client:{},meshesFor:async()=>[{copyright:'test provider',primitives:[prim]}],renderSelect:async()=>({tiles:[{id:7,parent:0,chain:[],fine:true}],pending:0,attribution:[]}),renderTile:async()=>source};
 attachSurveySurface(manualService,dir,{collectRegionTiles:async()=>[{}],mcPositions:(frame,p)=>p.positions,sampleColor:(p,u,v,out)=>out.splice(0,3,60,90,120)});
 await manualService.renderSelect(frame,[5,6,6]);
 for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,5));result=await manualService.renderSelect(frame,[5,6,6]);if(result.pending===0)break;}
 assert.equal(result.pending,0);assert.ok(result.tiles.some(t=>t.id===1_000_050_000));
 assert.equal((await manualService.renderTile(frame,1_000_050_000)).readInt32LE(4),1);
 assert.equal((await manualService.renderTile(frame,1_200_000_007)).readInt32LE(32),0);
});

test('photographic canopy overhang is retired above a surveyed roof without erasing the building underneath',async t=>{
 const protection=Buffer.alloc(400,1);
 const vegetationOverhang={width:3,height:3,mask:Buffer.alloc(9,1).toString('base64'),roofCeilings:Array(9).fill(8)};
 const extra={protectionGrid:{width:20,height:20,metresPerPixel:1,data:protection.toString('base64')},vegetationOverhang};
 const canopy=fixture(t,tile([[10,12,5],[11,13,5],[10,12,6]]),extra);
 assert.equal((await canopy.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const lowBranch=fixture(t,tile([[10,8.9,5],[11,9.1,5],[10,8.9,6]]),extra);
 assert.equal((await lowBranch.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const building=fixture(t,tile([[10,7,5],[11,8,5],[10,7,6]]),extra);
 assert.equal((await building.service.renderTile(origin,1_100_000_007)).readInt32LE(32),3);
 const noEvidence=fixture(t,tile([[10,12,5],[11,13,5],[10,12,6]]),{...extra,vegetationOverhang:{...vegetationOverhang,mask:Buffer.alloc(9).toString('base64')}});
 assert.equal((await noEvidence.service.renderTile(origin,1_100_000_007)).readInt32LE(32),3);
});

test('fresh survey chunks hide source filler even in protected margins, without changing other materials or regions',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-filler-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,10,z]);
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),attribution:'survey',tiles:[],terrainGuide:{width:3,height:3,points}}));
 const source=new Uint8Array(16*16*4);for(let y=0;y<4;y++)source.fill([20,21,22,23][y],y*256,(y+1)*256);
 const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>source};
 attachSurveySurface(service,dir,{voxelizeArea:()=>{throw Error('no collision assets needed for filler normalization');}});
 const result=await service.chunk(origin,0,0,-10,4);
 for(let y=0;y<4;y++)assert.equal(result[y*256+8*16+8],[3,4,22,23][y]);
 assert.equal(result[0],3); // The surveyed edge is covered too; no artificial inner margin.
 assert.deepEqual(await service.chunk({...origin,lat:49},0,0,-10,4),source);
 assert.deepEqual(await service.chunk(origin,5,5,-10,4),source);
 assert.equal(source[8*16+8],20); // Do not mutate cached source voxel bytes.
});

test('roof-only replacement removes contained fragments without erasing a wall crossing its band',async t=>{
 const extra={replacements:[{kind:'architecture-band',ring:[[3,3],[8,3],[8,8],[3,8]],holes:[],y0:6,y1:8}]};
 const fragment=fixture(t,tile([[4,6.5,4],[5,7.5,4],[4,7,5]]),extra);
 assert.equal((await fragment.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 for(const points of [[[4,3,4],[5,7.5,4],[4,7,5]],[[2,6.5,4],[5,7.5,4],[4,7,5]]]){
  const original=tile(points),wall=fixture(t,original,extra);
  assert.deepEqual(await wall.service.renderTile(origin,1_100_000_007),original);
 }
 const shifted=tile([[4,6.5,4],[5,7.5,4],[4,7,5]]);shifted.writeDoubleLE(2,16);
 const other=fixture(t,shifted,extra);
 assert.equal((await other.service.renderTile({...origin,h0:origin.h0-2},1_100_000_007)).readInt32LE(32),0);
});

test('all reconstructed surfaces remain selected on airborne startup, ascent, descent and outside-camera views',async t=>{
 const specs=[{runtimeId:1_000_000_000,kind:'ground',file:'ground.ect'},{runtimeId:1_000_030_010,kind:'reconstruction',file:'current-building.ect',alwaysVisible:true},{runtimeId:1_000_000_100,kind:'reconstruction',file:'galileo.ect'}];
 const source={id:7,parent:3,chain:[1,3],fine:true};
 for(const shifted of [false,true]){
  const frame={...origin,h0:origin.h0-(shifted?17:0)};
  const {service}=fixture(t,null,{tiles:specs},undefined,[source]);
  // Begin above the old thresholds; repeat middle heights from both sides.
  for(const [x,y,z]of [[6,150,6],[6,5,6],[6,40,6],[6,60,6],[6,150,6],[6,60,6],[6,40,6],[6,5,6],[100,150,100],[6,150,6]]){
   const result=await service.renderSelect(frame,[x,y+(shifted?17:0),z]);
   for(const spec of specs)assert.ok(result.tiles.some(v=>v.id===spec.runtimeId),`missing ${spec.runtimeId} at ${x},${y},${z}`);
   assert.deepEqual(result.tiles.find(v=>v.id===1_100_000_007),{...source,id:1_100_000_007,parent:1_100_000_003,chain:[1_100_000_001,1_100_000_003]});
  }
  assert.deepEqual((await service.renderSelect({...frame,lat:49},[6,150,6])).tiles,[source]);
 }
});

test('airborne source cleanup stays bounded and keeps unrelated geometry and texture bytes',async t=>{
 const extra={protectionGrid:{width:20,height:20,metresPerPixel:1,data:Buffer.alloc(400).toString('base64')}};
 const inside=fixture(t,tile([[4,.4,4],[5,.6,4],[4,.4,5]]),extra,undefined,[{id:7,parent:0,chain:[]}]);
 const result=await inside.service.renderSelect(origin,[100,150,100]);assert.equal(result.tiles[0].id,1_100_000_007);
 const removed=await inside.service.renderTile(origin,result.tiles[0].id);assert.equal(removed.readInt32LE(32),0);assert.deepEqual([...removed.subarray(-4)],[12,34,56,255]);
 const bytes=tile([[24,.4,24],[25,.6,24],[24,.4,25]]),outside=fixture(t,bytes,extra,undefined,[{id:7,parent:0,chain:[]}]);
 const selected=await outside.service.renderSelect(origin,[6,150,6]);assert.deepEqual(await outside.service.renderTile(origin,selected.tiles[0].id),bytes);
 assert.deepEqual(await outside.service.renderTile({...origin,lat:49},7),bytes);
});

test('manual-only facade cleanup applies even when there are no photographic render tiles',async t=>{
 const {service,dir}=fixture(t,tile([[5,4,5],[6,4,5],[5,5,5]]),{photoFacades:{file:'photo-facades.json'}},{collectRegionTiles(){throw Error('manual envelope needs no old photo');}},[{id:7,parent:0,chain:[]}]);
 fs.writeFileSync(path.join(dir,'photo-facades.json'),JSON.stringify({plans:[{id:'manual',manualRoof:true,bounds:[[3,0,3],[8,8,8]],walls:[{reconstructed:true,anchor:[3,0,3],direction:[1,0,0],normal:[0,0,1],bounds:[[0,0],[5,8]]}]}]}));
 let result;
 for(let i=0;i<100;i++){result=await service.renderSelect(origin,[6,5,6]);if(!result.pending)break;await new Promise(r=>setTimeout(r,1));}
 assert.equal(result.pending??0,0);
 assert.equal(result.tiles[0].id,1_200_000_007);
 assert.equal((await service.renderTile(origin,1_200_000_007)).readInt32LE(32),0);
});

test('furniture collision includes selected solids while keeping decorative tubes in the render stream',async t=>{
 const solids=tile([[2,1,2],[3,1,2],[2,1,3]]),tubes=tile([[4,2,4],[5,2,4],[4,2,5]]);
 const multipart=Buffer.concat([solids,tubes.subarray(32)]);multipart.writeInt32LE(2,4);
 let meshes;
 const spec={file:'furniture.ect',kind:'reconstruction',runtimeId:1_000_030_011,bounds:[[1,0,1],[6,3,6]],collisionParts:[0]};
 const {service,dir}=fixture(t,null,{tiles:[spec]},{voxelizeArea:(frame,assets)=>{meshes=assets;return {vox:new Uint8Array(16*16*8)};}});
 fs.writeFileSync(path.join(dir,spec.file),multipart);
 const frame={...origin,mcToEcef:(...p)=>p};
 service.campusCollision(frame,0,0,0,8);
 assert.equal(meshes.length,1);assert.equal(meshes[0].primitives.length,1);
 assert.deepEqual([...meshes[0].primitives[0].positions],[2,1,2,3,1,2,2,1,3]);
 const rendered=await service.renderTile(frame,spec.runtimeId);
 assert.equal(rendered.readInt32LE(4),2);assert.deepEqual(rendered,multipart);
});

test('bounded lower floors and stair overrides guide collision without affecting neighbouring terrain',t=>{
 const spec={file:'court.ect',kind:'reconstruction',runtimeId:1_000_030_020,bounds:[[0,-20,0],[16,2,16]]};
 const ring=[[4,4],[12,4],[12,12],[4,12]],step=[[4,4],[6,4],[6,12],[4,12]];
 const {service,dir}=fixture(t,null,{tiles:[spec],terrainOverrides:[{ring:step,height:-2},{ring,height:-6}]},{voxelizeArea:()=>({vox:new Uint8Array(16*16*20).fill(7)})});
 fs.writeFileSync(path.join(dir,spec.file),tile([[4,-6,4],[12,-6,4],[4,-6,12]]));
 const frame={...origin,mcToEcef:(...p)=>p};
 const result=service.campusCollision(frame,0,0,-12,20),at=(x,y,z)=>result[((y+12)*16+z)*16+x];
 assert.equal(at(8,-9,8),7);assert.equal(at(8,-11,8),255); // lower floor
 assert.equal(at(5,-7,8),255);assert.equal(at(5,-6,8),7); // earlier stair wins
 assert.equal(at(3,-7,8),255);assert.equal(at(3,-4,8),7); // outside stays on DEM
 const shifted=service.campusCollision({...frame,h0:frame.h0-2},0,0,-12,20);
 assert.equal(shifted[((-9+12)*16+8)*16+8],255); // origin-height shift retained
 assert.ok(service.campusCollision({...frame,lat:49},0,0,-12,20).every(x=>x===255));
});

test('ramp planes vary collision height along the run and preserve neighbouring terrain',t=>{
 const spec={file:'ramp.ect',kind:'reconstruction',runtimeId:1_000_030_022,bounds:[[0,-20,0],[16,2,16]]};
 const ring=[[4,4],[12,4],[12,12],[4,12]];
 const {service,dir}=fixture(t,null,{tiles:[spec],terrainOverrides:[{ring,plane:[0,-.5,0]}]},{voxelizeArea:()=>({vox:new Uint8Array(16*16*20).fill(7)})});
 fs.writeFileSync(path.join(dir,spec.file),tile([[4,-2,4],[12,-2,4],[4,-6,12]]));
 const frame={...origin,mcToEcef:(...p)=>p};
 const result=service.campusCollision(frame,0,0,-12,20),at=(x,y,z)=>result[((y+12)*16+z)*16+x];
 assert.equal(at(8,-8,4),255);assert.equal(at(8,-6,4),7);
 assert.equal(at(8,-8,11),7);assert.equal(at(8,-10,11),255);
 assert.equal(at(3,-8,11),255);assert.equal(at(3,-4,11),7);
 const shifted=service.campusCollision({...frame,h0:frame.h0-2},0,0,-12,20);
 assert.equal(shifted[((-8+12)*16+11)*16+8],255);
});

function supplementalFixture() {
 const points=[];for(let z=0;z<=16;z+=8)for(let x=32;x<=48;x+=8)points.push([x,2+(x-32)/8,z]);
 return {name:'east',terrainGuide:{width:3,height:3,points},rings:[{ring:[[32,0],[48,0],[48,16],[32,16]],holes:[[[40,4],[44,4],[44,8],[40,8]]]}],protectedFootprints:[{ring:[[36,2],[38,2],[38,14],[36,14]],holes:[]}],outdoorReconstructed:false};
}
test('supplemental ground clips low source mesh only in its bounded coverage; holes and canopy remain',async t=>{
 const extra={supplementalSurfaces:[supplementalFixture()]};
 const low=fixture(t,tile([[34,2.5,4],[35,2.6,4],[34,2.5,5]]),extra);
 assert.equal((await low.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 for(const positions of [[[41,2.5,5],[42,2.5,5],[41,2.5,6]],[[49,2.5,5],[50,2.5,5],[49,2.5,6]],[[34,12,4],[35,12,4],[34,12,5]]]){
  const bytes=tile(positions),f=fixture(t,bytes,extra);
  assert.deepEqual(await f.service.renderTile(origin,1_100_000_007),bytes);
 }
 const bytes=tile([[34,4.5,4],[35,4.6,4],[34,4.5,5]]),shift=fixture(t,bytes,extra);
 assert.equal((await shift.service.renderTile({...origin,h0:origin.h0-2},1_100_000_007)).readInt32LE(32),0);
});
test('outdoor boundary clipping preserves outside ground, winding, UVs and neighbour holes',async t=>{
 const patch=supplementalFixture();patch.outdoorReconstructed=true;
 const extra={supplementalSurfaces:[patch],protectionGrid:{width:20,height:20,metresPerPixel:1,data:Buffer.alloc(400).toString('base64')}};
 for(const [positions,area,insideOutside]of [
  [[[47,6,10],[51,6,10],[51,6,14]],7.5,p=>p[0]>=48-1e-6],
  [[[46,6,10],[49,6,10],[46,6,13]],.5,p=>p[0]>=48-1e-6],
  [[[44,6,10],[49,6,10],[49,6,14]],3.6,p=>p[0]>=48-1e-6],
  [[[39,6,5],[41,6,5],[39,6,7]],.5,p=>p[0]>=40-1e-6&&p[0]<=44+1e-6]
 ]){
  const bytes=tile(positions);
  positions.forEach((p,i)=>{bytes.writeFloatLE(p[0]/64,48+i*20+12);bytes.writeFloatLE(p[2]/32,48+i*20+16);});
  const {service,check}=fixture(t,bytes,extra),result=await service.renderTile(origin,1_100_000_007),vertices=[];
  for(let i=0;i<result.readInt32LE(32);i++){
   const at=48+i*20,p=[0,1,2].map(k=>result.readFloatLE(at+k*4));vertices.push(p);assert.ok(insideOutside(p));assert.equal(p[1],6);
   assert.ok(Math.abs(result.readFloatLE(at+12)-p[0]/64)<1e-6);assert.ok(Math.abs(result.readFloatLE(at+16)-p[2]/32)<1e-6);
  }
  let actual=0;
  for(let i=0;i<vertices.length;i+=3){const [a,b,c]=vertices.slice(i,i+3),signed=((b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0]))/2;assert.ok(signed>0);actual+=signed;}
  assert.ok(Math.abs(actual-area)<1e-5);assert.deepEqual([...result.subarray(-4)],[12,34,56,255]);assert.equal(check.stats().clippedSourceTriangles,1);
 }
 // Complete outside geometry, including its original bytes, is preserved.
 const bytes=tile([[49,6,10],[50,6,10],[49,6,13]]),outside=fixture(t,bytes,extra);
 assert.deepEqual(await outside.service.renderTile(origin,1_100_000_007),bytes);
});
test('outdoor clipping handles centroids in protected neighbours and holes in shifted saves',async t=>{
 const patch=supplementalFixture();patch.outdoorReconstructed=true;
 const extra={supplementalSurfaces:[patch],protectionGrid:{width:20,height:20,metresPerPixel:1,data:Buffer.alloc(400).toString('base64')}};
 for(const shift of [0,2])for(const [positions,expectedArea,allowed] of [
  [[[35,6,8],[39,6,8],[35,6,12]],4,p=>p[0]>=36-1e-6&&p[0]<=38+1e-6],
  [[[39,6,5],[43,6,5],[43,6,7]],3.75,p=>p[0]>=40-1e-6&&p[0]<=44+1e-6]
 ]){
  const bytes=tile(positions);bytes.writeDoubleLE(shift,16);
  positions.forEach((p,i)=>{bytes.writeFloatLE(p[0]/64,48+i*20+12);bytes.writeFloatLE(p[2]/32,48+i*20+16);});
  const {service}=fixture(t,bytes,extra),result=await service.renderTile({...origin,h0:origin.h0-shift},1_100_000_007),vertices=[];
  for(let i=0;i<result.readInt32LE(32);i++){
   const at=48+i*20,p=[0,1,2].map(k=>result.readFloatLE(at+k*4));vertices.push(p);
   assert.ok(allowed(p));assert.equal(p[1],6);assert.equal(result.readDoubleLE(16),shift);
   assert.ok(Math.abs(result.readFloatLE(at+12)-p[0]/64)<1e-6);assert.ok(Math.abs(result.readFloatLE(at+16)-p[2]/32)<1e-6);
  }
  let area=0;for(let i=0;i<vertices.length;i+=3){const [a,b,c]=vertices.slice(i,i+3);area+=((b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0]))/2;}
  assert.ok(Math.abs(area-expectedArea)<1e-5);assert.deepEqual([...result.subarray(-4)],[12,34,56,255]);
 }
 // A protected facade wholly within the patch must survive byte-for-byte.
 const bytes=tile([[36.25,6,8],[37.75,6,8],[36.25,9,8]]),f=fixture(t,bytes,extra);
 assert.deepEqual(await f.service.renderTile(origin,1_100_000_007),bytes);
});

test('supplemental collision follows measured slope and datum while protecting excluded holes and untreated walls',t=>{
 const spec={file:'east.ect',kind:'ground',runtimeId:1_000_060_000,bounds:[[32,0,0],[48,14,16]]};
 const extra={tiles:[spec],supplementalSurfaces:[supplementalFixture()]};
 const {service,dir}=fixture(t,null,extra,{voxelizeArea:()=>({vox:new Uint8Array(16*16*20).fill(7)})});
 fs.writeFileSync(path.join(dir,spec.file),tile([[32,2,0],[48,4,0],[32,2,16]]));
 const frame={...origin,mcToEcef:(...p)=>p};
 const result=service.campusCollision(frame,2,0,-8,20),at=(x,y,z)=>result[((y+8)*16+z)*16+x-32];
 assert.equal(at(34,-3,3),255);assert.equal(at(34,-1,3),7);
 assert.equal(at(46,-1,3),255);assert.equal(at(46,1,3),7);
 assert.equal(at(41,6,5),255); // excluded neighbour/courtyard hole
 assert.equal(at(37,8,5),255); // protected building without reconstruction
 assert.equal(at(34,8,5),7);
 const shifted=service.campusCollision({...frame,h0:frame.h0-2},2,0,-8,20);
 assert.equal(shifted[((-1+8)*16+3)*16+2],255);
 assert.ok(service.campusCollision({...frame,lat:49},2,0,-8,20).every(v=>v===255));
});
test('explicit reconstructed facade enables collision in its supplemental protected footprint',t=>{
 const spec={file:'wall.ect',kind:'reconstruction',runtimeId:1_000_030_028,bounds:[[36,0,2],[38,14,14]]};
 const extra={tiles:[spec],supplementalSurfaces:[supplementalFixture()],photoFacades:{collisionRetirement:[{ring:[[36,2],[38,2],[38,14],[36,14]],holes:[],y0:2,y1:14}]}};
 const {service,dir}=fixture(t,null,extra,{voxelizeArea:()=>({vox:new Uint8Array(16*16*20).fill(7)})});
 fs.writeFileSync(path.join(dir,spec.file),tile([[37,2,2],[37,14,2],[37,2,14]]));
 const data=service.campusCollision({...origin,mcToEcef:(...p)=>p},2,0,-8,20);
 assert.equal(data[((8+8)*16+5)*16+5],7);
});

test('supplemental canopy cleanup removes only reconstructed outdoor canopy and preserves low protected walls',async t=>{
 const patch=supplementalFixture();patch.outdoorReconstructed=true;
 patch.surfaceGuide={heights:Array(9).fill(8)};
 patch.vegetationOverhang={mask:Buffer.alloc(9,1).toString('base64'),roofCeilings:Array(9).fill(6)};
 const extra={supplementalSurfaces:[patch],protectionGrid:{width:20,height:20,metresPerPixel:1,data:Buffer.alloc(400).toString('base64')}};
 const tree=fixture(t,tile([[34,9,3],[35,10,3],[34,9,4]]),extra);
 assert.equal((await tree.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const overhang=fixture(t,tile([[37,10,3],[37,11,3],[37,10,4]]),extra);
 assert.equal((await overhang.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 for(const positions of [[[37,4.5,3],[37,5.5,3],[37,4.5,4]],[[41,10,5],[42,10,5],[41,10,6]],[[49,10,3],[50,10,3],[49,10,4]]]){
  const bytes=tile(positions),f=fixture(t,bytes,extra);assert.deepEqual(await f.service.renderTile(origin,1_100_000_007),bytes);
 }
});

test('corrected tiles share concurrent work, retry failures and invalidate a changed datum',async t=>{
 const bytes=tile([[4,.4,4],[8,.8,4],[4,.5,8]]);let calls=0,release;
 const {service}=fixture(t,bytes,{},undefined,[],async()=>{calls++;await new Promise(r=>release=r);return bytes;});
 const frame={...origin},a=service.renderTile(frame,1_100_000_007),b=service.renderTile(frame,1_100_000_007);
 assert.equal(calls,1);release();const [x,y]=await Promise.all([a,b]);assert.strictEqual(x,y);
 assert.strictEqual(await service.renderTile(frame,1_100_000_007),x);assert.equal(calls,1);
 frame.h0-=2;const c=service.renderTile(frame,1_100_000_007);assert.equal(calls,2);release();await c;
 let attempts=0;
 const retry=fixture(t,bytes,{},undefined,[],async()=>{attempts++;if(attempts===1)throw Error('temporary');return attempts===2?null:bytes;}).service;
 await assert.rejects(retry.renderTile(frame,1_100_000_007),/temporary/);
 assert.equal(await retry.renderTile(frame,1_100_000_007),null);
 assert.ok(await retry.renderTile(frame,1_100_000_007));assert.equal(attempts,3);
});
test('corrected tile cache evicts least recently used bytes and never retains oversized tiles',async t=>{
 const bytes=tile([[25,3,4],[26,4,4],[25,3,5]]);let calls=0;
 const {service}=fixture(t,bytes,{}, {correctedTileCacheBytes:bytes.length*2},[],async()=>{calls++;return bytes;});
 const frame={...origin},get=id=>service.renderTile(frame,1_100_000_000+id);
 await get(1);await get(2);await get(1);await get(3);assert.equal(calls,3);
 await get(1);assert.equal(calls,3);await get(2);assert.equal(calls,4);
 let largeCalls=0;
 const small=fixture(t,bytes,{}, {correctedTileCacheBytes:bytes.length-1},[],async()=>{largeCalls++;return bytes;}).service;
 await small.renderTile(frame,1_100_000_007);await small.renderTile(frame,1_100_000_007);assert.equal(largeCalls,2);
});

test('bounded complete-envelope cleanup preserves the outside of a source triangle in any save datum',async t=>{
 for(const shift of [0,7])for(const [points,width,expectedArea]of [
  [[[34,2,2],[38,2,2],[34,2,6]],4,2],
  [[[34,2,2],[40,2,2],[40,2,6]],6,32/3] // Outside centroid still crosses the complete envelope.
 ]){
  const source=tile(points);source.writeDoubleLE(shift,16);
  points.forEach(([x,y,z],i)=>{source.writeFloatLE((x-34)/width,48+i*20+12);source.writeFloatLE((z-2)/4,48+i*20+16);});
  const {service,dir}=fixture(t,source,{photoFacades:{file:'photo-facades.json'}},{collectRegionTiles(){throw Error('manual only');}},[{id:7,parent:0,chain:[]}]);
  fs.writeFileSync(path.join(dir,'photo-facades.json'),JSON.stringify({plans:[{id:'bounded',manualRoof:true,completeEnvelope:true,bounds:[[30,0,0],[36,8,8]],retirementBoundary:[{ring:[[30,0],[36,0],[36,8],[30,8]],holes:[]}],walls:[{reconstructed:true}]}]}));
  const frame={...origin,h0:origin.h0-shift};let selected;
  for(let i=0;i<100;i++){selected=await service.renderSelect(frame,[35,4,4]);if(!selected.pending)break;await new Promise(r=>setTimeout(r,1));}
  assert.equal(selected.pending??0,0);
  const b=await service.renderTile(frame,1_200_000_007);assert.deepEqual([...b.subarray(-4)],[12,34,56,255]);
  const count=b.readInt32LE(32),vertices=[];assert.ok(count>=3);
  for(let i=0;i<count;i++){
   const p=Array.from({length:5},(_,k)=>b.readFloatLE(48+i*20+k*4));assert.ok(p[0]>=36-1e-6);assert.ok(Math.abs(p[1]+b.readDoubleLE(16)-(2+shift))<1e-6);assert.ok(Math.abs(p[3]-(p[0]-34)/width)<1e-6);assert.ok(Math.abs(p[4]-(p[2]-2)/4)<1e-6);vertices.push(p);
  }
  let area=0;for(let i=0;i<count;i+=3){const [a,c,d]=vertices.slice(i,i+3);area+=Math.abs((c[0]-a[0])*(d[2]-a[2])-(c[2]-a[2])*(d[0]-a[0]))/2;}
  assert.ok(Math.abs(area-expectedArea)<1e-5,'Exactly the area outside the rebuilt footprint must survive');
 }
});

test('pinned river survives a live OSM outage without changing foreign regions or disabled water',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-water-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,0,z]);
 const river={id:'way/river',minx:30,maxx:40,minz:30,maxz:40,segs:[30,30,40,30,40,30,40,40,40,40,30,40,30,40,30,30]};
 river.surveyGround={rings:[{ring:[[30,30],[40,30],[40,40],[30,40]],holes:[]}],terrainGuide:{width:2,height:2,points:[[30,61.35,30],[40,61.35,30],[30,61.35,40],[40,61.35,40]]}};
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),tiles:[],terrainGuide:{width:3,height:3,points},pinnedWater:{features:[river]}}));
 let calls=0,fail=true;const other={id:'other'};
 const service={cfg:{},renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>null,waterFor:async()=>{calls++;if(fail)throw Error('OSM offline');return [other];}};
 attachSurveySurface(service,dir);
 const result=await service.waterFor(origin,25,25,16);assert.equal(result.length,1);assert.equal(result[0].id,river.id);assert.deepEqual([...result[0].segs],river.segs);
 assert.equal(result[0].surveyGround.heightOffset,0);
 const shifted=await service.waterFor({...origin,h0:origin.h0-3},25,25,16);assert.equal(shifted[0].surveyGround.heightOffset,3);assert.equal(shifted[0].surveyGround.terrainGuide.points[0][1],61.35);
 fail=false;assert.deepEqual((await service.waterFor(origin,25,25,16)).map(f=>f.id),['other','way/river']);
 assert.deepEqual(await service.waterFor(origin,0,0,16),[other]);
 assert.deepEqual(await service.waterFor({...origin,lat:1},25,25,16),[other]);
 const before=calls;service.cfg.water=false;assert.deepEqual(await service.waterFor(origin,25,25,16),[]);assert.equal(calls,before);
});

test('explicit river canopy retirement works beyond all terrain grids and preserves bridge holes',async t=>{
 const region={rings:[{ring:[[30,0],[40,0],[40,10],[30,10]],holes:[[[36,2],[39,2],[39,8],[36,8]]]}],y0:5,y1:15};
 const extra={architecture:{riverbank:{sourceRetirement:[region]}}};
 const tree=fixture(t,tile([[32,8,3],[34,9,3],[32,8,5]]),extra);
 assert.equal((await tree.service.renderTile(origin,1_100_000_007)).readInt32LE(32),0);
 const bytes=tile([[37,8,3],[38,8,3],[37,8,4]]),bridge=fixture(t,bytes,extra);
 assert.deepEqual(await bridge.service.renderTile(origin,1_100_000_007),bytes);
 assert.deepEqual(await bridge.service.renderTile({...origin,lat:49},1_100_000_007),bytes);
});

test('channel collision clears old canopy, keeps actual branches and native fluid, and protects the bridge',async t=>{
 const survey={rings:[{ring:[[32,0],[44,0],[44,16],[32,16]],holes:[[[37,4],[39,4],[39,8],[37,8]]]}],terrainGuide:{width:2,height:2,points:[[32,4.2,0],[44,4.2,0],[32,4.2,16],[44,4.2,16]]}};
 const trees={file:'river-tree.ect',kind:'vegetation',runtimeId:501,bounds:[[32,4,0],[44,12,16]]};
 const extra={tiles:[trees],architecture:{riverbank:{waterGround:survey,sourceRetirement:[{rings:survey.rings,y0:2,y1:13}]}}};
 const {service,dir}=fixture(t,null,extra,{voxelizeArea:()=>{throw Error('Tree geometry must not enter terrain inference');}});
 fs.writeFileSync(path.join(dir,trees.file),tile([[34,8,3],[35,9,3],[34,8,4]]));
 const frame={...origin,mcToEcef:(...p)=>p};
 const patch=service.campusCollision(frame,2,0,0,16),at=(y,x=2,z=3)=>patch[(y*16+z)*16+x];
 assert.equal(at(3),255);assert.equal(at(4),0);assert.equal(at(8),8);assert.equal(at(5),0);assert.equal(at(14),255);
 assert.equal(at(8,6,5),255);assert.equal(at(8,15,3),255);
 assert.ok(service.campusCollision({...frame,lat:49},2,0,0,16).every(v=>v===255));
 // Give the upstream generator a higher fluid voxel than the local sample.
 const upstream=new Uint8Array(16*16*16);upstream[(4*16+3)*16+2]=23;
 const waterFixture=fixture(t,null,extra,{voxelizeArea:(_f,_a,_x,_z,w,_y,h)=>({vox:new Uint8Array(w*w*h)})});
 fs.writeFileSync(path.join(waterFixture.dir,trees.file),tile([[34,8,3],[35,9,3],[34,8,4]]));
 // Reattach to a separate service whose original chunk owns that fluid.
 const svc={cfg:{},renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>null,chunk:async()=>upstream};
 attachSurveySurface(svc,waterFixture.dir,{voxelizeArea:(_f,_a,_x,_z,w,_y,h)=>({vox:new Uint8Array(w*w*h)})});
 const result=await svc.chunk(frame,2,0,0,16);assert.equal(result[(4*16+3)*16+2],23);
 service.cfg={water:false};assert.ok(service.campusCollision(frame,2,0,0,16).every(v=>v===255));
});

test('disabled native water retains the photographic channel surface and its original collision',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-water-off-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,0,z]);
 const rings=[{ring:[[30,0],[40,0],[40,10],[30,10]],holes:[]}];
 const riverbank={sourceRetirement:[{kind:'water-channel',rings,y0:2,y1:20}],waterGround:{rings,terrainGuide:{width:2,height:2,points:[[30,4,0],[40,4,0],[30,4,10],[40,4,10]]}}};
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),tiles:[],terrainGuide:{width:3,height:3,points},architecture:{riverbank}}));
 const bytes=tile([[32,4,2],[34,4,2],[32,4,4]]),service={cfg:{water:false},renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>bytes,chunk:async()=>new Uint8Array(4096)};
 attachSurveySurface(service,dir,{voxelizeArea:()=>({vox:new Uint8Array(4096)})});
 assert.deepEqual(await service.renderTile(origin,1_100_000_007),bytes);
 assert.ok(service.campusCollision({...origin,mcToEcef:(...p)=>p},2,0,0,16).every(v=>v===255));
});

test('fine tree packets exclude terrain inference and preserve fractional supports and solids',t=>{
 const specs=[{file:'ground.ect',kind:'ground',runtimeId:500,bounds:[[0,0,0],[16,1,16]]},{file:'tree.ect',kind:'vegetation',runtimeId:501,bounds:[[2,0,3],[3,5,4]]}];
 const {service,dir}=fixture(t,null,{tiles:specs},{voxelizeArea:(_frame,assets,_x,_z,w,_y,h)=>{
  assert.equal(assets.length,1,'Only the ground enters terrain filling');
  const vox=new Uint8Array(w*w*h);vox[3*16+2]=45;vox[(4*16+3)*16+2]=7;return {vox};
 }});
 fs.writeFileSync(path.join(dir,'ground.ect'),tile([[0,.875,0],[16,.875,0],[0,.875,16]]));
 fs.writeFileSync(path.join(dir,'tree.ect'),tile([[2.1,.5,3.1],[2.2,5,3.1],[2.3,.5,3.3]]));
 const frame={...origin,mcToEcef:(...p)=>p},packet=service.campusCollisionPacket(frame,0,0,0,8),cells=2048;
 assert.equal(packet[3*16+2],45);assert.equal(packet[(4*16+3)*16+2],7);assert.equal(packet[(2*16+3)*16+2],8);
 assert.equal(packet[(2*16+3)*16+3],0,'No dirt or coarse wood beside the visible trunk');
 const hints=new Map();for(let p=cells+8;p<packet.length;p+=4)hints.set(packet.readUInt16LE(p),packet.readUInt16LE(p+2));
 assert.ok(hints.has((2*16+3)*16+2));assert.ok(!hints.has(3*16+2));assert.ok(!hints.has((4*16+3)*16+2));
 const foreign=service.campusCollisionPacket({...frame,lat:49},0,0,0,8);assert.ok(foreign.subarray(0,cells).every(v=>v===255));assert.equal(foreign.readUInt32LE(cells+4),0);
});

test('fine reconstructed solids preserve terrain and nearby structures without filling corner cells',t=>{
 for(const shift of [0,2]){
  const specs=[{file:'base.ect',kind:'ground',runtimeId:600,bounds:[[0,0,0],[16,1,16]]},{file:'solid.ect',kind:'reconstruction',runtimeId:601,bounds:[[2,0,3],[2.25,5,3.25]],fineCollisionMaterials:[4]}];
  const {service,dir}=fixture(t,null,{tiles:specs},{voxelizeArea:(_frame,assets,_x,_z,w,_y,h)=>{
   assert.equal(assets.length,1,'Reconstructed solid is excluded from terrain filling');
   const vox=new Uint8Array(w*w*h);vox[3*16+2]=45;vox[(4*16+3)*16+2]=6;vox[(2*16+3)*16+3]=23;return {vox};
  }});
  fs.writeFileSync(path.join(dir,'base.ect'),tile([[0,.875,0],[16,.875,0],[0,.875,16]]));
  fs.writeFileSync(path.join(dir,'solid.ect'),tile([[2.1,.5,3.1],[2.2,5,3.1],[2.25,.5,3.25]]));
  const frame={...origin,h0:origin.h0-shift,mcToEcef:(...p)=>p},cells=2048,packet=service.campusCollisionPacket(frame,0,0,shift,8);
  assert.equal(packet[3*16+2],45,'Fractional ground is retained');assert.equal(packet[(4*16+3)*16+2],6,'Other structure is retained');assert.equal(packet[(2*16+3)*16+3],23,'Native fluid is retained');
  const index=(2*16+3)*16+2;assert.equal(packet[index],4);
  const hints=new Map();for(let p=cells+8;p<packet.length;p+=4)hints.set(packet.readUInt16LE(p),packet.readUInt16LE(p+2));
  assert.ok(hints.has(index));assert.ok(!hints.has(3*16+2));assert.ok(!hints.has((4*16+3)*16+2));assert.ok(!hints.has((2*16+3)*16+3));
  // Profile interval indices decode to a quarter-cell at this wall, not a full cube.
  const intervals=[];for(let lo=0;lo<16;lo++)for(let hi=lo+1;hi<=16;hi++)intervals.push([lo,hi]);
  const profile=hints.get(index),x=intervals[Math.floor(profile/136)],z=intervals[profile%136];assert.ok(x[1]<=4&&z[1]<=4);
  assert.equal(packet[(2*16+4)*16+2],0,'No invented solid or dirt in the neighbouring column');
 }
});

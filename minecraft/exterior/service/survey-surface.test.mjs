import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {attachSurveySurface} from './survey-surface.mjs';

const origin={lat:48.265,lon:11.671,h0:519.7618173672081};
function tile(positions){
 const b=Buffer.alloc(32+16+positions.length*20+4);b.write('ECT1');b.writeInt32LE(1,4);b.writeInt32LE(positions.length,32);b.writeInt32LE(1,36);b.writeInt32LE(1,40);b.fill(255,44,48);
 positions.forEach((p,i)=>[...p,.25,.75].forEach((n,j)=>b.writeFloatLE(n,48+i*20+j*4)));b.set([12,34,56,255],b.length-4);return b;
}
function fixture(t,bytes,extra={},deps,sourceTiles=[]){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-survey-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,0,z]);
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),attribution:'BVV CC BY 4.0',tiles:[],terrainGuide:{width:3,height:3,points},walls:[{points:[[10,0,3],[10,10,3],[10,10,17],[10,0,17]]}],...extra}));
 const service={renderSelect:async()=>({tiles:sourceTiles,attribution:[]}),renderTile:async()=>bytes};const check=attachSurveySurface(service,dir,deps);return {service,check,dir};
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

test('photographic replacement switches ids only after readiness, preserves old tiles and uses save datum without mutating source',async t=>{
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
 const initial=await service.renderSelect(frame,[5,6,6]);assert.equal(initial.pending,1);assert.equal(initial.tiles[0].id,1_100_000_007);
 let result;
 for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,5));result=await service.renderSelect(frame,[5,6,6]);if(result.pending===0)break;}
 assert.equal(result.pending,0);assert.ok(result.tiles.some(t=>t.id===1_000_050_000));assert.ok(result.tiles.some(t=>t.id===1_200_000_007));assert.ok(result.attribution.includes('test provider'));
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
 assert.equal(result[0],20); // Outside the covered guide's inner margin.
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

test('current landmarks survive aerial mode while unrelated photographic ground remains unchanged',async t=>{
 const extra={tiles:[{runtimeId:1_000_030_010,kind:'reconstruction',file:'current-building.ect',alwaysVisible:true}],replacements:[{ring:[[3,3],[8,3],[8,8],[3,8]],holes:[],y0:2,y1:20,alwaysVisible:true}],protectionGrid:{width:20,height:20,metresPerPixel:1,data:Buffer.alloc(400).toString('base64')}};
 const oldSite=fixture(t,tile([[4,8,4],[5,9,4],[4,8,5]]),extra);
 const aerial=await oldSite.service.renderSelect(origin,[6,100,6]);assert.ok(aerial.tiles.some(x=>x.id===1_000_030_010));
 assert.equal((await oldSite.service.renderTile(origin,1_300_000_007)).readInt32LE(32),0);
 for(const p of [[[12,.4,12],[13,.6,12],[12,.4,13]],[[4,25,4],[5,26,4],[4,25,5]]]){
  const original=tile(p),other=fixture(t,original,extra);assert.deepEqual(await other.service.renderTile(origin,1_300_000_007),original);
 }
 const shifted=tile([[4,8,4],[5,9,4],[4,8,5]]);shifted.writeDoubleLE(2,16);const other=fixture(t,shifted,extra);
 assert.equal((await other.service.renderTile({...origin,h0:origin.h0-2},1_300_000_007)).readInt32LE(32),0);
 assert.deepEqual((await other.service.renderSelect({...origin,lat:49},[6,100,6])).tiles,[]);
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

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
function fixture(t,bytes,extra={}){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-survey-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,0,z]);
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),attribution:'BVV CC BY 4.0',tiles:[],terrainGuide:{width:3,height:3,points},walls:[{points:[[10,0,3],[10,10,3],[10,10,17],[10,0,17]]}],...extra}));
 const service={renderSelect:async()=>({tiles:[],attribution:[]}),renderTile:async()=>bytes};const check=attachSurveySurface(service,dir);return {service,check};
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

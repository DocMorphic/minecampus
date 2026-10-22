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
function fixture(t,bytes){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'campus-survey-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const points=[];for(let z=0;z<=20;z+=10)for(let x=0;x<=20;x+=10)points.push([x,0,z]);
 fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({origin:Object.values(origin),attribution:'BVV CC BY 4.0',tiles:[],terrainGuide:{width:3,height:3,points},walls:[{points:[[10,0,3],[10,10,3],[10,10,17],[10,0,17]]}]}));
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

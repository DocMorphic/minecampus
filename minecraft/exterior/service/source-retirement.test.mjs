import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareSourceRetirement} from './source-retirement.mjs';
function tile(triangles,shift=0){
 const v=triangles.flat(),b=Buffer.alloc(32+16+v.length*20+4);b.write('ECT1');b.writeInt32LE(1,4);b.writeDoubleLE(shift,16);b.writeInt32LE(v.length,32);b.writeInt32LE(1,36);b.writeInt32LE(1,40);
 v.forEach((p,i)=>[...p,p[0]/8,p[2]/8].forEach((n,j)=>b.writeFloatLE(n,48+i*20+j*4)));b.set([12,34,56,255],b.length-4);return b;
}
const zone={rings:[{ring:[[2,2],[6,2],[6,6],[2,6]],holes:[]}],y0:5,y1:10};
test('retire an overhanging canopy above water without requiring a land surface',()=>{
 const input=tile([[[3,7,3],[4,7,3],[3,8,4]],[[3,2,3],[4,2,3],[3,2,4]]]);
 const output=prepareSourceRetirement([zone])(input);
 assert.equal(output.readInt32LE(32),3);assert.equal(output.readFloatLE(52),2);assert.deepEqual(output.subarray(-4),input.subarray(-4));
});
test('boundary clipping retains outside fragments with interpolated UVs and shifted datum',()=>{
 const input=tile([[[0,7,3],[8,7,3],[0,7,5]]],20),output=prepareSourceRetirement([zone])(input,20);
 const n=output.readInt32LE(32);assert.ok(n>3);
 for(let i=0;i<n;i++){
  const at=48+i*20,x=output.readFloatLE(at),z=output.readFloatLE(at+8);
  assert.ok(Math.abs(output.readFloatLE(at+12)-x/8)<1e-6);assert.ok(Math.abs(output.readFloatLE(at+16)-z/8)<1e-6);
  assert.equal(output.readFloatLE(at+4),7);
 }
 assert.deepEqual(output.subarray(-4),input.subarray(-4));
});
test('bridge protection holes retain source geometry inside an otherwise retired channel',()=>{
 const bridge={...zone,rings:[{...zone.rings[0],holes:[[[3,3],[5,3],[5,5],[3,5]]]}]};
 const input=tile([[[3.5,7,3.5],[4.5,7,3.5],[3.5,7,4.5]]]);assert.deepEqual(prepareSourceRetirement([bridge])(input),input);
 assert.strictEqual(prepareSourceRetirement([])(input),input);
});

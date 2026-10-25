import fs from 'node:fs';
import assert from 'node:assert/strict';
import {prepareSourceRetirement} from '../minecraft/exterior/service/source-retirement.mjs';
const m=JSON.parse(fs.readFileSync((process.argv[2]??'dist-minecraft/exterior')+'/manifest.json'));
const clip=prepareSourceRetirement(m.architecture.reactorEast.sourceRetirement);
const fixtures=[
 {name:'actual candidate 81 lower-east fragment',points:[[379.4514465332031,76.96099662780762,-81.01754760742188],[379.6569519042969,76.9567403793335,-83.27669525146484],[379.4516372680664,80.44420719146729,-81.22297477722168]],removed:true},
 {name:'higher reactor facade',points:[[379.45,89,-81.01],[379.65,89,-83.27],[379.45,91,-81.22]],removed:false},
 {name:'adjacent reactor envelope',points:[[365,70,-80],[365,72,-80],[365,70,-82]],removed:false}
];
let checked=0;
for(const shift of [0,2])for(const f of fixtures){
 const b=Buffer.alloc(32+16+3*20+4);b.write('ECT1');b.writeInt32LE(1,4);b.writeDoubleLE(shift,16);b.writeInt32LE(3,32);b.writeInt32LE(1,36);b.writeInt32LE(1,40);b.fill(255,44,48);
 f.points.forEach((p,i)=>[...p,.25,.75].forEach((v,k)=>b.writeFloatLE(v,48+i*20+k*4)));b.set([12,34,56,255],b.length-4);
 const result=clip(b,shift);
 if(f.removed)assert.equal(result.readInt32LE(32),0,f.name);else assert.deepEqual(result,b,f.name);
 assert.deepEqual(result.subarray(-4),b.subarray(-4));checked++;
}
console.log(JSON.stringify({status:'PASS: actual lower-east scan fragment removed at both datums; neighboring and higher reactor geometry preserved',controls:checked}));

import fs from 'node:fs';
import assert from 'node:assert/strict';
import {prepareSourceRetirement} from '../minecraft/exterior/service/source-retirement.mjs';
const m=JSON.parse(fs.readFileSync((process.argv[2]??'dist-minecraft/exterior')+'/manifest.json'));
const clip=prepareSourceRetirement(m.architecture.reactorSite.sourceRetirement);
const fixtures=[
 {name:'north tree scan',points:[[301.32035636901855,65.41673922538757,-125.35305643081665],[300.7034845352173,66.44147777557373,-124.73691511154175],[302.1430711746216,67.8756251335144,-125.76390075683594]],removed:true},
 {name:'north wing remnant',points:[[351.8907136917114,67.26728343963623,-120.42699563503265],[350.4510679244995,66.24160599708557,-120.6322546005249],[350.45115184783936,67.67604684829712,-120.6322854757309]],removed:true},
 {name:'east failed first hit',points:[[379.4520893096924,87.2083306312561,-80.40157413482666],[380.06892013549805,89.25076818466187,-84.30378532409668],[379.2466678619385,90.28346866369247,-79.58010387420654]],removed:true},
 {name:'lower neighbouring body',points:[[379.4520893096924,78,-80.40157413482666],[380.06892013549805,80,-84.30378532409668],[379.2466678619385,81,-79.58010387420654]],removed:false}
];
let checked=0;
for(const shift of [0,2])for(const f of fixtures){
 const b=Buffer.alloc(32+16+3*20+4);b.write('ECT1');b.writeInt32LE(1,4);b.writeDoubleLE(shift,16);b.writeInt32LE(3,32);b.writeInt32LE(1,36);b.writeInt32LE(1,40);b.fill(255,44,48);
 f.points.forEach((p,i)=>[...p,.25,.75].forEach((v,k)=>b.writeFloatLE(v,48+i*20+k*4)));b.set([12,34,56,255],b.length-4);
 const result=clip(b,shift);
 if(f.removed)assert.equal(result.readInt32LE(32),0,f.name);else assert.deepEqual(result,b,f.name);
 assert.deepEqual(result.subarray(-4),b.subarray(-4));checked++;
}
console.log(JSON.stringify({status:'PASS: three actual failed-view fragments removed at both datums; lower neighbour bytes preserved',controls:checked}));

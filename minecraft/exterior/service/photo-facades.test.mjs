import test from 'node:test';
import assert from 'node:assert/strict';
import {bakeWall,acceptsFacade} from './photo-facades.mjs';
const wall={anchor:[0,0,0],direction:[1,0,0],normal:[0,0,1],bounds:[[0,0],[4,4]],rings:[[[0,0],[4,0],[4,4],[0,4]]],vertices:[[0,0,0],[4,0,0],[4,4,0],[0,4,0]],indices:[0,1,2,0,2,3]};
const mesh=(z,color,x=4)=>({mc:new Float64Array([0,0,z,x,0,z,x,4,z,0,4,z]),uvs:new Float32Array([0,1,1,1,1,0,0,0]),indices:new Uint32Array([0,1,2,0,2,3]),color});
const options={pixelsPerMetre:4,maxProjectionDistance:6,sampleColor:(p,u,v,out)=>{out.splice(0,3,...p.color);}};
test('survey-normal depth chooses the wall over a foreground fragment regardless of source order',()=>{
 for(const sources of [[mesh(.2,[180,120,70]),mesh(3,[10,90,10])],[mesh(3,[10,90,10]),mesh(.2,[180,120,70])]]){
  const b=bakeWall(wall,sources,options);assert.equal(b.coverage,1);assert.equal(b.unfilled,0);assert.deepEqual([...b.data.subarray(0,4)],[180,120,70,255]);assert.ok(acceptsFacade([b]));
 }
});
test('projection rejects unrelated depth and preserves explicit unobserved coverage',()=>{
 const missing=bakeWall(wall,[mesh(8,[50,50,50])],options);assert.equal(missing.coverage,0);assert.equal(missing.unfilled,missing.wanted);assert.equal(acceptsFacade([missing]),false);
 const partial=bakeWall(wall,[mesh(.1,[50,70,90],2)],options);assert.equal(partial.coverage,.5);assert.equal(partial.unfilled,0);assert.equal(acceptsFacade([partial]),false);
});
test('bounded small gaps are filled from observed material without counting them as photographed',()=>{
 const b=bakeWall(wall,[mesh(.1,[50,70,90],3.5)],options);assert.equal(b.coverage,.875);assert.equal(b.unfilled,0);assert.ok(b.maxFillDistance<=.5);assert.ok(acceptsFacade([b]));
 assert.deepEqual([...b.data.subarray(-4)],[50,70,90,255]);
});
test('survey openings are excluded from coverage and remain transparent',()=>{
 const b=bakeWall({...wall,rings:[...wall.rings,[[1,1],[3,1],[3,3],[1,3]]]},[mesh(0,[80,80,80])],options);
 assert.equal(b.coverage,1);assert.equal(b.wanted,192);assert.equal(b.data[(8*b.width+8)*4+3],0);
});

test('coverage excludes surveyed buried foundations while still rejecting missing material above ground',()=>{
 const upper={...mesh(.1,[70,80,90]),mc:new Float64Array([0,2,.1,4,2,.1,4,4,.1,0,4,.1])};
 const visible={...wall,groundProfile:[[0,2.15],[4,2.15]]};
 const original=bakeWall(wall,[upper],options),b=bakeWall(visible,[upper],options);
 assert.equal(original.coverage,.5);assert.equal(acceptsFacade([original]),false);
 assert.equal(b.wanted,128);assert.equal(b.coverage,1);assert.ok(acceptsFacade([b]));
 assert.equal(b.data[(15*b.width+8)*4+3],0);
 const sloping=bakeWall({...wall,groundProfile:[[0,.15],[4,4.15]]},[upper],options);
 assert.equal(acceptsFacade([sloping]),false);
 const buried=bakeWall({...wall,groundProfile:[[0,5],[4,5]]},[upper],options);
 assert.equal(buried.wanted,0);assert.equal(acceptsFacade([buried]),false);
});

test('source ownership preserves an unsupported nearby wall and courtyard while replacing accepted walls and roof',async()=>{
 const {retiresPhotoSurface}=await import('./photo-facades.mjs');
 const front={...wall,accepted:true},back={...wall,anchor:[0,0,3],accepted:false};
 const photo={patches:[{bounds:[[0,0,0],[4,4,4]],walls:[front,back],roofTriangles:[[[0,4,0],[4,4,0],[0,4,1]],[[4,4,0],[4,4,1],[0,4,1]]],roofCache:new Map()}]};
 assert.equal(retiresPhotoSurface(photo,2,2,.4),true);
 assert.equal(retiresPhotoSurface(photo,2,2,2.8),false);
 assert.equal(retiresPhotoSurface(photo,5,2,.3),true);
 assert.equal(retiresPhotoSurface(photo,5,2,2.8),false);
 assert.equal(retiresPhotoSurface(photo,2,4,.5),true);
 assert.equal(retiresPhotoSurface(photo,2,4,2.5),false);
 assert.equal(retiresPhotoSurface(photo,20,4,.5),false);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {woodShapes,woodProfileBounds,WOOD_PROFILE_COUNT} from './wood-shapes.mjs';
function tube(cx,cz,r,y0,y1){
  const triangles=[];
  for(let i=0;i<9;i++){
    const a=i*2*Math.PI/9,b=(i+1)*2*Math.PI/9;
    const p=[cx+Math.cos(a)*r,y0,cz+Math.sin(a)*r],q=[cx+Math.cos(b)*r,y0,cz+Math.sin(b)*r],s=[q[0],y1,q[2]],t=[p[0],y1,p[2]];
    triangles.push([p,q,s],[p,s,t]);
  }
  return triangles;
}
test('near-trunk player clearance survives quantization across a block boundary',()=>{
  // Native ZNN43b failed here despite about4cm of visible wood clearance.
  const x=402.5954040177183,z=-382.78560948811094;
  const wood=tube(401.8545024531209,-383.061498640736,.42,63.8165,68);
  const shapes=woodShapes(wood,{x0:400,z0:-384,width:4,minY:64,height:2});
  assert.ok(shapes.size>0);
  for(const [i,profile]of shapes){
    const bx=400+i%4,bz=-384+Math.floor(i/4)%4,[a,b,c,d]=woodProfileBounds(profile);
    const overlap=bx+a<x+.3&&bx+c>x-.3&&bz+b<z+.3&&bz+d>z-.3;
    assert.equal(overlap,false,'Trunk profile intrudes into the clear player body');
  }
  // The same profiles still block a player walking straight into the trunk.
  assert.ok([...shapes].some(([i,p])=>{const bx=400+i%4,bz=-384+Math.floor(i/4)%4,[a,b,c,d]=woodProfileBounds(p);return bx+a<402&&bx+c>401.7&&bz+b<-382.9&&bz+d>-383.2;}));
});
test('branch geometry cannot invent support below itself or in another chunk',()=>{
  const tri=[[[.1,8.2,.1],[.8,8.3,.1],[.1,8.4,.8]]];
  const shapes=woodShapes(tri,{x0:0,z0:0,width:16,minY:0,height:16});
  assert.equal(shapes.size,1);assert.ok(shapes.has(8*256));
  assert.equal(woodShapes(tri,{x0:16,z0:0,width:16,minY:0,height:16}).size,0);
  const shifted=tri.map(t=>t.map(([x,y,z])=>[x,y+5,z]));
  assert.deepEqual([...woodShapes(shifted,{x0:0,z0:0,width:16,minY:5,height:16})],[...shapes]);
});
test('profiles round trip every valid rectangle and reject invalid inputs',()=>{
  const seen=new Set();
  for(let p=0;p<WOOD_PROFILE_COUNT;p++){
    const [x0,z0,x1,z1]=woodProfileBounds(p);assert.ok(x0<x1&&z0<z1);seen.add([x0,z0,x1,z1].join(','));
  }
  assert.equal(seen.size,WOOD_PROFILE_COUNT);
  assert.throws(()=>woodProfileBounds(-1),RangeError);
  assert.throws(()=>woodShapes([[[NaN,0,0],[0,1,0],[0,0,1]]],{x0:0,z0:0,minY:0,height:16}),TypeError);
});

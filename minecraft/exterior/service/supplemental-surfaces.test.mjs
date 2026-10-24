import test from 'node:test';
import assert from 'node:assert/strict';
import {supplementalSurfaces} from './supplemental-surfaces.mjs';

const grid={width:2,height:2,points:[[0,0,0],[1,0,0],[0,0,1],[1,0,1]]};
const signed=p=>p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-b[0]*a[1];},0)/2;
const ring=(r,n)=>Array.from({length:n},(_,i)=>[r*Math.cos(i*2*Math.PI/n),r*Math.sin(i*2*Math.PI/n)]);
test('dense curved coverage preserves outside terrain and a hole without excessive fragments',()=>{
 const outer=ring(10,256),hole=ring(2,64);
 const s=supplementalSurfaces([{terrainGuide:grid,rings:[{ring:outer,holes:[hole]}]}]);
 const triangle=[[-30,5,-20,0,0],[30,65,-20,1,0],[0,35,40,.5,1]];
 const fragments=s.outsideFragments(triangle);
 let area=0;
 for(const f of fragments){
  const a=signed(f.map(p=>[p[0],p[2]]));assert.ok(a>=-1e-8);area+=a;
  for(const [x,y,z,u,v]of f){assert.ok(Math.abs(y-x-35)<1e-8);assert.ok(Math.abs(u-(x+30)/60)<1e-8);assert.ok(Math.abs(v-(z+20)/60)<1e-8);}
 }
 assert.ok(Math.abs(area-(1800-signed(outer)+signed(hole)))<1e-6);
 // A distant edge's supporting line must not keep subdividing unrelated pieces.
 assert.ok(fragments.length<256*10,`Unexpected fragment growth: ${fragments.length}`);
});

test('bounded prism clipping preserves vertical geometry above and below its height interval',async()=>{
 const {surfaceBoundaryClipper}=await import('./supplemental-surfaces.mjs');
 const clip=surfaceBoundaryClipper([{rings:[{ring:[[-1,-1],[1,-1],[1,9],[-1,9]]}],y0:0,y1:2}]);
 const triangle=[[0,-2,0,0,0],[0,6,0,1,0],[0,-2,8,0,1]],fragments=clip.outsideFragments(triangle);let area=0;
 for(const f of fragments){
  const [a,b,c]=f;area+=Math.abs((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]))/2;
  const y=f.reduce((s,p)=>s+p[1],0)/3;assert.ok(y<=0||y>=2);
  for(const p of f){assert.equal(p[0],0);assert.ok(Math.abs(p[3]-(p[1]+2)/8)<1e-8);assert.ok(Math.abs(p[4]-p[2]/8)<1e-8);}
 }
 assert.ok(Math.abs(area-22)<1e-8);
 assert.deepEqual(clip.outsideFragments([[4,4,4,0,0],[5,4,4,1,0],[4,4,5,0,1]]),[[[4,4,4,0,0],[5,4,4,1,0],[4,4,5,0,1]]]);
});

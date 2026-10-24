// Run against the service extracted from the exact packaged JAR.
import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve(process.argv[2]);
const {voxelizeArea}=await import(pathToFileURL(path.join(root,'voxel.mjs')));
const {terrainColumnSupport}=await import(pathToFileURL(path.join(root,'terrain-column.mjs')));
const frame={ecefToMc:(x,y,z,out,i)=>out.set([x,y,z],i)};
const minY=-8,height=32,w=4;
const primitive=(y,ground=true)=>({positions:new Float64Array([0,y,0,4,y,0,4,y,4,0,y,4]),indices:new Uint32Array([0,1,2,0,2,3]),uvs:new Float32Array(8),color:[100,100,100],campusHeightfield:ground});
const run=primitives=>voxelizeArea(frame,[{primitives}],0,0,w,minY,height,{water:[]}).vox;
const at=(vox,x,y,z)=>vox[((y-minY)*w+z)*w+x];
const top=(vox,x,z)=>{for(let y=minY+height-1;y>=minY;y--){const code=at(vox,x,y,z);if(code)return y+(code>=32&&code<=175?((code-32)%16+1)/16:1);}return null;};
let samples=0;
for(const h of [-2,-1.99,-1.51,-1.5,-1.01,-.01,0,.01,.03124,.03126,.49,.5,.51,.99,1,1.01,3.25,3.468,3.99]){
 const vox=run([primitive(h)]),support=terrainColumnSupport(h);
 assert.equal(support.y+support.height/16,(Math.round(h*16)/16+0));
 for(let z=0;z<4;z++)for(let x=0;x<4;x++)assert.equal(top(vox,x,z),(Math.round(h*16)/16+0),`height ${h} column ${x},${z}`);
 samples++;
}
// An ordinary roof/wall voxel wins over a partial terrain voxel in either input order.
for(const p of [[primitive(3.25),primitive(3.75,false)],[primitive(3.75,false),primitive(3.25)]]){
 const vox=run(p);assert.equal(top(vox,1,1),4);assert.ok(at(vox,1,3,1)<32);
}
// Overlapping measured ground selects the taller support, independent of input order.
for(const p of [[primitive(3.25),primitive(3.75)],[primitive(3.75),primitive(3.25)]])assert.equal(top(run(p),1,1),3.75);
// Untagged photogrammetry retains full cubes and emits no new protocol codes.
const legacy=run([primitive(3.25,false)]);assert.equal(top(legacy,1,1),3);assert.ok(!legacy.some(c=>c>=32));
assert.throws(()=>terrainColumnSupport(NaN));
console.log(JSON.stringify({status:'PASS: packaged fractional supports, boundaries, material codes and overlapping geometry',heightCases:samples,overlapCases:4}));

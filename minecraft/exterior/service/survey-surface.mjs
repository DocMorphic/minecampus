// Minecampus original runtime correction. Survey data: BVV, CC BY 4.0.
// Provider photo meshes remain transient and retain their original attribution.
import fs from 'node:fs';
import path from 'node:path';

/** Replaces noisy ground with surveyed terrain and substitutes explicit photo-textured
 * reconstructions only where their survey footprint is known. */
export function attachSurveySurface(service, directory, {voxelizeArea}={}) {
  const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
  const ground=manifest.tiles.filter(t=>t.kind==='ground'||t.kind==='reconstruction');
  const matches=frame=>Math.abs(frame.lat-manifest.origin[0])<1e-7 && Math.abs(frame.lon-manifest.origin[1])<1e-7;
  const ids=new Map(ground.map((t,i)=>[t.runtimeId??1_000_000_000+i,t]));
  const replacements=(manifest.replacements??[]).map(p=>({...p,bounds:[Math.min(...p.ring.map(v=>v[0])),Math.min(...p.ring.map(v=>v[1])),Math.max(...p.ring.map(v=>v[0])),Math.max(...p.ring.map(v=>v[1]))]}));
  function inside(x,z,ring){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
  function replaced(p){return replacements.some(r=>p[1]>=r.y0&&p[1]<=r.y1&&p[0]>=r.bounds[0]&&p[2]>=r.bounds[1]&&p[0]<=r.bounds[2]&&p[2]<=r.bounds[3]&&inside(p[0],p[2],r.ring)&&!(r.holes??[]).some(h=>inside(p[0],p[2],h)));}
  const guide=manifest.terrainGuide,{width,height,points}=guide;
  const a=points[0],u=points[1],v=points[width];
  const ux=u[0]-a[0],uz=u[2]-a[2],vx=v[0]-a[0],vz=v[2]-a[2],det=ux*vz-uz*vx;
  function terrain(x,z){
    const dx=x-a[0],dz=z-a[2],s=(dx*vz-dz*vx)/det,t=(ux*dz-uz*dx)/det;
    if(s<.2||t<.2||s>width-1.2||t>height-1.2)return null;
    const i=Math.floor(s),j=Math.floor(t),fx=s-i,fz=t-j;
    return (points[j*width+i][1]*(1-fx)+points[j*width+i+1][1]*fx)*(1-fz)+(points[(j+1)*width+i][1]*(1-fx)+points[(j+1)*width+i+1][1]*fx)*fz;
  }
  let removed=0;
  function correct(bytes,shift=0){
    const input=Buffer.from(bytes);if(input.toString('ascii',0,4)!=='ECT1')throw Error('Unsupported terrain format');
    const count=input.readInt32LE(4),anchor=[8,16,24].map(i=>input.readDoubleLE(i));let offset=32;
    const output=[input.subarray(0,32)];
    for(let part=0;part<count;part++){
      const start=offset,vertices=input.readInt32LE(offset),w=input.readInt32LE(offset+4),h=input.readInt32LE(offset+8);offset+=16;
      const triangles=[];
      for(let t=0;t<vertices;t+=3){
        const triangle=Buffer.from(input.subarray(offset+t*20,offset+(t+3)*20));
        const positions=[0,1,2].map(k=>[0,1,2].map(c=>triangle.readFloatLE(k*20+c*4)+anchor[c]));
        const levels=positions.map(p=>terrain(p[0],p[2]));
        if(levels.every((y,i)=>y!==null && positions[i][1]-y-shift<1.25)){removed++;continue;}
        const center=[0,1,2].map(c=>(positions[0][c]+positions[1][c]+positions[2][c])/3);
        if(replaced([center[0],center[1]-shift,center[2]])){removed++;continue;}
        triangles.push(triangle);
      }
      const header=Buffer.from(input.subarray(start,start+16));header.writeInt32LE(triangles.length*3,0);
      offset+=vertices*20;const tex=input.subarray(offset,offset+w*h*4);offset+=w*h*4;
      output.push(header,...triangles,tex);
    }
    return Buffer.concat(output);
  }
  const CLIPPED_OFFSET=1_100_000_000;
  const modes=new WeakMap();
  const select=service.renderSelect.bind(service),tile=service.renderTile.bind(service);
  service.renderSelect=async(frame,cam,...args)=>{
    const selected=await select(frame,cam,...args);
    if(!matches(frame))return selected;
    // Preserve the authentic photo mesh from the air. At walking height, switch
    // to the surveyed surfaces; use distinct ids so both versions remain cached.
    const groundY=terrain(cam[0],cam[2]);const altitude=groundY===null?Infinity:cam[1]-groundY-(manifest.origin[2]-frame.h0);
    let detailed=modes.get(frame)??(altitude<42);
    if(detailed&&altitude>52)detailed=false;else if(!detailed&&altitude<35)detailed=true;
    modes.set(frame,detailed);
    if(detailed){
      selected.tiles=selected.tiles.map(t=>({...t,id:t.id+CLIPPED_OFFSET,parent:t.parent?t.parent+CLIPPED_OFFSET:0,chain:t.chain.map(id=>id+CLIPPED_OFFSET)}));
      for(const [id]of ids)selected.tiles.unshift({id,fine:true,parent:0,chain:[]});
    }
    selected.attribution.push(manifest.attribution);
    return selected;
  };
  service.renderTile=async(frame,id)=>{
    if(!matches(frame))return tile(frame,id);
    const shift=manifest.origin[2]-frame.h0;
    if(ids.has(id)){const b=Buffer.from(await fs.promises.readFile(path.join(directory,ids.get(id).file)));b.writeDoubleLE(b.readDoubleLE(16)+shift,16);return b;}
    if(id<CLIPPED_OFFSET)return tile(frame,id);
    const bytes=await tile(frame,id-CLIPPED_OFFSET);return bytes?correct(bytes,shift):bytes;
  };
  const decodedAssets=new Map();
  function assetMeshes(frame,spec) {
    if(decodedAssets.has(spec.file))return decodedAssets.get(spec.file);
    const bytes=fs.readFileSync(path.join(directory,spec.file)),count=bytes.readInt32LE(4),anchor=[8,16,24].map(i=>bytes.readDoubleLE(i));
    const primitives=[];let offset=32;const shift=manifest.origin[2]-frame.h0;
    for(let part=0;part<count;part++){
      const n=bytes.readInt32LE(offset),w=bytes.readInt32LE(offset+4),h=bytes.readInt32LE(offset+8);offset+=16;
      const positions=new Float64Array(n*3),uvs=new Float32Array(n*2),indices=new Uint32Array(n);
      for(let i=0;i<n;i++){
        const at=offset+i*20,x=bytes.readFloatLE(at)+anchor[0],y=bytes.readFloatLE(at+4)+anchor[1]+shift,z=bytes.readFloatLE(at+8)+anchor[2];
        positions.set(frame.mcToEcef(x,y,z),i*3);uvs.set([bytes.readFloatLE(at+12),bytes.readFloatLE(at+16)],i*2);indices[i]=i;
      }
      offset+=n*20;const texture={width:w,height:h,data:bytes.subarray(offset,offset+w*h*4)};offset+=w*h*4;
      primitives.push({positions,uvs,indices,texture,color:[180,180,180]});
    }
    const mesh={primitives,copyright:manifest.attribution};decodedAssets.set(spec.file,mesh);return mesh;
  }
  if(voxelizeArea){
    service.campusCollision=(frame,cx,cz,minY,span)=>{
      const output=new Uint8Array(16*16*span);output.fill(255);
      if(!matches(frame))return output;
      const shift=manifest.origin[2]-frame.h0,x0=cx*16,z0=cz*16;
      const assets=ground.filter(t=>t.bounds[0][0]<=x0+17&&t.bounds[1][0]>=x0-1&&t.bounds[0][2]<=z0+17&&t.bounds[1][2]>=z0-1);
      if(!assets.length)return output;
      const {vox}=voxelizeArea(frame,assets.map(t=>assetMeshes(frame,t)),x0,z0,16,minY,span,{fallbackGround:63,water:[]});
      for(let z=0;z<16;z++)for(let x=0;x<16;x++){
        const px=x0+x+.5,pz=z0+z+.5,base=terrain(px,pz);if(base===null)continue;
        const level=base+shift;
        for(let y=0;y<span;y++){
          const wy=y+minY;if(wy<level-4)continue;
          if(wy>level+1.25&&!replaced([px,wy+.5-shift,pz]))continue;
          const i=(y*16+z)*16+x;let code=vox[i];
          if(code===2)code=1;if(code===20)code=3;if(code===21||code===22)code=4;
          output[i]=code;
        }
      }
      return output;
    };
    const chunk=service.chunk.bind(service);
    service.chunk=async(frame,cx,cz,minY,span)=>{
      const original=await chunk(frame,cx,cz,minY,span),patch=service.campusCollision(frame,cx,cz,minY,span);
      const output=Uint8Array.from(original);for(let i=0;i<output.length;i++)if(patch[i]!==255)output[i]=patch[i];return output;
    };
  }
  return {manifest,renderTiles:ids.size,stats:()=>({removedSourceTriangles:removed})};
}

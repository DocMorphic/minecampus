// Minecampus original runtime correction. Survey data: BVV, CC BY 4.0.
// Provider photo meshes remain transient and retain their original attribution.
import fs from 'node:fs';
import path from 'node:path';
import {preparePhotographicFacades,retiresPhotoSurface} from './photo-facades.mjs';

/** Replaces noisy ground with surveyed terrain and substitutes explicit photo-textured
 * reconstructions only where their survey footprint is known. */
export function attachSurveySurface(service, directory, {voxelizeArea,collectRegionTiles,mcPositions,sampleColor}={}) {
  const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
  const ground=manifest.tiles.filter(t=>t.kind==='ground'||t.kind==='reconstruction'||t.kind==='vegetation');
  const collisionGround=[...ground,...(manifest.photoFacades?.collisionTiles??[])];
  const photoCollisionGrid=new Map(),photoCollisionCache=new Map();
  for(const r of manifest.photoFacades?.collisionRetirement??[]){
    const bounds=[Math.min(...r.ring.map(p=>p[0])),Math.min(...r.ring.map(p=>p[1])),Math.max(...r.ring.map(p=>p[0])),Math.max(...r.ring.map(p=>p[1]))];
    for(let x=Math.floor(bounds[0]/20);x<=Math.floor(bounds[2]/20);x++)for(let z=Math.floor(bounds[1]/20);z<=Math.floor(bounds[3]/20);z++){
      const key=x+','+z;if(!photoCollisionGrid.has(key))photoCollisionGrid.set(key,[]);photoCollisionGrid.get(key).push(r);
    }
  }
  function photoCollisionAt(x,y,z){
    const key=(Math.floor(x)+2048)*4096+Math.floor(z)+2048;let intervals=photoCollisionCache.get(key);
    if(!intervals){intervals=(photoCollisionGrid.get(Math.floor(x/20)+','+Math.floor(z/20))??[]).filter(r=>inside(x,z,r.ring)&&!r.holes.some(h=>inside(x,z,h))).map(r=>[r.y0,r.y1]);photoCollisionCache.set(key,intervals);}
    return intervals.some(([a,b])=>y>=a&&y<=b);
  }
  const matches=frame=>Math.abs(frame.lat-manifest.origin[0])<1e-7 && Math.abs(frame.lon-manifest.origin[1])<1e-7;
  const ids=new Map(ground.map((t,i)=>[t.runtimeId??1_000_000_000+i,t]));
  const replacements=(manifest.replacements??[]).map(p=>({...p,bounds:[Math.min(...p.ring.map(v=>v[0])),Math.min(...p.ring.map(v=>v[1])),Math.max(...p.ring.map(v=>v[0])),Math.max(...p.ring.map(v=>v[1]))]}));
  function inside(x,z,ring){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
  const replacementGrid=new Map();
  for(const r of replacements)for(let x=Math.floor(r.bounds[0]/20);x<=Math.floor(r.bounds[2]/20);x++)for(let z=Math.floor(r.bounds[1]/20);z<=Math.floor(r.bounds[3]/20);z++){const key=x+','+z;if(!replacementGrid.has(key))replacementGrid.set(key,[]);replacementGrid.get(key).push(r);}
  const alwaysIds=new Map([...ids].filter(([,t])=>t.alwaysVisible));
  function alwaysReplaced(x,y,z){
    return (replacementGrid.get(Math.floor(x/20)+','+Math.floor(z/20))??[]).some(r=>r.alwaysVisible&&y>=r.y0&&y<=r.y1&&inside(x,z,r.ring)&&!(r.holes??[]).some(h=>inside(x,z,h)));
  }
  const replacementCache=new Map();
  function replaced(p){
    const ix=Math.floor(p[0]),iz=Math.floor(p[2]),key=(ix+2048)*4096+iz+2048;
    let intervals=replacementCache.get(key);
    if(intervals===undefined){
      const x=ix+.5,z=iz+.5;
      intervals=(replacementGrid.get(Math.floor(x/20)+','+Math.floor(z/20))??[]).filter(r=>r.kind!=='architecture-band'&&x>=r.bounds[0]&&z>=r.bounds[1]&&x<=r.bounds[2]&&z<=r.bounds[3]&&(r.kind!=='architecture-fringe'||!protectedAt(x,z))&&inside(x,z,r.ring)&&!(r.holes??[]).some(h=>inside(x,z,h))).map(r=>[r.y0,r.y1]);
      replacementCache.set(key,intervals);
    }
    return intervals.some(([min,max])=>p[1]>=min&&p[1]<=max);
  }
  function containedBand(points){
    const x=(points[0][0]+points[1][0]+points[2][0])/3,z=(points[0][2]+points[1][2]+points[2][2])/3;
    // Bands are convex rectangles with no holes. An intersecting vertex is
    // insufficient: removing that triangle could erase an unsupported wall
    // extending below a roof-only reconstruction.
    return (replacementGrid.get(Math.floor(x/20)+','+Math.floor(z/20))??[]).some(r=>r.kind==='architecture-band'&&!(r.holes??[]).length&&points.every(([x,y,z])=>y>=r.y0&&y<=r.y1&&inside(x,z,r.ring)));
  }
  const guide=manifest.terrainGuide,{width,height,points}=guide;
  const a=points[0],u=points[1],v=points[width];
  const ux=u[0]-a[0],uz=u[2]-a[2],vx=v[0]-a[0],vz=v[2]-a[2],det=ux*vz-uz*vx;
  const protectedPixels=manifest.protectionGrid?Buffer.from(manifest.protectionGrid.data,'base64'):null;
  function protectedAt(x,z){
    if(!protectedPixels)return false;
    const dx=x-a[0],dz=z-a[2],s=(dx*vz-dz*vx)/det,t=(ux*dz-uz*dx)/det;
    const fx=Math.hypot(ux,uz)/manifest.protectionGrid.metresPerPixel,fz=Math.hypot(vx,vz)/manifest.protectionGrid.metresPerPixel,i=Math.floor(s*fx),j=manifest.protectionGrid.height-1-Math.floor(t*fz);
    return i>=0&&j>=0&&i<manifest.protectionGrid.width&&j<manifest.protectionGrid.height&&protectedPixels[j*manifest.protectionGrid.width+i]!==0;
  }
  // Precise bounded floors/treads cannot be represented by the coarse 2m DEM
  // guide. Earlier entries (stair treads) take precedence over the court floor.
  const terrainOverrideGrid=new Map();
  for(const r of manifest.terrainOverrides??[]){
    const xs=r.ring.map(p=>p[0]),zs=r.ring.map(p=>p[1]);
    for(let x=Math.floor(Math.min(...xs)/16);x<=Math.floor(Math.max(...xs)/16);x++)for(let z=Math.floor(Math.min(...zs)/16);z<=Math.floor(Math.max(...zs)/16);z++){
      const key=x+','+z;if(!terrainOverrideGrid.has(key))terrainOverrideGrid.set(key,[]);terrainOverrideGrid.get(key).push(r);
    }
  }
  function terrain(x,z){
    const override=(terrainOverrideGrid.get(Math.floor(x/16)+','+Math.floor(z/16))??[]).find(r=>inside(x,z,r.ring));
    if(override)return override.height;
    const dx=x-a[0],dz=z-a[2],s=(dx*vz-dz*vx)/det,t=(ux*dz-uz*dx)/det;
    if(s<.2||t<.2||s>width-1.2||t>height-1.2)return null;
    const i=Math.floor(s),j=Math.floor(t),fx=s-i,fz=t-j;
    return (points[j*width+i][1]*(1-fx)+points[j*width+i+1][1]*fx)*(1-fz)+(points[(j+1)*width+i][1]*(1-fx)+points[(j+1)*width+i+1][1]*fx)*fz;
  }
  function surface(x,z){
    const top=manifest.surfaceGuide;if(!top)return null;
    const dx=x-a[0],dz=z-a[2],s=(dx*vz-dz*vx)/det,t=(ux*dz-uz*dx)/det;
    if(s<.2||t<.2||s>width-1.2||t>height-1.2)return null;
    const i=Math.floor(s),j=Math.floor(t),fx=s-i,fz=t-j,p=top.heights;
    return (p[j*width+i]*(1-fx)+p[j*width+i+1]*fx)*(1-fz)+(p[(j+1)*width+i]*(1-fx)+p[(j+1)*width+i+1]*fx)*fz;
  }
  const overhang=manifest.vegetationOverhang,overhangMask=overhang?Buffer.from(overhang.mask,'base64'):null;
  function oldCanopy(x,y,z){
    if(!overhangMask)return false;
    const dx=x-a[0],dz=z-a[2],s=(dx*vz-dz*vx)/det,t=(ux*dz-uz*dx)/det,i=Math.floor(s),j=Math.floor(t);
    if(i<0||j<0||i>=width-1||j>=height-1)return false;
    const p=j*width+i,q=p+width,c=overhang.roofCeilings;
    return Boolean(overhangMask[p]|overhangMask[p+1]|overhangMask[q]|overhangMask[q+1])&&y>Math.max(c[p],c[p+1],c[q],c[q+1])+.5;
  }
  let removed=0;
  function correct(bytes,shift=0,photo=null,alwaysOnly=false){
    const input=Buffer.isBuffer(bytes)?bytes:Buffer.from(bytes);if(input.toString('ascii',0,4)!=='ECT1')throw Error('Unsupported terrain format');
    const count=input.readInt32LE(4),ax=input.readDoubleLE(8),ay=input.readDoubleLE(16),az=input.readDoubleLE(24);
    const output=Buffer.allocUnsafe(input.length);input.copy(output,0,0,32);let read=32,write=32;
    for(let part=0;part<count;part++){
      const vertices=input.readInt32LE(read),w=input.readInt32LE(read+4),h=input.readInt32LE(read+8),header=write;
      input.copy(output,write,read,read+16);read+=16;write+=16;let kept=0;
      for(let t=0;t<vertices;t+=3){
        const at=read+t*20;
        const x1=input.readFloatLE(at)+ax,y1=input.readFloatLE(at+4)+ay,z1=input.readFloatLE(at+8)+az;
        const x2=input.readFloatLE(at+20)+ax,y2=input.readFloatLE(at+24)+ay,z2=input.readFloatLE(at+28)+az;
        const x3=input.readFloatLE(at+40)+ax,y3=input.readFloatLE(at+44)+ay,z3=input.readFloatLE(at+48)+az;
        const x=(x1+x2+x3)/3,y=(y1+y2+y3)/3,z=(z1+z2+z3)/3,floor=terrain(x,z);
        let retire=alwaysOnly&&alwaysReplaced(x,y-shift,z);
        if(!alwaysOnly&&floor!==null){
          // The local outdoor layer is reconstructed from DGM/DOP and canopy
          // data. Retaining scattered pieces of its old photographic counterpart
          // leaves floating branches above paths. Building/roof masks protect
          // original architecture that has not been reconstructed.
          retire=Boolean(protectedPixels)&&!protectedAt(x,z);
          if(!retire)retire=oldCanopy(x,y-shift,z);
          const top=surface(x,z);if(!retire&&top!==null&&y-shift>top+(manifest.surfaceGuide.tolerance??3))retire=true;
          if(!retire&&y-floor-shift<1.5){
            const a=terrain(x1,z1),b=terrain(x2,z2),c=terrain(x3,z3);
            retire=a!==null&&b!==null&&c!==null&&y1-a-shift<1.25&&y2-b-shift<1.25&&y3-c-shift<1.25;
          }
          if(!retire)retire=replaced([x,y-shift,z])||replaced([x1,y1-shift,z1])||replaced([x2,y2-shift,z2])||replaced([x3,y3-shift,z3]);
        }
        if(!alwaysOnly&&!retire)retire=containedBand([[x1,y1-shift,z1],[x2,y2-shift,z2],[x3,y3-shift,z3]]);
        if(!alwaysOnly&&!retire&&photo)retire=retiresPhotoSurface(photo,x,y-shift,z);
        if(retire){removed++;continue;}
        input.copy(output,write,at,at+60);write+=60;kept+=3;
      }
      output.writeInt32LE(kept,header);read+=vertices*20;
      const textureBytes=w*h*4;input.copy(output,write,read,read+textureBytes);read+=textureBytes;write+=textureBytes;
    }
    return output.subarray(0,write);
  }
  const CLIPPED_OFFSET=1_100_000_000,PHOTO_OFFSET=1_200_000_000,AERIAL_OFFSET=1_300_000_000;
  const photographic=new WeakMap();
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
      let state=photographic.get(frame);
      if(manifest.photoFacades&&collectRegionTiles&&!state){
        state={ready:false,result:null};photographic.set(frame,state);
        state.promise=preparePhotographicFacades(service,directory,frame,manifest.origin,{collectRegionTiles,mcPositions,sampleColor})
          .then(result=>{state.result=result;state.ready=true;})
          .catch(()=>{state.ready=true;console.warn('[campus-photo] preparation unavailable; original retained');});
      }
      if(state&&!state.ready)selected.pending=(selected.pending??0)+1;
      const photo=state?.result,offset=photo?.patches.length?PHOTO_OFFSET:CLIPPED_OFFSET;
      selected.tiles=selected.tiles.map(t=>({...t,id:t.id+offset,parent:t.parent?t.parent+offset:0,chain:t.chain.map(id=>id+offset)}));
      if(photo){selected.tiles.unshift(...photo.tiles);selected.attribution.push(...photo.copyright);}

      for(const [id]of ids)selected.tiles.unshift({id,fine:true,parent:0,chain:[]});
    }else if(alwaysIds.size){
      // Recently built landmarks must not disappear into obsolete aerial tiles.
      // This mode retires only their explicit footprints, not the ground layer.
      selected.tiles=selected.tiles.map(t=>({...t,id:t.id+AERIAL_OFFSET,parent:t.parent?t.parent+AERIAL_OFFSET:0,chain:t.chain.map(id=>id+AERIAL_OFFSET)}));
      for(const [id]of alwaysIds)selected.tiles.unshift({id,fine:true,parent:0,chain:[]});
    }
    selected.attribution.push(manifest.attribution);
    return selected;
  };
  service.renderTile=async(frame,id)=>{
    if(!matches(frame))return tile(frame,id);
    const shift=manifest.origin[2]-frame.h0;
    const photo=photographic.get(frame)?.result;
    if(photo?.bytes.has(id))return photo.bytes.get(id);
    if(ids.has(id)){const b=Buffer.from(await fs.promises.readFile(path.join(directory,ids.get(id).file)));b.writeDoubleLE(b.readDoubleLE(16)+shift,16);return b;}
    if(id<CLIPPED_OFFSET)return tile(frame,id);
    if(id>=AERIAL_OFFSET){const bytes=await tile(frame,id-AERIAL_OFFSET);return bytes?correct(bytes,shift,null,true):bytes;}
    const enhanced=id>=PHOTO_OFFSET,bytes=await tile(frame,id-(enhanced?PHOTO_OFFSET:CLIPPED_OFFSET));return bytes?correct(bytes,shift,enhanced?photo:null):bytes;
  };
  const decodedAssets=new Map();
  function assetMeshes(frame,spec) {
    if(decodedAssets.has(spec.file))return decodedAssets.get(spec.file);
    const bytes=fs.readFileSync(path.join(directory,spec.file)),count=bytes.readInt32LE(4),anchor=[8,16,24].map(i=>bytes.readDoubleLE(i));
    const primitives=[];let offset=32;const shift=manifest.origin[2]-frame.h0;
    for(let part=0;part<count;part++){
      const n=bytes.readInt32LE(offset),w=bytes.readInt32LE(offset+4),h=bytes.readInt32LE(offset+8);offset+=16;
      if((spec.kind==='vegetation'&&part>0)||(spec.collisionParts&&!spec.collisionParts.includes(part))){offset+=n*20+w*h*4;continue;}
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
      const assets=collisionGround.filter(t=>t.bounds[0][0]<=x0+17&&t.bounds[1][0]>=x0-1&&t.bounds[0][2]<=z0+17&&t.bounds[1][2]>=z0-1);
      if(!assets.length)return output;
      const {vox}=voxelizeArea(frame,assets.map(t=>assetMeshes(frame,t)),x0,z0,16,minY,span,{fallbackGround:63,water:[]});
      for(let z=0;z<16;z++)for(let x=0;x<16;x++){
        const px=x0+x+.5,pz=z0+z+.5,base=terrain(px,pz),top=surface(px,pz);if(base===null)continue;
        const level=base+shift;
        for(let y=0;y<span;y++){
          const wy=y+minY;if(wy<level-4)continue;
          if(protectedAt(px,pz)&&wy>level+1.25&&!replaced([px,wy+.5-shift,pz])&&!photoCollisionAt(px,wy+.5-shift,pz)&&!oldCanopy(px,wy+.5-shift,pz)&&!(top!==null&&wy>top+shift+(manifest.surfaceGuide.tolerance??3)))continue;
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
      const output=Uint8Array.from(original);
      if(matches(frame))for(let z=0;z<16;z++)for(let x=0;x<16;x++){
        if(terrain(cx*16+x+.5,cz*16+z+.5)===null)continue;
        // Source voxelization uses visible vanilla filler under its mesh. At
        // steep survey banks or protected footprint margins that filler can
        // protrude through the replacement terrain. Normalize newly generated
        // filler to invisible, mineable map material. Existing saves and player
        // blocks still use the conservative migration path above.
        for(let y=0;y<span;y++){
          const i=(y*16+z)*16+x;
          if(output[i]===20)output[i]=3;
          else if(output[i]===21)output[i]=4;
        }
      }
      for(let i=0;i<output.length;i++)if(patch[i]!==255)output[i]=patch[i];return output;
    };
  }
  return {manifest,renderTiles:ids.size,stats:()=>({removedSourceTriangles:removed})};
}

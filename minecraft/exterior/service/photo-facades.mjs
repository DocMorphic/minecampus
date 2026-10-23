// Public survey geometry + transient provider material. No provider pixels are
// persisted or bundled: the existing authenticated tile client supplies them.
import fs from 'node:fs';
import path from 'node:path';

function inside(x,y,ring){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}

/** Orthographic texture reprojection onto one measured wall. Closest source
 * surface wins along the wall normal, rather than foreground trees winning a
 * conventional front-to-back depth test. Gaps are explicit in coverage metrics. */
export function bakeWall(wall,primitives,{pixelsPerMetre=10,maxProjectionDistance=6,sampleColor}){
 const [[left,bottom],[right,top]]=wall.bounds;
 const w=Math.max(1,Math.min(2048,Math.ceil((right-left)*pixelsPerMetre))),h=Math.max(1,Math.min(1024,Math.ceil((top-bottom)*pixelsPerMetre)));
 const sx=w/(right-left),sy=h/(top-bottom),data=Buffer.alloc(w*h*4),depth=new Float32Array(w*h).fill(Infinity),mask=new Uint8Array(w*h);
 const [a,d,n]=[wall.anchor,wall.direction,wall.normal];let wanted=0;
 // LoD2 foundations may sit several metres below the surrounding terrain.
 // Exclude only the measured buried area from coverage, without relaxing the
 // observed-material requirement for the wall visible above ground.
 const floors=new Float64Array(w).fill(-Infinity),profile=wall.groundProfile;
 if(profile?.length>=2){
  let segment=0;
  for(let x=0;x<w;x++){
   const X=left+(x+.5)/sx;
   while(segment<profile.length-2&&profile[segment+1][0]<X)segment++;
   const [p,q]=[profile[segment],profile[segment+1]],fraction=Math.max(0,Math.min(1,(X-p[0])/(q[0]-p[0])));
   floors[x]=p[1]*(1-fraction)+q[1]*fraction-.15;
  }
 }
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const X=left+(x+.5)/sx,Y=top-(y+.5)/sy;
  if(Y>=floors[x]&&inside(X,Y,wall.rings[0])&&!wall.rings.slice(1).some(r=>inside(X,Y,r))){mask[y*w+x]=1;wanted++;}
 }
 const targetMin=[Infinity,Infinity,Infinity],targetMax=[-Infinity,-Infinity,-Infinity];
 for(const p of wall.vertices)for(let k=0;k<3;k++){targetMin[k]=Math.min(targetMin[k],p[k]-maxProjectionDistance);targetMax[k]=Math.max(targetMax[k],p[k]+maxProjectionDistance);}
 const color=[0,0,0];
 for(const prim of primitives){
  if(prim.bounds&&prim.bounds[0].some((v,k)=>v>targetMax[k]||prim.bounds[1][k]<targetMin[k]))continue;
  const v=prim.mc,uv=prim.uvs,idx=prim.indices;
  for(let t=0;t<idx.length;t+=3){
   const ia=idx[t],ib=idx[t+1],ic=idx[t+2];
   const x0=v[ia*3]-a[0],z0=v[ia*3+2]-a[2],x1=v[ib*3]-a[0],z1=v[ib*3+2]-a[2],x2=v[ic*3]-a[0],z2=v[ic*3+2]-a[2];
   const A=[x0*d[0]+z0*d[2],v[ia*3+1],x0*n[0]+z0*n[2]],B=[x1*d[0]+z1*d[2],v[ib*3+1],x1*n[0]+z1*n[2]],C=[x2*d[0]+z2*d[2],v[ic*3+1],x2*n[0]+z2*n[2]];
   if(Math.min(A[2],B[2],C[2])>maxProjectionDistance||Math.max(A[2],B[2],C[2]) < -maxProjectionDistance)continue;
   const den=(B[1]-C[1])*(A[0]-C[0])+(C[0]-B[0])*(A[1]-C[1]);if(Math.abs(den)<.002)continue;
   const lx=Math.max(0,Math.floor((Math.min(A[0],B[0],C[0])-left)*sx)),rx=Math.min(w-1,Math.ceil((Math.max(A[0],B[0],C[0])-left)*sx));
   const ly=Math.max(0,Math.floor((top-Math.max(A[1],B[1],C[1]))*sy)),ry=Math.min(h-1,Math.ceil((top-Math.min(A[1],B[1],C[1]))*sy));
   for(let y=ly;y<=ry;y++)for(let x=lx;x<=rx;x++){
    const at=y*w+x;if(!mask[at])continue;
    const X=left+(x+.5)/sx,Y=top-(y+.5)/sy;
    const b0=((B[1]-C[1])*(X-C[0])+(C[0]-B[0])*(Y-C[1]))/den,b1=((C[1]-A[1])*(X-C[0])+(A[0]-C[0])*(Y-C[1]))/den,b2=1-b0-b1;
    if(b0<0||b1<0||b2<0)continue;
    const dist=Math.abs(b0*A[2]+b1*B[2]+b2*C[2]);if(dist>maxProjectionDistance||dist>=depth[at])continue;
    sampleColor(prim,b0*uv[ia*2]+b1*uv[ib*2]+b2*uv[ic*2],b0*uv[ia*2+1]+b1*uv[ib*2+1]+b2*uv[ic*2+1],color);
    data[at*4]=color[0];data[at*4+1]=color[1];data[at*4+2]=color[2];data[at*4+3]=255;depth[at]=dist;
   }
  }
 }
 // Multi-source flood fill handles scan gaps, without synthesizing window rows.
 // Coverage is measured before filling, so missing photography cannot pass as
 // observed detail. Unsupported faces remain on their original source mesh.
 const queue=new Int32Array(w*h),distance=new Uint16Array(w*h).fill(65535);let head=0,tail=0,observed=0,maxFillDistance=0;
 for(let i=0;i<w*h;i++)if(mask[i]&&Number.isFinite(depth[i])){queue[tail++]=i;distance[i]=0;observed++;}
 while(head<tail){const i=queue[head++],x=i%w;for(const j of [x>0?i-1:-1,x<w-1?i+1:-1,i-w,i+w]){
  if(j<0||j>=mask.length||!mask[j]||distance[j]!==65535)continue;
  distance[j]=distance[i]+1;maxFillDistance=Math.max(maxFillDistance,distance[j]/Math.min(sx,sy));data.copy(data,j*4,i*4,i*4+4);queue[tail++]=j;
 }}
 return {width:w,height:h,data,wanted,observed,coverage:wanted?observed/wanted:0,maxFillDistance,unfilled:wanted-tail};
}

export function acceptsFacade(bakes,minimumCoverage=.8){
 const wanted=bakes.reduce((n,b)=>n+b.wanted,0),observed=bakes.reduce((n,b)=>n+b.observed,0);
 return wanted>0&&observed/wanted>=minimumCoverage&&bakes.every(b=>b.unfilled===0&&b.coverage>=.2&&b.maxFillDistance<=4);
}

function encode(plan,bakes,roof,shift){
 const parts=plan.walls.map((wall,i)=>{
  const b=bakes[i],[[l,bottom],[r,top]]=wall.bounds,vertices=Buffer.alloc(wall.indices.length*20);
  for(let j=0;j<wall.indices.length;j++){
   const p=wall.vertices[wall.indices[j]],s=(p[0]-wall.anchor[0])*wall.direction[0]+(p[2]-wall.anchor[2])*wall.direction[2];
   for(const [k,v]of [p[0],p[1]+shift,p[2],(s-l)/(r-l),(top-p[1])/(top-bottom)].entries())vertices.writeFloatLE(v,j*20+k*4);
  }
  const header=Buffer.alloc(16);header.writeInt32LE(wall.indices.length,0);header.writeInt32LE(b.width,4);header.writeInt32LE(b.height,8);header.fill(255,12,16);
  return Buffer.concat([header,vertices,b.data]);
 });
 // Public orthophoto roof primitives have zero anchors. Translate their vertices
 // to the save's vertical datum exactly as for the reprojected walls.
 if(roof.toString('ascii',0,4)!=='ECT1'||[8,16,24].some(i=>roof.readDoubleLE(i)!==0))throw Error('Unsupported survey roof encoding');
 const raw=Buffer.from(roof.subarray(32));let at=0;
 for(let i=0;i<roof.readInt32LE(4);i++){
  const count=raw.readInt32LE(at),w=raw.readInt32LE(at+4),h=raw.readInt32LE(at+8);at+=16;
  for(let j=0;j<count;j++)raw.writeFloatLE(raw.readFloatLE(at+j*20+4)+shift,at+j*20+4);
  at+=count*20+w*h*4;
 }
 const header=Buffer.alloc(32);header.write('ECT1');header.writeInt32LE(parts.length+roof.readInt32LE(4),4);
 return Buffer.concat([header,...parts,raw]);
}

export async function preparePhotographicFacades(service,directory,frame,origin,deps){
 const spec=JSON.parse(await fs.promises.readFile(path.join(directory,'photo-facades.json'),'utf8'));
 const shift=origin[2]-frame.h0,tiles=[],bytes=new Map(),patches=[],copyright=new Set(),metrics=[];
 for(const plan of spec.plans){
  try{
   const min=plan.bounds[0].map((v,k)=>v-8+(k===1?shift:0)),max=plan.bounds[1].map((v,k)=>v+8+(k===1?shift:0));
   const nodes=await deps.collectRegionTiles(service.client,frame,min,max,1),meshes=await service.meshesFor(nodes);
   const primitives=[];
   for(const mesh of meshes){
    for(const credit of (mesh.copyright??'').split(';'))if(credit.trim())copyright.add(credit.trim());
    for(const p of mesh.primitives){
     const mc=Float64Array.from(deps.mcPositions(frame,p)),lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
     for(let i=0;i<mc.length;i+=3){mc[i+1]-=shift;for(let k=0;k<3;k++){lo[k]=Math.min(lo[k],mc[i+k]);hi[k]=Math.max(hi[k],mc[i+k]);}}
     primitives.push({...p,mc,bounds:[lo,hi]});
    }
   }
   const bakes=[];
   for(const wall of plan.walls){bakes.push(bakeWall(wall,primitives,{...spec,sampleColor:deps.sampleColor}));await new Promise(setImmediate);}
   const wanted=bakes.reduce((n,b)=>n+b.wanted,0),observed=bakes.reduce((n,b)=>n+b.observed,0);
   const usable=bakes.map((b,i)=>!plan.walls[i].reconstructed&&acceptsFacade([b],spec.minimumCoverage??.8)&&b.maxFillDistance<=2);
   // Each accepted wall is independently backed by observed photography. Do not
   // discard a well-supported face because another side of the building is
   // occluded; that other side stays on the original source mesh. The public
   // surveyed roof does not depend on photographic wall coverage.
   const accepted=usable.some(Boolean)||plan.walls.some(w=>w.reconstructed);
   metrics.push({id:plan.id,accepted,acceptedWalls:usable.filter(Boolean).length,reconstructedWalls:plan.walls.filter(w=>w.reconstructed).length,totalWalls:bakes.length,coverage:observed/wanted,walls:bakes.map(b=>({coverage:b.coverage,maxFillDistance:b.maxFillDistance,unfilled:b.unfilled}))});
   console.log(`[campus-photo] ${plan.id}: ${accepted?'ready':'original retained'}, coverage=${(100*observed/wanted).toFixed(1)}%`);
   if(!accepted)continue;
   bytes.set(plan.runtimeId,encode({...plan,walls:plan.walls.filter((w,i)=>usable[i])},bakes.filter((b,i)=>usable[i]),await fs.promises.readFile(path.join(directory,plan.roofFile)),shift));
   tiles.push({id:plan.runtimeId,fine:true,parent:0,chain:[]});
   patches.push({...plan,walls:plan.walls.map((w,i)=>({...w,accepted:usable[i]||Boolean(w.reconstructed)})),roofCache:new Map()});
  }catch(error){console.warn(`[campus-photo] ${plan.id}: source unavailable; original retained`);metrics.push({id:plan.id,accepted:false,reason:'source unavailable'});}
 }
 const grid=new Map();
 for(const patch of patches)for(let x=Math.floor((patch.bounds[0][0]-6)/20);x<=Math.floor((patch.bounds[1][0]+6)/20);x++)for(let z=Math.floor((patch.bounds[0][2]-6)/20);z<=Math.floor((patch.bounds[1][2]+6)/20);z++){
  const key=x+','+z;if(!grid.has(key))grid.set(key,[]);grid.get(key).push(patch);
 }
 return {tiles,bytes,patches,grid,copyright:[...copyright],metrics};
}


/** Keep unsupported courtyard faces. Retire only source surfaces assigned to an
 * accepted survey wall, plus the narrow layer occupied by a measured roof. */
export function retiresPhotoSurface(photo,x,y,z){
 for(const patch of photo.grid?(photo.grid.get(Math.floor(x/20)+','+Math.floor(z/20))??[]):(photo.patches??[])){
  const [lo,hi]=patch.bounds;
  if(x<lo[0]-6||x>hi[0]+6||z<lo[2]-6||z>hi[2]+6||y<lo[1]-2||y>hi[1]+3)continue;
  // Roof ownership uses the exact surveyed triangles rather than a building
  // bounding rectangle: courtyards and roof-height changes remain open.
  const key=Math.floor(x*2)+','+Math.floor(z*2);
  let height=patch.roofCache.get(key);
  if(height===undefined){
   const px=(Math.floor(x*2)+.5)/2,pz=(Math.floor(z*2)+.5)/2;height=null;
   for(const [a,b,c]of patch.roofTriangles??[]){
    const den=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2]);if(Math.abs(den)<1e-8)continue;
    const u=((b[2]-c[2])*(px-c[0])+(c[0]-b[0])*(pz-c[2]))/den,v=((c[2]-a[2])*(px-c[0])+(a[0]-c[0])*(pz-c[2]))/den,w=1-u-v;
    if(u>=0&&v>=0&&w>=0)height=Math.max(height??-Infinity,u*a[1]+v*b[1]+w*c[1]);
   }
   patch.roofCache.set(key,height);
  }
  if(height!==null&&Math.abs(y-height)<1.75)return true;
  let nearest=Infinity,owner=null;
  for(const wall of patch.walls){
   const dx=x-wall.anchor[0],dz=z-wall.anchor[2],s=dx*wall.direction[0]+dz*wall.direction[2];
   const [[l,b],[r,t]]=wall.bounds;
   // Distance to the finite wall segment includes its corners. A perpendicular
   // band alone leaves detached scan triangles just beyond both wall endpoints.
   const distance=Math.hypot(dx*wall.normal[0]+dz*wall.normal[2],Math.max(l-s,0,s-r));
   if(distance<nearest&&distance<6&&y>=b-.5&&y<=t+.5){nearest=distance;owner=wall;}
  }
  if(owner?.accepted)return true;
 }
 return false;
}

// Horizontal proxy bounds for reconstructed wood only. Geometry is already in
// Minecraft metres; foliage and inferred ground must never enter this path.
// Native sparse collision packets use 136 ordered endpoint pairs per axis.
const intervals=[];
for(let lo=0;lo<16;lo++)for(let hi=lo+1;hi<=16;hi++)intervals.push([lo,hi]);
const intervalIndex=new Map(intervals.map((v,i)=>[v.join(','),i]));
export const WOOD_PROFILE_COUNT=136*136;
export function woodProfileBounds(profile){
  if(!Number.isInteger(profile)||profile<0||profile>=WOOD_PROFILE_COUNT)throw new RangeError('Invalid wood profile');
  const [x0,x1]=intervals[Math.floor(profile/136)],[z0,z1]=intervals[profile%136];
  return [x0/16,z0/16,x1/16,z1/16];
}
function quantize(lo,hi){
  // Round to nearest sixteenth. Sub-grid slivers retain at least one
  // sixteenth of collision width instead of silently disappearing.
  let a=Math.max(0,Math.min(16,Math.round(lo*16))),b=Math.max(0,Math.min(16,Math.round(hi*16)));
  if(a===b){if(a===16)a--;else b++;}
  return intervalIndex.get(a+','+b);
}
function clip(poly,axis,value,keepAbove){
  const out=[];
  for(let i=0;i<poly.length;i++){
    const a=poly[i],b=poly[(i+1)%poly.length],da=(a[axis]-value)*(keepAbove?1:-1),db=(b[axis]-value)*(keepAbove?1:-1);
    if(da>=0)out.push(a);
    if((da<0)!==(db<0)){
      const t=da/(da-db);out.push(a.map((v,k)=>v+(b[k]-v)*t));
    }
  }
  return out;
}
/** Sparse cell -> profile map. No material classification, terrain filling or
 * block mutation occurs here. Each triangle is clipped to the actual cell,
 * avoiding the source voxelizer's half-height terrain convention. */
export function woodShapes(triangles,{x0,z0,width=16,minY,height}){
  if(![x0,z0,width,minY,height].every(Number.isInteger)||width<1||height<1)throw new RangeError('Invalid wood grid');
  const bounds=new Map();
  for(const tri of triangles){
    if(tri.length!==3||tri.some(p=>p.length!==3||p.some(v=>!Number.isFinite(v))))throw new TypeError('Invalid wood triangle');
    const lo=[0,1,2].map(k=>Math.min(...tri.map(p=>p[k]))),hi=[0,1,2].map(k=>Math.max(...tri.map(p=>p[k])));
    for(let y=Math.max(minY,Math.floor(lo[1]));y<=Math.min(minY+height-1,Math.floor(hi[1]));y++)
    for(let z=Math.max(z0,Math.floor(lo[2]));z<=Math.min(z0+width-1,Math.floor(hi[2]));z++)
    for(let x=Math.max(x0,Math.floor(lo[0]));x<=Math.min(x0+width-1,Math.floor(hi[0]));x++){
      let poly=tri;
      for(const [axis,lower]of [[0,x],[1,y],[2,z]]){poly=clip(poly,axis,lower,true);poly=clip(poly,axis,lower+1,false);if(!poly.length)break;}
      if(poly.length<3)continue;
      // A triangle merely touching a cell corner or edge has no occupied area.
      const a=poly[0];let area=0;
      for(let i=1;i+1<poly.length;i++){
        const u=poly[i].map((v,k)=>v-a[k]),v=poly[i+1].map((v,k)=>v-a[k]);
        area+=Math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);
      }
      if(area<1e-10)continue;
      const xmin=Math.min(...poly.map(p=>p[0]))-x,xmax=Math.max(...poly.map(p=>p[0]))-x,zmin=Math.min(...poly.map(p=>p[2]))-z,zmax=Math.max(...poly.map(p=>p[2]))-z;
      const key=((y-minY)*width+z-z0)*width+x-x0,old=bounds.get(key);
      bounds.set(key,old?[Math.min(old[0],xmin),Math.min(old[1],zmin),Math.max(old[2],xmax),Math.max(old[3],zmax)]:[xmin,zmin,xmax,zmax]);
    }
  }
  return new Map([...bounds].map(([i,[x0,z0,x1,z1]])=>[i,quantize(x0,x1)*136+quantize(z0,z1)]));
}

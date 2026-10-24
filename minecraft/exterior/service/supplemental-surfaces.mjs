  function inside(x, z, ring) {
    let yes = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const a = ring[i], b = ring[j];
      if ((a[1] > z) !== (b[1] > z) && x < (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]) + a[0]) yes = !yes;
    }
    return yes;
  }
  const contains = (rings, x, z) => rings.some(p => inside(x, z, p.ring) && !(p.holes ?? []).some(h => inside(x, z, h)));

/** Exact triangle complement of bounded polygon prisms; keeps source attributes. */
export function surfaceBoundaryClipper(entries = []) {
  const indexed=entries.map(e=>{const p=e.rings.flatMap(p=>p.ring);return {...e,bounds:[Math.min(...p.map(v=>v[0])),Math.min(...p.map(v=>v[1])),Math.max(...p.map(v=>v[0])),Math.max(...p.map(v=>v[1]))]};});
  const boundaries=indexed.flatMap(entry=>entry.rings.flatMap(p=>[p.ring,...(p.holes??[])]).flatMap(r=>r.map((a,i)=>{
    const b=r[(i+1)%r.length];return {a,b,entry,minX:Math.min(a[0],b[0]),maxX:Math.max(a[0],b[0]),minZ:Math.min(a[1],b[1]),maxZ:Math.max(a[1],b[1])};
  }))).filter(e=>Math.hypot(e.b[0]-e.a[0],e.b[1]-e.a[1])>1e-8);
  function split(poly,{a,b}){
    // Only a boundary segment touching this piece can separate covered and
    // uncovered ground. Its infinite supporting line elsewhere cannot. Keeping
    // those unrelated cuts created quadratic fragment growth on curved rings.
    const xs=poly.map(p=>p[0]),zs=poly.map(p=>p[2]);
    if(Math.max(...xs)<Math.min(a[0],b[0])-1e-8||Math.min(...xs)>Math.max(a[0],b[0])+1e-8
      ||Math.max(...zs)<Math.min(a[1],b[1])-1e-8||Math.min(...zs)>Math.max(a[1],b[1])+1e-8)return [poly];
    const length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    const distance=p=>((b[0]-a[0])*(p[2]-a[1])-(b[1]-a[1])*(p[0]-a[0]))/length;
    const values=poly.map(distance);
    if(Math.min(...values)>=-1e-8||Math.max(...values)<=1e-8)return [poly];
    // Clip the finite boundary segment to this convex piece. Bounding boxes
    // alone still admit many distant tangent lines around curved footprints.
    const winding=Math.sign(poly.reduce((s,p,i)=>{const q=poly[(i+1)%poly.length];return s+p[0]*q[2]-q[0]*p[2];},0));
    let enter=0,leave=1;
    if(winding)for(let i=0;i<poly.length;i++){
      const p=poly[i],q=poly[(i+1)%poly.length],dx=q[0]-p[0],dz=q[2]-p[2],scale=Math.hypot(dx,dz);
      if(scale<1e-12)continue;
      const da=winding*(dx*(a[1]-p[2])-dz*(a[0]-p[0]))/scale;
      const db=winding*(dx*(b[1]-p[2])-dz*(b[0]-p[0]))/scale;
      if(da< -1e-8&&db< -1e-8)return [poly];
      if(da<0&&db>=0)enter=Math.max(enter,da/(da-db));
      else if(db<0&&da>=0)leave=Math.min(leave,da/(da-db));
      if(enter>leave+1e-10)return [poly];
    }
    const sides=[[],[]];
    for(let i=0;i<poly.length;i++){
      const p=poly[i],q=poly[(i+1)%poly.length],d=values[i],next=values[(i+1)%poly.length];
      if(d>=-1e-8)sides[0].push(p);if(d<=1e-8)sides[1].push(p);
      if((d>1e-8&&next< -1e-8)||(d< -1e-8&&next>1e-8)){
        const t=d/(d-next),at=p.map((v,k)=>v+(q[k]-v)*t);sides[0].push(at);sides[1].push(at);
      }
    }
    return sides.filter(p=>p.length>=3);
  }
  return {
    outsideFragments(triangle){
      const xs=triangle.map(p=>p[0]),zs=triangle.map(p=>p[2]);
      const minX=Math.min(...xs),maxX=Math.max(...xs),minZ=Math.min(...zs),maxZ=Math.max(...zs);
      const minY=Math.min(...triangle.map(p=>p[1])),maxY=Math.max(...triangle.map(p=>p[1]));
      const candidates=indexed.filter(e=>e.bounds[0]<=maxX&&e.bounds[2]>=minX&&e.bounds[1]<=maxZ&&e.bounds[3]>=minZ&&(e.y0??-Infinity)<=maxY&&(e.y1??Infinity)>=minY);
      if(!candidates.length)return [triangle];
      const local=new Set(candidates),edges=boundaries.filter(e=>local.has(e.entry)&&e.maxX>=minX&&e.minX<=maxX&&e.maxZ>=minZ&&e.minZ<=maxZ);
      const heights=[...new Set(candidates.flatMap(e=>[e.y0,e.y1]).filter(Number.isFinite))];

      let pieces=[triangle];for(const edge of edges)pieces=pieces.flatMap(p=>split(p,edge));
      // Clip the vertical extent too. Boundary planes preserve every vertex
      // attribute, so sloping source ground/roofs retain their original UVs.
      for(const y of heights){
        const next=[];
        for(const poly of pieces){
          const values=poly.map(p=>p[1]-y);
          if(Math.min(...values)>=-1e-8||Math.max(...values)<=1e-8){next.push(poly);continue;}
          const sides=[[],[]];
          for(let i=0;i<poly.length;i++){
            const a=poly[i],b=poly[(i+1)%poly.length],d=values[i],e=values[(i+1)%poly.length];
            if(d>=-1e-8)sides[0].push(a);if(d<=1e-8)sides[1].push(a);
            if((d>1e-8&&e< -1e-8)||(d< -1e-8&&e>1e-8)){const t=d/(d-e),p=a.map((v,k)=>v+(b[k]-v)*t);sides[0].push(p);sides[1].push(p);}
          }
          next.push(...sides.filter(p=>p.length>=3));
        }
        pieces=next;
      }
      const result=[];
      for(const p of pieces){
        const x=p.reduce((s,v)=>s+v[0],0)/p.length,z=p.reduce((s,v)=>s+v[2],0)/p.length;
        const y=p.reduce((s,v)=>s+v[1],0)/p.length;
        if(candidates.some(e=>y>=(e.y0??-Infinity)-1e-8&&y<=(e.y1??Infinity)+1e-8&&contains(e.rings,x,z)))continue;
        for(let i=1;i<p.length-1;i++)result.push([p[0],p[i],p[i+1]]);
      }
      return result;
    },
  };
}

/** Bounded additional survey grids; never changes the original campus grid. */
export function supplementalSurfaces(entries = []) {
  const grids = entries.map(entry => {
    const {width, height, points} = entry.terrainGuide;
    if (width < 2 || height < 2 || points.length !== width * height || points.some(p => p.length !== 3 || p.some(v => !Number.isFinite(v)))) throw Error('Invalid supplemental survey grid');
    const a = points[0], u = points[1], v = points[width];
    const ux = u[0]-a[0], uz = u[2]-a[2], vx = v[0]-a[0], vz = v[2]-a[2], det = ux*vz-uz*vx;
    if (Math.abs(det) < 1e-8) throw Error('Degenerate supplemental survey grid');
    const vertices = entry.rings.flatMap(p => p.ring);
    const bounds = [Math.min(...vertices.map(p => p[0])), Math.min(...vertices.map(p => p[1])), Math.max(...vertices.map(p => p[0])), Math.max(...vertices.map(p => p[1]))];
    const canopyMask = entry.vegetationOverhang ? Buffer.from(entry.vegetationOverhang.mask, 'base64') : null;
    if (entry.surfaceGuide && entry.surfaceGuide.heights.length !== points.length) throw Error('Invalid supplemental surface heights');
    if (canopyMask && (canopyMask.length !== points.length || entry.vegetationOverhang.roofCeilings.length !== points.length)) throw Error('Invalid supplemental canopy grid');
    return {...entry, width, height, points, a, ux, uz, vx, vz, det, bounds, canopyMask};
  });
  const clipper=surfaceBoundaryClipper(entries);
  return {
    outsideFragments: clipper.outsideFragments,
    at(x, z) {
      for (const g of grids) {
        if (x < g.bounds[0] || z < g.bounds[1] || x > g.bounds[2] || z > g.bounds[3]) continue;
        if (!contains(g.rings, x, z)) continue;
        const dx = x-g.a[0], dz = z-g.a[2];
        let s = (dx*g.vz-dz*g.vx)/g.det, t = (g.ux*dz-g.uz*dx)/g.det;
        if (s < -1e-4 || t < -1e-4 || s > g.width-1+1e-4 || t > g.height-1+1e-4) continue;
        s = Math.max(0, Math.min(g.width-1.000001, s));
        t = Math.max(0, Math.min(g.height-1.000001, t));
        const i = Math.floor(s), j = Math.floor(t), fx = s-i, fz = t-j;
        const floor = (g.points[j*g.width+i][1]*(1-fx)+g.points[j*g.width+i+1][1]*fx)*(1-fz)
          +(g.points[(j+1)*g.width+i][1]*(1-fx)+g.points[(j+1)*g.width+i+1][1]*fx)*fz;
        const ids = [j*g.width+i, j*g.width+i+1, (j+1)*g.width+i, (j+1)*g.width+i+1];
        const heights = g.surfaceGuide?.heights;
        const top = heights ? (heights[ids[0]]*(1-fx)+heights[ids[1]]*fx)*(1-fz)+(heights[ids[2]]*(1-fx)+heights[ids[3]]*fx)*fz : null;
        const canopyCeiling = g.canopyMask && ids.some(id => g.canopyMask[id]) ? Math.max(...ids.map(id => g.vegetationOverhang.roofCeilings[id])) : null;
        return {floor, top, canopyCeiling, protected: contains(g.protectedFootprints ?? [], x, z), outdoorReconstructed: Boolean(g.outdoorReconstructed)};
      }
      return null;
    }
  };
}

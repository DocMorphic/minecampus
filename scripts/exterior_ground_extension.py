"""Source-height land extension with exact joins to existing reconstructed ground."""
import math
import struct
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union, nearest_points, split
from shapely.strtree import STRtree
from exterior_physics_i import polygons, roof_texture
from exterior_physics_library import triangles
from exterior_terrain import ElevationSampler



def split_narrow_joins(shape, old_triangles, tree):
    """Carry old mesh height breakpoints across sub-centimetre missing strips.

    Earcut may connect nearly collinear vertices across a one-metre cell. A
    height kink on the opposite edge then becomes a steep folded sliver. Short
    transverse cuts pair both sides of a narrow join at each old breakpoint.
    Cuts terminating inside broad terrain do not split it.
    """
    if shape.is_empty:return []
    cuts={}
    for index in tree.query(shape.buffer(.03)):
        _, tri=old_triangles[int(index)]
        xy=tri[:,[0,2]]
        for i,p in enumerate(xy):
            if shape.distance(Point(*p))>.03:continue
            for j in [(i+1)%3,(i+2)%3]:
                direction=xy[j]-p;length=np.linalg.norm(direction)
                if length<.001:continue
                normal=np.array([-direction[1],direction[0]])/length*.05
                a,b=p-normal,p+normal
                key=tuple(np.round(np.r_[a,b],8));cuts[key]=LineString([a,b])
    pieces=list(polygons(shape))
    for line in cuts.values():
        divided=[]
        for piece in pieces:
            if not line.crosses(piece):divided.append(piece);continue
            divided.extend(polygons(split(piece,line)))
        pieces=divided
    return pieces


def build(ctx, region, prefix, runtime_id, blend_metres=2):
    out,meta,cache,mc,encode=[ctx[k] for k in ('OUT','metadata','CACHE','mc','encode')]
    data=ctx.get('groundSourceDirectory',out);ground=[]
    lat,lon=np.radians(meta['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
    inverse=Transformer.from_crs(4978,25832,always_xy=True)
    def utm(v):return np.column_stack(inverse.transform(*((v-[0,64,0])@basis+origin).T))[:,:2]
    mc_region=unary_union([Polygon(mc(np.column_stack([np.asarray(p.exterior.coords),np.full(len(p.exterior.coords),474)]))[:,[0,2]]) for p in polygons(region)])
    for tile in meta['tiles']:
        if tile['kind']!='ground':continue
        lo,hi=tile['bounds']
        if not mc_region.buffer(blend_metres+1).intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
        raw=(data/tile['file']).read_bytes();count,*anchor=struct.unpack_from('<i3d',raw,4);offset=32
        for _ in range(count):
            n,w,h=struct.unpack_from('<3i',raw,offset);offset+=16
            v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=offset).reshape(-1,5)[:,:3]+anchor;offset+=n*20+w*h*4
            for t in v.reshape(-1,3,3):
                p=Polygon(t[:,[0,2]])
                if p.area>1e-8:ground.append((p,t))
    assert ground
    old=unary_union([p for p,t in ground]);tree=STRtree([p for p,t in ground])
    # Derive subtraction in Minecraft's horizontal frame, matching stored mesh edges.
    def in_mc(region):
        def ring(r):
            a=np.asarray(r.coords);return mc(np.column_stack([a,np.full(len(a),474)]))[:,[0,2]]
        return unary_union([Polygon(ring(p.exterior),[ring(h) for h in p.interiors]) for p in polygons(region)])
    target=in_mc(region);area=target.difference(old);assert area.area>0
    max_seam_error=0;points=[]
    with rasterio.open(cache/'campus-dgm-east.tif') as dem:
        sampler=ElevationSampler([dem])
        def point(x,z):
            nonlocal max_seam_error
            x,z=map(float,np.asarray([x,z],dtype=np.float32));loc=Point(x,z);i=int(tree.nearest(loc));poly,tri=ground[i];near=nearest_points(poly,loc)[0];distance=loc.distance(poly)
            weights=np.linalg.solve(np.vstack([tri[:,0],tri[:,2],np.ones(3)]),[near.x,near.y,1]);prior=float(weights@tri[:,1])
            en=utm(np.array([[x,64,z]]));h=float(mc(np.column_stack([en,sampler.sample(en)]))[0,1]);weight=min(1,distance/blend_metres);weight=weight*weight*(3-2*weight);y=prior*(1-weight)+h*weight
            if distance<.001:max_seam_error=max(max_seam_error,abs(y-prior))
            return [x,y,z]
        lo=np.floor(np.array(area.bounds[:2])/20).astype(int)*20;hi=np.ceil(np.array(area.bounds[2:])/20).astype(int)*20
        tiles=[]
        for z in range(lo[1],hi[1],20):
            for x in range(lo[0],hi[0],20):
                piece=area.intersection(box(x,z,x+20,z+20))
                if piece.area<1e-7:continue
                vertices=[]
                for zz in range(z,z+20):
                    for xx in range(x,x+20):
                        cell=piece.intersection(box(xx,zz,xx+1,zz+1))
                        for patch in split_narrow_joins(cell,ground,tree):
                            for tri in triangles(patch):
                                q=np.array([point(a,b) for a,b in tri])
                                # Float32 is the stored mesh geometry. Collapsed
                                # horizontal triangles cannot represent terrain.
                                normal=np.cross(q[1]-q[0],q[2]-q[0])
                                horizontal=q[:,[0,2]]
                                longest=max(np.linalg.norm(horizontal[1]-horizontal[0]),np.linalg.norm(horizontal[2]-horizontal[1]),np.linalg.norm(horizontal[0]-horizontal[2]))
                                # Less than four float32 coordinate steps across
                                # an edge is numerical residue, not a land patch.
                                precision=float(np.max(np.abs(np.spacing(horizontal.astype(np.float32)))))
                                if abs(normal[1])<max(2e-8,longest*precision*4):continue
                                if normal[1]<0:q=q[::-1]
                                vertices.extend(q.tolist())
                # Boolean differences can leave a tile made entirely of
                # sub-float32 slivers; it has no representable terrain.
                if not vertices:continue
                v=np.asarray(vertices);xy=utm(v);textured,pixels=roof_texture(cache,np.column_stack([xy,np.zeros(len(v)),v]));filename=f'{prefix}-{x}-{z}.ect';(out/filename).write_bytes(encode([(textured,pixels)]))
                tile={'file':filename,'kind':'ground','runtimeId':runtime_id+len(tiles),'bounds':[v.min(0).tolist(),v.max(0).tolist()]};tiles.append(tile);points.extend(v.tolist())
        gl=np.floor(np.array(area.bounds[:2])).astype(int);gh=np.ceil(np.array(area.bounds[2:])).astype(int)
        guide={'width':int(gh[0]-gl[0]+1),'height':int(gh[1]-gl[1]+1),'points':[point(x,z) for z in range(gl[1],gh[1]+1) for x in range(gl[0],gh[0]+1)]}
    rings=lambda region:[{'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]}for p in polygons(region)]
    meta['tiles'].extend(tiles);meta['supplementalSurfaces'].append({'name':prefix,'rings':rings(area),'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':True,'qualification':'BVV DGM1/DOP20 ground; two-metre smooth edge blend to stored neighbouring ground heights. Only missing land is added.'})
    return {'groundTiles':[t['file'] for t in tiles],'rings':rings(area),'areaSquareMetres':area.area,'priorOverlapSquareMetres':area.intersection(old).area,'blendMetres':blend_metres,'maximumSeamErrorMetres':max_seam_error,'sourceRetirementRings':rings(target),'sourceRetirementBoundsY':[min(p[1] for p in points)-2,max(p[1] for p in points)+3]}

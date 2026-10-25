"""Fill only a surveyed building's missing narrow ground guard, using its neighbours."""
import json
import math
import struct
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree
from exterior_physics_i import polygons, roof_texture
from exterior_physics_library import triangles


def build(ctx, footprint, runtime_id, filename):
    root, out, meta, encode = [ctx[k] for k in ('ROOT','OUT','metadata','encode')]
    data = ctx.get('groundSourceDirectory', out)
    search = footprint.buffer(2)
    ground = []
    for tile in meta['tiles']:
        if tile['kind']!='ground':continue
        lo, hi = tile['bounds']
        if not search.intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
        raw=(data/tile['file']).read_bytes();parts=struct.unpack_from('<i',raw,4)[0];anchor=np.array(struct.unpack_from('<3d',raw,8));offset=32
        for _ in range(parts):
            count,w,h=struct.unpack_from('<3i',raw,offset);offset+=16
            v=np.frombuffer(raw,dtype='<f4',count=count*5,offset=offset).reshape(-1,5)[:,:3]+anchor
            offset+=count*20+w*h*4
            for tri in v.reshape(-1,3,3):
                poly=Polygon(tri[:,[0,2]])
                if poly.area>1e-8 and poly.intersects(search):ground.append((poly,tri))
    assert ground, 'A foundation collar requires existing rebuilt neighbouring ground'
    shapes=[p for p,t in ground];tree=STRtree(shapes);existing=unary_union(shapes)
    region=footprint.buffer(.6).difference(existing).difference(footprint.buffer(-.005))
    assert not region.is_empty and region.area<footprint.length*.65
    distances=[]
    def point(x,z,record=False):
        # Evaluate at the coordinates actually stored in ECT float32 vertices.
        # Micrometre rounding can otherwise select the other side of a narrow
        # triangulation tie and introduce an avoidable millimetre height seam.
        x,z=map(float,np.asarray([x,z],dtype=np.float32))
        location=Point(x,z);index=int(tree.nearest(location));poly,tri=ground[index];near=nearest_points(poly,location)[0]
        weights=np.linalg.solve(np.vstack([tri[:,0],tri[:,2],np.ones(3)]),np.array([near.x,near.y,1]))
        if record:distances.append(location.distance(poly))
        return [x,float(weights@tri[:,1]),z]
    vertices=[]
    for poly in polygons(region):
        for xy in triangles(poly):
            v=np.array([point(x,z,True) for x,z in xy])
            if np.cross(v[1]-v[0],v[2]-v[0])[1]<0:v=v[::-1]
            vertices.extend(v.tolist())
    assert max(distances)<.65, 'Do not extrapolate a footing beyond the existing narrow guard'
    v=np.asarray(vertices)
    lat,lon=map(math.radians,meta['origin'][:2])
    origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    basis=np.array([[-math.sin(lon),math.cos(lon),0],[math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)],[math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
    xyz=(v-[0,64,0])@basis+origin
    utm=np.column_stack(Transformer.from_crs(4978,25832,always_xy=True).transform(*xyz.T))
    textured,pixels=roof_texture(ctx['CACHE'],np.column_stack([utm,v]))
    (out/filename).write_bytes(encode([(textured,pixels)]))
    meta['tiles'].append({'file':filename,'kind':'ground','runtimeId':runtime_id,'bounds':[v.min(0).tolist(),v.max(0).tolist()]})
    def rings(region):return [{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(region)]
    lo=np.floor(v[:,[0,2]].min(0));hi=np.ceil(v[:,[0,2]].max(0));width,height=(hi-lo).astype(int)+1
    guide={'width':int(width),'height':int(height),'points':[point(x,z) for z in np.arange(lo[1],hi[1]+1) for x in np.arange(lo[0],hi[0]+1)]}
    surface={'name':'znn-west-foundation-collar','rings':rings(region),'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':False,'qualification':'Sub-0.65m continuation from the nearest already rebuilt ground edge into the old building guard. Height is an estimate; DOP20 appearance retained. No surrounding terrain replaced.'}
    meta['supplementalSurfaces'].append(surface)
    return {'file':filename,'rings':surface['rings'],'areaSquareMetres':region.area,'maximumExtrapolationMetres':max(distances),'overlapPriorGroundSquareMetres':region.intersection(existing).area,'qualification':surface['qualification']}

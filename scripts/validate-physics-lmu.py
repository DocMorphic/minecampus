#!/usr/bin/env python3
"""Independently check the LMU survey envelope, actual facade mesh and DOP roof."""
import argparse
import hashlib
import json
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from scipy.ndimage import label, map_coordinates
from scipy.spatial import cKDTree
from shapely import contains_xy
from shapely.geometry import Point, Polygon, box, shape
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree
from exterior_physics_i import polygons

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=root/'dist-minecraft/exterior')
args = parser.parse_args(); out = args.directory
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
m = read(out/'manifest.json'); rec = m['architecture']['physicsLMU']; src = root/'minecraft/exterior'
spec = read(src/rec['sourceFile']); sources = read(src/'sources.json')
assert sha(src/rec['sourceFile']) == rec['sourceSha256']
assert sha(root/rec['generatorFile']) == rec['generatorSha256']
inputs = {}
for item, name in zip(sources['lod2'], ['campus-east.gml','campus-west.gml']): inputs[name] = item['sha256']
for kind, name in [('dgm1','campus-dgm-east.tif'),('dop20','campus-dop-east.tif')]: inputs[name] = sorted(sources[kind],key=lambda x:x['name'])[1]['sha256']
inputs['de_bkg_gcg2016.tif'] = sources['geoid']['sha256']
for name, digest in inputs.items(): assert sha(root/'.cache'/name) == digest, name
ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'}
surveys = {}
for filename in ['campus-east.gml','campus-west.gml']:
    for building in ET.parse(root/'.cache'/filename).findall('.//b:Building',ns):
        items=[]
        for kind in ['GroundSurface','RoofSurface','WallSurface']:
            for poly in building.findall('.//b:'+kind+'//g:Polygon',ns):
                rings=[np.array(list(map(float,p.text.split()))).reshape(-1,3) for p in poly.findall('.//g:LinearRing/g:posList',ns)]
                if rings: items.append((kind,rings))
        surveys[building.get('{'+ns['g']+'}id')]=items
raw = surveys[spec['building']]
foot = unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for k,p in raw if k=='GroundSurface'])
lat,lon=map(math.radians,m['origin'][:2])
origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]))
basis=np.array([[-math.sin(lon),math.cos(lon),0],[math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)],[math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
ecef=Transformer.from_crs(25832,4978,always_xy=True); geo=Transformer.from_crs(25832,4258,always_xy=True); inverse=Transformer.from_crs(4978,25832,always_xy=True)
def world(p):
    lon,lat=geo.transform(p[:,0],p[:,1])
    with rasterio.open(root/'.cache/de_bkg_gcg2016.tif') as d:
        c,r=(~d.transform)*(lon,lat); h=p[:,2]+map_coordinates(d.read(1).astype(float),[r-.5,c-.5],order=1,prefilter=False)
    return (np.column_stack(ecef.transform(p[:,0],p[:,1],h))-origin)@basis.T+[0,64,0]
def decode(path):
    data=path.read_bytes(); assert data[:4]==b'ECT1'
    count,*anchor=struct.unpack_from('<i3d',data,4); offset=32; parts=[]
    for _ in range(count):
        n,w,h=struct.unpack_from('<3i',data,offset); offset+=16
        assert n%3==0 and w>0 and h>0
        v=np.frombuffer(data,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);v[:,:3]+=anchor;offset+=n*20
        pixels=np.frombuffer(data,dtype='uint8',count=w*h*4,offset=offset).reshape(h,w,4);offset+=w*h*4
        assert np.isfinite(v).all();parts.append((v,pixels))
    assert offset==len(data);return parts
parts=decode(out/rec['meshFile']);roof_parts=decode(out/rec['roofFile'])
assert len(parts)==5 and len(roof_parts)==1
assert np.array_equal(parts[4][0],roof_parts[0][0]) and np.array_equal(parts[4][1],roof_parts[0][1])
source_roofs=[p for k,p in raw if k=='RoofSurface']
roof_points=np.concatenate([world(p) for rings in source_roofs for p in rings])
rv,pixels=parts[4];assert len(rv)==306
roof_error=float(cKDTree(roof_points).query(rv[:,:3])[0].max());assert roof_error<1e-4
roof_shape=unary_union([Polygon(world(p[0])[:,[0,2]],[world(h)[:,[0,2]] for h in p[1:]]).buffer(0) for p in source_roofs])
actual_roof=unary_union([Polygon(t[:,[0,2]]) for t in rv[:,:3].reshape(-1,3,3)])
# Coincident roofs at different heights create narrow projected internal
# seams. Compare covered area within float32 tolerance, not the Hausdorff
# distance to those internal seam boundaries.
assert actual_roof.difference(roof_shape.buffer(1e-4)).area<1e-8
assert roof_shape.difference(actual_roof.buffer(1e-4)).area<1e-8
assert actual_roof.symmetric_difference(roof_shape).area<roof_shape.length*1e-4
# Actual encoded roof pixels and UVs must retain the pinned aerial source.
e,n,_=inverse.transform(*((rv[:,:3]-[0,64,0])@basis+origin).T)
with rasterio.open(root/'.cache/campus-dop-east.tif') as dop:
    c,r=(~dop.transform)*(e,n);height,width=pixels.shape[:2]
    left=float(np.median(c-rv[:,3]*width));top=float(np.median(r-rv[:,4]*height))
    assert abs(left-round(left))<.002 and abs(top-round(top))<.002
    rgb=dop.read([1,2,3],window=rasterio.windows.Window(round(left),round(top),width,height)).transpose(1,2,0)
    assert np.array_equal(rgb,pixels[:,:,:3])
    assert np.max(abs(np.column_stack([(c-round(left))/width,(r-round(top))/height])-rv[:,3:]))<1e-4
plan=next(p for p in read(out/'photo-facades.json')['plans'] if p['id']==spec['building'])
wall_points=np.concatenate([world(p) for k,rings in raw if k=='WallSurface' for p in rings])
assert len(plan['walls'])==53 and all(w['reconstructed'] for w in plan['walls'])
wall_error=float(cKDTree(wall_points).query(np.concatenate([w['vertices'] for w in plan['walls']]))[0].max())
assert wall_error<1e-4
tris=np.concatenate([v[:,:3].reshape(-1,3,3) for v,_ in parts[:4]])
normals=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]);length=np.linalg.norm(normals,axis=1)
assert np.all(length>1e-9), 'degenerate facade triangle'
normals/=length[:,None]
# Check actual encoded surfaces cover each raw-survey wall silhouette, including
# stepped upper edges. Coverage tests the geometry, not just exported metadata.
coverage=[]
for i,w in enumerate(plan['walls']):
    a,u,n=[np.array(w[k]) for k in ['anchor','direction','normal']]
    shape=Polygon(w['rings'][0],w['rings'][1:]).buffer(0)
    depth=(tris-a)@n
    relevant=(normals@n>.999)&(depth.min(1)>-.501)&(depth.max(1)<.001)
    projected=[]
    for t in tris[relevant]:
        p=Polygon(np.column_stack([(t-a)@u,t[:,1]]))
        if p.area>1e-9: projected.append(p)
    union=unary_union(projected)
    missing=shape.difference(union.buffer(.0001)).area
    assert missing<.001,(i,'uncovered wall',missing)
    coverage.append({'face':i,'surveyArea':shape.area,'uncoveredArea':missing})
# Near-field rays must reach the recorded glass rather than a solid panel or
# reverse-facing triangle. Different faces can share material parts.
part_ids=np.concatenate([np.full(len(v)//3,i) for i,(v,_) in enumerate(parts[:4])])
e1,e2=tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]
for control in rec['controls']:
    q,n=np.array(control['position']),np.array(control['normal']);eye=q+n*.6;direction=-n
    h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
    inv=np.divide(1,det,out=np.zeros_like(det),where=abs(det)>1e-10)
    s=eye-tris[:,0];U=inv*np.einsum('ij,ij->i',s,h);Q=np.cross(s,e1)
    V=inv*(Q@direction);distance=inv*np.einsum('ij,ij->i',e2,Q)
    hits=np.flatnonzero((abs(det)>1e-10)&(U>=-1e-7)&(V>=-1e-7)&(U+V<=1.0000001)&(distance>=0))
    assert len(hits),control
    hit=hits[np.argmin(distance[hits])]
    assert part_ids[hit]==control['part'] and abs(distance[hit]-.6)<.0001,(control,part_ids[hit],distance[hit])
    assert normals[hit]@n>.999,control
# Retirement must exclude neighbours and the open inner courtyard.
retirement=unary_union([Polygon(p['ring'],p['holes']) for p in rec['retirement']])
world_foot=unary_union([Polygon(world(rings[0])[:,[0,2]],[world(h)[:,[0,2]] for h in rings[1:]]).buffer(0) for kind,rings in raw if kind=='GroundSurface'])
for p in polygons(world_foot):
    for h in p.interiors:
        core=Polygon(h).buffer(-.51)
        assert retirement.intersection(core).area<.001
for key,other in surveys.items():
    if key==spec['building']:continue
    for kind,rings in other:
        if kind!='GroundSurface':continue
        other_foot=Polygon(world(rings[0])[:,[0,2]],[world(h)[:,[0,2]] for h in rings[1:]]).buffer(0)
        if not other_foot.intersects(retirement):continue
        assert retirement.intersection(other_foot).area<.001,key
files=[rec['meshFile'],rec['roofFile']]
result={'status':'PASS: raw survey envelope, encoded wall coverage, first-hit glass controls, courtyard/neighbour preservation and public roof pixels','manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'validatorSha256':sha(Path(__file__)),'tileSha256':{f:sha(out/f) for f in files},'rawInputs':inputs,'roofVertexErrorMetres':roof_error,'wallVertexErrorMetres':wall_error,'wallCoverage':coverage,'surfaceControls':len(rec['controls']),'qualification':'Facade subdivisions remain estimated. This does not establish native collision, source retirement or visual acceptance.'}
(out/'physics-lmu-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['rawInputs','wallCoverage','tileSha256']},indent=2))

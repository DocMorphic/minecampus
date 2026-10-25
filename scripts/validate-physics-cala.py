#!/usr/bin/env python3
"""Check the CALA envelope, roof imagery and adjoining survey-height land."""
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

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=root/'dist-minecraft/exterior')
parser.add_argument('--ground-directory', type=Path, help='Existing tiles for an isolated incremental development build')
args = parser.parse_args(); out = args.directory; ground_dir = args.ground_directory or out
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
m = read(out/'manifest.json'); rec = m['architecture']['physicsCALA']; src = root/'minecraft/exterior'
spec = read(src/rec['sourceFile']); sources = read(src/'sources.json')
assert sha(src/rec['sourceFile']) == rec['sourceSha256']
assert sha(root/rec['generatorFile']) == rec['generatorSha256']
assert sha(root/'scripts/exterior_ground_extension.py') == rec['groundGeneratorSha256']
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
parts=decode(out/rec['meshFile']);roof=decode(out/rec['roofFile']);assert len(parts)==5 and len(roof)==1
assert np.array_equal(parts[4][0],roof[0][0]) and np.array_equal(parts[4][1],roof[0][1])
source_roofs=[p for k,p in raw if k=='RoofSurface'];roof_points=np.concatenate([world(p) for rings in source_roofs for p in rings]);rv=parts[4][0];assert len(rv)==18
roof_error=float(cKDTree(roof_points).query(rv[:,:3])[0].max());assert roof_error<1e-4
roof_shape=unary_union([Polygon(world(p[0])[:,[0,2]],[world(h)[:,[0,2]] for h in p[1:]]) for p in source_roofs])
actual_roof=unary_union([Polygon(t[:,[0,2]]) for t in rv[:,:3].reshape(-1,3,3)])
# Float32 vertex rounding on a205m perimeter is bounded in metres, then area.
assert actual_roof.hausdorff_distance(roof_shape)<1e-4
assert actual_roof.symmetric_difference(roof_shape).area<roof_shape.length*1e-4
plan=next(p for p in read(out/'photo-facades.json')['plans'] if p['id']==spec['building']);wall_points=np.concatenate([world(p) for k,rings in raw if k=='WallSurface' for p in rings])
assert len(plan['walls'])==8 and all(w['reconstructed'] for w in plan['walls'])
assert cKDTree(wall_points).query(np.concatenate([w['vertices'] for w in plan['walls']]))[0].max()<1e-4
for control in [c for c in rec['controls'] if c['kind']=='estimated-opening']:
    q,n=np.array(control['position']),np.array(control['normal']);wall=plan['walls'][control['face']];u=np.array(wall['direction']);hits=[]
    for part,(vertices,_) in enumerate(parts[:4]):
        for tri in vertices[:,:3].reshape(-1,3,3):
            projected=np.column_stack(((tri-q)@u,tri[:,1]-q[1]));poly=Polygon(projected)
            if poly.area<1e-8 or not poly.covers(Point(0,0)):continue
            distance=float(np.linalg.solve(np.column_stack([projected,np.ones(3)]),(tri-q)@n)[2]);hits.append((part,distance,float(np.cross(tri[1]-tri[0],tri[2]-tri[0])@n)))
    assert any(part==2 and abs(d)<.0001 and winding>0 for part,d,winding in hits),control
    assert not any(part!=2 and d>-.0001 for part,d,winding in hits),control
new_files=rec['groundTiles'];new_parts=[decode(out/name)[0] for name in new_files];new_tri=np.concatenate([v[:,:3].reshape(-1,3,3) for v,pixels in new_parts]);region=unary_union([Polygon(t[:,[0,2]]) for t in new_tri])
assert all(np.cross(t[1]-t[0],t[2]-t[0])[1]>-1e-8 for t in new_tri)
assert abs(region.area-rec['ground']['areaSquareMetres'])<.005
old=[];search=region.buffer(spec['groundBlendMetres']+1)
for tile in m['tiles']:
    if tile['kind']!='ground' or tile['file'] in new_files:continue
    lo,hi=tile['bounds']
    if not search.intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
    for v,_ in decode(ground_dir/tile['file']):
        for t in v[:,:3].reshape(-1,3,3):
            p=Polygon(t[:,[0,2]])
            if p.area>1e-8:old.append((p,t))
existing=unary_union([p for p,t in old]);assert region.intersection(existing).area<.005
foot_mc=unary_union([Polygon(world(p[0])[:,[0,2]],[world(h)[:,[0,2]] for h in p[1:]]) for k,p in raw if k=='GroundSurface'])
assert region.intersection(foot_mc.buffer(-.006)).area<.005
# Ground is source-height terrain, with only the specified old-edge blend.
vertices=np.unique(new_tri.reshape(-1,3),axis=0);en=np.column_stack(inverse.transform(*((vertices-[0,64,0])@basis+origin).T))[:,:2]
with rasterio.open(root/'.cache/campus-dgm-east.tif') as dem:
    c,r=(~dem.transform)*(en[:,0],en[:,1]);raw_h=map_coordinates(dem.read(1).astype(float),[r-.5,c-.5],order=1,prefilter=False)
raw_world=world(np.column_stack([en,raw_h]));tree=STRtree([p for p,t in old]);errors=[];core_errors=[];seam_errors=[]
for q,source in zip(vertices,raw_world):
    p=Point(q[0],q[2]);poly,t=old[int(tree.nearest(p))];near=nearest_points(poly,p)[0];d=p.distance(poly);weights=np.linalg.solve(np.vstack([t[:,0],t[:,2],np.ones(3)]),[near.x,near.y,1]);prior=float(weights@t[:,1]);w=min(1,d/spec['groundBlendMetres']);w=w*w*(3-2*w);errors.append(abs(q[1]-(prior*(1-w)+source[1]*w)))
    if d>=spec['groundBlendMetres']:core_errors.append(abs(q[1]-source[1]))
    if d<.001:seam_errors.append(abs(q[1]-prior))
assert max(errors)<.002 and core_errors and seam_errors,(max(errors),len(core_errors),len(seam_errors))
# The replacement region is bounded and cannot cut neighbouring surveyed shells.
retirement=unary_union([Polygon(p['ring'],p['holes']) for p in rec['retirement']])
# These native-camera failures sit beyond the original10.5m slope strip.
# A valid slope must retire their broken scan and supply actual ground there.
with rasterio.open(root/'.cache/campus-dgm-east.tif') as dem:
    controls=np.asarray(spec['groundRegressionControlsUTM'])
    heights=np.array([float(v[0]) for v in dem.sample(controls)])
control_world=world(np.column_stack([controls,heights]))
covered=existing.union(region)
for q in control_world:
    point=Point(q[0],q[2])
    assert retirement.covers(point),('unretired north-path gap',q.tolist())
    assert covered.buffer(.0001).covers(point),('missing north-path ground',q.tolist())

for bid,raw_other in surveys.items():
    if bid==spec['building']:continue
    for kind,p in raw_other:
        if kind!='GroundSurface':continue
        other=Polygon(world(p[0])[:,[0,2]])
        assert retirement.intersection(other).area<.001,(bid,'retirement')
        assert region.intersection(other).area<.001,(bid,'ground')
# All roof and ground pixels/UVs are from the pinned public aerial raster.
for v,pixels in [parts[4],*new_parts]:
    e,n,_=inverse.transform(*((v[:,:3]-[0,64,0])@basis+origin).T)
    with rasterio.open(root/'.cache/campus-dop-east.tif') as dop:
        c,r=(~dop.transform)*(e,n);height,width=pixels.shape[:2];left=float(np.median(c-v[:,3]*width));top=float(np.median(r-v[:,4]*height))
        assert abs(left-round(left))<.002 and abs(top-round(top))<.002
        rgb=dop.read([1,2,3],window=rasterio.windows.Window(round(left),round(top),width,height)).transpose(1,2,0);assert np.array_equal(rgb,pixels[:,:,:3])
        assert np.max(abs(np.column_stack([(c-round(left))/width,(r-round(top))/height])-v[:,3:]))<1e-4
files=[rec['meshFile'],rec['roofFile'],*new_files]
result={'status':'PASS: source envelope and roof, recessed openings, nonoverlapping DGM ground joins and public DOP pixels','manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'validatorSha256':sha(Path(__file__)),'tileSha256':{f:sha(out/f) for f in files},'rawInputs':inputs,'roofVertexErrorMetres':roof_error,'groundAreaSquareMetres':region.area,'groundVertices':len(vertices),'nativeGapControls':len(control_world),'groundHeightErrorMetres':max(errors),'coreRawDGMErrorMetres':max(core_errors),'seamHeightErrorMetres':max(seam_errors),'qualification':'Facade features are approximate. Native terrain, collision and visual acceptance remain required.'}
(out/'physics-cala-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

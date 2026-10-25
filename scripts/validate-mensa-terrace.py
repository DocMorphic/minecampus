#!/usr/bin/env python3
"""Check the terrace material split against raw BVV roof polygons and DOP pixels."""
from pathlib import Path
import argparse,hashlib,json,struct,xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.warp import reproject,Resampling
from rasterio.transform import from_origin
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from shapely.geometry import Polygon
from shapely.ops import unary_union
from PIL import Image

root=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');out=parser.parse_args().directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');rec=m['architecture']['mensaTerrace'];spec=read(root/'minecraft/exterior'/rec['sourceFile']);sources=read(root/'minecraft/exterior/sources.json')
assert rec['sourceSha256']==sha(root/'minecraft/exterior'/rec['sourceFile'])
plan=next(p for p in read(out/'photo-facades.json')['plans']if p['id']==spec['building'])
assert plan['runtimeId']==rec['runtimeId']==spec['runtimeId']==1_000_050_038 and plan['roofFile']==rec['roofFile'] and not plan['manualRoof']
assert rec['generatorSha256']==sha(root/rec['generatorFile'])
assert rec['roofSha256']==sha(out/rec['roofFile']) and rec['atlasSha256']==sha(out/rec['atlasFile'])
assert sha(root/'minecraft/exterior/assets/textures/campus/concrete_diff.png')==rec['materialSha256']
inputs={};ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'};roof_surfaces=[];target=None
for entry,name in zip(sources['lod2'],['campus-east.gml','campus-west.gml']):
    p=root/'.cache'/name;assert sha(p)==entry['sha256'];inputs[name]=sha(p)
    for b in ET.parse(p).findall('.//b:Building',ns):
        if b.get('{'+ns['g']+'}id')!=spec['building']:continue
        for surface in b.findall('.//b:RoofSurface',ns):
            for poly in surface.findall('.//g:Polygon',ns):
                rings=[np.array(list(map(float,p.text.split()))).reshape(-1,3)for p in poly.findall('.//g:LinearRing/g:posList',ns)]
                roof_surfaces.append(rings)
                if surface.get('{'+ns['g']+'}id')==spec['surfaceId']:assert target is None;target=rings
assert target is not None
lat,lon=np.radians(m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
ecef=Transformer.from_crs(25832,4978,always_xy=True);geo=Transformer.from_crs(25832,4258,always_xy=True)
p=root/'.cache/de_bkg_gcg2016.tif';assert sha(p)==sources['geoid']['sha256'];inputs[p.name]=sha(p)
with rasterio.open(p)as f:geoid=f.read(1).astype(float);transform=f.transform

def world(p):
    lon,lat=geo.transform(p[:,0],p[:,1]);c,r=(~transform)*(lon,lat);h=p[:,2]+map_coordinates(geoid,[r-.5,c-.5],order=1,prefilter=False)
    return (np.column_stack(ecef.transform(p[:,0],p[:,1],h))-origin)@basis.T+[0,64,0]

def decode(p):
    data=p.read_bytes();assert data[:4]==b'ECT1';count,*anchor=struct.unpack_from('<i3d',data,4);offset=32;parts=[]
    for i in range(count):
        n,w,h=struct.unpack_from('<3i',data,offset);offset+=16;assert n>0 and n%3==0
        v=np.frombuffer(data,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);v[:,:3]+=anchor;offset+=n*20
        pixels=np.frombuffer(data,dtype='uint8',count=w*h*4,offset=offset).reshape(h,w,4);offset+=w*h*4;parts.append((v,pixels))
    assert offset==len(data);return parts

parts=decode(out/rec['roofFile']);assert len(parts)==2
raw=np.concatenate([ring for rings in roof_surfaces for ring in rings]);points=world(raw);tree=cKDTree(points)
for vertices,pixels in parts:
    residual,nearest=tree.query(vertices[:,:3]);assert residual.max()<.0001
    assert np.isfinite(vertices).all() and np.all(vertices[:,3:]>=0) and np.all(vertices[:,3:]<=1)
expected=Polygon(world(target[0])[:,[0,2]],[world(r)[:,[0,2]]for r in target[1:]])
paved=unary_union([Polygon(t[:,[0,2]])for t in parts[1][0].reshape(-1,3,5)])
assert paved.symmetric_difference(expected).area<.002
upper=unary_union([Polygon(t[:,[0,2]])for t in parts[0][0].reshape(-1,3,5)])
assert upper.intersection(expected.buffer(-.001)).area<.001,'Other roofs must not cover the terrace'
all_expected=unary_union([Polygon(world(rings[0])[:,[0,2]],[world(r)[:,[0,2]]for r in rings[1:]]).buffer(0)for rings in roof_surfaces])
assert upper.union(paved).symmetric_difference(all_expected).area<.005
# Direct DOP crop must be unchanged on all remaining photographic roofs.
bounds=m['boundsUtm'];raw_uv=np.column_stack([(raw[:,0]-bounds[0])/.2,(bounds[3]-raw[:,1])/.2]);lo=np.floor(raw_uv.min(0)).astype(int)-2;hi=np.ceil(raw_uv.max(0)).astype(int)+2
image=np.zeros((hi[1]-lo[1],hi[0]-lo[0],3),dtype='uint8');dst=from_origin(bounds[0]+lo[0]*.2,bounds[3]-lo[1]*.2,.2,.2)
for entry,name in zip(sorted(sources['dop20'],key=lambda s:s['name']),['campus-dop-west.tif','campus-dop-east.tif']):
    p=root/'.cache'/name;assert sha(p)==entry['sha256'];inputs[name]=sha(p)
    with rasterio.open(p)as f:
        for band in range(3):reproject(rasterio.band(f,band+1),image[:,:,band],src_transform=f.transform,src_crs=f.crs,dst_transform=dst,dst_crs='EPSG:25832',resampling=Resampling.bilinear,init_dest_nodata=False)
assert np.array_equal(parts[0][1][:,:,:3],image)
_,nearest=tree.query(parts[0][0][:,:3]);expected_uv=(raw_uv[nearest]-lo)/(hi-lo);assert np.max(abs(parts[0][0][:,3:]-expected_uv))<1e-6
atlas=np.asarray(Image.open(out/rec['atlasFile']).convert('RGBA'));assert np.array_equal(parts[1][1],atlas) and np.all(atlas[:,:,3]==255)
report={'status':'PASS: named raw survey surface, all roof positions/coverage, retained DOP pixels and UVs, paving atlas integrity','manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'generatorSha256':rec['generatorSha256'],'validatorSha256':sha(Path(__file__)),'rawInputs':inputs,'roofSha256':sha(out/rec['roofFile']),'atlasSha256':sha(out/rec['atlasFile']),'areaSquareMetres':expected.area,'pavingTriangles':len(parts[1][0])//3,'remainingRoofTriangles':len(parts[0][0])//3,'visualAcceptance':False}
(out/'mensa-terrace-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

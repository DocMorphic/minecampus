#!/usr/bin/env python3
"""Check the west ZNN envelope against raw survey, elevation and existing terrain."""
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
m = read(out/'manifest.json'); rec = m['architecture']['physicsZNNWest']; src = root/'minecraft/exterior'
spec = read(src/rec['sourceFile']); sources = read(src/'sources.json')
assert sha(src/rec['sourceFile']) == rec['sourceSha256']
assert sha(root/rec['generatorFile']) == rec['generatorSha256']
assert sha(root/'scripts/exterior_foundation_collar.py') == rec['collarGeneratorSha256']
assert sha(src/spec['osm']['sourceFile']) == spec['osm']['sha256']
assert sha(out/rec['coverageFile']) == rec['coverageSha256']
inputs = {}
for item, name in zip(sources['lod2'], ['campus-east.gml','campus-west.gml']): inputs[name] = item['sha256']
for kind, name in [('dgm1','campus-dgm-east.tif'),('dop20','campus-dop-east.tif')]: inputs[name] = sorted(sources[kind],key=lambda x:x['name'])[1]['sha256']
inputs['de_bkg_gcg2016.tif'] = sources['geoid']['sha256']
inputs['32698_5349_20_DOM.tif'] = next(x['sha256'] for x in read(src/'vegetation-sources.json')['inputs'] if x['cachePath']=='32698_5349_20_DOM.tif')
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
parts=decode(out/rec['meshFile']);roof=decode(out/rec['roofFile']);assert len(parts)==5 and len(roof)==2
for part,colour in zip(parts[:4],spec['materialColours']):assert np.array_equal(part[1][0,0],colour)
assert np.array_equal(parts[4][0],roof[0][0]) and np.array_equal(parts[4][1],roof[0][1])
source_roofs=[p for k,p in raw if k=='RoofSurface']; roof_points=np.concatenate([world(p) for rings in source_roofs for p in rings])
rv=parts[4][0];assert len(rv)==9
roof_error=float(cKDTree(roof_points).query(rv[:,:3])[0].max());assert roof_error<1e-4
roof_shape=unary_union([Polygon(world(p[0])[:,[0,2]],[world(h)[:,[0,2]] for h in p[1:]]) for p in source_roofs])
assert unary_union([Polygon(t[:,[0,2]]) for t in rv[:,:3].reshape(-1,3,3)]).symmetric_difference(roof_shape).area<.001
plans=read(out/'photo-facades.json')['plans']; plan=next(p for p in plans if p['id']==spec['building'])
wall_points=np.concatenate([world(p) for k,rings in raw if k=='WallSurface' for p in rings])
assert len(plan['walls'])==4 and all(w['reconstructed'] for w in plan['walls'])
assert cKDTree(wall_points).query(np.concatenate([w['vertices'] for w in plan['walls']]))[0].max()<1e-4
triangles=[v[:,:3].reshape(-1,3,3) for v,_ in parts]
for control in rec['controls']:
    q,n=np.array(control['position']),np.array(control['normal']); a=triangles[control['part']]
    e1,e2=a[:,1]-a[:,0],a[:,2]-a[:,0]; h=np.cross(-n,e2);det=np.einsum('ij,ij->i',e1,h); valid=abs(det)>1e-9;inv=np.divide(1,det,out=np.zeros_like(det),where=valid)
    s=q+n*.8-a[:,0];u=inv*np.einsum('ij,ij->i',s,h);cross=np.cross(s,e1);v=inv*(cross@(-n));distance=inv*np.einsum('ij,ij->i',e2,cross)
    hits=valid&(u>=-1e-6)&(v>=-1e-6)&(u+v<=1+1e-6)&(distance>=0)
    assert hits.any() and abs(distance[hits].min()-.8)<1e-4
    assert np.all((np.cross(e1,e2)[hits & (distance<.8001)]@n)>0)
# Reconstruct the two high plateaus directly from pinned raw rasters.
osm=ET.parse(src/spec['osm']['sourceFile']).getroot();project=Transformer.from_crs(4326,25832,always_xy=True)
nodes={n.get('id'):project.transform(float(n.get('lon')),float(n.get('lat'))) for n in osm.findall('node')}
way=next(w for w in osm.findall('way') if w.get('id')==spec['osm']['way']);compound=Polygon([nodes[n.get('ref')] for n in way.findall('nd')])
left,bottom,right,top=spec['siteBoundsUTM'];rows,cols=np.mgrid[:round((top-bottom)*5),:round((right-left)*5)];E=left+(cols+.5)*.2;N=top-(rows+.5)*.2;xy=np.column_stack([E.ravel(),N.ravel()])
with rasterio.open(root/'.cache/campus-dgm-east.tif') as dem,rasterio.open(root/'.cache/32698_5349_20_DOM.tif') as dom:
    heights=(np.array(list(dom.sample(xy)))[:,0]-np.array(list(dem.sample(xy)))[:,0]).reshape(E.shape)
    labels,count=label(contains_xy(compound,E,N)&~contains_xy(foot.buffer(.2),E,N)&(heights>5))
    components=[labels==i for i in range(1,count+1) if (labels==i).sum()*.04>=1];assert len(components)==len(spec['equipment'])==2
    pads=[]
    for component,tank in zip(components,spec['equipment']):
        height=float(np.percentile(heights[component],95));cap=component&(heights>=height-.3)
        centre=np.array([E[cap].mean(),N[cap].mean()]);radius=np.sqrt(cap.sum()*.04/math.pi)
        assert np.max(abs(centre-tank['centreUTM']))<1e-8 and abs(radius-tank['radiusMetres'])<1e-8
        assert abs(height-tank['topAboveLocalGroundMetres'])<1e-6
        ground=float(next(dem.sample([centre]))[0]);assert abs(ground-tank['centreGroundElevation'])<1e-6
        pads.append(Point(centre).buffer(radius+.18,resolution=32))
        centre_mc=world(np.array([[*centre,ground]]))[0];vertices=parts[2][0][:,:3];horizontal=np.linalg.norm(vertices[:,[0,2]]-centre_mc[[0,2]],axis=1);subset=vertices[horizontal<radius+.01]
        assert len(subset)>100
        actual_top=world(np.array([[*centre,ground+height]]))[0][1]
        assert abs(subset[:,1].max()-actual_top)<.001
        assert horizontal[horizontal<radius+.01].max()<=radius+.001
# Bounded source retirement must retain unknown equipment and neighbours.
coverage=read(out/rec['coverageFile']);modeled=foot.union(unary_union(pads));unknown=compound.difference(modeled)
others=unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for bid,s in surveys.items() if bid!=spec['building'] for k,p in s if k=='GroundSurface'])
retirement=shape(coverage['retirement']);expected=modeled.buffer(spec['cleanupMarginMetres']).difference(unknown).difference(others.buffer(.5))
assert retirement.symmetric_difference(expected).area<1e-8
assert retirement.intersection(unknown).area<1e-8 and retirement.intersection(others.buffer(.4999)).area<1e-8
assert retirement.covers(Point(698607.77096342,5349624.576364818)), 'Diagnosed low scan fragment remains'
# Compare the actual collar against existing ground triangles, independently of its metadata.
collar_name=rec['foundationCollar']['file'];collar=decode(out/collar_name)[0][0]; region=unary_union([Polygon(t[:,[0,2]]) for t in collar[:,:3].reshape(-1,3,3)])
foot_mc=unary_union([Polygon(world(p[0])[:,[0,2]],[world(h)[:,[0,2]] for h in p[1:]]) for k,p in raw if k=='GroundSurface'])
old=[];search=foot_mc.buffer(2)
for t in m['tiles']:
    if t['kind']!='ground' or t['file']==collar_name:continue
    lo,hi=t['bounds']
    if not search.intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
    for v,_ in decode(ground_dir/t['file']):
        for tri in v[:,:3].reshape(-1,3,3):
            poly=Polygon(tri[:,[0,2]])
            if poly.area>1e-8 and poly.intersects(search):old.append((poly,tri))
existing=unary_union([p for p,t in old]);expected=foot_mc.buffer(.6).difference(existing).difference(foot_mc.buffer(-.005))
assert region.symmetric_difference(expected).area<.001
assert region.intersection(existing).area<.001 and region.intersection(foot_mc.buffer(-.0051)).area<1e-6
shapes=[p for p,t in old];tree=STRtree(shapes);max_distance=0;max_height_error=0
for x,y,z in np.unique(collar[:,:3],axis=0):
    p=Point(x,z);poly,t=old[int(tree.nearest(p))];near=nearest_points(poly,p)[0];weights=np.linalg.solve(np.vstack([t[:,0],t[:,2],np.ones(3)]),[near.x,near.y,1]);max_distance=max(max_distance,p.distance(poly));max_height_error=max(max_height_error,abs(y-weights@t[:,1]))
assert max_distance<.65 and max_height_error<.001, (max_distance,max_height_error)
# Every photographed roof and collar pixel is a crop of the public DOP, with correct georeferencing.
for vertices,pixels in [parts[4],decode(out/collar_name)[0]]:
    e,n,_=inverse.transform(*((vertices[:,:3]-[0,64,0])@basis+origin).T)
    with rasterio.open(root/'.cache/campus-dop-east.tif') as d:
        c,r=(~d.transform)*(e,n);height,width=pixels.shape[:2];left=float(np.median(c-vertices[:,3]*width));top=float(np.median(r-vertices[:,4]*height))
        assert abs(left-round(left))<.001 and abs(top-round(top))<.001
        rgb=d.read([1,2,3],window=rasterio.windows.Window(round(left),round(top),width,height)).transpose(1,2,0)
        assert np.array_equal(rgb,pixels[:,:,:3]);assert np.max(abs(np.column_stack([(c-round(left))/width,(r-round(top))/height])-vertices[:,3:]))<1e-4
files=[rec['meshFile'],rec['roofFile'],collar_name]
result={'status':'PASS: raw surveyed envelope/roof, independently recovered tank controls, bounded retirement, collar joins and DOP pixels','manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'validatorSha256':sha(Path(__file__)),'tileSha256':{f:sha(out/f) for f in files},'rawInputs':inputs,'roofVertexErrorMetres':roof_error,'collarAreaSquareMetres':region.area,'collarMaximumExtrapolationMetres':max_distance,'collarMaximumHeightErrorMetres':max_height_error,'qualification':'Estimated tank silhouettes and facade finishes; native visual and collision acceptance remain separate.'}
(out/'physics-znn-west-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

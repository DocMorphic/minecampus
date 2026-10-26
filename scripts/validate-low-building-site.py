#!/usr/bin/env python3
"""Check source bounds, retained terrain, stack geometry and courtyard planting."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import shapes
from shapely.geometry import Polygon,Point,shape,box
from shapely.ops import unary_union

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');a=p.parse_args()
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(a.directory/'manifest.json');old=read(a.baseline/'manifest.json');s=read(root/'minecraft/exterior/low-building-site.json');record=m['architecture']['lowBuildingSite']
assert m['tiles'][:len(old['tiles'])]==old['tiles'] and len(m['tiles'])==len(old['tiles'])+2
assert m['buildings']==old['buildings'];assert m['supplementalSurfaces'][:-1]==old['supplementalSurfaces']
assert {k:v for k,v in m['architecture'].items()if k!='lowBuildingSite'}==old['architecture']
assert sha(a.directory/'photo-facades.json')==sha(a.baseline/'photo-facades.json')
prior={p.name:sha(p)for p in a.baseline.glob('*.ect')};assert all(sha(a.directory/n)==h for n,h in prior.items())
assert record['sourceSha256']==sha(root/'minecraft/exterior/low-building-site.json')
assert record['generatorSha256']==sha(root/'scripts/exterior_low_building_site.py')
assert record['vegetationGeneratorSha256']==sha(root/'scripts/exterior_vegetation.py')
assert record['ground']['retainedExistingGround'] and not record['groundTiles']

def decode(path):
 raw=path.read_bytes();count,*anchor=struct.unpack_from('<i3d',raw,4);offset=32;parts=[]
 assert raw[:4]==b'ECT1'
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',raw,offset);offset+=16
  assert n>0 and n%3==0 and w>0 and h>0
  v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=offset).reshape(-1,5)[:,:3]+anchor;offset+=n*20+w*h*4
  assert np.isfinite(v).all();parts.append(v.reshape(-1,3,3))
 assert offset==len(raw)
 return parts

court=shape(read(a.directory/record['coverageFile'])['courtyard']);assert 268<court.area<270
surface=m['supplementalSurfaces'][-1];assert surface['name']=='low-building-courtyard-ground'
mc_court=unary_union([Polygon(q['ring'],q.get('holes',[]))for q in surface['rings']]);assert abs(mc_court.area-court.area)<.02
# Prove the retained encoded terrain already covers the full courtyard opening.
ground=[]
for tile in old['tiles']:
 if tile['kind']!='ground':continue
 lo,hi=tile['bounds']
 if not mc_court.intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
 for part in decode(a.baseline/tile['file']):
  for triangle in part:
   q=Polygon(triangle[:,[0,2]])
   if q.area>1e-8 and mc_court.intersects(q):ground.append(q)
missing=mc_court.difference(unary_union(ground)).area;assert missing<.005,missing
stack=record['stack'];assert stack['meshSha256']==sha(a.directory/stack['meshFile'])
with rasterio.open(root/'.cache/32698_5349_20_DOM.tif')as dom:
 window=from_bounds(*s['stackSearchBoundsUTM'],dom.transform).round_offsets().round_lengths();h=dom.read(1,window=window);t=dom.window_transform(window);mask=h>=s['stackThresholdDHHN2016']
 region=unary_union([shape(g)for g,v in shapes(mask.astype('uint8'),mask=mask,transform=t)if v]);centre=np.array(region.centroid.coords[0])
 assert np.linalg.norm(centre-stack['centreUTM'])<1e-7
 assert abs(float(np.quantile(h[mask],.95))-stack['topDHHN2016'])<1e-7
 assert stack['domSha256']==sha(root/'.cache/32698_5349_20_DOM.tif')
assert next(t for t in m['tiles']if t['file']==stack['meshFile'])['fineCollisionMaterials']==[4,4]
base=np.array(stack['baseMC']);tip=np.array(stack['topMC']);parts=decode(a.directory/stack['meshFile']);verts=np.concatenate(parts).reshape(-1,3)
assert abs(verts[:,1].min()-base[1])<1e-5 and abs(verts[:,1].max()-tip[1])<1e-5
assert 25<tip[1]-base[1]<26
for tri in parts[0]:
 normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);assert np.linalg.norm(normal)>1e-7
 if abs(normal[1])<np.linalg.norm(normal)*.01:
  centre=tri.mean(0);axis=base+(tip-base)*(centre[1]-base[1])/(tip[1]-base[1]);assert np.dot(normal[[0,2]],(centre-axis)[[0,2]])>0
assert all(np.cross(t[1]-t[0],t[2]-t[0])[1]>0 for t in parts[1])
# All retirement volumes stay outside neighbours or strictly above their roofs.
for zone in record['sourceRetirement']:
 q=unary_union([Polygon(r['ring'],r.get('holes',[]))for r in zone['rings']])
 for building in old['buildings']:
  if zone['y0']>building['bounds'][1][1]:continue
  if building['id']==s['building']:
   roof=next(b for b in old['architecture']['galileoLowBuildings']['buildings']if b['building']==s['building'])
   footprint=unary_union([Polygon(t[:,[0,2]])for part in decode(a.baseline/roof['roofFile'])for t in part])
  else:footprint=unary_union([Polygon([(v[0],v[2])for v in ring]).buffer(0)for ring in building['grounds']])
  assert q.intersection(footprint).area<.01,(building['id'],q.intersection(footprint).area)
shrubs=record['shrubs'];assert shrubs['meshSha256']==sha(a.directory/shrubs['meshFile'])
plants=decode(a.directory/shrubs['meshFile']);assert len(plants)==2 and len(plants[1])==shrubs['leafCards']*2
assert all(mc_court.buffer(1e-4).covers(Point(p[[0,2]]))for p in np.concatenate(plants).reshape(-1,3))
assert shrubs['detectedAreaSquareMetres']<=court.area
assert all(.6<p['topMC'][1]-p['baseMC'][1]<4.6 for p in shrubs['samples'])
shrub_tile=next(t for t in m['tiles']if t['file']==shrubs['meshFile']);assert shrub_tile['collisionParts']==[] and shrub_tile['kind']=='vegetation'
result={'status':'PASS: retained ground and prior meshes; source-anchored stack and bounded low vegetation; native review pending','manifestSha256':sha(a.directory/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':record['sourceSha256'],'generatorSha256':record['generatorSha256'],'retainedMeshSha256':prior,'retainedMeshCount':len(prior),'missingCourtyardGroundSquareMetres':missing,'courtyardAreaSquareMetres':mc_court.area,'stackHeightMetres':float(tip[1]-base[1]),'plantCells':len(shrubs['samples']),'plantAreaSquareMetres':shrubs['detectedAreaSquareMetres'],'leafCards':shrubs['leafCards'],'nativeReviewed':False}
(a.directory/'low-building-site-validation.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items()if k!='retainedMeshSha256'})

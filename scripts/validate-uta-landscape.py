#!/usr/bin/env python3
"""Verify UTA south replacement terrain, canopy bounds and building preservation."""
import argparse,ast,hashlib,json,math,struct,sys
from pathlib import Path
from exterior_ground_provenance import ground_generator_matches
import numpy as np
import rasterio,mapbox_earcut
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from shapely.geometry import Polygon,Point,box,shape
from shapely.ops import unary_union,nearest_points
from shapely.strtree import STRtree
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from exterior_physics_i import nearby_surveys,survey_plan
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');record=m['architecture']['utaLandscape'];spec=read(root/'minecraft/exterior'/record['sourceFile']);d=read(out/record['derivedFile'])
for p,key in [(root/'minecraft/exterior'/record['sourceFile'],'sourceSha256'),(root/record['generatorFile'],'generatorSha256'),(root/'scripts/exterior_ground_extension.py','groundGeneratorSha256'),(root/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(root/'minecraft/exterior/vegetation-sources.json','vegetationSourceSha256'),(out/record['derivedFile'],'derivedSha256')]:assert sha(p)==record[key] or (key=='groundGeneratorSha256' and ground_generator_matches(p,record[key])),p
for source in read(root/'minecraft/exterior/vegetation-sources.json')['inputs']:assert sha(root/'.cache'/source['cachePath'])==source['sha256']
source=read(root/'minecraft/exterior/sources.json')
for e,name in zip(source['lod2'],['campus-east.gml','campus-west.gml']):assert sha(root/'.cache'/name)==e['sha256']
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc')
ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer,'mapbox_earcut':mapbox_earcut}
exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'frame','exec'),ctx)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='triangulate');exec(compile(ast.Module(body=[fn],type_ignores=[]),'triangulate','exec'),ctx);mc=ctx['mc']
surveys=nearby_surveys(root/'.cache',spec['boundsUTM'])
regions=lambda rings:unary_union([Polygon(p['ring'],p.get('holes',[]))for p in rings])
raw_footprints=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for _,s in surveys for k,r in s if k=='GroundSurface'])
raw_roofs=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for _,s in surveys for k,r in s if k=='RoofSurface'])
selected=Polygon(spec['landscapeBoundaryUTM']).intersection(box(*spec['boundsUTM']))
expected_ground=selected.difference(raw_footprints.buffer(spec['groundBuildingGuardMetres']))
expected_outdoor=expected_ground.difference(raw_footprints.union(raw_roofs).buffer(spec['buildingGuardMetres']))
assert shape(d['groundDomainUTM']).symmetric_difference(expected_ground).area<1e-6
assert shape(d['outdoorDomainUTM']).symmetric_difference(expected_outdoor).area<1e-6
assert record['sourceRetirement']==d['sourceRetirement'] and len(record['sourceRetirement'])==1
volume=record['sourceRetirement'][0];outdoor=regions(volume['rings'])
protected=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for _,s in surveys for k,r in s if k in ('GroundSurface','RoofSurface')])
assert outdoor.intersection(protected).area<1e-7
assert volume['y0']<62 and volume['y1']>85
for ring in volume['rings']:assert dict(ring,y0=volume['y0'],y1=volume['y1'])in m['photoFacades']['collisionRetirement']
# Regress the three native first-hit locations that visibly blocked the route.
evidence=read(root/'minecraft/exterior'/spec['sourceEvidence'])['southObstructionDiagnosis']
for ray in evidence['rays']:assert expected_outdoor.contains(Point(*ray['hitPositionUTM']))
def decode(p):
 raw=p.read_bytes();assert raw[:4]==b'ECT1';count,*anchor=struct.unpack_from('<i3d',raw,4);offset=32;parts=[]
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',raw,offset);offset+=16;v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);v[:,:3]+=anchor;offset+=n*20;pixels=np.frombuffer(raw,dtype='uint8',count=w*h*4,offset=offset).reshape(h,w,4);offset+=w*h*4;assert np.isfinite(v).all();parts.append((v,pixels))
 assert offset==len(raw);return parts
new_parts=[decode(out/name)[0]for name in record['groundTiles']];tri=np.concatenate([v[:,:3].reshape(-1,3,3)for v,p in new_parts]);new=unary_union([Polygon(t[:,[0,2]])for t in tri]);assert abs(new.area-d['ground']['areaSquareMetres'])<.02
old=[]
for t in m['tiles']:
 if t['kind']!='ground' or t['file']in record['groundTiles'] or t['file']in m['architecture'].get('uydSite',{}).get('groundTiles',[]):continue
 lo,hi=t['bounds']
 if not new.buffer(spec['groundBlendMetres']+1).intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
 for v,_ in decode(out/t['file']):
  for q in v[:,:3].reshape(-1,3,3):
   poly=Polygon(q[:,[0,2]])
   if poly.area>1e-8:old.append((poly,q))
existing=unary_union([p for p,q in old]);assert new.intersection(existing).area<.01
lat,lon=np.radians(m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
inverse=Transformer.from_crs(4978,25832,always_xy=True)
def utm(v):return np.column_stack(inverse.transform(*((v-[0,64,0])@basis+origin).T))[:,:2]
vertices=np.unique(tri.reshape(-1,3),axis=0);en=utm(vertices)
with rasterio.open(root/'.cache/campus-dgm-east.tif')as raster:
 c,r=(~raster.transform)*(en[:,0],en[:,1]);height=map_coordinates(raster.read(1).astype(float),[r-.5,c-.5],order=1,prefilter=False)
expected=mc(np.column_stack([en,height]))[:,1];old_tree=STRtree([p for p,q in old]);errors=[];seams=[]
for q,h in zip(vertices,expected):
 point=Point(q[0],q[2]);poly,t=old[int(old_tree.nearest(point))];near=nearest_points(poly,point)[0];distance=point.distance(poly);w=min(1,distance/spec['groundBlendMetres']);w=w*w*(3-2*w);weights=np.linalg.solve(np.vstack([t[:,0],t[:,2],np.ones(3)]),[near.x,near.y,1]);prior=float(weights@t[:,1]);errors.append(abs(q[1]-(prior*(1-w)+h*w)))
 if distance<.001:seams.append(abs(q[1]-prior))
assert max(errors)<.002 and seams and max(seams)<.002,(max(errors),max(seams))
with rasterio.open(root/'.cache/campus-dop-east.tif')as dop:
 for v,pixels in new_parts:
  e,n=utm(v[:,:3]).T;c,r=(~dop.transform)*(e,n);h,w=pixels.shape[:2];left=float(np.median(c-v[:,3]*w));top=float(np.median(r-v[:,4]*h));assert abs(left-round(left))<.002 and abs(top-round(top))<.002
  expected=dop.read([1,2,3],window=rasterio.windows.Window(round(left),round(top),w,h)).transpose(1,2,0);assert np.array_equal(expected,pixels[:,:,:3])
# The entire selected outdoor cleanup has actual new or retained ground beneath it.
outdoor=regions(d['outdoorRings']);missing=outdoor.buffer(-.02).difference(new.union(existing)).area;assert missing<.05,('Retirement without replacement ground',missing)
assert new.intersection(protected).area<.01
allowed=Polygon(spec['treeSelectionBoundaryUTM']).intersection(expected_outdoor)
assert shape(d['treeSelectionDomainUTM']).symmetric_difference(allowed).area<1e-6
assert len(d['trees'])>=8
for t in d['trees']:
 assert allowed.covers(Point(*t['utm'])) and 3<t['height']<26
 for previous in [*m['vegetation']['trees'],*[t for s in m['supplementalSurfaces']if s['name']!='uta-south-landscape-retirement'for t in s.get('vegetation',{}).get('trees',[])]]:
  assert np.linalg.norm(np.asarray(previous['utm'])-t['utm'])>=2.99
assert len({t['runtimeId']for t in m['tiles']})==len(m['tiles'])
unchanged=None
if args.baseline:
 before=read(args.baseline/'manifest.json');assert m['tiles'][:len(before['tiles'])]==before['tiles']
 for p in args.baseline.glob('*.ect'):assert sha(out/p.name)==sha(p),p.name
 assert read(out/'photo-facades.json')==read(args.baseline/'photo-facades.json')
 for k,v in before['architecture'].items():assert m['architecture'][k]==v,k
 assert m['supplementalSurfaces'][:len(before['supplementalSurfaces'])]==before['supplementalSurfaces'];unchanged=len(list(args.baseline.glob('*.ect')))
result={'status':'PASS: source-fitted landscape, measured terrain joins, exact aerial pixels and protected buildings/roofs','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':record['sourceSha256'],'derivedSha256':record['derivedSha256'],'groundTiles':len(record['groundTiles']),'groundAreaSquareMetres':new.area,'maximumGroundHeightResidualMetres':max(errors),'maximumSeamErrorMetres':max(seams),'missingOutdoorReplacementGroundSquareMetres':missing,'protectedBuildingOverlapSquareMetres':outdoor.intersection(protected).area,'newTrees':len(d['trees']),'priorRenderCollisionInputsUnchanged':unchanged,'tileSha256':{n:sha(out/n)for n in record['groundTiles']+record['treeTiles']},'visualAcceptance':False}
(out/'uta-south-landscape-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

#!/usr/bin/env python3
"""Verify UYD survey planes, roof pixels, terrain profiles and bounded ownership."""
import argparse, ast, hashlib, json, math, struct
from pathlib import Path
import numpy as np
import rasterio, mapbox_earcut
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree
from exterior_physics_i import nearby_surveys, survey_plan, roof_texture

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');record=m['architecture']['uydExterior'];spec=read(root/'minecraft/exterior'/record['sourceFile'])
for p,key in [(root/'minecraft/exterior'/record['sourceFile'],'sourceSha256'),(root/record['generatorFile'],'generatorSha256'),(root/'minecraft/exterior'/record['referenceFile'],'referenceSha256'),(out/record['roofFile'],'roofSha256'),(out/record['collisionFile'],'collisionSha256'),(root/'.cache/campus-dgm-east.tif','datumSourceSha256')]:assert sha(p)==record[key],p
for entry,name in zip(read(root/'minecraft/exterior/sources.json')['lod2'],['campus-east.gml','campus-west.gml']):assert sha(root/'.cache'/name)==entry['sha256']
assert record['datumSourceSha256']==read(root/'minecraft/exterior/sources.json')['dgm1'][1]['sha256']
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc');ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer,'mapbox_earcut':mapbox_earcut};exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'frame','exec'),ctx)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='triangulate');exec(compile(ast.Module(body=[fn],type_ignores=[]),'triangulate','exec'),ctx);mc=ctx['mc']
surveys=nearby_surveys(root/'.cache',spec['siteBoundsUTM']);foot,walls,roof,points=survey_plan(ctx,next(s for bid,s in surveys if bid==spec['building']))
plans=read(out/'photo-facades.json');plan=next(p for p in plans['plans']if p['id']==spec['building'])
assert len(walls)==5 and len(roof)//3==5 and not plan['manualRoof'] and not plan.get('completeEnvelope')
assert plans['minimumCoverage']==.8 and plans['maxProjectionDistance']==6 and plans['pixelsPerMetre']==10
assert len({p['runtimeId']for p in plans['plans']})==len(plans['plans'])
assert plan['runtimeId']not in [t['runtimeId']for t in m['tiles']]
for index,(actual,expected) in enumerate(zip(plan['walls'],walls)):
 assert bool(actual.get('reconstructed'))==(index==spec['fallbackWall'])
 for key in expected:assert actual[key]==expected[key],key
assert len(plan['walls'])==len(walls)
assert np.array_equal(np.asarray(plan['roofTriangles']),roof[:,3:6].reshape(-1,3,3))
def decode(path):
 raw=path.read_bytes();assert raw[:4]==b'ECT1';count,*anchor=struct.unpack_from('<i3d',raw,4);assert anchor==[0,0,0];offset=32;parts=[];pixels=[]
 for i in range(count):
  n,w,h=struct.unpack_from('<3i',raw,offset);offset+=16;p=np.frombuffer(raw,dtype='<f4',count=n*5,offset=offset).reshape(-1,5);offset+=n*20;tex=raw[offset:offset+w*h*4];offset+=w*h*4
  assert n>0 and n%3==0 and np.isfinite(p).all();q=p[:,:3].reshape(-1,3,3);assert np.min(np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1))>1e-9;parts.append(p);pixels.append((w,h,tex))
 assert offset==len(raw);return parts,pixels
parts,pixels=decode(out/record['collisionFile']);roof_parts,roof_pixels=decode(out/record['roofFile']);expected,texture=roof_texture(root/'.cache',roof)
assert len(parts)==2 and len(roof_parts)==1
assert np.array_equal(parts[0],np.asarray([[*w['vertices'][i],0,0]for w in walls for i in w['indices']],dtype=np.float32))
assert np.array_equal(parts[1],expected.astype(np.float32)) and np.array_equal(parts[1],roof_parts[0])
assert pixels[1]==roof_pixels[0]==(*texture.size,texture.convert('RGBA').tobytes())
shape=lambda rings:unary_union([Polygon(p['ring'],p['holes'])for p in rings])
neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys if bid!=spec['building']for k,r in s if k=='GroundSurface'])
owned=shape(plan['retirementBoundary']);assert plan['retirement']==plan['retirementBoundary']
assert owned.equals(foot.buffer(spec['cleanupMarginMetres']).difference(neighbours.buffer(spec['neighbourGuardMetres'])))
assert owned.intersection(neighbours).area<1e-8
assert {'file':record['collisionFile'],'bounds':plan['bounds'],'kind':'reconstruction','collisionHeightfieldParts':[1]}in m['photoFacades']['collisionTiles']
for r in plan['retirement']:assert dict(r,y0=plan['bounds'][0][1]-2,y1=plan['bounds'][1][1]+5)in m['photoFacades']['collisionRetirement']
datum=next(s for s in m['supplementalSurfaces']if s['name']=='uyd-envelope-datum');assert not datum['outdoorReconstructed']
assert shape(datum['rings']).equals(foot.buffer(spec['datumMarginMetres']).difference(neighbours))
lat,lon=np.radians(m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]]);inverse=Transformer.from_crs(4978,25832,always_xy=True)
locations=[np.asarray(datum['terrainGuide']['points'])];profiles=[]
for w in plan['walls']:
 profile=np.asarray(w['groundProfile']);assert len(profile)>=2 and np.max(np.diff(profile[:,0]))<=.500001
 q=np.array(w['anchor'])+profile[:,0,None]*np.array(w['direction']);q[:,1]=profile[:,1];profiles.extend(q.tolist())
locations.append(np.asarray(profiles));positions=np.concatenate(locations);flat=positions.copy();flat[:,1]=64;en=np.column_stack(inverse.transform(*((flat-[0,64,0])@basis+origin).T))[:,:2]
with rasterio.open(root/'.cache/campus-dgm-east.tif')as dem:
 c,r=(~dem.transform)*(en[:,0],en[:,1]);h=map_coordinates(dem.read(1).astype(float),[r-.5,c-.5],order=1,prefilter=False)
error=float(np.max(np.abs(mc(np.column_stack([en,h]))[:,1]-positions[:,1])));assert error<.001
fallback=plan['walls'][spec['fallbackWall']]
fp,fc=decode(out/record['meshFile'])
assert len(fp)==1 and fc==[(1,1,bytes(spec['fallbackColour']))]
assert np.array_equal(fp[0],np.asarray([[*fallback['vertices'][i],.5,.5]for i in fallback['indices']],dtype=np.float32))
assert sha(out/record['meshFile'])==record['meshSha256']
assert sum(bool(w.get('reconstructed'))for w in plan['walls'])==1
assert len({t['runtimeId']for t in m['tiles']}|{p['runtimeId']for p in plans['plans']})==len(m['tiles'])+len(plans['plans'])
unchanged=None
if args.baseline:
 before=read(args.baseline/'manifest.json');assert before['tiles']==[t for t in m['tiles']if t['file']!=record['meshFile']]
 assert before['supplementalSurfaces']==[t for t in m['supplementalSurfaces']if t['name']!='uyd-envelope-datum']
 assert read(args.baseline/'photo-facades.json')['plans']==[p for p in plans['plans']if p['id']!=spec['building']]
 for k,v in before['architecture'].items():assert m['architecture'][k]==v,k
 names={t['file']for t in before['tiles']}|set(before['photoFacades']['roofFiles'])|{t['file']for t in before['photoFacades']['collisionTiles']}
 for name in names:assert sha(args.baseline/name)==sha(out/name),name
 unchanged=len(names)
result={'status':'PASS: survey envelope, exact roof pixels, independently gated faces, provisional east wall and bounded ownership','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':record['sourceSha256'],'roofSha256':record['roofSha256'],'collisionSha256':record['collisionSha256'],'meshSha256':record['meshSha256'],'walls':5,'roofTriangles':5,'terrainSamples':len(positions),'maximumTerrainResidualMetres':error,'neighbourOverlapSquareMetres':owned.intersection(neighbours).area,'priorRenderCollisionInputsUnchanged':unchanged,'visualAcceptance':False}
(out/'uyd-exterior-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

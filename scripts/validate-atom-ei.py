#!/usr/bin/env python3
"""Check source registration, shell joins, winding, neighbours and preservation."""
import argparse, ast, hashlib, json, math, re, struct, sys
from collections import Counter
from pathlib import Path
import numpy as np
import rasterio
import mapbox_earcut
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import Polygon
from shapely.ops import unary_union

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from exterior_physics_i import nearby_surveys
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
m=read(out/'manifest.json');record=m['architecture']['atomEi'];spec=read(root/'minecraft/exterior'/record['sourceFile']);derived=read(out/record['derivedFile'])
for path,key in [(root/'minecraft/exterior'/record['sourceFile'],'sourceSha256'),(root/record['generatorFile'],'generatorSha256'),(root/'minecraft/exterior'/record['referenceFile'],'referenceSha256'),(out/record['derivedFile'],'derivedSha256'),(out/record['meshFile'],'meshSha256'),(out/record['roofFile'],'roofSha256')]:assert sha(path)==record[key],path
source=read(root/'minecraft/exterior/sources.json')
for entry,name in zip(source['lod2'],['campus-east.gml','campus-west.gml']):assert sha(root/'.cache'/name)==entry['sha256']==derived['surveyHashes'][name]
# Use the production datum conversion without executing the full world build.
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc')
ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer}
exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'frame','exec'),ctx);mc=ctx['mc']
surveys=nearby_surveys(root/'.cache',spec['siteBoundsUTM']);surfaces=next(s for bid,s in surveys if bid==spec['building'])
raw=(out/record['meshFile']).read_bytes();assert struct.unpack_from('<i3d',raw,4)==(6,0,0,0)
parts=[];offset=32;areas=[]
for i in range(6):
 count,w,h=struct.unpack_from('<iii',raw,offset);offset+=16
 p=np.frombuffer(raw,dtype='<f4',count=count*5,offset=offset).reshape(-1,5).astype(float);offset+=count*20+w*h*4
 assert count%3==0 and np.isfinite(p).all();q=p[:,:3].reshape(-1,3,3)
 area=np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1)*.5
 assert area.min()>1e-9,(i,area.min());areas.append(float(area.sum()));parts.append(p)
assert offset==len(raw)
dome=parts[0][:,:3].reshape(-1,3,3)
# Every non-boundary mesh edge has two owners; only the survey skirt stays open.
keys=np.round(dome,4);edges=Counter(tuple(sorted((tuple(t[i]),tuple(t[(i+1)%3]))))for t in keys for i in range(3))
assert set(edges.values())<={1,2},'Non-manifold shell'
boundary=np.asarray([e for e,n in edges.items()if n==1]);base=derived['baseCentreMC'][1]
assert len(boundary)>0 and np.max(np.abs(boundary[:,:,1]-base))<.002,'Gap above dome skirt'
# UV-carried normals must agree with outward winding after float32 encoding.
oct=parts[0][:,3:5]*2-1;n=np.column_stack([oct[:,0],1-np.abs(oct).sum(1),oct[:,1]])
negative=n[:,1]<0
# The only lower-hemisphere values are datum-tilt at the equator.
if negative.any():n[np.where(negative)[0][:,None],[0,2]]=(1-np.abs(oct[negative,::-1]))*np.sign(oct[negative])
n/=np.linalg.norm(n,axis=1)[:,None];normals=n.reshape(-1,3,3).mean(1)
assert np.min(np.sum(np.cross(dome[:,1]-dome[:,0],dome[:,2]-dome[:,0])*normals,axis=1))>0
# Independent ray/surface comparison against raw roof observations, not the
# generator's self-reported residual. Nearest candidate triangles are enough
# only when the point projects inside one; every observation must be covered.
roof=np.unique(np.concatenate([r[0]for kind,r in surfaces if kind=='RoofSurface']),axis=0)
apex=roof[np.argmax(roof[:,2])];radius=np.linalg.norm(roof[:,:2]-apex[:2],axis=1)
observed=roof[(roof[:,2]>=spec['domeBaseHeight']-1e-5)&(radius<spec['domeRadiusRangeMetres'][1])]
observed_mc=mc(observed);centres=dome.mean(1);tree=cKDTree(centres);errors=[]
for point in observed_mc:
 distances,indices=tree.query(point,k=160)
 best=float('inf')
 for tri in dome[indices]:
  a,b,c=tri;ab=b-a;ac=c-a;normal=np.cross(ab,ac);normal/=np.linalg.norm(normal)
  distance=(point-a)@normal;projected=point-distance*normal
  v,w=np.linalg.lstsq(np.column_stack([ab,ac]),projected-a,rcond=None)[0]
  if min(v,w,1-v-w)>=-.001:best=min(best,abs(distance))
 assert best<.012,(point,best)
 errors.append(best)
# Retained lower roof triangles must be the exact triangulated survey, including
# connectivity, after float32 transport; no smoothing or height change below dome.
ctx.update(mapbox_earcut=mapbox_earcut)
fn=next(n for n in ast.parse((root/'scripts/build-exterior.py').read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='triangulate')
exec(compile(ast.Module(body=[fn],type_ignores=[]),'triangulate','exec'),ctx)
lower=[]
for kind,rings in surfaces:
 if kind!='RoofSurface':continue
 p=rings[0]
 if p[:,2].min()>=spec['domeBaseHeight']-1e-5 and np.linalg.norm(p[:,:2]-apex[:2],axis=1).max()<spec['domeRadiusRangeMetres'][1]:continue
 _,q,indices=ctx['triangulate'](rings);lower.extend(q[indices].reshape(-1,3).tolist())
assert np.array_equal(np.asarray(lower,dtype=np.float32),parts[5][:,:3].astype(np.float32))
owned=unary_union([Polygon(p['ring'],p['holes'])for p in derived['retirement']])
neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys if bid!=spec['building']for kind,r in s if kind=='GroundSurface'])
assert owned.intersection(neighbours).area<1e-8
plans=read(out/'photo-facades.json')['plans'];plan=next(p for p in plans if p['id']==spec['building']);assert plan['completeEnvelope'] and plan['manualRoof'] and len(plan['walls'])==112 and all(w['reconstructed']for w in plan['walls'])
assert len(derived['outerBaseWalls'])==79 and len(derived['skirtAndReturnWalls'])==33 and derived['smallReturnTriangles']==1
runtime=[t['runtimeId']for t in m['tiles']];assert len(runtime)==len(set(runtime))
shader=(root/'minecraft/exterior/shaders/campus_ground.fsh').read_text()
centres=re.findall(r'worldPosition.xz-vec2\((245\.[0-9]+),(-96\.[0-9]+)\)',shader)
assert len(centres)==2
for centre in centres:assert np.max(np.abs(np.asarray(centre,dtype=float)-np.asarray(derived['baseCentreMC'])[[0,2]]))<1e-7
assert 'if(abs(MaterialDetail-27.0)<.1)' in shader and 'if(abs(MaterialDetail-28.0)<.1)' in shader
patch=(root/'minecraft/exterior/patches/realworldmc-exterior.patch').read_text()
assert 't.data.id==1_000_030_046' in patch and 'i==0?27f:(i==1?28f:(i==3?6f:(i==5?0f:16f)))' in patch
unchanged=None
if args.baseline:
 before=read(args.baseline/'manifest.json');assert m['tiles'][:-1]==before['tiles']
 assert read(args.baseline/'photo-facades.json')['plans']==plans[:-1]
 # Metadata preservation prevents unrelated material, terrain and replacement edits.
 for key in before:
  if key not in ['architecture','tiles','photoFacades']:assert m[key]==before[key],key
 assert {k:v for k,v in m['architecture'].items()if k!='atomEi'}==before['architecture']
 unchanged=len(before['tiles'])
result={'status':'PASS: source-constrained dome, closed shell above skirt, outward smooth normals, lower survey roof and neighbour exclusions','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':record['sourceSha256'],'generatorSha256':record['generatorSha256'],'meshSha256':record['meshSha256'],'roofSha256':record['roofSha256'],'observedRoofVertices':len(observed),'maximumMeshDistanceToSurveyMetres':max(errors),'partAreasSquareMetres':areas,'openEdgesAtSurveySkirt':len(boundary),'protectedNeighbourOverlapSquareMetres':owned.intersection(neighbours).area,'unchangedPreviousTileRecords':unchanged,'visualAcceptance':False}
(out/'atom-ei-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

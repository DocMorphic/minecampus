#!/usr/bin/env python3
"""Verify measured canopy roofs, open sides, support clearance and bounded replacement."""
import argparse, ast, hashlib, json, math, struct, sys
from pathlib import Path
import numpy as np
import rasterio
import mapbox_earcut
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from exterior_physics_i import nearby_surveys,survey_plan
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
m=read(out/'manifest.json');rec=m['architecture']['atomEiCanopies'];spec=read(root/'minecraft/exterior'/rec['sourceFile']);data=read(out/rec['derivedFile'])
for path,key in [(root/'minecraft/exterior'/rec['sourceFile'],'sourceSha256'),(root/rec['generatorFile'],'generatorSha256'),(root/'minecraft/exterior'/rec['referenceFile'],'referenceSha256'),(out/rec['derivedFile'],'derivedSha256')]:assert sha(path)==rec[key],path
source=read(root/'minecraft/exterior/sources.json')
for item,file in zip(source['lod2'],['campus-east.gml','campus-west.gml']):assert sha(root/'.cache'/file)==item['sha256']
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc')
ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer,'mapbox_earcut':mapbox_earcut}
exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'frame','exec'),ctx)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='triangulate');exec(compile(ast.Module(body=[fn],type_ignores=[]),'triangulate','exec'),ctx);mc=ctx['mc']
surveys=dict(nearby_surveys(root/'.cache',spec['siteBoundsUTM']));selected=set(spec['buildings'])
protect=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys.items()if bid not in selected|{spec['mainBuilding']}for k,r in s if k=='GroundSurface'])
plans=read(out/'photo-facades.json')['plans'];results=[]
for record in data['buildings']:
 bid=record['building'];path=out/record['meshFile'];assert sha(path)==record['meshSha256'];raw=path.read_bytes();assert struct.unpack_from('<i3d',raw,4)==(2,0,0,0)
 parts=[];offset=32
 for part in range(2):
  n,w,h=struct.unpack_from('<iii',raw,offset);offset+=16;v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);offset+=n*20+w*h*4
  assert np.isfinite(v).all()and n%3==0
  tri=v[:,:3].reshape(-1,3,3);assert np.min(np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1))>1e-9
  parts.append(v)
 assert offset==len(raw)
 # Frame UVs carry a constant analytic plane normal, independent of skinny
 # triangle cross products and screen derivatives. Check decoded normals on
 # every triangle against exported positions within float32 roundoff.
 v=parts[1].reshape(-1,3,5);uv=v[:,:,3:];assert np.array_equal(uv[:,0],uv[:,1]) and np.array_equal(uv[:,0],uv[:,2])
 assert ((uv>=0)&(uv<=1)).all()
 octa=uv[:,0]*2-1;n=np.column_stack((octa[:,0],1-np.abs(octa).sum(1),octa[:,1]));lower=n[:,1]<0
 n[np.ix_(lower,[0,2])]=(1-np.abs(n[np.ix_(lower,[2,0])]))*np.where(n[np.ix_(lower,[0,2])]>=0,1,-1)
 n/=np.linalg.norm(n,axis=1)[:,None]
 edge=v[:,1:,:3]-v[:,:1,:3];residual=np.max(np.abs(np.sum(edge*n[:,None,:],axis=2)))
 assert residual<.00005,('Frame plane normal disagreement',residual)
 assert np.all((np.abs(n[:,1])<1e-6)|(np.abs(n[:,1])>.99999)), 'Frames must follow vertical walls or surveyed nearly level planes'
 foot,walls,roof,points=survey_plan(ctx,surveys[bid]);assert np.array_equal(parts[0][:,:3].astype(np.float32),roof[:,3:6].astype(np.float32))
 # No former volume side may survive below the roof. Each low triangle must
 # belong to a single slender post, including its projected edge and interior.
 posts=np.asarray([p['positionMC']for p in record['supports']]);half=spec['postWidthMetres']/2
 tri=parts[1][:,:3].reshape(-1,3,3);low=tri[tri[:,:,1].min(1)<parts[0][:,1].min()-.15]
 for q in low:
  inside=np.all(np.abs(q[:,[0,2]][None,:,:]-posts[:,[0,2]][:,None,:])<=half+.00003,axis=(1,2))
  assert inside.any(),'Enclosure geometry remains under canopy'
 assert len(low)>0 and all(p['topMC']-p['positionMC'][1]>2.4 for p in record['supports'])
 owned=unary_union([Polygon(p['ring'],p['holes'])for p in record['retirement']]);assert owned.intersection(protect).area<1e-8
 assert owned.difference(foot.buffer(spec['cleanupMarginMetres']+.00001)).area<1e-7
 plan=next(p for p in plans if p['id']==bid);assert plan['manualRoof'] and plan['completeEnvelope'] and all(w.get('reconstructed')for w in plan['walls'])
 assert record['retiredCollisionFile']not in [t['file']for t in m['photoFacades']['collisionTiles']]
 assert len(plan['roofTriangles'])==len(roof)//3
 tile=next(t for t in m['tiles']if t['runtimeId']==record['runtimeId']);assert tile['fineCollisionMaterials']==[4,4] and tile['profile']=='atom-ei-canopy'
 results.append({'building':bid,'meshSha256':record['meshSha256'],'exactRoofTriangles':len(roof)//3,'framePlaneNormalMaximumResidualMetres':float(residual),'postCount':len(posts),'falseVolumeFacesRetired':len(walls),'lowTrianglesConfinedToPosts':len(low),'protectedNeighbourOverlapSquareMetres':owned.intersection(protect).area})
ids=[t['runtimeId']for t in m['tiles']];assert len(ids)==len(set(ids))
if args.baseline:
 before=read(args.baseline/'manifest.json');assert before['tiles']==m['tiles'][:-3]
 assert {k:v for k,v in m['architecture'].items()if k!='atomEiCanopies'}==before['architecture']
 for key in before:
  if key not in ['tiles','architecture','photoFacades']:assert m[key]==before[key],key
 oldplans=read(args.baseline/'photo-facades.json')['plans'];assert len(oldplans)==len(plans)
 for a,b in zip(oldplans,plans):
  assert a['id']==b['id']
  if a['id']not in selected:assert a==b,a['id']
  else:
   assert a['roofTriangles']==b['roofTriangles']and a['bounds']==b['bounds']
   assert a['roofFile']==b['roofFile']and a['collisionFile']==b['collisionFile']
result={'status':'PASS: exact survey roofs, open volume sides, slender supports and bounded neighbour-safe retirement','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':rec['sourceSha256'],'generatorSha256':rec['generatorSha256'],'buildings':results,'unchangedPreviousTiles':len(m['tiles'])-3 if args.baseline else None,'visualAcceptance':False,'qualification':'Glass blending, under-canopy walking, source-fragment cleanup and native appearance require runtime evidence.'}
(out/'atom-ei-canopies-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

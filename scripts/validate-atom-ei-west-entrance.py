#!/usr/bin/env python3
"""Verify surveyed roof fidelity, open approach, glazing placement and preservation."""
import argparse,ast,hashlib,json,math,struct,sys
from pathlib import Path
import numpy as np
import rasterio,mapbox_earcut
from pyproj import Transformer
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from exterior_physics_i import nearby_surveys,survey_plan
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');rec=m['architecture']['atomEiWestEntrance'];spec=read(root/'minecraft/exterior'/rec['sourceFile']);derived=read(out/rec['derivedFile'])
for path,key in [(root/'minecraft/exterior'/rec['sourceFile'],'sourceSha256'),(root/rec['generatorFile'],'generatorSha256'),(root/'minecraft/exterior'/rec['referenceFile'],'referenceSha256'),(out/rec['derivedFile'],'derivedSha256'),(out/rec['meshFile'],'meshSha256')]:assert sha(path)==rec[key],path
sources=read(root/'minecraft/exterior/sources.json')
for item,name in zip(sources['lod2'],['campus-east.gml','campus-west.gml']):assert sha(root/'.cache'/name)==item['sha256']
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc');ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer,'mapbox_earcut':mapbox_earcut};exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'datum','exec'),ctx)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='triangulate');exec(compile(ast.Module(body=[fn],type_ignores=[]),'triangulate','exec'),ctx);mc=ctx['mc'];surveys=dict(nearby_surveys(root/'.cache',spec['siteBoundsUTM']));foot,walls,roof,points=survey_plan(ctx,surveys[spec['building']]);mainFoot=survey_plan(ctx,surveys[spec['mainBuilding']])[0]
raw=(out/rec['meshFile']).read_bytes();assert struct.unpack_from('<i3d',raw,4)==(4,0,0,0);offset=32;parts=[];normalErrors=[]
for part in range(4):
 count,w,h=struct.unpack_from('<iii',raw,offset);offset+=16;v=np.frombuffer(raw,dtype='<f4',count=count*5,offset=offset).reshape(-1,5).astype(float);offset+=count*20+w*h*4;assert np.isfinite(v).all()and count%3==0 and count>0
 tri=v[:,:3].reshape(-1,3,3);assert np.min(np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1))>1e-9
 if part!=3:
  uv=v[:,3:].reshape(-1,3,2);assert np.array_equal(uv[:,0],uv[:,1])and np.array_equal(uv[:,0],uv[:,2]);assert ((uv>=0)&(uv<=1)).all();octa=uv[:,0]*2-1;n=np.column_stack([octa[:,0],1-np.abs(octa).sum(1),octa[:,1]]);lower=n[:,1]<0;n[np.ix_(lower,[0,2])]=(1-np.abs(n[np.ix_(lower,[2,0])]))*np.where(n[np.ix_(lower,[0,2])]>=0,1,-1);n/=np.linalg.norm(n,axis=1)[:,None];error=np.max(np.abs(np.sum((tri[:,1:]-tri[:,:1])*n[:,None,:],axis=2)));assert error<.00005;normalErrors.append(float(error))
 parts.append(v)
assert offset==len(raw)
assert np.array_equal(parts[0][:,:3].astype(np.float32),roof[:,3:6].astype(np.float32)), 'Survey roof triangles changed'
assert len(parts[0])==30
roof_bottom=points[:,1].max()-spec['roofThicknessMetres']-spec['ribDepthMetres']-.001
assert parts[1][:,1].min()>roof_bottom, 'Soffit or ribs intrude into open approach'
# All low geometry belongs to exterior glazing immediately beside the main
# body, not to the former outer volume enclosure.
max_gap=max(mainFoot.boundary.distance(Point(v[[0,2]]))for part in parts[2:]for v in part)
assert max_gap<.12,('Glazing no longer follows main base',max_gap)
assert parts[2][:,1].max()<points[:,1].min()+3.1 and parts[3][:,1].max()<points[:,1].min()+3.1
# Independently project exported panes onto each measured facade plane.
# Full backing behind raised frames prevents oblique views exposing brick.
glass_backing_area = 0.0
for face in derived['glazingFaces']:
 anchor=np.asarray(face['anchor']);direction=np.asarray(face['direction']);normal=np.asarray(face['normal']);projected=[]
 for tri in parts[3][:,:3].reshape(-1,3,3):
  delta=tri-anchor
  if np.max(np.abs(delta@normal))<.00005:
   projected.append(Polygon(np.column_stack([delta@direction,tri[:,1]])))
 from shapely.geometry import box
 expected=box(0,face['bottom'],face['length'],face['top']);coverage=unary_union(projected)
 assert expected.symmetric_difference(coverage).area<.0002, 'Glazing backing has holes behind raised frames'
 glass_backing_area+=expected.area
# Verify each new walking target against the declared encoded terrain tile,
# instead of assuming that a nearby terrain-guide sample has the same ID.
probe_plan=root/'minecraft/exterior/checks/atom-ei-west-entrance.json'
verified_probe_surfaces=0
for control in read(probe_plan)['gravityProbes']:
 if not control.get('westEntrance'):continue
 terrain=next(t for t in m['tiles'] if t['runtimeId']==control['tile'])
 b=(out/terrain['file']).read_bytes();nparts,*anchor=struct.unpack_from('<i3d',b,4);offset=32;found=False
 for part in range(nparts):
  count,w,h=struct.unpack_from('<iii',b,offset);offset+=16
  vertices=np.frombuffer(b,dtype='<f4',count=count*5,offset=offset).reshape(-1,5)[:,:3]+anchor;offset+=count*20+w*h*4
  if part!=control['part']:continue
  x,y,z=control['target']
  for tri in vertices.reshape(-1,3,3):
   a,bv,c=tri;matrix=np.column_stack([(bv-a)[[0,2]],(c-a)[[0,2]]])
   if abs(np.linalg.det(matrix))<1e-9:continue
   u,v=np.linalg.solve(matrix,np.array([x,z])-a[[0,2]])
   if u>=-1e-6 and v>=-1e-6 and u+v<=1+1e-6:
    height=a[1]+u*(bv[1]-a[1])+v*(c[1]-a[1])
    found |= abs(height-y)<.0001
 assert found, ('Walking target is not on declared rendered terrain',control['label'])
 verified_probe_surfaces+=1
assert verified_probe_surfaces==6
seam_ids=set(spec['reconstructedSeamNeighbours'])
assert seam_ids=={'DEBY_LOD2_108698338','DEBY_LOD2_108698340'}
canopies=read(out/m['architecture']['atomEiCanopies']['derivedFile'])['buildings']
for bid in seam_ids:
 c=next(c for c in canopies if c['building']==bid);assert sha(out/c['meshFile'])==c['meshSha256'];assert c['retiredCollisionFile'] not in [t['file']for t in m['photoFacades']['collisionTiles']]
protect=unary_union([survey_plan(ctx,s)[0]for bid,s in surveys.items()if bid not in {spec['building'],spec['mainBuilding']}|seam_ids])
owned=unary_union([Polygon(p['ring'],p['holes'])for p in derived['retirement']]);assert owned.intersection(protect).area<1e-8
assert owned.difference(foot.buffer(spec['cleanupMarginMetres'])).area<1e-8, 'Retirement escaped bounded west projection'
plans=read(out/'photo-facades.json')['plans'];plan=next(p for p in plans if p['id']==spec['building']);assert plan['manualRoof']and plan['completeEnvelope']and all(w['reconstructed']for w in plan['walls']);assert rec['retiredCollisionFile']not in [t['file']for t in m['photoFacades']['collisionTiles']]
tile=next(t for t in m['tiles']if t['runtimeId']==spec['runtimeId']);assert tile['fineCollisionMaterials']==[4,4,4,4]
previous_count=None
if args.baseline:
 before=read(args.baseline/'manifest.json');assert before['tiles']==m['tiles'][:-1];previous_count=len(before['tiles'])
 names={t['file']for t in before['tiles']}|set(before['photoFacades']['roofFiles'])|{t['file']for t in before['photoFacades']['collisionTiles']}
 for name in names:assert sha(args.baseline/name)==sha(out/name),name
 oldplans=read(args.baseline/'photo-facades.json')['plans'];assert len(oldplans)==len(plans)
 for old,new in zip(oldplans,plans):
  if old['id']!=spec['building']:assert old==new,old['id']
  else:assert old['roofTriangles']==new['roofTriangles']and old['bounds']==new['bounds']
result={'status':'PASS: exact surveyed roof; low geometry confined to main-base glazing; open projected volume; protected neighbours and retained inputs','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':rec['sourceSha256'],'generatorSha256':rec['generatorSha256'],'meshSha256':rec['meshSha256'],'exactRoofTriangles':10,'frameNormalMaximumResidualMetres':max(normalErrors),'maximumGlazingDistanceFromMainBaseMetres':max_gap,'verifiedProbeSurfaces':verified_probe_surfaces,'probePlanSha256':sha(probe_plan),'continuousGlassBackingSquareMetres':glass_backing_area,'falseVolumeWallsRetired':len(walls),'protectedNeighbourOverlapSquareMetres':owned.intersection(protect).area,'previousRenderTilesUnchanged':previous_count,'visualAcceptance':False,'qualification':'Source registration of the photographed entrance is inferred. Native appearance, open approach collision and reflections require separate verification.'}
(out/'atom-ei-west-entrance-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

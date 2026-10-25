#!/usr/bin/env python3
"""Independently verify the encoded FRM II envelope against the pinned survey."""
import argparse,ast,hashlib,json,math,struct,sys
from pathlib import Path
from collections import Counter
import numpy as np
import rasterio,mapbox_earcut
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from exterior_physics_i import nearby_surveys,survey_plan
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');record=m['architecture']['reactorExterior'];spec=read(root/'minecraft/exterior'/record['sourceFile']);derived=read(out/record['derivedFile'])
for p,key in [(root/'minecraft/exterior'/record['sourceFile'],'sourceSha256'),(root/record['generatorFile'],'generatorSha256'),(root/'minecraft/exterior'/record['referenceFile'],'referenceSha256'),(out/record['derivedFile'],'derivedSha256'),(out/record['meshFile'],'meshSha256'),(out/record['roofFile'],'roofSha256')]:assert sha(p)==record[key],p
for entry,name in zip(read(root/'minecraft/exterior/sources.json')['lod2'],['campus-east.gml','campus-west.gml']):assert sha(root/'.cache'/name)==entry['sha256']==derived['surveyHashes'][name]
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc')
ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer,'mapbox_earcut':mapbox_earcut}
exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'frame','exec'),ctx)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='triangulate');exec(compile(ast.Module(body=[fn],type_ignores=[]),'triangulate','exec'),ctx);mc=ctx['mc']
surveys=nearby_surveys(root/'.cache',spec['siteBoundsUTM']);surfaces=next(s for bid,s in surveys if bid==spec['building']);foot,walls,roof,points=survey_plan(ctx,surfaces)
raw=(out/record['meshFile']).read_bytes();assert struct.unpack_from('<i3d',raw,4)==(7,0,0,0)
parts=[];areas=[];offset=32
for i in range(7):
 count,w,h=struct.unpack_from('<iii',raw,offset);offset+=16
 p=np.frombuffer(raw,dtype='<f4',count=count*5,offset=offset).reshape(-1,5).astype(float);offset+=count*20+w*h*4
 assert count>0 and count%3==0 and np.isfinite(p).all()
 q=p[:,:3].reshape(-1,3,3);area=np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1)*.5
 assert area.min()>1e-9,(i,area.min());areas.append(float(area.sum()));parts.append(p)
assert offset==len(raw)
# Check every raw roof observation against encoded geometry, not a reported fit.
barrel=parts[0][:,:3];tree=cKDTree(barrel)
observed=np.unique(np.concatenate([r[0]for i,(k,r)in enumerate(surfaces)if i in spec['barrelRoofSurfaceIndices']]),axis=0)
errors,_=tree.query(mc(observed));assert errors.max()<spec['sourceVertexToleranceMetres'],errors.max()
q=barrel.reshape(-1,3,3)
edges=Counter(tuple(sorted((tuple(t[i]),tuple(t[(i+1)%3]))))for t in q for i in range(3))
assert set(edges.values())<={1,2},'Non-manifold roof mesh'
# Boundary edges must all lie on a loft end or eave; no dropped tiny interior
# triangles are allowed to turn into cracks after float32 encoding.
end_observations=[mc(np.asarray(p))for p in derived['endPointsUTM']]
boundary=np.asarray([e for e,count in edges.items()if count==1]);unexpected=[]
for a,b in boundary:
 centre=(a+b)/2
 end_distance=min(abs((centre-end[0])@np.array([.9855,0,.1697]))for end in end_observations)
 # End profiles have a centimetre-scale surveyed skew; eaves are at 501.94m DHHN.
 eave=abs(centre[1]-np.min(mc(observed)[:,1]))<.02
 if not eave and end_distance>.06:unexpected.append(centre.tolist())
assert not unexpected,('Interior barrel boundary',unexpected[:3],len(unexpected))
# Encoded smooth normals must agree with winding.
oct=parts[0][:,3:5]*2-1;n=np.column_stack([oct[:,0],1-np.abs(oct).sum(1),oct[:,1]]);negative=n[:,1]<0
assert not negative.any();n/=np.linalg.norm(n,axis=1)[:,None]
assert np.min(np.sum(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0])*n.reshape(-1,3,3).mean(1),axis=1))>0
lower=[s for i,s in enumerate(surfaces)if s[0]=='RoofSurface'and i not in spec['barrelRoofSurfaceIndices']and i not in spec['rooflightSurfaceIndices']]
_,_,low_roof,_=survey_plan(ctx,lower)
assert np.array_equal(low_roof[:,3:6].astype(np.float32),parts[5][:,:3].astype(np.float32))
owned=unary_union([Polygon(p['ring'],p['holes'])for p in derived['retirement']]);neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys if bid!=spec['building']for k,r in s if k=='GroundSurface'])
assert owned.intersection(neighbours).area<1e-8
plans=read(out/'photo-facades.json')['plans'];plan=next(p for p in plans if p['id']==spec['building']);assert len(plan['walls'])==55 and all(w['reconstructed']for w in plan['walls']) and plan['manualRoof'] and plan['completeEnvelope']
assert len(derived['facades'])==55 and len(derived['wallAdjustments'])==5
assert len({t['runtimeId']for t in m['tiles']})==len(m['tiles'])
datum=next(s for s in m['supplementalSurfaces']if s['name']=='reactor-envelope-datum');assert datum['name']=='reactor-envelope-datum' and datum['rings']==derived['datumRings'] and not datum['outdoorReconstructed']
assert unary_union([Polygon(p['ring'],p['holes'])for p in datum['rings']]).intersection(neighbours).area<1e-8
assert sha(root/'.cache/campus-dgm-east.tif')==derived['datumSourceSha256']
assert derived['datumSourceSha256']==read(root/'minecraft/exterior/sources.json')['dgm1'][1]['sha256']
from scipy.ndimage import map_coordinates
lat,lon=np.radians(m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]))
basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
guide=np.asarray(datum['terrainGuide']['points']);flat=guide.copy();flat[:,1]=64
inverse=Transformer.from_crs(4978,25832,always_xy=True);en=np.column_stack(inverse.transform(*((flat-[0,64,0])@basis+origin).T))[:,:2]
with rasterio.open(root/'.cache/campus-dgm-east.tif')as dem:
 c,r=(~dem.transform)*(en[:,0],en[:,1]);height=map_coordinates(dem.read(1).astype(float),[r-.5,c-.5],order=1,prefilter=False)
expected=mc(np.column_stack([en,height]))[:,1];datum_error=float(np.max(abs(expected-guide[:,1])));assert datum_error<.001

plan_file=root/'minecraft/exterior/checks/reactor-exterior.json';inspection=read(plan_file)
all_footprints=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys for k,r in s if k=='GroundSurface'])
new_routes=[p for p in inspection['gravityProbes']if p.get('reactorExterior')]
for probe in new_routes:
 x,y,z=probe['target'];assert all_footprints.distance(Point(x,z))>.3,('Walking probe in building',probe['label'])
assert len(new_routes)>=3
unchanged=None
if args.baseline:
 before=read(args.baseline/'manifest.json');assert m['tiles'][:-1]==before['tiles'];assert read(args.baseline/'photo-facades.json')['plans']==plans[:-1]
 for t in before['tiles']:assert sha(args.baseline/t['file'])==sha(out/t['file']),t['file']
 for k,v in before['architecture'].items():assert m['architecture'][k]==v,k
 for k,v in before.items():
  if k not in ['architecture','tiles','photoFacades','supplementalSurfaces']:assert m[k]==v,k
 assert m['supplementalSurfaces'][:-1]==before['supplementalSurfaces']
 unchanged=len(before['tiles'])
result={'status':'PASS: encoded measured barrel, retained lower roof, complete exterior and protected neighbours','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':record['sourceSha256'],'meshSha256':record['meshSha256'],'roofSha256':record['roofSha256'],'observedBarrelVertices':len(observed),'maximumEncodedVertexErrorMetres':float(errors.max()),'barrelTriangles':len(q),'barrelBoundaryEdges':len(boundary),'retainedLowerRoofTriangles':len(low_roof)//3,'partAreasSquareMetres':areas,'completeSurveyWalls':55,'curvedGablesClosed':5,'maximumDatumGuideResidualMetres':datum_error,'protectedNeighbourOverlapSquareMetres':owned.intersection(neighbours).area,'priorRenderTilesUnchanged':unchanged,'inspectionPlanSha256':sha(plan_file),'outdoorNorthWestRoutes':len(new_routes),'visualAcceptance':False,'qualification':'Geometry checks do not establish facade accuracy or visual acceptance; native walking and image review remain required.'}
(out/'reactor-exterior-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

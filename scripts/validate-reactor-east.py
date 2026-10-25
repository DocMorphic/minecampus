#!/usr/bin/env python3
"""Check the encoded east-hall envelope, exact roof and neighboring preservation."""
import argparse,ast,hashlib,json,math,struct,sys
from pathlib import Path
import numpy as np
import rasterio,mapbox_earcut
from pyproj import Transformer
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from scipy.ndimage import map_coordinates
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from exterior_physics_i import nearby_surveys,survey_plan,roof_texture
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');record=m['architecture']['reactorEast'];spec=read(root/'minecraft/exterior'/record['sourceFile']);derived=read(out/record['derivedFile'])
for p,key in [(root/'minecraft/exterior'/record['sourceFile'],'sourceSha256'),(root/record['generatorFile'],'generatorSha256'),(root/'minecraft/exterior'/record['referenceFile'],'referenceSha256'),(out/record['derivedFile'],'derivedSha256'),(out/record['meshFile'],'meshSha256'),(out/record['roofFile'],'roofSha256')]:assert sha(p)==record[key],p
for entry,name in zip(read(root/'minecraft/exterior/sources.json')['lod2'],['campus-east.gml','campus-west.gml']):assert sha(root/'.cache'/name)==entry['sha256']
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc');ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer,'mapbox_earcut':mapbox_earcut};exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'frame','exec'),ctx);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='triangulate');exec(compile(ast.Module(body=[fn],type_ignores=[]),'triangulate','exec'),ctx);mc=ctx['mc']
surveys=nearby_surveys(root/'.cache',spec['siteBoundsUTM']);surfaces=next(s for bid,s in surveys if bid==spec['building']);foot,walls,roof,points=survey_plan(ctx,surfaces)
def decode(path):
 raw=path.read_bytes();assert raw[:4]==b'ECT1';count,*anchor=struct.unpack_from('<i3d',raw,4);assert anchor==[0,0,0];offset=32;parts=[];pixels=[]
 for i in range(count):
  n,w,h=struct.unpack_from('<3i',raw,offset);offset+=16;p=np.frombuffer(raw,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);offset+=n*20;tex=raw[offset:offset+w*h*4];offset+=w*h*4
  assert n>0 and n%3==0 and np.isfinite(p).all();assert (p[:,3:]>=0).all()and(p[:,3:]<=1).all();q=p[:,:3].reshape(-1,3,3);assert np.min(np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1))>1e-9;parts.append(p);pixels.append((w,h,tex))
 assert offset==len(raw);return parts,pixels
parts,pixels=decode(out/record['meshFile']);assert len(parts)==6
roof_parts,roof_pixels=decode(out/record['roofFile']);expected,texture=roof_texture(root/'.cache',roof)
assert len(roof)//3==67 and np.array_equal(expected.astype(np.float32),parts[4].astype(np.float32));assert np.array_equal(parts[4],roof_parts[0]);assert pixels[4]==roof_pixels[0];assert pixels[4]==(*texture.size,texture.convert('RGBA').tobytes())
all_triangles=np.concatenate([parts[i][:,:3].reshape(-1,3,3)for i in [0,2,3,5]]);n=np.cross(all_triangles[:,1]-all_triangles[:,0],all_triangles[:,2]-all_triangles[:,0]);n/=np.linalg.norm(n,axis=1)[:,None];errors=[]
for index,wall in enumerate(walls):
 anchor,direction,normal=[np.asarray(wall[k])for k in ('anchor','direction','normal')];region=Polygon(wall['rings'][0],wall['rings'][1:]);distance=(all_triangles-anchor)@normal
 selected=all_triangles[(n@normal>.999)&(np.max(np.abs(distance),axis=1)<spec['windowRecessMetres']+.025)]
 projected=[Polygon(np.column_stack([(q-anchor)@direction,q[:,1]])).intersection(region)for q in selected];coverage=unary_union(projected);error=region.difference(coverage).area;errors.append(error);assert error<.006,(index,error)
 assert abs(sum(derived['facades'][index][k]for k in ['opaqueArea','glassArea','plinthArea','doorArea'])-region.area)<1e-5
assert len(walls)==44 and len(derived['facades'])==44
owned=unary_union([Polygon(p['ring'],p['holes'])for p in derived['retirement']]);neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys if bid!=spec['building']for k,r in s if k=='GroundSurface']);protected=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys if bid!=spec['building'] and bid not in spec['reconstructedNeighbourIds'] for k,r in s if k=='GroundSurface']);assert owned.intersection(protected).area<1e-8
assert spec['reconstructedNeighbourIds']==['DEBY_LOD2_5323135'] and 'reactorExterior' in m['architecture']
assert owned.equals(foot.buffer(spec['cleanupMarginMetres']).difference(protected.buffer(spec['neighbourGuardMetres'])))
plans=read(out/'photo-facades.json')['plans'];plan=next(p for p in plans if p['id']==spec['building']);assert len(plan['walls'])==44 and all(w['reconstructed']for w in plan['walls'])and plan['manualRoof']and plan['completeEnvelope'];assert np.array_equal(np.asarray(plan['roofTriangles']),roof[:,3:6].reshape(-1,3,3))
datum=next(s for s in m['supplementalSurfaces']if s['name']=='reactor-east-envelope-datum');assert not datum['outdoorReconstructed'];assert unary_union([Polygon(p['ring'],p['holes'])for p in datum['rings']]).intersection(neighbours).area<1e-8
assert sha(root/'.cache/campus-dgm-east.tif')==derived['datumSourceSha256']==read(root/'minecraft/exterior/sources.json')['dgm1'][1]['sha256']
lat,lon=np.radians(m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]]);guide=np.asarray(datum['terrainGuide']['points']);flat=guide.copy();flat[:,1]=64;inverse=Transformer.from_crs(4978,25832,always_xy=True);en=np.column_stack(inverse.transform(*((flat-[0,64,0])@basis+origin).T))[:,:2]
with rasterio.open(root/'.cache/campus-dgm-east.tif')as dem:
 c,r=(~dem.transform)*(en[:,0],en[:,1]);h=map_coordinates(dem.read(1).astype(float),[r-.5,c-.5],order=1,prefilter=False)
datum_error=float(np.max(np.abs(mc(np.column_stack([en,h]))[:,1]-guide[:,1])));assert datum_error<.001
inspection=read(root/'minecraft/exterior/checks/reactor-east.json');retained=read(root/'minecraft/exterior/checks/reactor-exterior.json')
assert inspection['cameras'][:len(retained['cameras'])]==retained['cameras'] and inspection['gravityProbes'][:len(retained['gravityProbes'])]==retained['gravityProbes']
all_feet=foot.union(neighbours);routes=[p for p in inspection['gravityProbes']if p.get('reactorEast')];assert len(routes)==5
for probe in routes:
 x,y,z=probe['target'];assert all_feet.distance(Point(x,z))>.3,probe['label']
 tile=next(t for t in m['tiles']if t['runtimeId']==probe['tile']);assert tile['kind']=='ground'
 terrain,_=decode(out/tile['file']);hits=[]
 for q in terrain[probe['part']][:,:3].reshape(-1,3,3):
  poly=Polygon(q[:,[0,2]])
  if poly.area>1e-8 and poly.covers(Point(x,z)):
   weights=np.linalg.solve(np.vstack([q[:,0],q[:,2],np.ones(3)]),[x,z,1]);hits.append(float(weights@q[:,1]))
 assert hits and abs(max(hits)-probe['supportHeight'])<.001,probe['label']
unchanged=None
if args.baseline:
 before=read(args.baseline/'manifest.json');assert m['tiles'][:-1]==before['tiles'];assert read(args.baseline/'photo-facades.json')['plans']==plans[:-1]
 for t in before['tiles']:assert sha(args.baseline/t['file'])==sha(out/t['file']),t['file']
 for k,v in before['architecture'].items():assert m['architecture'][k]==v,k
 assert m['supplementalSurfaces'][:-1]==before['supplementalSurfaces'];unchanged=len(before['tiles'])
result={'status':'PASS: complete encoded survey envelope, exact roof imagery and protected neighbours','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':record['sourceSha256'],'meshSha256':record['meshSha256'],'roofSha256':record['roofSha256'],'completeSurveyWalls':44,'retainedRoofTriangles':67,'maximumUncoveredWallSquareMetres':max(errors),'maximumDatumResidualMetres':datum_error,'protectedNeighbourOverlapSquareMetres':owned.intersection(protected).area,'reconstructedNeighbourOverlapSquareMetres':owned.intersection(neighbours).area,'priorRenderTilesUnchanged':unchanged,'newVerifiedGroundRoutes':len(routes),'inspectionPlanSha256':sha(root/'minecraft/exterior/checks/reactor-east.json'),'visualAcceptance':False}
(out/'reactor-east-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

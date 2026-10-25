#!/usr/bin/env python3
"""Check the bounded Galileo grade against its prior mesh and pinned source DEM."""
import argparse,ast,hashlib,json,math,struct,sys
from pathlib import Path
import numpy as np,rasterio,mapbox_earcut
from scipy.ndimage import map_coordinates
from pyproj import Transformer
from shapely import points,distance,intersects
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior')
p.add_argument('--baseline',required=True,type=Path)
args=p.parse_args();out=args.directory;before=args.baseline
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');old=read(before/'manifest.json');rec=m['galileoEastGrading'];source=root/'minecraft/exterior';spec=read(source/rec['sourceFile'])
for path,key in [(source/rec['sourceFile'],'sourceSha256'),(root/rec['generatorFile'],'generatorSha256'),(root/rec['rampGeneratorFile'],'rampGeneratorSha256'),(source/rec['referenceFile'],'referenceSha256')]:assert sha(path)==rec[key],path
reference=read(source/spec['reference'])
for name,value in reference['sourceFiles'].items():assert sha(root/'.cache'/name)==value,name
controls=reference['controls'];patch=spec['patches'][0]
xy=np.array([c['utm']for c in controls]);heights=np.array([c['heightDHHN2016']for c in controls]);design=np.column_stack((xy-patch['originUtm'],np.ones(len(xy))));fit=np.linalg.lstsq(design,heights,rcond=None)[0]
np.testing.assert_allclose(fit,patch['planeCoefficients'],rtol=0,atol=1e-10)
assert np.max(abs(design@fit-heights))<.17 and np.linalg.norm(fit[:2])<.005
entries={t['file']:t for t in m['tiles']};previous={t['file']:t for t in old['tiles']};assert set(previous)<=set(entries)
changed=[name for name in previous if sha(out/name)!=sha(before/name)]
assert set(changed)=={'ground-698300-5349200.ect','ground-698300-5349300.ect','vegetation-4-2.ect','galileo-east-ramps.ect'},changed

def decode(path):
 raw=path.read_bytes();assert raw[:4]==b'ECT1';count,*anchor=struct.unpack_from('<i3d',raw,4);off=32;parts=[]
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',raw,off);off+=16;v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=off).reshape(-1,5).astype(float);v[:,:3]+=anchor;off+=n*20;pixels=raw[off:off+w*h*4];off+=w*h*4;parts.append((v,pixels))
 assert off==len(raw);return parts
# Reuse only the established geodetic coordinate transform; independently
# calculate expected source heights, grade weights and neighbour exclusions.
tree=ast.parse((root/'scripts/build-exterior.py').read_text());start=next(i for i,n in enumerate(tree.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ORIGIN'for t in n.targets));stop=next(i for i,n in enumerate(tree.body[start:],start)if isinstance(n,ast.FunctionDef)and n.name=='mc')
ctx={'ROOT':root,'CACHE':root/'.cache','np':np,'math':math,'rasterio':rasterio,'Transformer':Transformer,'mapbox_earcut':mapbox_earcut}
exec(compile(ast.Module(body=tree.body[start:stop+1],type_ignores=[]),'frame','exec'),ctx)
poly=Polygon(patch['footprintUtm']);surveys=nearby_surveys(root/'.cache',[698250,5349200,698400,5349400]);neighbours=unary_union([Polygon(rings[0][:,:2],[h[:,:2]for h in rings[1:]]).buffer(0)for bid,surfaces in surveys if bid not in spec['ownBuildings']for kind,rings in surfaces if kind=='GroundSurface']).buffer(spec['neighbourExclusionMetres'])
errors=[];outside=0;maximum_outside=0;changed_vertices=0
with rasterio.open(root/'.cache/campus-dgm-east.tif')as dem:
 raster=dem.read(1).astype(float)
 for name in [n for n in changed if n.startswith('ground-')]:
  (a,ap),(b,bp)=decode(before/name)[0],decode(out/name)[0]
  assert a.shape==b.shape and ap==bp,'Ground texture or topology changed: '+name
  np.testing.assert_allclose(a[:,3:],b[:,3:],rtol=0,atol=3e-6)
  e,north=map(int,Path(name).stem.split('-')[1:]);xy=np.column_stack((e+100*b[:,3],north+100-100*b[:,4]))
  # Original raster-centre vertices are authoritative samples. Cut-edge points
  # interpolate these triangles and may extend one cell beyond the grade collar.
  grid=(abs(np.mod(xy[:,0],1)-.5)<.0001)&(abs(np.mod(xy[:,1],1)-.5)<.0001)
  sample=np.round(xy[grid]*2)/2;actual=b[grid,:3]
  col,row=(~dem.transform)*(sample[:,0],sample[:,1]);h=map_coordinates(raster,[row-.5,col-.5],order=1,prefilter=False)
  locations=points(sample);t=np.clip(distance(locations,poly)/patch['blendMetres'],0,1);weight=1-t*t*(3-2*t);weight[intersects(locations,neighbours)]=0
  target=(sample-patch['originUtm'])@fit[:2]+fit[2];h+=weight*(target-h)
  expected=ctx['mc'](np.column_stack((sample,h)));errors.extend(np.max(abs(expected-actual),axis=1).tolist())
  mask=abs(b[:,1]-a[:,1])>1e-5;changed_vertices+=int(mask.sum());dist=distance(points(xy[mask]),poly.buffer(patch['blendMetres']))
  assert np.max(dist)<1.42,'Change beyond one terrain-cell interpolation support'
  outside+=int((dist>.001).sum());maximum_outside=max(maximum_outside,float(np.max(dist)))
assert errors and max(errors)<.001,max(errors)
# Finished-grade changes must not move the existing ramps or fill their floors.
a=decode(before/'galileo-east-ramps.ect');b=decode(out/'galileo-east-ramps.ect')
for part in [1,2]:assert np.array_equal(a[part][0],b[part][0]) and a[part][1]==b[part][1]
for part in range(4):assert a[part][1]==b[part][1]
assert old['architecture']['galileoRamps']['ramps']==m['architecture']['galileoRamps']['ramps']
assert entries['galileo-east-ramps.ect']['collisionHeightfieldParts']==[1,3]
for t in b[1][0][:,:3].reshape(-1,3,3):
 centre=t.mean(0);found=[q for q in m['terrainOverrides']if 'plane'in q and Polygon(q['ring']).buffer(1e-6).covers(Point(centre[0],centre[2]))]
 assert any(abs(np.dot(q['plane'],[centre[0],centre[2],1])-centre[1])<.0001 for q in found)
for (a,ap),(b,bp)in zip(decode(before/'vegetation-4-2.ect'),decode(out/'vegetation-4-2.ect')):
 assert a.shape==b.shape and ap==bp;np.testing.assert_allclose(a,b,rtol=0,atol=.001)
assert old['groundSurfaces']['maskSha256']==m['groundSurfaces']['maskSha256'],'Unrelated material frame moved'
assert old['buildings']==m['buildings'],'Surveyed building geometry changed'
report={'status':'PASS: bounded inferred grade, unchanged ramp floors/portals and stable material boundaries','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':rec['sourceSha256'],'generatorSha256':rec['generatorSha256'],'referenceSha256':rec['referenceSha256'],'changedMeshes':changed,'unchangedMeshes':len(previous)-len(changed),'laterMeshesOutsideGradeCheck':sorted(set(entries)-set(previous)),'tileSha256':{n:sha(out/n)for n in changed},'sourceControlMaximumResidualMetres':float(np.max(abs(design@fit-heights))),'rasterCentreSamples':len(errors),'maximumEncodedSourceErrorMetres':max(errors),'changedGroundVertexRecords':changed_vertices,'cutEdgeVerticesBeyondGradeCollar':outside,'maximumInterpolationReachBeyondCollarMetres':maximum_outside,'rampFloorsAndPortalBoundariesUnchanged':True,'groundTexturesAndMaterialMaskUnchanged':True,'nativeVisualAcceptance':False}
(out/'galileo-east-grade-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

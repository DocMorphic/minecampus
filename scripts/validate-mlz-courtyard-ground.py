#!/usr/bin/env python3
"""Verify bounded courtyard materials against original BVV imagery and native rays."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from PIL import Image
from shapely.geometry import Polygon,Point,shape
from shapely.ops import transform,unary_union
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from exterior_mlz_courtyard_ground import regions
parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--baseline',type=Path);args=parser.parse_args();out=args.directory
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
m=read(out/'manifest.json');rec=m['architecture']['mlzCourtyardGround'];source=root/'minecraft/exterior';spec=read(source/rec['sourceFile'])
for path,key in [(source/rec['sourceFile'],'sourceSha256'),(root/rec['generatorFile'],'generatorSha256'),(source/rec['referenceFile'],'referenceSha256'),(out/rec['derivedFile'],'derivedSha256'),(source/'assets/textures/campus/ground_surfaces.png','maskSha256')]:assert sha(path)==rec[key],path
for name,digest in rec['materialHashes'].items():assert sha(source/'assets/textures/campus'/name)==digest
assert rec['maskSha256']==m['groundSurfaces']['maskSha256']
spec,polygons,to_world,residual=regions(root,m);world={k:transform(to_world,p)for k,p in polygons.items()};domain=unary_union(list(world.values()))
footprints=unary_union([Polygon(np.asarray(r)[:,[0,2]]).buffer(0)for b in m['buildings']for r in b['grounds']])
assert domain.intersection(footprints).area<1e-5
assert abs(sum(p.area for p in world.values())-domain.area)<1e-5
mask=np.asarray(Image.open(source/'assets/textures/campus/ground_surfaces.png'));samples=[]
for control in spec['nativeControls']:
 x,z=control['positionMC'];kind=control['material'];assert world[kind].contains(Point(x,z))
 rgb=mask[int((256-z)/672*4096),int((x+352)/672*4096),:3].tolist();assert rgb=={'asphalt':[0,0,255],'grass':[255,0,0],'paving':[0,255,0]}[kind]
 samples.append({'label':control['label'],'positionMC':[x,z],'channelsRGB':rgb})
source_dop=root/'.cache/campus-dop-east.tif';dop=next(x for x in read(source/'sources.json')['dop20']if x['sha256']==sha(source_dop));assert dop
changed={};tiles={t['file']:t for t in m['tiles']}
with rasterio.open(source_dop)as raster:
 for name,info in rec['tiles'].items():
  path=out/name;data=path.read_bytes();assert sha(path)==info['sha256'];assert struct.unpack_from('<i3d',data,4)==(1,0,0,0)
  n,w,h=struct.unpack_from('<3i',data,32);offset=48+n*20;assert hashlib.sha256(data[:offset]).hexdigest()==info['geometryAndUVSha256']
  _,e,north=Path(name).stem.split('-');e,north=int(e),int(north)
  original=raster.read(window=from_bounds(e,north,e+100,north+100,transform=raster.transform))[:3].transpose(1,2,0)
  pixels=np.frombuffer(data,dtype='uint8',offset=offset).reshape(h,w,4)
  assert original.shape==(h,w,3)
  rows,cols=np.where(np.any(pixels[:,:,:3]!=original,axis=2));changed[name]=len(rows)
  # A touched 20 cm texel must intersect the declared domain, allowing its half diagonal.
  utm_domain=unary_union(list(polygons.values())).buffer(.142)
  from shapely import contains_xy
  assert np.all(contains_xy(utm_domain,e+(cols+.5)*.2,north+100-(rows+.5)*.2)),name
  if args.baseline:
   old=(args.baseline/name).read_bytes();assert old[:offset]==data[:offset],name+' geometry changed'
   assert hashlib.sha256(old).hexdigest()==info['beforeSha256']
assert set(changed)=={'ground-698300-5349300.ect','ground-698400-5349300.ect'}
result={'status':'PASS: raw source imagery retained outside bounded courtyard; building exclusions, mask controls and provenance verified','manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':rec['sourceSha256'],'generatorSha256':rec['generatorSha256'],'maskSha256':rec['maskSha256'],'tileSha256':{name:sha(out/name)for name in changed},'changedPixelsAgainstRawDOP':changed,'buildingOverlapSquareMetres':domain.intersection(footprints).area,'samples':samples,'baselineGeometryAndUVComparison':bool(args.baseline),'visualAcceptance':False}
(out/'mlz-courtyard-ground-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

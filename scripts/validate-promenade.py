#!/usr/bin/env python3
"""Validate inferred promenade surfaces; optional prior-build preservation proof."""
import argparse,hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import shape,Polygon,box,Point
from shapely.ops import transform,unary_union
root=Path(__file__).resolve().parents[1];out=root/'dist-minecraft/exterior'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path);args=p.parse_args()
m=json.loads((out/'manifest.json').read_text());s=m['groundSurfaces']['promenade']
for f,k in [(root/'minecraft/exterior/promenade-paths.json','sourceSha256'),(out/'promenade-surfaces.geojson','derivedSha256')]:assert hashlib.sha256(f.read_bytes()).hexdigest()==s[k]
to_utm=Transformer.from_crs(4326,25832,always_xy=True).transform
features=json.loads((out/'promenade-surfaces.geojson').read_text())['features'];polys=[transform(to_utm,shape(f['geometry']))for f in features];new=unary_union(polys)
assert len(features)==4 and sum(p.area for p in polys)-new.area<1e-5
previous=[]
for f in [root/'minecraft/exterior/ground-surfaces.geojson',out/'path-surfaces.geojson',out/'cos-site-surfaces.geojson',out/'grs-courtyard-surfaces.geojson']:
 previous.extend(transform(to_utm,shape(e['geometry']))for e in json.loads(f.read_text())['features'])
assert new.intersection(unary_union(previous)).area<1e-5
ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'};footprints=[]
for name in ['campus-west.gml','campus-east.gml']:
 for p in ET.parse(root/'.cache'/name).findall('.//b:GroundSurface//g:Polygon',ns):
  rings=[np.array(list(map(float,r.text.split()))).reshape(-1,3)[:,:2] for r in p.findall('.//g:LinearRing/g:posList',ns)]
  if rings:footprints.append(Polygon(rings[0],rings[1:]).buffer(0))
padding=s['texturePaddingInsideFootprintsMetres']
assert padding==.20 and new.intersection(unary_union(footprints).buffer(-padding)).area<1e-5
assert new.difference(box(*m['boundsUtm'])).area<1e-5
mask=np.array(Image.open(root/'minecraft/exterior/assets/textures/campus/ground_surfaces.png'))
controls=[(30275349,5.515,15.875),(32458178,62.714,-23.075),(386192514,60.228,-90.700),(617369303,35.228,-76.411),(32458178,82.148982,-97.193730),(32458178,81.967341,-96.261060),(32458178,81.596075,-94.214627)]
for way,x,z in controls:assert mask[int((256-z)/672*4096),int((x+352)/672*4096)].tolist()==[0,0,255,255],way
result={'status':'PASS: four bounded asphalt corridors and native controls; prior material areas excluded; footprint intrusion limited to the documented texture margin','surfaceAreaSquareMetres':new.area,'textureMarginInsideFootprintsMetres':padding,'controlsMC':[{'osmWay':w,'x':x,'z':z}for w,x,z in controls]}
if args.baseline:
 old=np.array(Image.open(args.baseline/'ground_surfaces.png'));changed=np.any(old!=mask,axis=2)
 boundary=np.zeros(changed.shape,dtype=bool)
 for axis in [0,1]:
  for step in [-1,1]:boundary|=np.any(old!=np.roll(old,step,axis=axis),axis=2)
 # One neighbouring texel covers the old binary raster's polygon boundary.
 band=boundary.copy()
 for dy in [-1,0,1]:
  for dx in [-1,0,1]:band|=np.roll(np.roll(boundary,dy,axis=0),dx,axis=1)
 # A subpixel gap can be absent from the old binary raster altogether.
 # Verify those newly visible boundaries against the vector source itself.
 extra=changed&~band&(np.any(old!=[0,0,0,255],axis=2)|(mask[:,:,0]>0)|(mask[:,:,1]>0)|(mask[:,:,3]!=255))
 bounds=m['boundsUtm'];middle=np.array([(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2]);q=np.array(m['terrainGuide']['points'])
 uv=np.array([(e-middle[0],n-middle[1],1)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)])
 coeff=np.linalg.lstsq(uv,q[:,[0,2]],rcond=None)[0];assert np.max(np.abs(uv@coeff-q[:,[0,2]]))<.03
 inverse=np.linalg.inv(np.vstack((coeff.T,[0,0,1])));edges=unary_union([p.boundary for p in previous]);distances=[]
 for row,col in zip(*np.where(extra)):
  x=(col+.5)/4096*672-352;z=256-(row+.5)/4096*672;e,n=np.array([x,z,1])@inverse[:2,:].T+middle
  distance=Point(e,n).distance(edges);assert distance<.15,(x,z,distance);distances.append(distance)
 band|=extra
 interior_changes=changed&~band
 assert np.all(old[interior_changes]==[0,0,0,255])
 assert np.all(mask[interior_changes][:,[0,1,3]]==[0,0,255]) and np.all(mask[interior_changes][:,2]>0)
 prior=json.loads((args.baseline/'manifest.json').read_text())
 for key in ['tiles','buildings','terrainGuide','terrainSampling','siteGrading','surfaceGuide','photoFacades','protectedFootprints','protectionGrid','vegetation','architecture']:assert m[key]==prior[key],key
 inventory=json.loads((args.baseline/'inventory.json').read_text());tiles=[t['file']for t in m['tiles']]
 for f in tiles:assert hashlib.sha256((out/f).read_bytes()).hexdigest()==inventory[f],f
 result['preservation']={'changedPixels':int(changed.sum()),'changedPixelsNearPriorBoundaries':int((changed&band).sum()),'asphaltPixelsAwayFromPriorRasterBoundaries':int(interior_changes.sum()),'subpixelVectorBoundaryChecks':len(distances),'maximumSubpixelBoundaryDistanceMetres':max(distances,default=0),'existingMaterialInteriorsUnchanged':True,'changesToExistingMaterialsConfinedToEdgeCoverage':True,'unchangedRenderTiles':len(tiles),'unchangedTerrainArchitectureFacadeAndVegetationGuides':True}
(out/'promenade-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

#!/usr/bin/env python3
"""Check mapped material alignment and court exclusions against public controls.
Run with the geodata Python environment after build-exterior.py.
This checks data placement, not rendered visual quality.
"""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
from shapely.geometry import shape,box
from shapely.ops import transform
from pyproj import Transformer
root=Path(__file__).resolve().parents[1];out=root/'dist-minecraft/exterior'
m=json.loads((out/'manifest.json').read_text());spec=m['groundSurfaces']
source=root/'minecraft/exterior/ground-surfaces.geojson';mask=root/'minecraft/exterior/assets/textures/campus/ground_surfaces.png'
assert hashlib.sha256(source.read_bytes()).hexdigest()==spec['sourceSha256']
assert hashlib.sha256(mask.read_bytes()).hexdigest()==spec['maskSha256']
a=np.array(Image.open(mask));assert a.shape==(4096,4096,4)
q=np.array(m['terrainGuide']['points']);bounds=m['boundsUtm'];middle=np.array([(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2])
uv=np.array([(e-middle[0],n-middle[1],1)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)])
coeff=np.linalg.lstsq(uv,q[:,[0,2]],rcond=None)[0]
assert np.max(np.abs(uv@coeff-q[:,[0,2]]))<.03
samples=[]
def check(name,x,z,expected):
 row=int((256-z)/672*4096);col=int((x+352)/672*4096);got=a[row,col,:3].tolist()
 assert got==expected,(name,got,expected)
 samples.append({'name':name,'positionMC':[round(x,3),round(z,3)],'channelsRGB':got})
# First point is the fixed native approach ray's surveyed terrain hit.
check('Mensa bank terrain hit',11.612,-231.731,[255,0,0])
check('MW mapped paving',25,-125,[0,255,0])
check('Southern mapped asphalt',-32,122,[0,0,255])
toUtm=Transformer.from_crs(4326,25832,always_xy=True)
for feature in json.loads(source.read_text())['features']:
 tags=feature['properties']['tags']
 if tags.get('leisure')!='pitch':continue
 polygon=transform(toUtm.transform,shape(feature['geometry'])).intersection(box(*bounds));point=polygon.representative_point()
 x,z=np.array([point.x-middle[0],point.y-middle[1],1])@coeff
 check(tags['sport']+' '+str(feature['properties']['osmWay']),x,z,[0,0,0])
result={'status':'PASS: ground material alignment and mapped court exclusions','samples':samples}
(out/'ground-surfaces-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

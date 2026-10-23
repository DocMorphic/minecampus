#!/usr/bin/env python3
"""Check mapped material alignment and court exclusions against public controls.
Run with the geodata Python environment after build-exterior.py.
This checks data placement, not rendered visual quality.
"""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
from shapely.geometry import shape,box,Polygon
from shapely.ops import transform,unary_union
from pyproj import Transformer
root=Path(__file__).resolve().parents[1];out=root/'dist-minecraft/exterior'
m=json.loads((out/'manifest.json').read_text());spec=m['groundSurfaces']
source=root/'minecraft/exterior/ground-surfaces.geojson';mask=root/'minecraft/exterior/assets/textures/campus/ground_surfaces.png'
assert hashlib.sha256(source.read_bytes()).hexdigest()==spec['sourceSha256']
assert hashlib.sha256(mask.read_bytes()).hexdigest()==spec['maskSha256']
for path,key in [(root/'minecraft/exterior/path-widths.json','sourceSha256'),(out/'path-surfaces.geojson','derivedSha256')]:
 assert hashlib.sha256(path.read_bytes()).hexdigest()==spec['paths'][key]
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
# Controls independently projected from explicit-width source lines and points
# beyond their half-widths; the narrow western path borders an existing lawn.
check('Boltzmann road centre (330587895)',34.464,-97.081,[0,0,255])
check('Beyond Boltzmann road width',31.022,-97.715,[0,0,0])
check('Eastern footway centre (983606070)',107.705,-168.459,[0,0,255])
check('Beyond eastern footway width',107.455,-166.980,[0,0,0])
check('Western paving path centre (1289405426)',-294.368,-253.750,[0,255,0])
check('Western path adjacent lawn',-294.638,-252.275,[255,0,0])
toUtm=Transformer.from_crs(4326,25832,always_xy=True)
paths=unary_union([transform(toUtm.transform,shape(f['geometry'])) for f in json.loads((out/'path-surfaces.geojson').read_text())['features']])
mapped=unary_union([transform(toUtm.transform,shape(f['geometry'])) for f in json.loads(source.read_text())['features']])
overlap=paths.intersection(mapped).area
assert overlap<.001,('Width-derived paths cover existing mapped areas',overlap)
for feature in json.loads(source.read_text())['features']:
 tags=feature['properties']['tags']
 if tags.get('leisure')!='pitch':continue
 polygon=transform(toUtm.transform,shape(feature['geometry'])).intersection(box(*bounds));point=polygon.representative_point()
 x,z=np.array([point.x-middle[0],point.y-middle[1],1])@coeff
 check(tags['sport']+' '+str(feature['properties']['osmWay']),x,z,[0,0,0])
site=spec['cosSite']
for path,key in [(root/'minecraft/exterior/cos-site.json','sourceSha256'),(out/'cos-site-surfaces.geojson','derivedSha256')]:
 assert hashlib.sha256(path.read_bytes()).hexdigest()==site[key]
features=json.loads((out/'cos-site-surfaces.geojson').read_text())['features']
polygons=[transform(toUtm.transform,shape(f['geometry'])) for f in features]
site_union=unary_union(polygons)
site_overlap=site_union.intersection(mapped.union(paths)).area
assert site_overlap<.001,('COS paving covers existing mapped materials',site_overlap)
assert sum(p.area for p in polygons)-site_union.area<.001,'COS surface patches overlap'
assert site_union.intersection(Polygon(m['siteGrading']['footprintUtm'])).area<.001,'COS paving crosses building footprint'
for feature,polygon in zip(features,polygons):
 point=polygon.representative_point()
 x,z=np.array([point.x-middle[0],point.y-middle[1],1])@coeff
 check('COS '+str(feature['properties']['osmWay']),x,z,[0,255,0]if feature['properties']['material']=='paving'else[0,0,255])
result={'cosSiteOverlapSquareMetres':site_overlap,'cosSiteSurfacePatches':len(features),'status':'PASS: ground material alignment, explicit-width edges and mapped-area exclusions','pathOverlapWithMappedAreasSquareMetres':overlap,'samples':samples}
(out/'ground-surfaces-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

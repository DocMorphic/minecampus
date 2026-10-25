#!/usr/bin/env python3
"""Check reactor material provenance, source boundaries and independent projection."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, LineString, shape, box
from shapely.ops import unary_union
from shapely import contains_xy, prepare
from exterior_physics_i import nearby_surveys

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior')
out = p.parse_args().directory; src = root/'minecraft/exterior'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
m = read(out/'manifest.json'); rec = m['architecture']['reactorGroundMaterials']
for key,folder in [('source',src),('research',src),('generator',root),('mask',src),('derived',out)]:
    assert sha(folder/rec[key+'File']) == rec[key+'Sha256'], key
spec = read(src/rec['sourceFile']); research = read(src/rec['researchFile'])
assert spec['researchSha256'] == rec['researchSha256']
sources = read(src/'sources.json')
for entry,filename in zip(sources['lod2'],['campus-east.gml','campus-west.gml']):
    assert sha(root/'.cache'/filename) == entry['sha256']
# Reconstruct classification independently from the pinned source, not the atlas.
limit = box(*spec['boundsUTM'])
footprints = unary_union([Polygon(rings[0][:,:2],[h[:,:2] for h in rings[1:]]).buffer(0)
    for _,surfaces in nearby_surveys(root/'.cache',limit.bounds) for kind,rings in surfaces if kind=='GroundSurface'])
records = research['mappedFeatures']
grass = unary_union([shape(f['geometryUTM']) for f in records if f['tags'].get('landuse')=='grass']).intersection(limit).difference(footprints)
expected = {'grass':grass,'paving':[],'asphalt':[]}
for f in records:
    tags = f['tags']; g = shape(f['geometryUTM']); highway = tags.get('highway')
    if highway not in ('service','footway','path') or tags.get('surface') in ('grass','dirt','unpaved','fine_gravel'):continue
    if g.geom_type=='Polygon' and tags.get('area')!='yes':g=LineString(g.exterior.coords)
    if g.geom_type!='LineString':continue
    width = float(tags.get('width',spec['estimatedWidthsMetres'][highway]))
    kind = 'asphalt' if tags.get('surface') in ('asphalt','chipseal') else spec['untaggedMaterial']
    expected[kind].append(g.buffer(width*.5,cap_style=2,join_style=2).intersection(limit).difference(footprints).difference(grass))
expected['paving'].append(Polygon(spec['parkingApronUTM']).intersection(limit).difference(footprints).difference(grass))
expected['asphalt']=unary_union(expected['asphalt'])
expected['paving']=unary_union(expected['paving']).difference(expected['asphalt'])
features=read(out/rec['derivedFile'])['features']; layers={f['properties']['material']:shape(f['geometry']) for f in features}
assert set(layers)==set(expected)
for name,region in layers.items():
    assert region.symmetric_difference(expected[name]).area < 1e-6, name
    assert region.intersection(footprints).area < 1e-6
    assert region.difference(limit).area < 1e-6
    assert abs(region.area-rec['areaSquareMetres'][name]) < 1e-6
    for other in layers:
        if name!=other:assert region.intersection(layers[other]).area < 1e-6
# Independent ECEF -> UTM inverse, with 2cm exclusion at classification edges.
lat,lon=map(math.radians,m['origin'][:2])
origin=np.asarray(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]))
basis=np.asarray([[-math.sin(lon),math.cos(lon),0],[math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)],[math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
inv=Transformer.from_crs(4978,25832,always_xy=True)
im=np.asarray(Image.open(src/rec['maskFile'])); width,height=rec['maskSize'];assert im.shape==(height,width,4)
(left,bottom),(right,top)=rec['maskBoundsMC']; step=(right-left)/width
rows,cols=np.mgrid[3:height:8,3:width:8]; x=left+(cols.ravel()+.5)*step; z=top-(rows.ravel()+.5)*step
xyz=np.column_stack([x,np.zeros_like(x),z])@basis+origin; E,N,_=inv.transform(*xyz.T)
checked=0
for channel,name in enumerate(('grass','paving','asphalt')):
    inner,outer=layers[name].buffer(-.02),layers[name].buffer(.02);prepare(inner);prepare(outer)
    inside=contains_xy(inner,E,N);outside=~contains_xy(outer,E,N);actual=im[rows.ravel(),cols.ravel(),channel]>127
    assert actual[inside].all(), (name,'missing pixels')
    assert not actual[outside].any(), (name,'outside source')
    checked+=int((inside|outside).sum())
b=spec['boundsUTM'];edge=np.minimum.reduce([E-b[0],b[2]-E,N-b[1],b[3]-N]);t=np.clip(edge/spec['boundaryBlendMetres'],0,1)
expected_alpha=t*t*(3-2*t)*255;actual_alpha=im[rows.ravel(),cols.ravel(),3]
assert np.max(np.abs(actual_alpha-expected_alpha))<1.0
mapping=(src/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED REACTOR GROUND MAPPING\n')[1].split('// END GENERATED REACTOR GROUND MAPPING')[0]
assert hashlib.sha256(mapping.encode()).hexdigest()==rec['shaderMappingSha256']
shader=read(src/'shaders/campus_ground.json');assert len(shader['samplers'])==12
assert next(v for v in shader['uniforms'] if v['name']=='ReactorGroundTexture')['values']==[13]
result={'status':'PASS: source classification, building exclusion, atlas projection and bounded fade',
    'manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)),
    'maskSha256':rec['maskSha256'],'classifiedSamplesChecked':checked,'alphaSamplesChecked':len(x),
    'maximumAlphaError':float(np.max(np.abs(actual_alpha-expected_alpha))),
    'qualification':'Material/source validation; native appearance acceptance is separate.'}
(out/'reactor-ground-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

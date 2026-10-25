#!/usr/bin/env python3
"""Independently verify the shared northern material field and source scope."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union
from shapely import contains_xy, prepare
from exterior_physics_i import nearby_surveys

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--directory', type=Path, default=root/'dist-minecraft/exterior')
out = p.parse_args().directory
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
m = read(out/'manifest.json'); rec = m['northGroundMaterials']; src = root/'minecraft/exterior'
for key, folder in [('generator', root), ('classificationGenerator', root), ('source', src), ('previousDerived', out), ('derived', out), ('mask', src)]:
    assert sha(folder/rec[key+'File']) == rec[key+'Sha256'], key
for file, digest in rec['coverageFiles'].items(): assert sha(out/file) == digest
spec = read(src/rec['sourceFile'])
for entry in spec['landscape']['osm']: assert sha(src/entry['sourceFile']) == entry['sha256']
sources = read(src/'sources.json')
for kind, filename in [('dop20','campus-dop-east.tif'), ('dgm1','campus-dgm-east.tif')]:
    assert sha(root/'.cache'/filename) == sorted(sources[kind], key=lambda x:x['name'])[1]['sha256']
for entry, filename in zip(sources['lod2'], ['campus-east.gml', 'campus-west.gml']): assert sha(root/'.cache'/filename) == entry['sha256']
for entry in read(src/'vegetation-sources.json')['inputs']:
    if entry['cachePath'].endswith('32698_5349_20_DOM.tif'): assert sha(root/'.cache'/entry['cachePath']) == entry['sha256']
assert sha(root/'.cache/de_bkg_gcg2016.tif') == sources['geoid']['sha256']
features = read(out/rec['derivedFile'])['features']; previous = read(out/rec['previousDerivedFile'])['features']
assert features[:len(previous)] == previous
areas = [shape(read(out/file)['ground']) for file in rec['coverageFiles']]
area = unary_union(areas); extension = area.difference(areas[0])
footprints = unary_union([Polygon(rings[0][:,:2], [h[:,:2] for h in rings[1:]]).buffer(0)
    for _, surfaces in nearby_surveys(root/'.cache', area.bounds) for kind, rings in surfaces if kind=='GroundSurface'])
for f in features[len(previous):]:
    assert f['properties']['source'] == 'OSM', 'Do not restore rejected raster lawn islands'
    region = shape(f['geometry']); assert region.difference(extension).area < 1e-6
    assert region.intersection(footprints).area < 1e-6
layers = {kind: unary_union([shape(f['geometry']) for f in features if f['properties']['material']==kind]) for kind in ('grass','gravel','asphalt')}
layers['grass'] = layers['grass'].difference(layers['asphalt'])
layers['gravel'] = layers['gravel'].difference(layers['asphalt']).difference(layers['grass'])
for kind, region in layers.items(): assert abs(region.area-rec['materialAreasSquareMetres'][kind]) < 1e-6
# Evaluate every pixel centre using an independently formed ENU inverse. The
# tiny tangent-plane height error is bounded by omitting centres within 2cm of
# vector boundaries. This checks axis direction, scale and channel assignment.
lat, lon = map(math.radians, m['origin'][:2])
origin = np.asarray(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]))
basis = np.asarray([[-math.sin(lon),math.cos(lon),0], [math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)], [math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
inv = Transformer.from_crs(4978,25832,always_xy=True)
image = np.asarray(Image.open(src/rec['maskFile'])); size = rec['maskSize']
assert image.shape == (size,size,4) and (image[:,:,3]==255).all()
(left,bottom),(right,top) = rec['maskBoundsMC']; step = (right-left)/size
checked = 0
# Deterministic 1-in-8 grid over the full atlas, rather than only feature points.
rows, cols = np.mgrid[3:size:8,3:size:8]; x = left+(cols.ravel()+.5)*step; z = top-(rows.ravel()+.5)*step
xyz = np.column_stack([x,np.full_like(x,0),z])@basis+origin
E,N,_ = inv.transform(*xyz.T)
for channel, kind in enumerate(('grass','gravel','asphalt')):
    region = layers[kind]
    inner_region, outer_region = region.buffer(-.02), region.buffer(.02)
    prepare(inner_region); prepare(outer_region)
    inner = contains_xy(inner_region,E,N); outer = contains_xy(outer_region,E,N)
    actual = image[rows.ravel(),cols.ravel(),channel] > 127
    assert np.all(actual[inner]), (kind,'missing classified pixels')
    assert not actual[~outer].any(), (kind,'classification outside source polygons')
    checked += int((inner | ~outer).sum())
source = (src/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED NORTH GROUND MAPPING\n')[1].split('// END GENERATED NORTH GROUND MAPPING')[0]
assert hashlib.sha256(source.encode()).hexdigest()==rec['shaderMappingSha256']
expected_ids = {t['runtimeId'] for t in m['tiles'] if 1000060400<=t.get('runtimeId',0)<1000060800}
assert set(rec['groundTileIds'])==expected_ids
result={'status':'PASS: preserved prior classification, bounded additions outside buildings, pinned inputs and independent atlas projection',
    'manifestSha256':sha(out/'manifest.json'),'validatorSha256':sha(Path(__file__)), 'maskSha256':rec['maskSha256'],
    'classifiedSamplesChecked':checked,'groundTiles':len(expected_ids),'preservedFeatures':len(previous),'addedFeatures':len(features)-len(previous),
    'qualification':'Source and material-map verification; native visual acceptance is separate.'}
(out/'north-ground-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

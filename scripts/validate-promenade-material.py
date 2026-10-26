#!/usr/bin/env python3
"""Bind clean asphalt to the existing mapped corridors and shared shaders."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, shape
from shapely.ops import transform, unary_union
from shapely import contains_xy, prepare
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'minecraft/exterior'
DATA = ROOT / 'dist-minecraft/exterior'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
spec = json.loads((SOURCE / 'promenade-material.json').read_text())
manifest = json.loads((DATA / 'manifest.json').read_text())
frame = manifest['groundMaterialFrame']
assert hashlib.sha256(json.dumps(frame, sort_keys=True).encode()).hexdigest() == spec['groundFrameSha256']
assert sha(SOURCE / spec['material']) == spec['materialSha256']
assert spec['heightRangeMC'] == [58, 70]
assert 0 < spec['edgeBlendMetres'] <= .05
assert spec['asphaltMetresPerRepeat'] == 4
assert .5 <= spec['albedoMultiplier'] <= 1
to_utm = Transformer.from_crs(4326, 25832, always_xy=True).transform
expected = {}
for source, record in spec['sources'].items():
    previous = manifest['groundSurfaces'][record['manifestKey']]
    assert previous['sourceFile'] == source
    assert sha(SOURCE / source) == record['sourceSha256'] == previous['sourceSha256']
    assert sha(DATA / record['derivedFile']) == record['derivedSha256'] == previous['derivedSha256']
    document = json.loads((SOURCE / source).read_text())
    assert sha(DATA / 'campus-orthophoto.jpg') == document['orthophotoSha256']
    for feature in json.loads((DATA / record['derivedFile']).read_text())['features']:
        assert feature['properties']['material'] == feature['properties']['tags']['surface'] == 'asphalt'
        geometry = transform(to_utm, shape(feature['geometry']))
        parts = [geometry] if geometry.geom_type == 'Polygon' else list(geometry.geoms)
        for i, polygon in enumerate(parts):
            assert not polygon.interiors
            points = np.array(polygon.exterior.coords)[:-1] - frame['originUtm']
            projected = np.column_stack([points, np.ones(len(points))]) @ frame['fit']
            expected[(source, feature['properties']['osmWay'], i)] = Polygon(projected)
actual = {}
for region in spec['regions']:
    key = (region['sourceFile'], region['osmWay'], region['part'])
    assert key not in actual
    polygon = Polygon(region['polygonMC'])
    assert polygon.is_valid and polygon.area > 0
    assert polygon.equals_exact(expected[key], tolerance=1e-7), key
    actual[key] = polygon
assert actual.keys() == expected.keys()
domain = unary_union(list(actual.values()))
footprints = unary_union([Polygon(np.asarray(r)[:, [0, 2]]).buffer(0)
                         for b in manifest['buildings'] for r in b['grounds']])
# The existing source permits a 20 cm material margin under facades, not new
# interiors. Exact source-domain equality above prevents expanding that margin.
assert domain.intersection(footprints.buffer(-.205)).area < 1e-5
assert sha(SOURCE / spec['maskFile']) == spec['maskSha256']
pixels = np.asarray(Image.open(SOURCE / spec['maskFile']).convert('L'))
width, height = spec['maskSize']
assert pixels.shape == (height, width)
x0, z0, x1, z1 = spec['maskBoundsMC']
dx, dz = (x1-x0)/width, (z1-z0)/height
# Independently reproduce the existing ground-atlas blue-channel lookup.
assert spec['coverageMethod'] == 'existing-atlas-blue-channel'
assert sha(SOURCE/spec['coverageSource']) == spec['coverageSourceSha256'] == manifest['groundSurfaces']['maskSha256']
blue = np.asarray(Image.open(SOURCE/spec['coverageSource']).convert('RGBA'))[:,:,2]
sx0, sz0, sx1, sz1 = spec['coverageSourceBoundsMC']
assert [sx0, sz0, sx1, sz1] == [-352, -416, 320, 256]
# Pillow EXTENT maps destination pixel centres to source pixel centres.
xs = ((x0+(np.arange(width)+.5)*dx-sx0)/(sx1-sx0)*blue.shape[1])-.5
zs = ((sz1-(z1-(np.arange(height)+.5)*dz))/(sz1-sz0)*blue.shape[0])-.5
ix=np.floor(xs).astype(int); iz=np.floor(zs).astype(int)
fx=xs-ix; fz=zs-iz
expected_pixels=(blue[iz[:,None],ix[None,:]]*(1-fx)[None,:]*(1-fz)[:,None]
 +blue[iz[:,None],(ix+1)[None,:]]*fx[None,:]*(1-fz)[:,None]
 +blue[(iz+1)[:,None],ix[None,:]]*(1-fx)[None,:]*fz[:,None]
 +blue[(iz+1)[:,None],(ix+1)[None,:]]*fx[None,:]*fz[:,None])
assert np.max(np.abs(pixels.astype(float)-expected_pixels)) <= 1.01
mask_area = float(pixels.sum(dtype=np.float64)/255*dx*dz)
binding = (SOURCE / 'client/CampusMaterials.java').read_text()
assert 'material.safeGetUniform("PromenadeTexture").set(14);' in binding
for name in ['campus_ground.json', 'campus_reflection.json']:
    uniforms = json.loads((SOURCE/'shaders'/name).read_text())['uniforms']
    assert next(u for u in uniforms if u['name']=='PromenadeTexture')['values'] == [14]
subprocess.run([sys.executable, str(ROOT / 'scripts/build-promenade-material.py'), '--check'], check=True)
main = (SOURCE / 'shaders/campus_ground.fsh').read_text()
reflection = (SOURCE / 'shaders/campus_reflection.fsh').read_text()
assert 'if(abs(MaterialDetail-1.0)<.1||physicsGround)' in main
assert 'if(SurveyedGround>.5)' in reflection
for text in [main, reflection]:
    assert 'float promenade=promenadeCoverage(worldPosition);' in text
    assert 'promenadeAlbedo(worldPosition)' in text
result = {'status': 'PASS: existing rendered asphalt atlas coverage, pinned sources and shared albedo',
          'coverageMethod': spec['coverageMethod'], 'contextPolygons': len(actual), 'ways': len({k[1] for k in actual}),
          'areaSquareMetres': domain.area, 'buildingOverlapSquareMetres': domain.intersection(footprints).area,
          'maskAreaSquareMetres': mask_area, 'maskPixelSizeMetres': [dx, dz],
          'maskSha256': spec['maskSha256'],
          'bindingSha256': sha(SOURCE/'client/CampusMaterials.java'),
          'shaderDefinitionHashes': {n:sha(SOURCE/'shaders'/n) for n in ['campus_ground.json','campus_reflection.json']},
          'sourceSha256': sha(SOURCE / 'promenade-material.json'),
          'generatorSha256': sha(ROOT / 'scripts/build-promenade-material.py'),
          'validatorSha256': sha(Path(__file__)),
          'manifestSha256': sha(DATA / 'manifest.json'),
          'shaderHashes': {n: sha(SOURCE / 'shaders' / n) for n in ['campus_ground.fsh', 'campus_reflection.fsh']},
          'nativeVisualAcceptance': False}
(DATA / 'promenade-material-validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

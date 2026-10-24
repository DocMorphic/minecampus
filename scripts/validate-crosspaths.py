#!/usr/bin/env python3
"""Check crossing material extents against source geometry and the prior package."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box, shape
from shapely.ops import transform, unary_union

root = Path(__file__).resolve().parents[1]
out = root / 'dist-minecraft/exterior'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', type=Path, required=True)
args = parser.parse_args()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = read(out / 'manifest.json')
spec = read(root / 'minecraft/exterior/crosspaths.json')
stats = manifest['groundSurfaces']['crosspaths']
assert sha(root / 'minecraft/exterior/crosspaths.json') == stats['sourceSha256']
assert sha(out / 'crosspath-surfaces.geojson') == stats['derivedSha256']
to_utm = Transformer.from_crs(4326, 25832, always_xy=True).transform
features = read(out / 'crosspath-surfaces.geojson')['features']
assert {f['properties']['osmWay'] for f in features} == {w['osmWay'] for w in spec['ways']}
polys = [transform(to_utm, shape(f['geometry'])) for f in features]
union = unary_union(polys)
assert len(polys) == 8 and all(p.is_valid and p.area > 1 for p in polys)
assert sum(p.area for p in polys) - union.area < 1e-5
assert union.difference(box(*manifest['boundsUtm'])).area < 1e-5
prior = []
for p in [root / 'minecraft/exterior/ground-surfaces.geojson', *[out / n for n in [
        'path-surfaces.geojson', 'cos-site-surfaces.geojson', 'grs-courtyard-surfaces.geojson', 'promenade-surfaces.geojson']]]:
    prior += [transform(to_utm, shape(f['geometry'])) for f in read(p)['features']]
assert union.intersection(unary_union(prior)).area < 1e-5
ns = {'g': 'http://www.opengis.net/gml', 'b': 'http://www.opengis.net/citygml/building/1.0'}
footprints = []
for name in ['campus-west.gml', 'campus-east.gml']:
    for p in ET.parse(root / '.cache' / name).findall('.//b:GroundSurface//g:Polygon', ns):
        rings = [np.array(list(map(float, r.text.split()))).reshape(-1, 3)[:, :2]
                 for r in p.findall('.//g:LinearRing/g:posList', ns)]
        if rings:
            footprints.append(Polygon(rings[0], rings[1:]).buffer(0))
assert stats['texturePaddingInsideFootprintsMetres'] == 0
assert union.intersection(unary_union(footprints)).area < 1e-5

mask = np.array(Image.open(root / 'minecraft/exterior/assets/textures/campus/ground_surfaces.png'))
old = np.array(Image.open(args.baseline / 'ground_surfaces.png'))
assert np.array_equal(mask[:, :, [0, 1, 3]], old[:, :, [0, 1, 3]])
assert np.all(mask[:, :, 2] >= old[:, :, 2])
changed = mask[:, :, 2] != old[:, :, 2]
assert changed.any()
# Independently fit the survey-to-game frame, then bound every changed texel.
bounds = manifest['boundsUtm']
middle = np.array([(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2])
q = np.array(manifest['terrainGuide']['points'])[:, [0, 2]]
uv = np.array([(e-middle[0], n-middle[1], 1) for n in range(bounds[1], bounds[3]+1, 2)
               for e in range(bounds[0], bounds[2]+1, 2)])
coeff = np.linalg.lstsq(uv, q, rcond=None)[0]
assert np.max(np.abs(uv @ coeff - q)) < .03
def project(e, n, z=None):
    points = np.column_stack((np.asarray(e)-middle[0], np.asarray(n)-middle[1], np.ones_like(e))) @ coeff
    return points[:, 0], points[:, 1]
projected = transform(project, union)
# 0.15 m = half the 0.164 m texel diagonal plus the measured <3 cm frame-fit tolerance.
allowed = rasterize([(projected.buffer(.15), 1)], out_shape=(4096, 4096),
                    transform=from_origin(-352, 256, 672/4096, 672/4096), dtype='uint8') > 0
assert not np.any(changed & ~allowed)
for control in spec['nativeMaterialControls']:
    x, z = control['x'], control['z']
    assert mask[int((256-z)/672*4096), int((x+352)/672*4096)].tolist() == [0, 0, 255, 255], control

before = read(args.baseline / 'manifest.json')
for key in ['tiles', 'buildings', 'terrainGuide', 'terrainSampling', 'siteGrading', 'surfaceGuide',
            'photoFacades', 'protectedFootprints', 'protectionGrid', 'vegetation', 'architecture']:
    assert manifest[key] == before[key], key
assert manifest['groundSurfaces']['promenade'] == before['groundSurfaces']['promenade']
inventory = read(args.baseline / 'inventory.json')
for name in [*[t['file'] for t in manifest['tiles']], 'promenade-surfaces.geojson']:
    assert sha(out / name) == inventory[name], name
report = {'status': 'PASS: eight bounded cross-path additions; prior material channels and all geometry preserved',
          'surfaceAreaSquareMetres': union.area, 'areasSquareMetres': stats['areasSquareMetres'],
          'nativeMaterialControls': spec['nativeMaterialControls'], 'changedMaskPixels': int(changed.sum()),
          'allChangesWithinDerivedCorridors': True, 'grassPavingSoilChannelsByteIdentical': True,
          'existingAsphaltCoverageNeverReduced': True, 'priorPromenadePolygonsByteIdentical': True,
          'unchangedRenderTiles': len(manifest['tiles']), 'surveyedFootprintOverlapSquareMetres': 0}
(out / 'crosspath-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

#!/usr/bin/env python3
"""Check supplemental ground against pinned DGM/DOP, including clipped coverage.

This checks representation of the source rasters, not real-world survey accuracy.
"""
from pathlib import Path
import argparse, hashlib, json, math, struct, xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.windows import Window
from scipy.ndimage import map_coordinates
from pyproj import Transformer
from shapely import polygons, union_all
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=root/'dist-minecraft/exterior')
out = parser.parse_args().directory
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = read(out/'manifest.json')
spec_path = root/'minecraft/exterior/physics-i-5101.json'
spec = read(spec_path)
site = manifest['architecture']['physicsISite']
assert site['sourceSha256'] == sha(spec_path)
extent = box(*spec['site']['boundsUTM'])
sources = read(root/'minecraft/exterior/sources.json')
inputs = list(zip(sources['lod2'], ['campus-east.gml', 'campus-west.gml']))
inputs += [(sorted(sources[kind], key=lambda s: s['name'])[1], filename)
           for kind, filename in [('dgm1', 'campus-dgm-east.tif'), ('dop20', 'campus-dop-east.tif')]]
inputs.append((sources['geoid'], 'de_bkg_gcg2016.tif'))
input_hashes = {}
for source, filename in inputs:
    digest = sha(root/'.cache'/filename)
    assert digest == source['sha256'], 'Source integrity mismatch: '+filename
    input_hashes[filename] = digest

# Read original ground rings, including their holes, independently of the
# generator's neighbourhood filter. Buildings just outside the edge can still
# contribute to its half-metre guard.
ns = {'g': 'http://www.opengis.net/gml', 'b': 'http://www.opengis.net/citygml/building/1.0'}
neighbours = []
for name in ['campus-east.gml', 'campus-west.gml']:
    for building in ET.parse(root/'.cache'/name).findall('.//b:Building', ns):
        if building.get('{'+ns['g']+'}id') == spec['building']:
            continue
        for poly in building.findall('.//b:GroundSurface//g:Polygon', ns):
            rings = [np.asarray(list(map(float, r.find('g:posList', ns).text.split()))).reshape(-1, 3)[:, :2]
                     for r in poly.findall('.//g:LinearRing', ns)]
            shape = Polygon(rings[0], rings[1:]).buffer(0)
            if shape.intersects(extent.buffer(.5)):
                neighbours.append(shape)
expected_area = extent.difference(unary_union(neighbours).buffer(.5))

lat, lon = map(math.radians, manifest['origin'][:2])
zero = np.array(Transformer.from_crs(4979, 4978, always_xy=True).transform(
    manifest['origin'][1], manifest['origin'][0], manifest['origin'][2]))
east = np.array([-math.sin(lon), math.cos(lon), 0])
up = np.array([math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)])
south = np.array([math.sin(lat)*math.cos(lon), math.sin(lat)*math.sin(lon), -math.cos(lat)])
to_geo = Transformer.from_crs(25832, 4258, always_xy=True)
to_ecef = Transformer.from_crs(25832, 4978, always_xy=True)

def sample(raster, values, x, y):
    col, row = (~raster.transform)*(x, y)
    assert np.all((col >= .5) & (row >= .5) & (col <= raster.width-.5) & (row <= raster.height-.5))
    return map_coordinates(values, [row-.5, col-.5], order=1, prefilter=False)

surfaces, seams, hashes = [], {}, {}
count = 0
maximum_error = maximum_seam = 0.0
with rasterio.open(root/'.cache/campus-dgm-east.tif') as dem, \
     rasterio.open(root/'.cache/de_bkg_gcg2016.tif') as geoid, \
     rasterio.open(root/'.cache/campus-dop-east.tif') as photo:
    heights, undulation = dem.read(1).astype(float), geoid.read(1).astype(float)
    for index, (e, n) in enumerate(spec['site']['tileOriginsUTM']):
        name = f'physics-ground-{e}-{n}.ect'
        assert name in site['groundTiles']
        path = out/name
        data = path.read_bytes()
        parts, *anchor = struct.unpack_from('<i3d', data, 4)
        vertices, width, height = struct.unpack_from('<3i', data, 32)
        assert parts == 1 and (width, height) == (200, 200)
        v = np.frombuffer(data, dtype='<f4', count=vertices*5, offset=48).reshape(-1, 5).astype(float)
        xy = np.column_stack([e+v[:, 3]*40, n+40-v[:, 4]*40])
        z = sample(dem, heights, xy[:, 0], xy[:, 1])
        longitude, latitude = to_geo.transform(xy[:, 0], xy[:, 1])
        z += sample(geoid, undulation, longitude, latitude)
        absolute = np.column_stack(to_ecef.transform(xy[:, 0], xy[:, 1], z))-zero
        expected = np.column_stack([absolute@east, absolute@up+64, absolute@south])
        actual = v[:, :3]+anchor
        error = float(np.linalg.norm(actual-expected, axis=1).max())
        assert error < .001, (name, error)
        maximum_error = max(maximum_error, error)
        count += vertices
        surfaces.append(union_all(polygons(xy.reshape(-1, 3, 2)), grid_size=.0001))
        boundary = (v[:, 3] == 0) | (v[:, 3] == 1) | (v[:, 4] == 0) | (v[:, 4] == 1)
        for p, point in zip(xy[boundary], actual[boundary]):
            key = tuple(p.round(4))
            if key in seams:
                maximum_seam = max(maximum_seam, float(np.linalg.norm(point-seams[key])))
            else:
                seams[key] = point
        col, row = (~photo.transform)*(e, n+40)
        rgb = photo.read([1, 2, 3], window=Window(round(col), round(row), 200, 200)).transpose(1, 2, 0)
        rgba = np.dstack([rgb, np.full((200, 200), 255, dtype=np.uint8)])
        assert data[48+vertices*20:] == rgba.tobytes(), 'Ground texture differs from native DOP20 pixels'
        hashes[name] = sha(path)

coverage = union_all(surfaces, grid_size=.0001)
missing = expected_area.difference(coverage).area
excess = coverage.difference(expected_area).area
assert missing < .05 and excess < .05, (missing, excess)
assert maximum_seam < .0001, maximum_seam
result = {'status': 'PASS: supplemental ground matches DGM1/DOP20 and bounded neighbour exclusions',
          'validatorSha256': sha(Path(__file__)), 'inputSha256': input_hashes,
          'manifestSha256': sha(out/'manifest.json'), 'sourceSha256': sha(spec_path),
          'tileSha256': hashes, 'tileCount': len(hashes), 'vertexRecordsChecked': count,
          'maximumSourcePositionErrorMetres': maximum_error, 'maximumTileSeamErrorMetres': maximum_seam,
          'missingCoverageSquareMetres': missing, 'excessCoverageSquareMetres': excess,
          'qualification': 'Source representation accuracy only; not a claim of millimetre real-world survey accuracy.'}
(out/'physics-site-validation.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))

"""One georeferenced material atlas for adjoining northern survey-ground meshes."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import Polygon, shape, mapping
from shapely.ops import unary_union

from exterior_physics_i import nearby_surveys, polygons
from exterior_physics_ii_landscape import classify

SITES = ('physicsII', 'physicsWSI', 'physicsZNN', 'riverbank')


def build(ctx):
    root, cache, out, meta, mc = [ctx[k] for k in ('ROOT', 'CACHE', 'OUT', 'metadata', 'mc')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    records = [meta['architecture'][key] for key in SITES]
    areas = [shape(json.loads((out/record['coverageFile']).read_text())['ground']) for record in records]
    area = unary_union(areas)
    surveys = nearby_surveys(cache, area.bounds)
    footprints = unary_union([Polygon(rings[0][:, :2], [h[:, :2] for h in rings[1:]]).buffer(0)
                              for _, surfaces in surveys for kind, rings in surfaces if kind == 'GroundSurface'])
    spec = json.loads((root/'minecraft/exterior/physics-ii.json').read_text())
    # Preserve the existing classification on Physik II exactly. Only extend its
    # pinned OSM/raster interpretation onto the adjoining reconstructed ground.
    previous = json.loads((out/records[0]['materialDerivedFile']).read_text())['features']
    _, additions, _ = classify(root, cache, spec, area.difference(areas[0]), footprints)
    # Native candidate50 exposed half-metre grass islands around shadowed
    # paving and parked cars. Extend only mapped OSM surfaces; preserve aerial
    # colour and the existing ground grain in unclassified adjoining areas.
    # Prior Physik II features remain unchanged for a bounded comparison.
    additions = [f for f in additions if f['properties']['source'] == 'OSM']
    features = previous + additions
    layers = {kind: unary_union([shape(f['geometry']) for f in features if f['properties']['material'] == kind])
              for kind in ('grass', 'gravel', 'asphalt')}
    layers['grass'] = layers['grass'].difference(layers['asphalt'])
    layers['gravel'] = layers['gravel'].difference(layers['asphalt']).difference(layers['grass'])
    projected = {}
    for kind, region in layers.items():
        def project(ring):
            xy = np.asarray(ring.coords)
            return mc(np.column_stack([xy, np.full(len(xy), 475)]))[:, [0, 2]]
        projected[kind] = [Polygon(project(p.exterior), [project(h) for h in p.interiors]) for p in polygons(region)]
    all_points = np.concatenate([np.asarray(p.exterior.coords) for region in projected.values() for p in region])
    ax = math.floor(all_points[:, 0].min()/16)*16
    az = math.ceil(all_points[:, 1].max()/16)*16
    span = math.ceil(max(all_points[:, 0].max()-ax, az-all_points[:, 1].min())/32)*32
    size = 2048
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[:, :, 3] = 255
    transform = from_origin(ax, az, span/size, span/size)
    for channel, kind in enumerate(('grass', 'gravel', 'asphalt')):
        if projected[kind]:
            pixels[:, :, channel] = rasterize([(p, 255) for p in projected[kind]], out_shape=(size, size), transform=transform, dtype='uint8')
    target = root/'minecraft/exterior/assets/textures/campus/north_ground_surfaces.png'
    Image.fromarray(pixels).save(target, optimize=True)
    derived = out/'north-ground-surfaces.geojson'
    derived.write_text(json.dumps({'type': 'FeatureCollection', 'coordinateSystem': 'EPSG:25832',
        'attribution': '© OpenStreetMap contributors; ©BVV',
        'qualification': 'Shared material classification across existing reconstructed ground. OSM paths/lawns on adjoining ground; prior Physik II low-green inference retained unchanged. New raster lawn inference rejected after native review; no new survey or geometry.',
        'features': features}, separators=(',', ':'))+'\n')
    shader = root/'minecraft/exterior/shaders/campus_ground.fsh'
    text = shader.read_text()
    start, end = '// BEGIN GENERATED NORTH GROUND MAPPING\n', '// END GENERATED NORTH GROUND MAPPING'
    source = f'vec2 northGroundUv(vec2 position) {{ return vec2(position.x-{ax:.1f},{az:.1f}-position.y)/{span:.1f}; }}\n'
    if start not in text:
        text = text.replace('void main() {', start+end+'\nvoid main() {')
    prefix, rest = text.split(start)
    _, suffix = rest.split(end)
    shader.write_text(prefix+start+source+end+suffix)
    meta['northGroundMaterials'] = {
        'generatorFile': 'scripts/exterior_north_ground.py', 'generatorSha256': sha(Path(__file__)),
        'classificationGeneratorFile': 'scripts/exterior_physics_ii_landscape.py',
        'classificationGeneratorSha256': sha(root/'scripts/exterior_physics_ii_landscape.py'),
        'sourceFile': 'physics-ii.json', 'sourceSha256': sha(root/'minecraft/exterior/physics-ii.json'),
        'coverageFiles': {record['coverageFile']: sha(out/record['coverageFile']) for record in records},
        'previousDerivedFile': records[0]['materialDerivedFile'], 'previousDerivedSha256': sha(out/records[0]['materialDerivedFile']),
        'derivedFile': derived.name, 'derivedSha256': sha(derived),
        'maskFile': 'assets/textures/campus/'+target.name, 'maskSha256': sha(target),
        'maskBoundsMC': [[ax, az-span], [ax+span, az]], 'maskSize': size,
        'shaderMappingSha256': hashlib.sha256(source.encode()).hexdigest(),
        'materialAreasSquareMetres': {kind: region.area for kind, region in layers.items()},
        'groundTileIds': [t['runtimeId'] for t in meta['tiles'] if t['file'] in {name for record in records for name in record['groundTiles']}],
    }
    print('Shared northern ground materials:', meta['northGroundMaterials']['materialAreasSquareMetres'], flush=True)

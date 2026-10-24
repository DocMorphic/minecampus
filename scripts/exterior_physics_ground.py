"""Bounded OSM material overlay for Physics ground and its western seam."""
import hashlib
import json
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, box, shape, mapping
from shapely.ops import transform, unary_union
from rasterio.features import rasterize
from rasterio.transform import from_origin
from exterior_physics_i import nearby_surveys, polygons


def build(ctx):
    root, cache, out, meta, mc = [ctx[k] for k in ['ROOT', 'CACHE', 'OUT', 'metadata', 'mc']]
    source = root/'minecraft/exterior/physics-ground-surfaces.geojson'
    data = json.loads(source.read_text())
    site = meta['architecture']['physicsISite']
    bounds = list(site['boundsUTM'])
    bounds[0] -= 20
    limit = box(*bounds)
    to_utm = Transformer.from_crs(4326, 25832, always_xy=True).transform
    to_geo = Transformer.from_crs(25832, 4326, always_xy=True).transform
    buildings = unary_union([
        Polygon(rings[0][:, :2], [h[:, :2] for h in rings[1:]]).buffer(0)
        for _, surfaces in nearby_surveys(cache)
        for kind, rings in surfaces if kind == 'GroundSurface'
    ])
    mapped = []
    for feature in data['features']:
        if feature['properties']['kind'] == 'polygon':
            p = transform(to_utm, shape(feature['geometry'])).buffer(0)
            mapped.append((feature, p.intersection(limit).difference(buildings)))
    # A woodland polygon describes canopy, not the absence of hard paths.
    exclusion = buildings.union(unary_union([p for f, p in mapped
                                             if f['properties']['material'] != 'soil']))
    for feature in data['features']:
        props = feature['properties']
        if props['kind'] != 'path':
            continue
        width = props['widthMetres']
        assert .25 <= width <= 20
        line = transform(to_utm, shape(feature['geometry']))
        p = line.buffer(width/2, cap_style=2, join_style=2).intersection(limit).difference(exclusion)
        mapped.append((feature, p))
    # Resolve intersecting path strips once so material coverage never sums
    # above one. Asphalt takes precedence at joins; mapped lawns were excluded.
    layers = {name: [] for name in ['grass', 'paving', 'asphalt', 'soil']}
    records = []
    for feature, p in mapped:
        if p.is_empty:
            continue
        layers[feature['properties']['material']].append(p)
        records.append({'type': 'Feature', 'properties': feature['properties'],
                        'geometry': mapping(transform(to_geo, p))})
    areas = {name: unary_union(parts) for name, parts in layers.items()}
    areas['paving'] = areas['paving'].difference(areas['asphalt'])
    areas['grass'] = areas['grass'].difference(areas['asphalt'].union(areas['paving']))
    # Preserve more specific grass/path classifications where canopy overlaps.
    areas['soil'] = areas['soil'].difference(unary_union([areas[n] for n in ['grass', 'paving', 'asphalt']]))
    size, span, samples = 2048, 256, 4
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[:, :, 3] = 255
    # Fade only the artificial study boundary, not actual path/lawn edges.
    # A 20 m western overlap carries the material across the old terrain seam.
    basis = mc(np.array([[bounds[0], bounds[1], 475],
                         [bounds[0]+1, bounds[1], 475],
                         [bounds[0], bounds[1]+1, 475]]))[:, [0, 2]]
    inverse = np.linalg.inv(np.column_stack((basis[1]-basis[0], basis[2]-basis[0])))
    corners = mc(np.array([[e,n,475] for e in [bounds[0],bounds[2]] for n in [bounds[1],bounds[3]]]))[:,[0,2]]
    atlas_x = float(np.floor(corners[:,0].min()/16)*16)
    atlas_top = float(np.ceil(corners[:,1].max()/16)*16)
    assert corners[:,0].max() <= atlas_x+span and corners[:,1].min() >= atlas_top-span
    # Generate the geographic blend calculation alongside the atlas. Alpha is
    # now available for soil coverage, matching the original four-class map.
    values = ','.join(f'{v:.10f}' for v in inverse.T.flatten())
    origin = ','.join(f'{v:.10f}' for v in basis[0])
    span_e, span_n = bounds[2]-bounds[0], bounds[3]-bounds[1]
    mapping_source = (f'vec2 physicsGroundUv(vec2 position) {{ return vec2(position.x-{atlas_x:.1f},{atlas_top:.1f}-position.y)/{span:.1f}; }}\n'
        'float physicsGroundBlend(vec2 position) {\n'
        f'    vec2 local=mat2({values})*(position-vec2({origin}));\n'
        f'    float edge=min(min(local.x,{span_e:.1f}-local.x),min(local.y,{span_n:.1f}-local.y));\n'
        '    return smoothstep(0.0,8.0,edge);\n}\n')
    shader = root/'minecraft/exterior/shaders/campus_ground.fsh'
    start, end = '// BEGIN GENERATED PHYSICS GROUND MAPPING\n', '// END GENERATED PHYSICS GROUND MAPPING'
    text = shader.read_text()
    assert text.count(start) == 1 and text.count(end) == 1
    prefix, rest = text.split(start)
    _, suffix = rest.split(end)
    shader.write_text(prefix+start+mapping_source+end+suffix)
    projected = {}
    def ring(coords):
        xy = np.asarray(coords)
        return mc(np.column_stack((xy, np.full(len(xy), 475))))[:, [0, 2]]
    for name, area in areas.items():
        projected[name] = [(Polygon(ring(p.exterior.coords), [ring(h.coords) for h in p.interiors]), 255)
                           for p in polygons(area)]
    for row in range(0, size, 128):
        height = min(128, size-row)
        grid = from_origin(atlas_x, atlas_top-row*span/size, span/size/samples, span/size/samples)
        for channel, name in enumerate(['grass', 'paving', 'asphalt', 'soil']):
            if projected[name]:
                high = rasterize(projected[name], out_shape=(height*samples, size*samples),
                                 transform=grid, dtype='uint8')
                coverage = np.rint(high.reshape(height, samples, size, samples).mean(axis=(1, 3))).astype('uint8')
                pixels[row:row+height, :, channel] = 255-coverage if name == 'soil' else coverage
    target = root/'minecraft/exterior/assets/textures/campus/physics_ground_surfaces.png'
    Image.fromarray(pixels).save(target, optimize=True)
    derived = out/'physics-ground-surfaces.geojson'
    derived.write_text(json.dumps({'type': 'FeatureCollection', 'license': data['license'],
        'attribution': data['attribution'], 'features': records}, separators=(',', ':'))+'\n')
    meta['architecture']['physicsGroundMaterials'] = {
        'sourceFile': source.name, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'maskFile': 'assets/textures/campus/'+target.name,
        'maskSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'derivedFile': derived.name, 'derivedSha256': hashlib.sha256(derived.read_bytes()).hexdigest(),
        'generatorSha256': hashlib.sha256((root/'scripts/exterior_physics_ground.py').read_bytes()).hexdigest(),
        'maskBoundsMC': [[atlas_x, atlas_top-span], [atlas_x+span, atlas_top]], 'maskSize': [size, size],
        'maskChannels': ['grass', 'paving', 'asphalt', 'soil = 1 - alpha'],
        'materialBoundsUTM': bounds, 'westernOverlapMetres': 20, 'boundaryBlendMetres': 8,
        'blendOriginMC': basis[0].tolist(), 'blendMcToLocalUtm': inverse.tolist(),
        'shaderMappingSha256': hashlib.sha256(mapping_source.encode()).hexdigest(),
        'areaSquareMetres': {name: area.area for name, area in areas.items()},
        'buildingOverlapSquareMetres': unary_union(list(areas.values())).intersection(buildings).area,
        'qualification': 'OSM polygons and tagged paths. Untagged widths are explicit estimates; '
                         'not surveyed curbs or individual paving units. Building footprints excluded. '
                         'Bounded overlay on surveyed ground, with original material map retained outside '
                         'coverage. Twenty-metre western overlap and eight-metre boundary blend. '
                         'Leaf litter/soil under mapped woodland is an appearance estimate; '
                         'the OSM canopy tag does not survey the floor cover. '
                         'No terrain or collision changes.'}
    assert meta['architecture']['physicsGroundMaterials']['buildingOverlapSquareMetres'] < .001
    print('Physics ground materials:', meta['architecture']['physicsGroundMaterials']['areaSquareMetres'], flush=True)

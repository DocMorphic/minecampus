"""Survey envelope for the UYD exterior, with independently gated photo faces."""
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import unary_union

from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_terrain import ElevationSampler


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ('ROOT', 'CACHE', 'OUT', 'metadata', 'mc', 'encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root / 'minecraft/exterior/uyd-exterior.json'
    spec = json.loads(source.read_text())
    bid = spec['building']
    surveys = nearby_surveys(cache, spec['siteBoundsUTM'])
    footprint, walls, roof, points = survey_plan(ctx, next(s for key, s in surveys if key == bid))
    assert len(walls) == 5 and len(roof) // 3 == 5
    neighbours = unary_union([
        Polygon(mc(r[0])[:, [0, 2]], [mc(h)[:, [0, 2]] for h in r[1:]]).buffer(0)
        for key, surfaces in surveys if key != bid
        for kind, r in surfaces if kind == 'GroundSurface'
    ])
    serialize = lambda shape: [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]} for p in polygons(shape)]
    owned = footprint.buffer(spec['cleanupMarginMetres']).difference(neighbours.buffer(spec['neighbourGuardMetres']))
    rings = serialize(owned)
    datum_region = footprint.buffer(spec['datumMarginMetres']).difference(neighbours)
    lat, lon = np.radians(meta['origin'][:2])
    origin = np.array(Transformer.from_crs(4979, 4978, always_xy=True).transform(meta['origin'][1], meta['origin'][0], meta['origin'][2]))
    basis = np.array([[-np.sin(lon), np.cos(lon), 0], [np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)], [np.sin(lat)*np.cos(lon), np.sin(lat)*np.sin(lon), -np.cos(lat)]])
    inverse = Transformer.from_crs(4978, 25832, always_xy=True)
    lo = np.floor(np.array(datum_region.bounds[:2])/2)*2
    hi = np.ceil(np.array(datum_region.bounds[2:])/2)*2
    grid = np.array([[x, 64, z] for z in np.arange(lo[1], hi[1]+1, 2) for x in np.arange(lo[0], hi[0]+1, 2)])
    with rasterio.open(cache / 'campus-dgm-east.tif') as dem:
        sampler = ElevationSampler([dem])

        def terrain_y(flat):
            flat = np.array(flat, dtype=float).copy()
            flat[:, 1] = 64
            en = np.column_stack(inverse.transform(*((flat-[0, 64, 0])@basis+origin).T))[:, :2]
            return mc(np.column_stack([en, sampler.sample(en)]))[:, 1]

        grid[:, 1] = terrain_y(grid)
        for wall in walls:
            left, right = wall['bounds'][0][0], wall['bounds'][1][0]
            along = np.linspace(left, right, max(2, int(np.ceil((right-left)/.5))+1))
            flat = np.array(wall['anchor']) + along[:, None]*np.array(wall['direction'])
            wall['groundProfile'] = np.column_stack([along, terrain_y(flat)]).tolist()

    roof_vertices, roof_pixels = roof_texture(cache, roof)
    roof_file = bid + '-photo-roof.ect'
    collision_file = bid + '-photo-collision.ect'
    assert not (out/roof_file).exists() and not (out/collision_file).exists()
    (out/roof_file).write_bytes(encode([(roof_vertices, roof_pixels)]))
    collision_vertices = [[*wall['vertices'][i], 0, 0] for wall in walls for i in wall['indices']]
    (out/collision_file).write_bytes(encode([(collision_vertices, Image.new('RGBA', (1, 1), (150, 150, 145, 255))), (roof_vertices, roof_pixels)]))
    plans_file = out / 'photo-facades.json'
    plans = json.loads(plans_file.read_text())
    assert bid not in [p['id'] for p in plans['plans']]
    bounds = [points.min(0).tolist(), points.max(0).tolist()]
    plan = {'id': bid, 'runtimeId': 1_000_050_000+len(plans['plans']), 'manualRoof': False,
            'roofFile': roof_file, 'collisionFile': collision_file, 'bounds': bounds, 'walls': walls,
            'roofTriangles': roof[:, 3:6].reshape(-1, 3, 3).tolist(), 'retirement': rings,
            'retirementBoundary': rings}
    # Only the unsupported face is modelled. The other four remain subject to
    # the unchanged photographic coverage gate; never bake synthetic openings.
    fallback = walls[spec['fallbackWall']]
    fallback['reconstructed'] = True
    fallback_file = bid + '-survey-east-wall.ect'
    fallback_vertices = [[*fallback['vertices'][i], .5, .5] for i in fallback['indices']]
    (out/fallback_file).write_bytes(encode([(fallback_vertices, Image.new('RGBA', (1, 1), tuple(spec['fallbackColour'])))]))
    fv = np.asarray(fallback_vertices)[:, :3]
    meta['tiles'].append({'file': fallback_file, 'kind': 'reconstruction', 'runtimeId': spec['runtimeId'],
        'bounds': [fv.min(0).tolist(), fv.max(0).tolist()]})
    plans['plans'].append(plan)
    plans_file.write_text(json.dumps(plans, separators=(',', ':')))
    meta['photoFacades']['buildings'].append(bid)
    meta['photoFacades']['roofFiles'].append(roof_file)
    # Keep the measured shallow roof as a fractional heightfield support. Fine
    # solid profiles quantize horizontal bounds but retain whole-block height.
    meta['photoFacades']['collisionTiles'].append({'file': collision_file, 'bounds': bounds, 'kind': 'reconstruction', 'collisionHeightfieldParts': [1]})
    meta['photoFacades']['collisionRetirement'].extend(dict(r, y0=bounds[0][1]-2, y1=bounds[1][1]+5) for r in rings)
    meta['supplementalSurfaces'].append({'name': 'uyd-envelope-datum', 'rings': serialize(datum_region),
        'terrainGuide': {'width': int((hi[0]-lo[0])/2+1), 'height': int((hi[1]-lo[1])/2+1), 'points': grid.tolist()},
        'protectedFootprints': [], 'outdoorReconstructed': False})
    record = {'sourceFile': source.name, 'sourceSha256': sha(source), 'generatorFile': 'scripts/exterior_uyd.py',
              'generatorSha256': sha(Path(__file__)), 'referenceFile': spec['reference'],
              'referenceSha256': sha(root/'minecraft/exterior'/spec['reference']), 'roofFile': roof_file,
              'roofSha256': sha(out/roof_file), 'collisionFile': collision_file,
              'collisionSha256': sha(out/collision_file), 'datumSourceSha256': sha(cache/'campus-dgm-east.tif'),
              'qualification': spec['qualification']}
    record.update(meshFile=fallback_file, meshSha256=sha(out/fallback_file))
    meta['architecture']['uydExterior'] = record
    print('UYD: five surveyed wall faces and roof triangles; east wall provisional, four photo-gated faces', flush=True)

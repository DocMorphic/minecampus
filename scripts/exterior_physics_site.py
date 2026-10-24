"""Bounded DGM1/DOP20 ground extension for Physics I; core tiles stay exact."""
import hashlib
import json
import math
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import mapbox_earcut
from exterior_physics_i import BID, nearby_surveys, polygons
from exterior_terrain import ElevationSampler


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ['ROOT', 'CACHE', 'OUT', 'metadata', 'mc', 'encode']]
    source = root/'minecraft/exterior/physics-i-5101.json'
    spec = json.loads(source.read_text())
    bounds = spec['site']['boundsUTM']
    left, bottom, right, top = bounds
    assert left == meta['boundsUtm'][2], 'The extension must meet, not cover, existing ground tiles'
    surveys = nearby_surveys(cache)
    neighbours = unary_union([Polygon(r[0][:, :2], [h[:, :2] for h in r[1:]]).buffer(0)
                             for bid, surfaces in surveys if bid != BID for kind, r in surfaces if kind == 'GroundSurface']).buffer(.5)
    area = box(*bounds).difference(neighbours)
    with rasterio.open(cache/'campus-dgm-east.tif') as dem, rasterio.open(cache/'campus-dop-east.tif') as photo:
        elevation = ElevationSampler([dem])
        def xyz(xy):
            xy = np.asarray(xy)
            return mc(np.column_stack([xy, elevation.sample(xy)]))
        def mc_ring(ring):
            xy = np.asarray(ring.coords)
            return xyz(xy)[:, [0, 2]].tolist()
        rings = [{'ring': mc_ring(p.exterior), 'holes': [mc_ring(h) for h in p.interiors]} for p in polygons(area)]
        xs, ys = np.arange(left, right+1, 2), np.arange(bottom, top+1, 2)
        xy = np.array([(x, y) for y in ys for x in xs])
        guide = {'width': len(xs), 'height': len(ys), 'points': xyz(xy).tolist()}
        new_tiles = []
        for index, (e, n) in enumerate(spec['site']['tileOriginsUTM']):
            tile_area = area.intersection(box(e, n, e+40, n+40))
            if tile_area.area < .01:
                continue
            vertices = []
            for y in range(n, n+40):
                for x in range(e, e+40):
                    cell = box(x, y, x+1, y+1).intersection(tile_area)
                    for p in polygons(cell):
                        if p.area < 1e-7:
                            continue
                        loops = [np.asarray(p.exterior.coords[:-1])] + [np.asarray(h.coords[:-1]) for h in p.interiors]
                        xy = np.concatenate(loops)
                        indices = mapbox_earcut.triangulate_float64(xy, np.cumsum([len(r) for r in loops]).astype(np.uint32))
                        q = xyz(xy)
                        for i in indices:
                            vertices.append([*q[i], (xy[i, 0]-e)/40, (n+40-xy[i, 1])/40])
            # Pixel coordinates align with the pinned aerial raster, within
            # its tiny transform roundoff. No invented/upscaled roof data.
            col, row = (~photo.transform)*(e, n+40)
            rgb = photo.read([1, 2, 3], window=Window(round(col), round(row), 200, 200)).transpose(1, 2, 0)
            name = f'physics-ground-{e}-{n}.ect'
            (out/name).write_bytes(encode([(vertices, Image.fromarray(rgb))]))
            q = np.asarray(vertices)[:, :3]
            tile = {'file': name, 'kind': 'ground', 'runtimeId': 1_000_060_000+index, 'bounds': [q.min(0).tolist(), q.max(0).tolist()]}
            new_tiles.append(tile)
        meta['tiles'].extend(new_tiles)
        meta.setdefault('supplementalSurfaces', []).append({'name': 'physics-i-east', 'rings': rings, 'terrainGuide': guide,
            'protectedFootprints': [{'ring': mc_ring(p.exterior), 'holes': [mc_ring(h) for h in p.interiors]} for p in polygons(unary_union([Polygon(r[0][:, :2], [h[:, :2] for h in r[1:]]).buffer(0) for bid, surfaces in surveys for kind, r in surfaces if kind == 'GroundSurface']).buffer(spec['sourceCleanupMarginMetres']))],
            'outdoorReconstructed': False, 'qualification': 'DGM1/DOP20 ground outside the old campus boundary. Neighbouring building footprints are excluded. Source vegetation remains until explicitly reconstructed.'})
        meta['architecture']['physicsISite'] = {'sourceFile': source.name, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'boundsUTM': bounds, 'groundTiles': [t['file'] for t in new_tiles], 'areaSquareMetres': area.area,
            'sourceMetres': 1, 'guideMetres': 2, 'neighbourGuardMetres': .5,
            'qualification': 'Measured ground extension; vegetation and native visual verification remain pending.'}
        print('Physics I site:', len(new_tiles), 'ground tiles, neighbour footprints excluded', flush=True)

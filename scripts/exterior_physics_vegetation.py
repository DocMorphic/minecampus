"""Extend the existing surveyed-canopy method only over the new Physics I site."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, polygons
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx):
    root, cache, out, meta = [ctx[k] for k in ['ROOT', 'CACHE', 'OUT', 'metadata']]
    surface = meta['supplementalSurfaces'][-1]
    bounds = meta['architecture']['physicsISite']['boundsUTM']
    area = unary_union([Polygon(p['ring'], p['holes']) for p in surface['rings']])
    with tempfile.TemporaryDirectory(prefix='physics-vegetation-', dir=cache) as temp:
        folder = Path(temp)
        with rasterio.open(cache/'campus-dop-east.tif') as raster:
            col, row = (~raster.transform)*(bounds[0], bounds[3])
            w, h = (bounds[2]-bounds[0])*5, (bounds[3]-bounds[1])*5
            photo = raster.read([1, 2, 3], window=Window(round(col), round(row), w, h)).transpose(1, 2, 0)
            Image.fromarray(photo).save(folder/'campus-orthophoto.jpg', quality=94)
        sub = {'boundsUtm': bounds, 'terrainGuide': surface['terrainGuide'], 'tiles': [], 'replacements': []}
        with rasterio.open(cache/'campus-dgm-east.tif') as dem:
            build_vegetation({**ctx, 'OUT': folder, 'metadata': sub, 'height': ElevationSampler([dem]),
                              'buildings': nearby_surveys(cache),
                              'excludedTreeCentresUTM': [t['utm'] for t in meta['vegetation']['trees']]})
        for i, tile in enumerate(sub['tiles']):
            name = 'physics-'+tile['file']
            shutil.copy2(folder/tile['file'], out/name)
            meta['tiles'].append({**tile, 'file': name, 'runtimeId': 1_000_010_100+i})
        for replacement in sub['replacements']:
            clipped = Polygon(replacement['ring'], replacement.get('holes', [])).intersection(area)
            for p in polygons(clipped):
                meta['replacements'].append({**replacement, 'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]})
        surface['outdoorReconstructed'] = True
        surface['surfaceGuide'] = sub['surfaceGuide']
        surface['vegetationOverhang'] = sub['vegetationOverhang']
        surface['vegetation'] = sub['vegetation']
        surface['qualification'] = 'DGM1/DOP20 ground and DOM20-supported reconstructed canopy. Procedural branches/species appearance are approximate; neighbouring building footprints are excluded.'
        shutil.copy2(folder/'vegetation-survey.jpg', out/'physics-vegetation-survey.jpg')
        source = root/'minecraft/exterior/vegetation-sources.json'
        meta['architecture']['physicsISite']['qualification'] = 'Measured ground and surveyed-canopy extension; native visual acceptance remains pending.'
        meta['architecture']['physicsISite']['vegetation'] = {'trees': len(sub['vegetation']['trees']), 'groups': len(sub['tiles']),
            'sourceFile': source.name, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'qualification': 'Surveyed canopy positions and heights; inferred crowns and branches, with CC0 foliage assets. Visual acceptance remains pending.'}
        print('Physics I vegetation:', len(sub['vegetation']['trees']), 'survey-supported trees; bounded source cleanup', flush=True)

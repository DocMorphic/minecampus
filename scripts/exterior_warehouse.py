"""Surveyed small warehouse with reference-informed masonry; no interior.

ESO 2017 establishes the low roof/fascia, brick colour and east opening.
The opposite sides' masonry and absence of additional openings are estimates.
"""
import hashlib
import json
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, box
import mapbox_earcut

BUILDING = 'DEBY_LOD2_52738492'


def build(ctx, bid, walls):
    if bid != BUILDING:
        return
    root, out, meta, encode = [ctx[k] for k in ['ROOT', 'OUT', 'metadata', 'encode']]
    reference = json.loads((root / 'minecraft/exterior/photos/warehouse-eso-reference.json').read_text())
    assert hashlib.sha256((root / reference['cropFile']).read_bytes()).hexdigest() == reference['cropSha256']
    material = next(m for m in json.loads((root / 'minecraft/exterior/material-sources.json').read_text())['materials'] if m['name'] == 'brick_diff')
    source = root / 'minecraft/exterior/assets/textures/campus/brick_diff.png'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == material['resourceSha256']
    textures = [Image.open(source).convert('RGBA'), Image.new('RGBA', (1, 1), (168, 172, 167, 255)),
                Image.new('RGBA', (1, 1), (35, 43, 43, 255)), Image.new('RGBA', (1, 1), (73, 76, 73, 255))]
    parts = [[] for _ in textures]
    evidence = []

    def pt(x, y, z):
        p = anchor + direction * x + normal * z
        p[1] = y
        return p

    def quad(points, part):
        uv = [(0, 1), (1, 1), (1, 0), (0, 0)]
        for i in [0, 1, 2, 0, 2, 3]:
            parts[part].append([*points[i], *uv[i]])

    def block(x0, y0, z0, x1, y1, z1, part):
        points = [pt(x, y, z) for z in [z0, z1] for y in [y0, y1] for x in [x0, x1]]
        for face in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
            quad([points[i] for i in face], part)

    assert len(walls) == 5
    lengths = [9.2448, 12.4381, 4.6062, 4.6359, 12.4183]
    for index, wall in enumerate(walls):
        anchor, direction, normal = [np.asarray(wall[k]) for k in ['anchor', 'direction', 'normal']]
        l, b = wall['bounds'][0]
        r, t = wall['bounds'][1]
        assert abs(r - l - lengths[index]) < .005 and 63.9 < b < 64.1 and 67 < t < 67.2
        shape = Polygon(wall['rings'][0], wall['rings'][1:]).intersection(box(l, b + .10, r, t - .22))
        opening = None
        if index == 0:
            assert normal[0] > .98
            x0, x1 = l + (r - l) * .52 - .4, l + (r - l) * .52 + .4
            y0, y1 = b + 1.45, b + 2.25
            opening = box(x0, y0, x1, y1)
            assert shape.covers(opening)
            shape = shape.difference(opening)
            quad([pt(x0, y0, -.15), pt(x1, y0, -.15), pt(x1, y1, -.15), pt(x0, y1, -.15)], 2)
            for a, c in [(x0 - .04, x0 + .04), (x1 - .04, x1 + .04)]:
                block(a, y0 - .04, -.17, c, y1 + .04, .02, 3)
            for a, c in [(y0 - .04, y0 + .04), (y1 - .04, y1 + .04)]:
                block(x0, a, -.17, x1, c, .02, 3)
            block(x0 - .07, y0 - .09, -.15, x1 + .07, y0 - .04, .13, 1)
        # 1.5-metre adapted tiles approximate common brick size, with a
        # continuous phase across the survey's two nearly collinear west faces.
        period = 1.5
        phase = lengths[2] if index == 3 else 0
        for gx in np.arange(np.floor((l + phase) / period) * period - phase, r, period):
            for gy in np.arange(np.floor(b / period) * period, t, period):
                cut = shape.intersection(box(gx, gy, gx + period, gy + period))
                for poly in ([cut] if cut.geom_type == 'Polygon' else getattr(cut, 'geoms', [])):
                    if poly.geom_type != 'Polygon' or poly.area < 1e-8:
                        continue
                    rings = [np.asarray(poly.exterior.coords[:-1])] + [np.asarray(h.coords[:-1]) for h in poly.interiors]
                    xy = np.concatenate(rings)
                    indices = mapbox_earcut.triangulate_float64(xy, np.cumsum([len(v) for v in rings]).astype(np.uint32))
                    for i in indices:
                        x, y = xy[i]
                        parts[0].append([*pt(x, y, 0), (x - gx) / period, 1 - (y - gy) / period])
        block(l, t - .22, -.10, r, t, .055, 1)
        block(l, b, -.08, r, b + .10, .015, 3)
        ring = [pt(x, b, z)[[0, 2]].tolist() for x, z in [(l - .1, -.3), (r + .1, -.3), (r + .1, .2), (l - .1, .2)]]
        meta['replacements'].append({'ring': ring, 'holes': [], 'y0': b - .1, 'y1': t + .1, 'kind': 'architecture'})
        wall['reconstructed'] = True
        evidence.append({'surfaceIndex': index, 'lengthMetres': r - l, 'baseY': b, 'topY': t, 'eastOpening': opening is not None})
    vertices = np.concatenate([np.asarray(p)[:, :3] for p in parts])
    name = bid + '-warehouse.ect'
    (out / name).write_bytes(encode(list(zip(parts, textures))))
    meta['tiles'].append({'file': name, 'kind': 'reconstruction', 'profile': 'warehouse', 'runtimeId': 1_000_030_008,
                          'bounds': [vertices.min(0).tolist(), vertices.max(0).tolist()]})
    meta['architecture']['warehouseExterior'] = {'building': bid, 'reference': reference['sourcePage'], 'faces': evidence,
        'note': 'Survey envelope and roof retained. East opening and warm masonry informed by ESO 2017; exact opening dimensions, fascia and unseen elevations inferred. CC0 brick texture is an approximation, not a photograph of this building. No interior.'}
    print('Warehouse: surveyed walls, physically scaled brick, roof edge and reference-informed east opening', flush=True)

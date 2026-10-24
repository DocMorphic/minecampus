"""Physics I's surveyed envelope beyond the original campus terrain bounds.

BVV supplies geometry and roof pixels. Facade subdivisions are explicitly
estimated from the qualified sources, and are never described as as-built.
"""
import hashlib
from pathlib import Path
import base64
import json
import math
import xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
import mapbox_earcut

BID = 'DEBY_LOD2_5323136'


def polygons(shape):
    if shape.geom_type == 'Polygon':
        return [shape]
    return [p for p in getattr(shape, 'geoms', []) if p.geom_type == 'Polygon']


def nearby_surveys(cache, site_bounds=None):
    """Include neighbouring bodies omitted by the old campus boundary filter."""
    site = site_bounds if site_bounds is not None else json.loads((Path(__file__).resolve().parents[1] / 'minecraft/exterior/physics-i-5101.json').read_text())['site']['boundsUTM']
    ns = {'g': 'http://www.opengis.net/gml', 'b': 'http://www.opengis.net/citygml/building/1.0'}
    result = []
    for filename in ['campus-east.gml', 'campus-west.gml']:
        for b in ET.parse(cache / filename).findall('.//b:Building', ns):
            surfaces = []
            for kind in ['GroundSurface', 'WallSurface', 'RoofSurface']:
                for poly in b.findall('.//b:' + kind + '//g:Polygon', ns):
                    rings = []
                    for ring in poly.findall('.//g:LinearRing', ns):
                        pos = ring.find('g:posList', ns)
                        if pos is None:
                            continue
                        p = np.asarray(list(map(float, pos.text.split()))).reshape(-1, 3)
                        if np.linalg.norm(p[0] - p[-1]) < .001:
                            p = p[:-1]
                        if len(p) >= 3:
                            rings.append(p)
                    if rings:
                        surfaces.append((kind, rings))
            grounds = [r[0] for kind, r in surfaces if kind == 'GroundSurface']
            if not grounds:
                continue
            p = np.concatenate(grounds)
            if p[:, 0].max() < site[0]-40 or p[:, 0].min() > site[2]+20 or p[:, 1].max() < site[1]-20 or p[:, 1].min() > site[3]+30:
                continue
            result.append((b.get('{' + ns['g'] + '}id'), surfaces))
    return result


def survey_plan(ctx, surfaces):
    mc, triangulate = ctx['mc'], ctx['triangulate']
    footprint = unary_union([Polygon(mc(r[0])[:, [0, 2]], [mc(h)[:, [0, 2]] for h in r[1:]]).buffer(0)
                            for kind, r in surfaces if kind == 'GroundSurface'])
    walls, roofs, points = [], [], []
    for kind, rings in surfaces:
        p, q, indices = triangulate(rings)
        points.extend(q.tolist())
        if kind == 'RoofSurface':
            roofs.extend(np.concatenate([p[t], q[t]], axis=1).tolist() for t in indices)
        if kind != 'WallSurface':
            continue
        anchor = q[0].copy()
        delta = next((v - anchor for v in q if np.linalg.norm((v - anchor)[[0, 2]]) > .1), None)
        if delta is None:
            continue
        direction = np.array([delta[0], 0, delta[2]])
        direction /= np.linalg.norm(direction)
        normal = np.array([-direction[2], 0, direction[0]])
        # Retain the original survey ring's orientation. A ground-footprint
        # probe is ambiguous at walls above setbacks/overhangs (face 33).
        outer = mc(rings[0])
        source_normal = np.sum(np.cross(outer, np.roll(outer, -1, axis=0)), axis=0)
        assert np.linalg.norm(source_normal) > 1e-7
        if np.dot(normal, source_normal) < 0:
            normal = -normal
        xy = np.column_stack(((q - anchor) @ direction, q[:, 1]))
        lo, hi = xy.min(0), xy.max(0)
        if hi[0] - lo[0] < .1 or hi[1] - lo[1] < .1:
            continue
        walls.append({'anchor': anchor.tolist(), 'direction': direction.tolist(), 'normal': normal.tolist(),
                      'bounds': [lo.tolist(), hi.tolist()],
                      'rings': [np.column_stack(((mc(r) - anchor) @ direction, mc(r)[:, 1])).tolist() for r in rings],
                      'vertices': q.tolist(), 'indices': indices.reshape(-1).tolist()})
    return footprint, walls, np.asarray(roofs).reshape(-1, 6), np.asarray(points)


def roof_texture(cache, roof):
    """Use native DOP20 pixels, without clamping to the old 600m image."""
    with rasterio.open(cache / 'campus-dop-east.tif') as raster:
        cols, rows = (~raster.transform) * (roof[:, 0], roof[:, 1])
        left, top = math.floor(cols.min()) - 2, math.floor(rows.min()) - 2
        right, bottom = math.ceil(cols.max()) + 2, math.ceil(rows.max()) + 2
        assert 0 <= left < right <= raster.width and 0 <= top < bottom <= raster.height
        photo = Image.fromarray(raster.read([1, 2, 3], window=Window(left, top, right-left, bottom-top)).transpose(1, 2, 0))
        vertices = np.column_stack([roof[:, 3:6], (cols-left)/(right-left), (rows-top)/(bottom-top)])
    return vertices, photo


def protection_fringe(meta, owned):
    """Include only marked old-grid cells crossing this building's owned band.

    Reproduce the runtime's grid basis: its pixel edges, rather than a smooth
    buffer, determine which original source triangles the old mask protects.
    """
    grid, guide = meta['protectionGrid'], meta['terrainGuide']
    pixels = np.frombuffer(base64.b64decode(grid['data']), dtype=np.uint8).reshape(grid['height'], grid['width'])
    points = np.asarray(guide['points'])[:, [0, 2]]
    origin = points[0]
    u, v = points[1]-origin, points[guide['width']]-origin
    u *= grid['metresPerPixel']/np.linalg.norm(u)
    v *= grid['metresPerPixel']/np.linalg.norm(v)
    basis = np.column_stack([u, v])
    bounds = np.asarray(box(*owned.bounds).exterior.coords)
    projected = (bounds-origin) @ np.linalg.inv(basis).T
    lo, hi = np.floor(projected.min(0)).astype(int), np.floor(projected.max(0)).astype(int)
    cells, polygons = [], []
    for i in range(max(0, lo[0]), min(grid['width']-1, hi[0])+1):
        for k in range(max(0, lo[1]), min(grid['height']-1, hi[1])+1):
            j = grid['height']-1-k
            if not pixels[j, i]:
                continue
            corner = origin+u*i+v*k
            cell = Polygon([corner, corner+u, corner+u+v, corner+v])
            if owned.covers(cell) or cell.intersection(owned).area < 1e-8:
                continue
            cells.append([i, j])
            polygons.append(cell)
    return unary_union(polygons).difference(owned), cells


def build(ctx):
    root, cache, out, meta, encode = [ctx[k] for k in ['ROOT', 'CACHE', 'OUT', 'metadata', 'encode']]
    source = root / 'minecraft/exterior/physics-i-5101.json'
    spec = json.loads(source.read_text())
    assert hashlib.sha256((root / 'minecraft/exterior' / spec['reference']).read_bytes()).hexdigest() == spec['referenceSha256']
    surveys = nearby_surveys(cache)
    surfaces = next(s for bid, s in surveys if bid == BID)
    footprint, walls, roof, points = survey_plan(ctx, surfaces)
    assert len(walls) == spec['wallCount'] and len(roof) == spec['roofTriangles'] * 3
    assert hashlib.sha256(json.dumps(walls, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == spec['surveyWallsSha256']
    roof_vertices, roof_photo = roof_texture(cache, roof)
    parts = [[], [], [], []]
    textures = [Image.new('RGBA', (1, 1), tuple(c)) for c in spec['materialColours']]
    features = []
    base = float(points[:, 1].min())

    def pt(x, y, z=0):
        q = anchor + direction * x + normal * z
        q[1] = y
        return q

    def quad(q, part):
        for i in [0, 1, 2, 0, 2, 3]:
            parts[part].append([*q[i], *[(0, 1), (1, 1), (1, 0), (0, 0)][i]])

    def surface(shape, part, depth=0):
        for poly in polygons(shape):
            if poly.area < 1e-7:
                continue
            rings = [np.asarray(poly.exterior.coords[:-1])] + [np.asarray(h.coords[:-1]) for h in poly.interiors]
            xy = np.concatenate(rings)
            indices = mapbox_earcut.triangulate_float64(xy, np.cumsum([len(r) for r in rings]).astype(np.uint32)).reshape(-1, 3)
            for triangle in indices:
                # The survey's wall direction can reverse independently of
                # its outward normal. Glazing must retain the outward side so
                # reflections can reject the reverse side of a window.
                if part == 1:
                    q = np.array([pt(*xy[i], depth) for i in triangle])
                    if np.dot(np.cross(q[1]-q[0], q[2]-q[0]), normal) < 0:
                        triangle = triangle[::-1]
                for i in triangle:
                    x, y = xy[i]
                    parts[part].append([*pt(x, y, depth), float((x-left)/(right-left)), float((y-base)/15)])

    def block(x0, y0, z0, x1, y1, z1, part):
        q = [pt(x, y, z) for z in [z0, z1] for y in [y0, y1] for x in [x0, x1]]
        for face in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
            quad([q[i] for i in face], part)

    for index, wall in enumerate(walls):
        anchor, direction, normal = [np.asarray(wall[k]) for k in ['anchor', 'direction', 'normal']]
        shape = Polygon(wall['rings'][0], wall['rings'][1:]).buffer(0)
        left, bottom, right, top = shape.bounds
        config = spec['faces'][str(index)]
        openings = []
        if config['profile'] in ['ribbon', 'fins']:
            ranges = config.get('alongMetres', [[left+.22, right-.22]])
            for x0, x1 in ranges:
                for h0, h1 in spec['windowLevelsAboveBase']:
                    patch = shape.intersection(box(x0, base+h0, x1, base+h1))
                    for poly in polygons(patch):
                        if poly.area > .12:
                            openings.append(poly)
        surface(shape.difference(unary_union(openings)), 3 if config['profile'] == 'hall' else 0)
        controls = []
        for opening in openings:
            inset = spec['recessMetres']
            surface(opening, 1, -inset)
            ring = np.asarray(opening.exterior.coords[:-1])
            for a, b in zip(ring, np.roll(ring, -1, axis=0)):
                quad([pt(*a), pt(*b), pt(*b, -inset), pt(*a, -inset)], 0)
            surface(opening.difference(opening.buffer(-.055, join_style=2)), 2, -inset+.025)
            x0, y0, x1, y1 = opening.bounds
            # The bay pitch is an estimate. Fins and major piers are distinct
            # from the smaller window frames, matching the source's two rhythms.
            spacing = spec['finPitchMetres'] if config['profile'] == 'fins' else spec['mullionPitchMetres']
            for x in np.arange(left+spacing, right-.15, spacing):
                patch = opening.intersection(box(x-.035, y0, x+.035, y1))
                surface(patch, 2, -inset+.03)
                if config['profile'] == 'fins' and opening.covers(box(x-.07, y0, x+.07, y1)):
                    block(x-.07, y0, -inset+.04, x+.07, y1, .12, 0)
            if config['profile'] == 'ribbon':
                for x in np.arange(left+spec['majorBayPitchMetres'], right-.2, spec['majorBayPitchMetres']):
                    pier = opening.intersection(box(x-.11, y0, x+.11, y1))
                    surface(pier, 0, .015)
            point = opening.representative_point()
            controls.append({'positionMC': pt(point.x, point.y, -inset).tolist(), 'normalMC': normal.tolist()})
        # Small panel joints remain on the opaque concrete surface; they do not
        # remove surveyed mass or fabricate full-height doors.
        if config['profile'] != 'hall':
            opaque = shape.difference(unary_union(openings))
            for x in np.arange(left+spec['majorBayPitchMetres']/2, right-.1, spec['majorBayPitchMetres']/2):
                surface(opaque.intersection(box(x-.012, bottom, x+.012, top)), 3, .008)
        wall['reconstructed'] = True
        features.append({'surveyFace': index, 'profile': config['profile'], 'basis': config['basis'], 'openingControls': controls})
    # Keep part indices stable even for future revisions with no dark details.
    assert all(parts)
    parts.append(roof_vertices.tolist())
    textures.append(roof_photo)
    name = BID + '-physics-i-exterior.ect'
    (out/name).write_bytes(encode(list(zip(parts, textures))))
    roof_name = BID + '-photo-roof.ect'
    (out/roof_name).write_bytes(encode([(roof_vertices, roof_photo)]))
    all_vertices = np.concatenate([np.asarray(p)[:, :3] for p in parts])
    bounds = [all_vertices.min(0).tolist(), all_vertices.max(0).tolist()]
    meta['tiles'].append({'file': name, 'kind': 'reconstruction', 'profile': 'physics-i-exterior', 'runtimeId': spec['runtimeId'], 'bounds': bounds})
    neighbours = unary_union([Polygon(ctx['mc'](r[0])[:, [0, 2]], [ctx['mc'](h)[:, [0, 2]] for h in r[1:]]).buffer(0)
                             for bid, s in surveys if bid != BID for kind, r in s if kind == 'GroundSurface']).buffer(.5)
    # Match the site protection margin. A smaller retirement band leaves a
    # narrow protected strip of detached source triangles around clean walls.
    owned = footprint.buffer(spec['sourceCleanupMarginMetres'], join_style=2)
    fringe, protection_cells = protection_fringe(meta, owned)
    cleanup = owned.union(fringe).difference(neighbours)
    rings = [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]} for p in polygons(cleanup)]
    plan_file = out/'photo-facades.json'
    plans = json.loads(plan_file.read_text())
    assert BID not in [p['id'] for p in plans['plans']]
    plan = {'id': BID, 'runtimeId': 1_000_050_000+len(plans['plans']), 'manualRoof': True, 'completeEnvelope': True,
            'roofFile': roof_name, 'collisionFile': roof_name, 'bounds': [points.min(0).tolist(), points.max(0).tolist()],
            'walls': walls, 'roofTriangles': roof[:, 3:6].reshape(-1, 3, 3).tolist(), 'retirement': rings, 'retirementBoundary': rings}
    plans['plans'].append(plan)
    plan_file.write_text(json.dumps(plans, separators=(',', ':')))
    meta['photoFacades']['buildings'].append(BID)
    meta['photoFacades']['roofFiles'].append(roof_name)
    # The complete reconstruction already supplies its collision primitives.
    meta['photoFacades']['collisionRetirement'].extend(dict(r, y0=base-2, y1=float(points[:, 1].max())+5) for r in rings)
    meta['architecture']['physicsIExterior'] = {'building': BID, 'sourceFile': source.name, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'qualification': spec['qualification'], 'faces': features, 'retirement': rings, 'roofTriangles': len(roof)//3,
        'neighbourExclusions': [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]} for p in polygons(neighbours)],
        'rasterProtectionCells': protection_cells,
        'rasterRetirementFringe': [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]} for p in polygons(fringe.difference(neighbours))],
        'surveyFootprint': [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]} for p in polygons(footprint)]}
    print('Physics I:', len(walls), 'surveyed wall faces,', len(roof)//3, 'roof triangles; estimated facade divisions', flush=True)

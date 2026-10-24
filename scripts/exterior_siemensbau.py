"""Survey envelope with explicitly qualified Siemensbau opening estimates."""
import hashlib
import json
import struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import mapbox_earcut


def build(ctx, bid, walls):
    if bid != 'DEBY_LOD2_5284457':
        return
    root, out, meta, encode = [ctx[k] for k in ['ROOT', 'OUT', 'metadata', 'encode']]
    source = root / 'minecraft/exterior/siemensbau-5103.json'
    spec = json.loads(source.read_text())
    assert hashlib.sha256((root / 'minecraft/exterior' / spec['reference']).read_bytes()).hexdigest() == spec['referenceSha256']
    assert len(walls) == spec['expectedWallCount']
    assert hashlib.sha256(json.dumps(walls, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == spec['surveyWallsSha256']
    base = min(w['bounds'][0][1] for w in walls)
    top = max(w['bounds'][1][1] for w in walls)
    textures = [Image.new('RGBA', (1, 1), c) for c in
                [(183, 187, 180, 255), (49, 66, 72, 255), (207, 211, 205, 255), (54, 60, 59, 255)]]
    parts = [[] for _ in textures]
    evidence = []

    def pt(x, y, z=0):
        p = anchor + direction * x + normal * z
        p[1] = y
        return p

    def quad(points, part):
        for i in [0, 1, 2, 0, 2, 3]:
            parts[part].append([*points[i], *[(0, 1), (1, 1), (1, 0), (0, 0)][i]])

    def polygons(shape):
        return [shape] if shape.geom_type == 'Polygon' else [p for p in getattr(shape, 'geoms', []) if p.geom_type == 'Polygon']

    def surface(shape, part, inset=0):
        for poly in polygons(shape):
            if poly.area < 1e-7:
                continue
            rings = [np.asarray(poly.exterior.coords[:-1])] + [np.asarray(h.coords[:-1]) for h in poly.interiors]
            xy = np.concatenate(rings)
            for i in mapbox_earcut.triangulate_float64(xy, np.cumsum([len(r) for r in rings]).astype(np.uint32)):
                x, y = xy[i]
                parts[part].append([*pt(x, y, -inset), float((x - left) / (right - left)), float((y - base) / (top - base))])

    def block(x0, y0, z0, x1, y1, z1, part):
        points = [pt(x, y, z) for z in [z0, z1] for y in [y0, y1] for x in [x0, x1]]
        for face in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
            quad([points[i] for i in face], part)

    for index, wall in enumerate(walls):
        anchor, direction, normal = [np.asarray(wall[k]) for k in ['anchor', 'direction', 'normal']]
        shape = Polygon(wall['rings'][0], wall['rings'][1:]).buffer(0)
        left, bottom, right, ceiling = shape.bounds
        config = spec['faces'][str(index)]
        features = []
        for opening in config['openings']:
            x0, x1 = opening['alongMetres']
            y0, y1 = [base + v for v in opening['heightAboveBase']]
            patch = box(x0, y0, x1, y1)
            assert shape.covers(patch), (bid, index, opening)
            assert all(patch.intersection(other).area < 1e-6 for other, _ in features)
            features.append((patch, opening))
        surface(shape.difference(unary_union([p for p, _ in features])), 0)
        controls = []
        for patch, opening in features:
            x0, y0, x1, y1 = patch.bounds
            door = opening['kind'] == 'door'
            inset = .24 if door else spec['recessMetres']
            part = 3 if door else 1
            surface(patch, part, inset)
            ring = np.asarray(patch.exterior.coords[:-1])
            for a, b in zip(ring, np.roll(ring, -1, axis=0)):
                quad([pt(*a), pt(*b), pt(*b, -inset), pt(*a, -inset)], 0)
            surface(patch.difference(patch.buffer(-spec['frameMetres'], join_style=2)), 2, inset - .035)
            # Closed exterior doors and simple two-leaf office windows. These
            # divisions and recess sizes are inferred, not surveyed features.
            centre = (x0 + x1) / 2
            surface(patch.intersection(box(centre - .025, y0, centre + .025, y1)), 2, inset - .035)
            if not door:
                block(x0 - .04, y0 - .06, -.17, x1 + .04, y0, .10, 2)
            else:
                block(x1 - .20, y0 + .90, -inset + .04, x1 - .17, y0 + 1.13, -inset + .09, 2)
            controls.append({'kind': opening['kind'], 'basis': opening['basis'],
                             'positionMC': pt((x0 + x1) / 2 - .15, (y0 + y1) / 2, -inset).tolist(),
                             'normalMC': normal.tolist(), 'part': part})
        # Keep the measured height and roof. A restrained drip edge closes the
        # former scan's folded perimeter; dimensions are explicitly inferred.
        block(left, ceiling - .12, -.12, right, ceiling + .015, .055, 3)
        wall['reconstructed'] = True
        evidence.append({'surveyFace': index, 'basis': config['basis'], 'openings': controls})

    raw = (out / (bid + '-photo-roof.ect')).read_bytes()
    assert raw[:4] == b'ECT1' and struct.unpack_from('<i', raw, 4)[0] == 1
    count, width, height = struct.unpack_from('<iii', raw, 32)
    roof = np.frombuffer(raw, dtype='<f4', count=count * 5, offset=48).reshape((-1, 5)).copy()
    parts.append(roof.tolist())
    textures.append(Image.frombytes('RGBA', (width, height), raw[48 + count * 20:]))
    vertices = np.concatenate([np.asarray(p)[:, :3] for p in parts])
    name = bid + '-siemensbau-exterior.ect'
    (out / name).write_bytes(encode(list(zip(parts, textures))))
    meta['tiles'].append({'file': name, 'kind': 'reconstruction', 'profile': 'siemensbau-exterior',
                          'runtimeId': spec['runtimeId'], 'bounds': [vertices.min(0).tolist(), vertices.max(0).tolist()]})
    footprints = {name: unary_union([Polygon(ctx['mc'](r[0])[:, [0, 2]], [ctx['mc'](h)[:, [0, 2]] for h in r[1:]]).buffer(0)
                                     for typ, r in surfaces if typ == 'GroundSurface'])
                  for name, surfaces in ctx['buildings']}
    neighbours = unary_union([f for name, f in footprints.items() if name != bid]).buffer(spec['sourceRetirement']['neighbourGuardMetres'])
    cleanup = footprints[bid].buffer(spec['sourceRetirement']['collarMetres'], join_style=2).difference(neighbours)
    rings = [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]} for p in polygons(cleanup)]
    for ring in rings:
        meta['replacements'].append(dict(ring, y0=base - .1, y1=top + spec['sourceRetirement']['roofPaddingMetres'], kind='architecture'))
    meta['architecture']['siemensbauExterior'] = {'building': bid, 'tumBuilding': '5103', 'runtimeId': spec['runtimeId'],
        'sourceFile': source.name, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'qualification': spec['qualification'], 'faces': evidence, 'retirement': rings,
        'roofSourceSha256': hashlib.sha256(raw).hexdigest()}
    print('Siemensbau 5103:', sum(len(f['openings']) for f in evidence), 'qualified openings; surveyed envelope and exact roof', flush=True)
    return rings

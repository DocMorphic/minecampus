"""Surveyed cyclotron and GRS-Altbau exteriors with qualified facade estimates.

Public survey roofs and collision files are retained byte-for-byte. Facade
openings are closed exterior recesses; this does not fabricate interiors.
"""
import hashlib
import json
import struct
from pathlib import Path

import mapbox_earcut
import numpy as np
from PIL import Image
from shapely import set_precision
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union


def polygons(shape):
    if shape.is_empty:
        return []
    return [shape] if shape.geom_type == 'Polygon' else [p for p in shape.geoms if p.geom_type == 'Polygon']


def build(ctx):
    root, out, meta, encode = [ctx[k] for k in ('ROOT', 'OUT', 'metadata', 'encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/galileo-low-buildings.json'
    spec = json.loads(source.read_text())
    reference = root/'minecraft/exterior'/spec['reference']
    assert sha(reference) == spec['referenceSha256']
    plans_file = out/'photo-facades.json'
    plans = json.loads(plans_file.read_text())
    footprints = {b['id']: unary_union([Polygon([(v[0], v[2]) for v in ring]).buffer(0) for ring in b['grounds']]) for b in meta['buildings']}
    ground_footprints = dict(footprints)
    # The serialized courtyard GroundSurface connects inner and outer loops
    # with a diagonal bridge. Project the retained roof triangles to recover
    # the complete wing and its real courtyard hole without filling that hole.
    for building in spec['buildings']:
        plan = next(p for p in plans['plans'] if p['id'] == building['id'])
        raw = (out/plan['roofFile']).read_bytes()
        count = struct.unpack_from('<i', raw, 32)[0]
        vertices = np.frombuffer(raw, dtype='<f4', count=count*5, offset=48).reshape(-1,5)[:,:3]
        footprints[building['id']] = unary_union([Polygon(t[:,[0,2]]) for t in vertices.reshape(-1,3,3)]).buffer(0)
    records = []
    for building in spec['buildings']:
        bid = building['id']
        plan = next(p for p in plans['plans'] if p['id'] == bid)
        walls = plan['walls']
        assert sha(out/plan['roofFile']) == building['roofSha256']
        assert hashlib.sha256(json.dumps(walls, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == building['surveyWallsSha256']
        assert building['runtimeId'] not in [t['runtimeId'] for t in meta['tiles']]
        # Stable part layout: pale wall, glazing, frame, blue infill, reddish
        # opaque finish, closed door, followed by the untouched survey roof.
        parts = [[] for _ in range(6)]
        colours = spec['colours']
        evidence = []
        for index, wall in enumerate(walls):
            anchor, direction, normal = [np.asarray(wall[k], dtype=float) for k in ('anchor', 'direction', 'normal')]
            shape = Polygon(wall['rings'][0], wall['rings'][1:]).buffer(0)
            left, bottom, right, top = shape.bounds
            # Some courtyard survey normals point into the building. Determine
            # recess direction against the actual footprint, including its hole.
            centre = shape.representative_point()
            centre3 = anchor + direction*centre.x
            corrected = footprints[bid].contains(Point((centre3+normal*.2)[[0, 2]]))
            if corrected:
                normal = -normal

            def point(x, y, depth=0):
                q = anchor + direction*x + normal*depth
                q[1] = y
                return q

            def quad(points, part):
                for i in (0, 1, 2, 0, 2, 3):
                    parts[part].append([*points[i], .5, .5])

            def surface(region, part, depth=0):
                # Near-coincident survey corners can leave vanishing bridges
                # when panels meet the wall edge. Normalize below mesh precision
                # and verify coverage so triangulation cannot fill window holes.
                for poly in polygons(set_precision(region, 1e-7)):
                    if poly.area < 1e-8:
                        continue
                    rings = [np.asarray(poly.exterior.coords[:-1])] + [np.asarray(h.coords[:-1]) for h in poly.interiors]
                    xy = np.concatenate(rings)
                    indices = mapbox_earcut.triangulate_float64(xy, np.cumsum([len(r) for r in rings]).astype(np.uint32))
                    coverage = unary_union([Polygon(xy[ids]) for ids in indices.reshape(-1,3)])
                    assert coverage.symmetric_difference(poly).area < 1e-5, (bid, index, 'Facade triangulation changed its holes')
                    for ids in indices.reshape(-1,3):
                        triangle = [point(*xy[i], depth) for i in ids]
                        if np.dot(np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0]), normal) < 0:
                            triangle.reverse()
                        parts[part].extend([*p, .5, .5] for p in triangle)

            config = building['faces'][str(index)]
            openings = []
            for opening in config['openings']:
                x0, x1 = [left+(right-left)*u for u in opening['alongFraction']]
                y0, y1 = [building['baseY']+h for h in opening['heightAboveBase']]
                region = box(x0, y0, x1, y1)
                assert shape.buffer(1e-7).covers(region), (bid, index, opening)
                assert all(region.intersection(p).area < 1e-8 for p, _ in openings)
                openings.append((region, opening))
            opaque = shape.difference(unary_union([p for p, _ in openings]))
            tinted = []
            for panel in config.get('panels', []):
                x0, x1 = [left+(right-left)*u for u in panel['alongFraction']]
                y0, y1 = [building['baseY']+h for h in panel['heightAboveBase']]
                region = box(x0, y0, x1, y1).intersection(opaque)
                assert all(region.intersection(p).area < 1e-7 for p in tinted)
                surface(region, panel['part'])
                tinted.append(region)
            surface(opaque.difference(unary_union(tinted)), 0)
            controls = []
            for region, opening in openings:
                x0, y0, x1, y1 = region.bounds
                inset = spec['recessMetres']
                part = 5 if opening['kind'] == 'door' else 1
                surface(region, part, -inset)
                ring = np.asarray(region.exterior.coords[:-1])
                for a, b in zip(ring, np.roll(ring, -1, axis=0)):
                    quad([point(*a), point(*b), point(*b, -inset), point(*a, -inset)], 0)
                surface(region.difference(region.buffer(-spec['frameMetres'], join_style=2)), 2, -inset+.03)
                for division in range(1, opening['divisions']):
                    x = x0+(x1-x0)*division/opening['divisions']
                    surface(box(x-.035, y0, x+.035, y1), 2, -inset+.03)
                if part == 1:
                    # The thin sill gives an actual shadow edge instead of a
                    # photographic white streak; its dimensions are estimates.
                    quad([point(x0, y0, -.01), point(x1, y0, -.01), point(x1, y0, .09), point(x0, y0, .09)], 2)
                controls.append({'kind':opening['kind'], 'basis':opening['basis'], 'target':point(x0+(x1-x0)/opening['divisions']*.5, (y0+y1)/2, -inset).tolist(), 'normal':normal.tolist(), 'tile':building['runtimeId'], 'part':part, 'alongFraction':opening['alongFraction']})
            # Preserve sloping/stepped upper outlines. Clip the fascia to the
            # measured wall polygon instead of spanning a bounding rectangle.
            fascia = shape.intersection(box(left, top-spec['fasciaMetres'], right, top))
            surface(fascia, 2, .035)
            evidence.append({'face':index, 'outwardNormalCorrected':bool(corrected), 'normal':normal.tolist(), 'basis':config['basis'], 'openings':controls})
            wall['reconstructed'] = True
        raw = (out/plan['roofFile']).read_bytes()
        assert raw[:4] == b'ECT1' and struct.unpack_from('<i', raw, 4)[0] == 1
        active = [i for i, vertices in enumerate(parts) if vertices]
        assert active in ([0,1,2,4,5], [0,1,2,3,5])
        for face in evidence:
            for control in face['openings']:
                control['part'] = active.index(control['part'])
        payload = bytearray(encode([(parts[i], Image.new('RGBA', (1, 1), tuple(colours[i]))) for i in active]))
        assert payload[8:32] == raw[8:32]
        struct.pack_into('<i', payload, 4, len(active)+1)
        payload.extend(raw[32:])
        name = bid+'-low-building-exterior.ect'
        assert not (out/name).exists()
        (out/name).write_bytes(payload)
        xyz = np.array([v[:3] for vertices in parts for v in vertices])
        low = np.minimum(xyz.min(0), plan['bounds'][0]); high = np.maximum(xyz.max(0), plan['bounds'][1])
        meta['tiles'].append({'file':name, 'kind':'reconstruction', 'profile':'galileo-low-building', 'runtimeId':building['runtimeId'], 'bounds':[low.tolist(), high.tolist()], 'alwaysVisible':True, 'collisionParts':[]})
        protected = unary_union([p for key, p in footprints.items() if key != bid]).buffer(spec['neighbourGuardMetres'])
        cleanup = footprints[bid].buffer(spec['cleanupMarginMetres'], join_style=2).difference(protected)
        rings = [{'ring':list(p.exterior.coords), 'holes':[list(h.coords) for h in p.interiors]} for p in polygons(cleanup)]
        assert cleanup.intersection(protected).area < 1e-7
        for ring in rings:
            meta['replacements'].append(dict(ring, y0=plan['bounds'][0][1]-.1, y1=plan['bounds'][1][1]+spec['roofPaddingMetres'], kind='architecture', alwaysVisible=True))
        plan.update(manualRoof=True, retirementBoundary=rings)
        records.append({'building':bid, 'runtimeId':building['runtimeId'], 'meshFile':name, 'meshSha256':sha(out/name), 'roofFile':plan['roofFile'], 'roofSha256':sha(out/plan['roofFile']), 'collisionFile':plan['collisionFile'], 'collisionSha256':sha(out/plan['collisionFile']), 'faces':evidence, 'retirement':rings, 'cleanupAreaSquareMetres':cleanup.area, 'footprintBasis':'Projection of unchanged survey roof triangles; courtyard holes retained', 'groundLoopMissingAreaSquareMetres':footprints[bid].difference(ground_footprints[bid]).area})
    plans_file.write_text(json.dumps(plans, separators=(',', ':')))
    meta['architecture']['galileoLowBuildings'] = {'sourceFile':source.name, 'sourceSha256':sha(source), 'generatorFile':'scripts/exterior_galileo_low_buildings.py', 'generatorSha256':sha(Path(__file__)), 'referenceFile':spec['reference'], 'referenceSha256':sha(reference), 'buildings':records, 'qualification':spec['qualification']}
    print('Low buildings:', len(records), 'surveyed envelopes;', sum(len(f['openings']) for b in records for f in b['faces']), 'qualified window/door groups', flush=True)

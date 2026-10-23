"""BVV 5130 envelope with a photograph-informed west end and roof-edge repair.

The four-window end is observed in 2014/2018 references. Other elevations keep
photography below the reconstructed fascia; their opening schedule is unknown.
"""
import json
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import mapbox_earcut

BUILDING = 'DEBY_LOD2_8486669'


def build(ctx, bid, walls):
    if bid != BUILDING:
        return
    root, out, meta, encode = [ctx[k] for k in ['ROOT', 'OUT', 'metadata', 'encode']]
    reference = json.loads((root / 'minecraft/exterior/photos/telefonzentrale-reference.json').read_text())
    assert len(walls) == 9
    grain = np.asarray(Image.open(root / 'minecraft/exterior/assets/textures/campus/concrete_diff.png').convert('RGB').resize((128, 128))).mean(2)
    render = np.empty((128, 128, 4), np.uint8)
    for k, base in enumerate([172, 174, 168]):
        render[:, :, k] = np.clip(base + (grain - grain.mean()) * .18, 0, 255)
    render[:, :, 3] = 255
    textures = [Image.fromarray(render), Image.new('RGBA', (1, 1), (49, 63, 61, 255)),
                Image.new('RGBA', (1, 1), (40, 42, 40, 255))]
    parts = [[] for _ in textures]

    def pt(x, y, z):
        p = anchor + direction * x + normal * z
        p[1] = y
        return p

    def quad(points, part):
        for i in [0, 1, 2, 0, 2, 3]:
            parts[part].append([*points[i], *[(0, 1), (1, 1), (1, 0), (0, 0)][i]])

    def block(x0, y0, z0, x1, y1, z1, part):
        points = [pt(x, y, z) for z in [z0, z1] for y in [y0, y1] for x in [x0, x1]]
        for face in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
            quad([points[i] for i in face], part)

    def retire(l, r, bottom, top, outside, kind='architecture'):
        ring = [pt(x, bottom, z)[[0, 2]].tolist() for x, z in [(l - .05, -.3), (r + .05, -.3), (r + .05, outside), (l - .05, outside)]]
        meta['replacements'].append({'ring': ring, 'holes': [], 'y0': bottom, 'y1': top, 'kind': kind})

    # The four-window west end belongs to 5130, west of Siemensbau (5103).
    # Face 2 runs south-to-north; reverse it to measure openings from the north.
    west = walls[2]
    end = np.asarray(west['anchor'])
    anchor = end + np.asarray(west['direction']) * west['bounds'][1][0]
    direction = end - anchor
    direction[1] = 0
    length = np.linalg.norm(direction)
    direction /= length
    normal = np.array([-direction[2], 0, direction[0]])
    assert 12.52 < length < 12.55 and normal[0] < -.98
    v = np.asarray(west['vertices'])
    assert np.max(np.abs((v - anchor) @ normal)) < .005
    polygons = [Polygon(np.column_stack(((v - anchor) @ direction, v[:, 1])))]
    west['reconstructed'] = True
    shape = unary_union(polygons).buffer(0)
    l, b, r, t = shape.bounds
    openings = []
    for centre in [2.45, 4.70, 7.55, 9.80]:
        x0, x1, y0, y1 = centre - .62, centre + .62, b + 1.15, b + 2.60
        hole = box(x0, y0, x1, y1)
        assert shape.covers(hole)
        shape = shape.difference(hole)
        quad([pt(x0, y0, -.18), pt(x1, y0, -.18), pt(x1, y1, -.18), pt(x0, y1, -.18)], 1)
        for a, c in [(x0, x0 + .06), (x1 - .06, x1)]:
            block(a, y0, -.20, c, y1, -.10, 2)
        for a, c in [(y0, y0 + .06), (y1 - .06, y1)]:
            block(x0, a, -.20, x1, c, -.10, 2)
        for x in [x0, x1]:
            quad([pt(x, y0, 0), pt(x, y1, 0), pt(x, y1, -.18), pt(x, y0, -.18)], 0)
        for y in [y0, y1]:
            quad([pt(x0, y, 0), pt(x1, y, 0), pt(x1, y, -.18), pt(x0, y, -.18)], 0)
        block(x0 - .035, y0 - .055, -.18, x1 + .035, y0, .08, 2)
        openings.append({'centreFromNorthMetres': centre, 'widthMetres': 1.24, 'heightMetres': 1.45, 'recessMetres': .18})
    # A narrow joint beneath the fascia is visible in both west-end references.
    shape = shape.difference(box(l, t - .82, r, t - .80))
    block(l, t - .82, -.03, r, t - .80, -.005, 2)
    for poly in ([shape] if shape.geom_type == 'Polygon' else shape.geoms):
        xy = np.concatenate([np.asarray(poly.exterior.coords[:-1])] + [np.asarray(h.coords[:-1]) for h in poly.interiors])
        ends = np.cumsum([len(poly.exterior.coords) - 1] + [len(h.coords) - 1 for h in poly.interiors]).astype(np.uint32)
        for i in mapbox_earcut.triangulate_float64(xy, ends):
            x, y = xy[i]
            parts[0].append([*pt(x, y, 0), float(np.clip((x-l)/(r-l),0,1)), float(np.clip((y-b)/(t-b),0,1))])
    retire(l, r, b - .1, t + .5, .6)
    # The roof outline/height are surveyed. Continuing the observed fascia on
    # the other faces is an inference; do not infer their window/door layout.
    for index, wall in enumerate(walls):
        anchor, direction, normal = [np.asarray(wall[k]) for k in ['anchor', 'direction', 'normal']]
        (l, b), (r, t) = wall['bounds']
        if index not in [0, 2, 3, 5, 7]:
            continue  # Preserve the connecting passage and its surveyed height steps.
        assert 67.72 < t < 67.74
        if index != 2:
            block(l, t - .80, -.08, r, t - .07, .035, 0)
            retire(l, r, t - .85, t + .85, 1.3, 'architecture-band')
        block(l, t - .07, -.10, r, t + .015, .07, 2)
    vertices = np.concatenate([np.asarray(p)[:, :3] for p in parts])
    name = bid + '-west-exterior.ect'
    (out / name).write_bytes(encode(list(zip(parts, textures))))
    meta['tiles'].append({'file': name, 'kind': 'reconstruction', 'profile': 'telefonzentrale-west', 'runtimeId': 1_000_030_009,
                          'bounds': [vertices.min(0).tolist(), vertices.max(0).tolist()]})
    meta['architecture']['telefonzentraleExterior'] = {'building': bid, 'tumBuilding': '5130', 'westLengthMetres': length,
        'westSurveyFaces': [2], 'windows': openings, 'references': reference['references'],
        'note': 'Four west windows and grey render observed; exact opening sizes, recess and colour inferred. Roof-edge continuation on other faces inferred. Other facade areas retain photography; survey roof unchanged; no interior.'}
    print('Telefonzentrale: four-window west end and survey-aligned roof edge; other facade areas retain photography', flush=True)

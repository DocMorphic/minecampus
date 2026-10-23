"""Visible UYE elevations: surveyed envelope, reference-informed roof edge/glazing.

Only the east and north elevations visible in the ESO aerial are replaced.
The architect's 2011 photograph informs the material/overhang vocabulary;
pane divisions and recess depth are estimates, not a measured glazing schedule.
"""
import json
import numpy as np
from PIL import Image

BUILDING = 'DEBY_LOD2_31360854'
FACES = {0: 22, 1: 12}


def build(ctx, bid, walls):
    if bid != BUILDING:
        return
    root, out, meta, encode = [ctx[k] for k in ['ROOT', 'OUT', 'metadata', 'encode']]
    reference = json.loads((root / 'minecraft/exterior/photos/uye-architect-reference.json').read_text())
    grain = np.asarray(Image.open(root / 'minecraft/exterior/assets/textures/campus/concrete_diff.png').convert('RGB').resize((128, 128))).mean(2)
    pale = np.empty((128, 128, 4), np.uint8)
    for k, base in enumerate([212, 211, 202]):
        pale[:, :, k] = np.clip(base + (grain - grain.mean()) * .12, 0, 255)
    pale[:, :, 3] = 255
    textures = [Image.fromarray(pale), Image.new('RGBA', (1, 1), (46, 66, 66, 255)),
                Image.new('RGBA', (1, 1), (38, 43, 43, 255))]
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

    for index, bays in FACES.items():
        wall = walls[index]
        anchor, direction, normal = [np.asarray(wall[k]) for k in ['anchor', 'direction', 'normal']]
        l, b = wall['bounds'][0]
        r, t = wall['bounds'][1]
        assert abs(r - l - (29.04 if index == 0 else 15.43)) < .05
        assert 64 < b < 64.2 and 67.8 < t < 68
        assert (index == 0 and normal[0] > .98) or (index == 1 and normal[2] < -.98)
        glass_bottom, glass_top, recess = b + .18, t - .49, .50
        # The roof edge stays on the survey envelope; the glazing retreats
        # beneath it. This does not enlarge the measured footprint/roof.
        block(l, glass_top, -recess - .12, r, t, .015, 0)
        block(l, b, -recess - .12, r, glass_bottom, .015, 0)
        quad([pt(l, glass_bottom, -recess), pt(r, glass_bottom, -recess),
              pt(r, glass_top, -recess), pt(l, glass_top, -recess)], 1)
        for x in np.linspace(l, r, bays + 1):
            block(max(l, x - .035), glass_bottom, -recess - .02,
                  min(r, x + .035), glass_top, -recess + .075, 2)
        for y in [glass_bottom, b + 1.12, t - 1.12, glass_top - .05]:
            block(l, y, -recess - .02, r, y + .05, -recess + .075, 2)
        # Closed end reveals meet the retained photographic elevations.
        for x in [l, r]:
            quad([pt(x, glass_bottom, 0), pt(x, glass_top, 0),
                  pt(x, glass_top, -recess), pt(x, glass_bottom, -recess)], 2)
        ring = [pt(x, b, z)[[0, 2]].tolist() for x, z in
                [(l - .12, -.85), (r + .12, -.85), (r + .12, .25), (l - .12, .25)]]
        meta['replacements'].append({'ring': ring, 'holes': [], 'y0': b - .1, 'y1': t + .1, 'kind': 'architecture'})
        wall['reconstructed'] = True
        evidence.append({'surfaceIndex': index, 'lengthMetres': r - l, 'bays': bays,
                         'baseY': b, 'topY': t, 'recessMetres': recess})
    vertices = np.concatenate([np.asarray(p)[:, :3] for p in parts])
    name = bid + '-uye-exterior.ect'
    (out / name).write_bytes(encode(list(zip(parts, textures))))
    meta['tiles'].append({'file': name, 'kind': 'reconstruction', 'profile': 'uye-exterior',
                          'runtimeId': 1_000_030_007, 'bounds': [vertices.min(0).tolist(), vertices.max(0).tolist()]})
    meta['architecture']['uyeExterior'] = {
        'building': bid, 'reference': reference['sourcePage'], 'faces': evidence,
        'note': 'East/north exterior only. BVV envelope and roof retained; facade vocabulary from the architect photo and ESO aerial. Pane counts, divisions and 0.50 m recess are inferred. West/south retain photography. No interior.'}
    print('UYE: east/north roof fascia and recessed glazing; other elevations and roof retained', flush=True)

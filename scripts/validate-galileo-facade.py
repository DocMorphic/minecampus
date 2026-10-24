#!/usr/bin/env python3
"""Check bounded facade replacement, preserved roofs and complete wall backing."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

root = Path(__file__).resolve().parents[1]
out = root / 'dist-minecraft/exterior'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', type=Path, required=True)
args = parser.parse_args()
old = args.baseline / 'exterior'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before, current = read(old / 'manifest.json'), read(out / 'manifest.json')
facade = current['architecture']['galileoFacade']
assert sha(root / 'minecraft/exterior' / facade['sourceFile']) == facade['sourceSha256']
changed = {bid + '.ect' for bid in facade['walls']}
assert changed == {'DEBY_LOD2_107614322.ect', 'DEBY_LOD2_107614323.ect'}
assert current['tiles'] == before['tiles'], 'Survey bounds or runtime IDs changed'
for key in before:
    if key != 'architecture':
        assert current[key] == before[key], key
for key in before['architecture']:
    assert current['architecture'][key] == before['architecture'][key], key
for tile in before['tiles']:
    if tile['file'] not in changed:
        assert sha(old / tile['file']) == sha(out / tile['file']), tile['file']
for name in ['photo-facades.json', 'campus-orthophoto.jpg']:
    if (old / name).exists():
        assert sha(old / name) == sha(out / name), name


def decode(path):
    data = path.read_bytes()
    count, = struct.unpack_from('<i', data, 4)
    offset, result = 32, []
    for _ in range(count):
        start = offset
        n, w, h = struct.unpack_from('<3i', data, offset)
        offset += 16
        vertices = np.frombuffer(data, dtype='<f4', count=n * 5, offset=offset).reshape(-1, 3, 5).astype(float)
        offset += n * 20 + w * h * 4
        result.append((vertices, (w, h), data[start:offset]))
    assert offset == len(data)
    return result


checked = 0
worst_gap = 0.
stats = {}
for bid, records in facade['walls'].items():
    previous, generated = decode(old / (bid + '.ect')), decode(out / (bid + '.ect'))
    assert len(previous) == len(generated) == 4
    assert previous[3][2] == generated[3][2], 'Survey roof or aerial UV bytes changed'
    assert all(part[1] == (1, 1) for part in generated[:3]), 'Photographic wall strip survived'
    walls = [wall['points'] for wall in before['walls'] if wall['building'] == bid]
    assert [record['points'] for record in records] == walls, 'A survey wall was omitted'
    backing = generated[2][0][:, :, :3]
    for wall in walls:
        q = np.asarray(wall)
        delta = max((point - q[0] for point in q), key=lambda d: np.linalg.norm(d[[0, 2]]))
        along = np.array([delta[0], 0., delta[2]])
        along /= np.linalg.norm(along)
        normal = np.array([-along[2], 0., along[0]])
        poly = Polygon(np.column_stack((q @ along, q[:, 1])))
        if not poly.is_valid:
            poly = poly.buffer(0)
        distance = (backing - q[0]) @ normal
        ids = np.all(np.abs(np.abs(distance) - .145) < .00004, axis=1)
        # The recessed backing must cover the original surveyed face in
        # projection. This inspects actual triangle bytes, not generator counts.
        candidates = [Polygon(np.column_stack((t @ along, t[:, 1]))) for t in backing[ids]]
        cover = unary_union([p for p in candidates if p.is_valid and p.area > 1e-9])
        gap = poly.difference(cover.buffer(.00004)).area
        assert gap < .002, (bid, gap)
        worst_gap = max(worst_gap, gap)
        checked += 1
    stats[bid] = {
        'surveyWalls': len(walls),
        'wallTriangles': sum(len(part[0]) for part in generated[:3]),
        'roofTriangles': len(generated[3][0]),
        'roofPartSha256': hashlib.sha256(generated[3][2]).hexdigest(),
        'panelCells': sum(record['panelCells'] for record in records),
        'glassAreaSquareMetres': sum(record['glassAreaSquareMetres'] for record in records),
    }
report = {
    'status': 'PASS: only two Galileo meshes changed; survey roofs and 97 other render tiles preserved; all survey walls have complete recessed backing',
    'unchangedRenderTiles': len(before['tiles']) - 2,
    'surveyWallsChecked': checked,
    'maximumUncoveredBackingAreaSquareMetres': worst_gap,
    'buildings': stats,
    'qualification': facade['reconstruction']['qualification'],
}
(out / 'galileo-facade-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

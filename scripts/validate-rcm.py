#!/usr/bin/env python3
"""Check scope, exact survey roof retention and neighbouring-building protection."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import struct
from shapely.geometry import Polygon
from shapely.ops import unary_union

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', type=Path, required=True)
args = parser.parse_args()
old, out = args.baseline / 'exterior', root / 'dist-minecraft/exterior'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
key = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'))
before, current = read(old / 'manifest.json'), read(out / 'manifest.json')
record = current['architecture']['rcmExterior']
spec = read(root / 'minecraft/exterior' / record['sourceFile'])
bid = spec['building']
assert record['sourceSha256'] == sha(root / 'minecraft/exterior' / record['sourceFile'])
for field in before:
    if field not in ['tiles', 'architecture', 'replacements', 'photoFacades']:
        assert before[field] == current[field], field
for field in before['architecture']:
    assert before['architecture'][field] == current['architecture'][field], field
assert len(current['tiles']) == len(before['tiles']) + 1
for tile in before['tiles']:
    assert (old / tile['file']).read_bytes() == (out / tile['file']).read_bytes(), tile['file']
previous = collections.Counter(map(key, before['replacements']))
now = collections.Counter(map(key, current['replacements']))
assert all(now[k] >= n for k, n in previous.items())
oldplans, plans = read(old / 'photo-facades.json')['plans'], read(out / 'photo-facades.json')['plans']
assert len(oldplans) == len(plans)
for a, b in zip(oldplans, plans):
    assert a['id'] == b['id']
    assert (old / a['roofFile']).read_bytes() == (out / b['roofFile']).read_bytes()
    if a['id'] != bid:
        assert a == b
        assert (old / a['collisionFile']).read_bytes() == (out / b['collisionFile']).read_bytes()
    else:
        assert b['manualRoof'] and b['roofTriangles'] == a['roofTriangles']
        assert all(dict(x, reconstructed=True) == y for x, y in zip(a['walls'], b['walls']))

def parts(path):
    raw = path.read_bytes()
    count = struct.unpack_from('<i', raw, 4)[0]
    offset, result = 32, []
    for _ in range(count):
        start = offset
        n, w, h = struct.unpack_from('<iii', raw, offset)
        offset += 16 + n * 20 + w * h * 4
        result.append(raw[start:offset])
    assert offset == len(raw)
    return result

roof = parts(old / (bid + '-photo-roof.ect'))
body = parts(out / (bid + '-rcm-exterior.ect'))
assert len(roof) == 1 and len(body) == 5 and body[-1] == roof[0]
foot = lambda b: unary_union([Polygon([(p[0], p[2]) for p in g]).buffer(0) for g in b['grounds']])
target = next(foot(b) for b in before['buildings'] if b['id'] == bid)
neighbours = unary_union([foot(b) for b in before['buildings'] if b['id'] != bid]).buffer(spec['sourceRetirement']['neighbourGuardMetres'])
cleanup = unary_union([Polygon(r['ring'], r['holes']) for r in record['retirement']])
assert cleanup.intersection(neighbours).area < .001
assert cleanup.difference(target.buffer(spec['sourceRetirement']['collarMetres'], join_style=2)).area < .001
assert len(record['faces']) == 5
result = {'status': 'PASS: existing render meshes, survey roofs and unrelated facade/collision plans retained; new body follows the 5104 survey envelope',
          'previousRenderMeshesUnchanged': len(before['tiles']), 'surveyRoofsUnchanged': len(plans),
          'unrelatedCollisionFilesUnchanged': len(plans) - 1, 'roofSha256': sha(old / (bid + '-photo-roof.ect')),
          'cleanupAreaSquareMetres': cleanup.area, 'neighbourGuardMetres': spec['sourceRetirement']['neighbourGuardMetres'],
          'openingCount': sum(len(f['openings']) for f in record['faces']),
          'qualification': spec['qualification'], 'sourceSha256': record['sourceSha256']}
(out / 'rcm-validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

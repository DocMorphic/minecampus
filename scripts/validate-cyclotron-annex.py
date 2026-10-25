#!/usr/bin/env python3
"""Verify the annex component against the pre-reconstruction survey plan.

This is geometric evidence only. It does not establish native appearance,
collision-packet equivalence, save preservation or release readiness.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--baseline', type=Path, required=True)
parser.add_argument('--full-data', action='store_true', help='Verify every retained mesh file in the complete release data')
args = parser.parse_args()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
old, out = args.baseline, args.directory
before, current = read(old/'manifest.json'), read(out/'manifest.json')
spec = read(root/'minecraft/exterior/cyclotron-annex.json')
record = current['architecture']['cyclotronAnnex']
for path, key in [(root/'minecraft/exterior'/record['sourceFile'], 'sourceSha256'),
                  (root/record['generatorFile'], 'generatorSha256'),
                  (root/'minecraft/exterior'/record['referenceFile'], 'referenceSha256')]:
    assert sha(path) == record[key]
assert current['tiles'][:-1] == before['tiles']
assert current['replacements'][:len(before['replacements'])] == before['replacements']
assert {k: v for k, v in current['architecture'].items() if k != 'cyclotronAnnex'} == before['architecture']
for key in before:
    if key not in ['tiles', 'replacements', 'architecture']:
        assert current[key] == before[key], key
old_plans, new_plans = read(old/'photo-facades.json'), read(out/'photo-facades.json')
assert {k:v for k,v in old_plans.items() if k!='plans'} == {k:v for k,v in new_plans.items() if k!='plans'}
assert len(old_plans['plans']) == len(new_plans['plans'])
source = None
for a, b in zip(old_plans['plans'], new_plans['plans']):
    if a['id'] != spec['building']:
        assert a == b
        continue
    source = a
    expected = json.loads(json.dumps(a))
    for wall in expected['walls']:
        wall['reconstructed'] = True
    expected.update(manualRoof=True, retirementBoundary=record['retirement'])
    assert b == expected
assert source is not None
raw = (out/record['meshFile']).read_bytes()
assert raw[:4] == b'ECT1' and struct.unpack_from('<i', raw, 4)[0] == 2
count, width, height = struct.unpack_from('<iii', raw, 32)
vertices = np.frombuffer(raw, dtype='<f4', count=count*5, offset=48).reshape(-1,5)
expected = np.asarray([[*w['vertices'][i], .5, .5] for w in source['walls'] for i in w['indices']], dtype='<f4')
assert np.array_equal(vertices, expected)
assert np.isfinite(vertices).all()
assert len(source['walls']) == 8
roof_offset = 48 + count*20 + width*height*4
assert raw[roof_offset:] == (old/source['roofFile']).read_bytes()[32:]
for name in [source['roofFile'], source['collisionFile']]:
    assert (out/name).read_bytes() == (old/name).read_bytes()
footprints = {b['id']: unary_union([Polygon([(p[0],p[2]) for p in ring]).buffer(0) for ring in b['grounds']])
              for b in before['buildings']}
cleanup = unary_union([Polygon(p['ring'],p['holes']) for p in record['retirement']])
protected = unary_union([p for bid,p in footprints.items() if bid != spec['building']]).buffer(spec['neighbourGuardMetres'])
assert cleanup.intersection(protected).area < 1e-7
assert cleanup.difference(footprints[spec['building']].buffer(spec['cleanupMarginMetres'],join_style=2)).area < 1e-7
assert all(p['y0'] == source['bounds'][0][1]-.1 and p['y1'] == source['bounds'][1][1]+spec['roofPaddingMetres']
           for p in current['replacements'][len(before['replacements']):])
assert sha(out/record['meshFile']) == record['meshSha256']
retained = {}
if args.full_data:
    names = {t['file'] for t in before['tiles']}
    names.update(p['roofFile'] for p in old_plans['plans'])
    names.update(p['collisionFile'] for p in old_plans['plans'])
    for name in sorted(names):
        assert sha(old/name) == sha(out/name), name
        retained[name] = sha(out/name)
result = {'status':'PASS: isolated component matches all eight survey wall faces and exact encoded roof part',
          'building':spec['building'], 'wallFaces':8, 'wallTriangles':count//3,
          'meshSha256':sha(out/record['meshFile']), 'roofSha256':sha(out/source['roofFile']),
          'existingCollisionFileSha256':sha(out/source['collisionFile']),
          'otherPhotoPlansUnchanged':len(old_plans['plans'])-1,
          'otherRenderEntriesUnchanged':len(before['tiles']),
          'retainedMeshSha256':retained, 'fullDataVerified':args.full_data,
          'cleanupAreaSquareMetres':cleanup.area, 'protectedNeighbourOverlapSquareMetres':cleanup.intersection(protected).area,
          'manifestSha256':sha(out/'manifest.json'), 'validatorSha256':sha(Path(__file__)),
          'nativeReviewed':False, 'installed':False,
          'remainingChecks':['Material routing and release integration','Independent packaged collision-packet comparison','Matched native walking/aerial inspection and save preservation'],
          'qualification':spec['qualification']}
(out/'cyclotron-annex-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['qualification','remainingChecks','retainedMeshSha256']},indent=2))

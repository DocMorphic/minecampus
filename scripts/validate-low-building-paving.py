#!/usr/bin/env python3
"""Check paving source bindings, surveyed exclusions and both render passes."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'minecraft/exterior'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
spec = json.loads((SOURCE / 'low-building-paving.json').read_text())
manifest = json.loads((ROOT / 'dist-minecraft/exterior/manifest.json').read_text())
frame = manifest['groundMaterialFrame']
assert hashlib.sha256(json.dumps(frame, sort_keys=True).encode()).hexdigest() == spec['groundFrameSha256']
assert spec['aerialSource'] in json.loads((SOURCE / 'sources.json').read_text())['dop20']
assert sha(ROOT / '.cache' / spec['aerialCacheFile']) == spec['aerialSource']['sha256']
assert sha(SOURCE / spec['material']) == spec['materialSha256']
assert abs(np.linalg.norm(spec['pavingAxisMC']) - 1) < 1e-10
surface = next(s for s in manifest['supplementalSurfaces'] if s['name'] == 'low-building-courtyard-ground')
courtyard = unary_union([Polygon(p['ring'], p['holes']) for p in surface['rings']])
footprints = unary_union([Polygon(np.asarray(r)[:, [0, 2]]).buffer(0)
                         for b in manifest['buildings'] for r in b['grounds']])
patches = []
for region in spec['regions']:
    points = np.array(region['polygonEPSG25832']) - frame['originUtm']
    projected = np.column_stack([points, np.ones(len(points))]) @ frame['fit']
    assert np.max(np.abs(projected - region['polygonMC'])) < 1e-8
    patch = Polygon(region['polygonMC'])
    assert patch.is_valid and patch.area > 1
    assert patch.difference(courtyard).area < 1e-8
    assert patch.intersection(footprints).area < 1e-8
    patches.append(patch)
domain = unary_union(patches)
# Small overlaps connect the inferred walk to the two visible patio ends.
assert domain.geom_type == 'Polygon', 'Paving route must remain connected'
subprocess.run([sys.executable, str(ROOT / 'scripts/build-low-building-paving.py'), '--check'], check=True)
main = (SOURCE / 'shaders/campus_ground.fsh').read_text()
reflection = (SOURCE / 'shaders/campus_reflection.fsh').read_text()
assert 'if(abs(MaterialDetail-1.0)<.1||physicsGround) {\n        float courtyardCoverage=' in main
assert 'if(SurveyedGround>.5) {\n        float courtyardCoverage=' in reflection
assert 'courtyardPavingAlbedo(worldPosition)' in main and 'courtyardPavingAlbedo(worldPosition)' in reflection
result = {'status': 'PASS: pinned aerial, shared material, projection and building exclusions',
          'areaSquareMetres': domain.area, 'buildingOverlapSquareMetres': domain.intersection(footprints).area,
          'sourceSha256': sha(SOURCE / 'low-building-paving.json'),
          'generatorSha256': sha(ROOT / 'scripts/build-low-building-paving.py'),
          'validatorSha256': sha(Path(__file__)),
          'shaderHashes': {n: sha(SOURCE / 'shaders' / n) for n in ['campus_ground.fsh', 'campus_reflection.fsh']},
          'nativeVisualAcceptance': False}
(ROOT / 'dist-minecraft/exterior/low-building-paving-validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

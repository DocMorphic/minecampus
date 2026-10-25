"""Retain the cyclotron annex's surveyed stepped envelope without baked foliage.

The wall finish is provisional. No unobserved windows, doors or interiors are
invented; the original roof part and existing collision files remain exact.
"""
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union


def build(ctx):
    root, out, meta, encode = [ctx[k] for k in ('ROOT', 'OUT', 'metadata', 'encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root / 'minecraft/exterior/cyclotron-annex.json'
    spec = json.loads(source.read_text())
    reference = root / 'minecraft/exterior' / spec['reference']
    assert sha(reference) == spec['referenceSha256']
    plans_file = out / 'photo-facades.json'
    plans = json.loads(plans_file.read_text())
    plan = next(p for p in plans['plans'] if p['id'] == spec['building'])
    walls = plan['walls']
    signature = hashlib.sha256(json.dumps(walls, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert signature == spec['surveyWallsSha256']
    assert len(walls) == spec['expectedWallCount']
    assert spec['runtimeId'] not in [t['runtimeId'] for t in meta['tiles']]
    vertices = [[*wall['vertices'][i], .5, .5] for wall in walls for i in wall['indices']]
    # Append the complete encoded roof part, preserving every vertex and texel.
    roof = (out / plan['roofFile']).read_bytes()
    assert roof[:4] == b'ECT1' and struct.unpack_from('<i', roof, 4)[0] == 1
    body = bytearray(encode([(vertices, Image.new('RGBA', (1, 1), tuple(spec['wallColour'])))]))
    assert roof[8:32] == body[8:32], 'Roof and wall encodings must share the same anchor'
    struct.pack_into('<i', body, 4, 2)
    body.extend(roof[32:])
    name = spec['building'] + '-cyclotron-annex.ect'
    assert not (out / name).exists()
    (out / name).write_bytes(body)
    meta['tiles'].append({'file': name, 'kind': 'reconstruction', 'runtimeId': spec['runtimeId'],
                          'profile': 'cyclotron-annex', 'bounds': plan['bounds'], 'alwaysVisible': True})
    footprints = {
        b['id']: unary_union([Polygon([(p[0], p[2]) for p in ring]).buffer(0) for ring in b['grounds']])
        for b in meta['buildings']
    }
    neighbours = unary_union([p for key, p in footprints.items() if key != spec['building']])
    domain = footprints[spec['building']].buffer(spec['cleanupMarginMetres'], join_style=2)
    domain = domain.difference(neighbours.buffer(spec['neighbourGuardMetres']))
    polygons = [domain] if domain.geom_type == 'Polygon' else list(domain.geoms)
    rings = [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]}
             for p in polygons if p.geom_type == 'Polygon' and p.area > 1e-8]
    assert rings
    for ring in rings:
        meta['replacements'].append(dict(ring, y0=plan['bounds'][0][1]-.1,
                                         y1=plan['bounds'][1][1]+spec['roofPaddingMetres'],
                                         kind='architecture', alwaysVisible=True))
    for wall in walls:
        wall['reconstructed'] = True
    plan.update(manualRoof=True, retirementBoundary=rings)
    # Keep existing retirement/collision records: the added render mesh has the
    # same surveyed triangles. Packet equivalence must be checked before release.
    plans_file.write_text(json.dumps(plans, separators=(',', ':')))
    meta['architecture']['cyclotronAnnex'] = {
        'sourceFile': source.name, 'sourceSha256': sha(source),
        'generatorFile': 'scripts/exterior_cyclotron_annex.py',
        'generatorSha256': sha(Path(__file__)), 'referenceFile': spec['reference'],
        'referenceSha256': sha(reference), 'meshFile': name, 'meshSha256': sha(out/name),
        'roofFile': plan['roofFile'], 'roofSha256': sha(out/plan['roofFile']),
        'collisionFile': plan['collisionFile'], 'collisionSha256': sha(out/plan['collisionFile']),
        'wallFaces': len(walls), 'wallTriangles': len(vertices)//3,
        'retirement': rings, 'qualification': spec['qualification']
    }
    print('Cyclotron annex: eight exact surveyed faces and original roof; provisional wall finish', flush=True)


if __name__ == '__main__':
    import argparse
    import shutil

    parser = argparse.ArgumentParser(description='Build an isolated annex component; does not alter the installed game or release data.')
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root/'minecraft/exterior/cyclotron-annex.json').read_text())
    meta = json.loads((args.baseline/'manifest.json').read_text())
    plans = json.loads((args.baseline/'photo-facades.json').read_text())
    plan = next(p for p in plans['plans'] if p['id'] == spec['building'])
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ['photo-facades.json', plan['roofFile'], plan['collisionFile']]:
        shutil.copy2(args.baseline/name, args.output/name)

    def encode(parts):
        payload = bytearray(b'ECT1' + struct.pack('<i3d', len(parts), 0, 0, 0))
        for vertices, texture in parts:
            texture = texture.convert('RGBA')
            payload += struct.pack('<3i4B', len(vertices), texture.width, texture.height, 255, 255, 255, 255)
            payload += np.asarray(vertices, dtype='<f4').tobytes() + texture.tobytes()
        return payload

    build({'ROOT':root, 'OUT':args.output, 'metadata':meta, 'encode':encode})
    (args.output/'manifest.json').write_text(json.dumps(meta, separators=(',', ':')))

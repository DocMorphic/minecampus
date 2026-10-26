#!/usr/bin/env python3
"""Verify scoped facade changes, closed opening surfaces and retained source data."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', type=Path, required=True)
parser.add_argument('--directory', type=Path, default=root/'dist-minecraft/exterior')
args = parser.parse_args()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
before, current = [read(p/'manifest.json') for p in (args.baseline, args.directory)]
old_plans, new_plans = [read(p/'photo-facades.json') for p in (args.baseline, args.directory)]
record = current['architecture']['galileoLowBuildings']
spec = read(root/'minecraft/exterior'/record['sourceFile'])
for p, key in [(root/'minecraft/exterior'/record['sourceFile'], 'sourceSha256'), (root/record['generatorFile'], 'generatorSha256'), (root/'minecraft/exterior'/record['referenceFile'], 'referenceSha256')]:
    assert sha(p) == record[key]
assert current['tiles'][:-2] == before['tiles']
assert current['replacements'][:len(before['replacements'])] == before['replacements']
assert {k:v for k,v in current['architecture'].items() if k != 'galileoLowBuildings'} == before['architecture']
for k in before:
    if k not in ('tiles', 'replacements', 'architecture'):
        assert before[k] == current[k], k
targets = {b['id']:b for b in spec['buildings']}
assert set(targets) == {'DEBY_LOD2_5284438', 'DEBY_LOD2_5284436'}
assert {k:v for k,v in old_plans.items() if k != 'plans'} == {k:v for k,v in new_plans.items() if k != 'plans'}
retained_names = {t['file'] for t in before['tiles']}
retained_names.update(p[k] for p in old_plans['plans'] for k in ('roofFile', 'collisionFile'))
retained = {}
for name in sorted(retained_names):
    assert sha(args.baseline/name) == sha(args.directory/name), name
    retained[name] = sha(args.directory/name)
footprints = {b['id']:unary_union([Polygon([(v[0],v[2]) for v in ring]).buffer(0) for ring in b['grounds']]) for b in before['buildings']}


def decode(path):
    raw = path.read_bytes()
    count, *anchor = struct.unpack_from('<i3d', raw, 4)
    offset = 32; result = []
    for part in range(count):
        start = offset
        n, w, h = struct.unpack_from('<3i', raw, offset); offset += 16
        vertices = np.frombuffer(raw, dtype='<f4', count=n*5, offset=offset).reshape(-1,5)[:,:3]+anchor
        offset += n*20+w*h*4
        assert np.isfinite(vertices).all() and n%3 == 0
        result.append((vertices.reshape(-1,3,3), raw[start:offset]))
    assert offset == len(raw)
    return result


def ray_hit(origin, direction, triangles):
    if not len(triangles):
        return float('inf')
    edge1=triangles[:,1]-triangles[:,0]; edge2=triangles[:,2]-triangles[:,0]
    h=np.cross(np.broadcast_to(direction,edge2.shape),edge2); det=np.sum(edge1*h,axis=1)
    valid=np.abs(det)>1e-8
    inv=np.divide(1,det,out=np.zeros_like(det),where=valid)
    s=origin-triangles[:,0]; u=inv*np.sum(s*h,axis=1); q=np.cross(s,edge1)
    v=inv*np.sum(q*direction,axis=1); t=inv*np.sum(edge2*q,axis=1)
    valid &= (u>=-1e-6)&(v>=-1e-6)&(u+v<=1+1e-6)&(t>1e-6)
    return float(np.min(t[valid])) if valid.any() else float('inf')


for bid in targets:
    old=next(p for p in old_plans['plans'] if p['id']==bid)
    triangles=decode(args.baseline/old['roofFile'])[0][0]
    footprints[bid]=unary_union([Polygon(t[:,[0,2]]) for t in triangles]).buffer(0)
    if bid=='DEBY_LOD2_5284436':
        assert footprints[bid].geom_type=='Polygon' and len(footprints[bid].interiors)==1


checks=[]
assert len(old_plans['plans']) == len(new_plans['plans'])
for old, new in zip(old_plans['plans'], new_plans['plans']):
    assert old['id'] == new['id']
    if old['id'] not in targets:
        assert old == new
        continue
    bid=old['id']; b=next(b for b in record['buildings'] if b['building']==bid)
    expected=json.loads(json.dumps(old))
    for wall in expected['walls']:
        wall['reconstructed']=True
    expected.update(manualRoof=True,retirementBoundary=b['retirement'])
    assert expected == new
    parts=decode(args.directory/b['meshFile']); roof=decode(args.baseline/old['roofFile'])
    assert len(parts)==6 and parts[-1][1]==roof[0][1]
    for triangle in parts[1][0]:
        normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0])
        assert np.linalg.norm(normal)>1e-7
        normal/=np.linalg.norm(normal)
        centre=triangle.mean(0)
        assert not footprints[bid].contains(Point((centre+normal*.4)[[0,2]])), 'Glass winding points inward'
        assert footprints[bid].contains(Point((centre-normal*.1)[[0,2]])), 'Glass backing outside survey envelope'
    assert sha(args.directory/b['meshFile'])==b['meshSha256']
    tile=next(t for t in current['tiles'] if t['runtimeId']==b['runtimeId'])
    assert tile['collisionParts']==[], 'Original survey collision remains authoritative'
    assert len(b['faces'])==len(old['walls'])
    tested=0
    for face in b['faces']:
        for control in face['openings']:
            p=np.array(control['target']); n=np.array(control['normal'])
            assert footprints[bid].contains(Point(p[[0,2]])), 'Recess goes outside building'
            assert not footprints[bid].contains(Point((p+n*.6)[[0,2]])), 'Wrong outward normal'
            hits=[ray_hit(p+n*.6,-n,t) for t,_ in parts[:-1]]
            assert abs(hits[control['part']]-.6)<.002
            assert min(hits)>=.598, (bid, face['face'], control, hits, 'Opaque surface obstructs opening')
            tested+=1
    cleanup=unary_union([Polygon(x['ring'],x['holes']) for x in b['retirement']])
    protected=unary_union([p for key,p in footprints.items() if key!=bid]).buffer(spec['neighbourGuardMetres'])
    assert cleanup.intersection(protected).area<1e-7
    assert cleanup.difference(footprints[bid].buffer(spec['cleanupMarginMetres'],join_style=2)).area<1e-7
    checks.append({'building':bid,'faces':len(b['faces']),'openingRays':tested,'roofSha256':b['roofSha256'],'collisionSha256':b['collisionSha256'],'meshSha256':b['meshSha256'],'cleanupAreaSquareMetres':cleanup.area,'protectedNeighbourOverlapSquareMetres':cleanup.intersection(protected).area})
result={'status':'PASS: two bounded surveyed exteriors, correctly oriented closed recesses, exact roofs and all prior mesh/collision data retained','manifestSha256':sha(args.directory/'manifest.json'),'validatorSha256':sha(Path(__file__)),'sourceSha256':record['sourceSha256'],'generatorSha256':record['generatorSha256'],'referenceSha256':record['referenceSha256'],'retainedMeshSha256':retained,'buildings':checks,'nativeReviewed':False,'qualification':spec['qualification']}
(args.directory/'galileo-low-buildings-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='retainedMeshSha256'},indent=2))

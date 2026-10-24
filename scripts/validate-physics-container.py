#!/usr/bin/env python3
"""Check surveyed roof, bounded retirement, real window holes and glazing winding."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');folder=p.parse_args().directory
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((folder/'manifest.json').read_text());record=manifest['architecture']['physicsContainer'];source=root/'minecraft/exterior'/record['sourceFile'];spec=json.loads(source.read_text())
assert sha(root/record['generatorFile'])==record['generatorSha256'];assert sha(source)==record['sourceSha256'];assert sha(root/'minecraft/exterior'/spec['reference'])==spec['referenceSha256']
plans=json.loads((folder/'photo-facades.json').read_text())['plans'];plan=next(p for p in plans if p['id']==spec['building']);tile=next(t for t in manifest['tiles']if t['runtimeId']==spec['runtimeId'])
def decode(path):
 data=path.read_bytes();count,*anchor=struct.unpack_from('<i3d',data,4);offset=32;parts=[]
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',data,offset);offset+=16;v=np.frombuffer(data,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);v[:,:3]+=anchor;offset+=n*20;texture=data[offset:offset+w*h*4];offset+=w*h*4;parts.append((v,texture))
 assert offset==len(data);assert all(np.isfinite(v).all()for v,t in parts);return parts
parts=decode(folder/tile['file']);roof=decode(folder/plan['roofFile']);assert len(parts)==5 and len(roof)==1
assert np.array_equal(parts[4][0],roof[0][0]);assert parts[4][1]==roof[0][1]
expected=np.array(plan['roofTriangles']).reshape(-1,3);error=float(np.max(np.abs(parts[4][0][:,:3]-expected)));assert error<.0001 and len(expected)==18
assert all(w['reconstructed']for w in plan['walls'])and len(plan['walls'])==8
# Each independently specified opening must hit its recessed pane, with outward
# winding, and must not intersect cladding in front of it.
checks=[]
for control in record['openingControls']:
 target=np.array(control['position']);n=np.array(control['normal']);wall=plan['walls'][control['face']];u=np.array(wall['direction']);hits=[]
 for part,(vertices,_) in enumerate(parts):
  for tri in vertices[:,:3].reshape(-1,3,3):
   projected=np.column_stack(((tri-target)@u,tri[:,1]-target[1]));polygon=Polygon(projected)
   if polygon.area<1e-8 or not polygon.covers(Point(0,0)):continue
   coeff=np.linalg.solve(np.column_stack([projected,np.ones(3)]),(tri-target)@n);distance=float(coeff[2]);hits.append((part,distance,float(np.dot(np.cross(tri[1]-tri[0],tri[2]-tri[0]),n))))
 assert any(part==1 and abs(d)<.0001 and winding>0 for part,d,winding in hits),control
 assert not any(part!=1 and d>-.0001 for part,d,winding in hits),control
 checks.append(control['face'])
assert len(checks)==sum(len(v)for v in spec['openings'].values())
# Do not retire any neighbouring reconstructed building's surveyed footprint.
retirement=unary_union([Polygon(r['ring'],r['holes'])for r in record['retirement']])
for other in plans:
 if other['id']==spec['building']:continue
 roofxy=[Polygon(np.asarray(t)[:,[0,2]])for t in other.get('roofTriangles',[])]
 if roofxy:assert retirement.intersection(unary_union(roofxy)).area<.001,other['id']
# The new ground exactly fills the former neighbouring-footprint guard;
# verify it covers each wall midpoint, including the narrow external gap.
ground_tile=next(t for t in manifest['tiles']if t['runtimeId']==spec['groundRuntimeId'])
ground_parts=decode(folder/ground_tile['file']);ground_shape=unary_union([Polygon(t[:,[0,2]])for v,_ in ground_parts for t in v[:,:3].reshape(-1,3,3)])
for wall in record['surveyWalls']:
 midpoint=np.array(wall['anchor'])+np.array(wall['direction'])*(wall['bounds'][1][0]/2)+np.array(wall['normal'])*.25
 assert ground_shape.buffer(.0001).covers(Point(midpoint[0],midpoint[2]))
result={'status':'PASS: surveyed roof/pixels, bounded source retirement, real recessed openings and outward panes','manifestSha256':sha(folder/'manifest.json'),'sourceSha256':sha(source),'validatorSha256':sha(Path(__file__)),'roofMaximumCoordinateErrorMetres':error,'paneControlsVerified':len(checks),'tileSha256':{t['file']:sha(folder/t['file'])for t in [tile,ground_tile]},'qualification':'Independent geometry checks; architectural detail remains an estimate and native acceptance is separate.'}
(folder/'physics-container-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

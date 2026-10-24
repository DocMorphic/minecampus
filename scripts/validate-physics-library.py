#!/usr/bin/env python3
"""Validate library source provenance, roof preservation and an open undercroft."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from shapely.geometry import Polygon,Point
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');folder=p.parse_args().directory
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
manifest=json.loads((folder/'manifest.json').read_text());record=manifest['architecture']['physicsLibrary'];source=root/'minecraft/exterior'/record['sourceFile'];spec=json.loads(source.read_text());assert sha(root/record['generatorFile'])==record['generatorSha256'];assert sha(source)==record['sourceSha256'];assert sha(root/'minecraft/exterior'/spec['reference'])==spec['referenceSha256']
plan=next(p for p in json.loads((folder/'photo-facades.json').read_text())['plans']if p['id']==spec['building']);tile=next(t for t in manifest['tiles']if t['runtimeId']==spec['runtimeId'])
def decode(path):
 data=path.read_bytes();count,*anchor=struct.unpack_from('<i3d',data,4);offset=32;parts=[]
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',data,offset);offset+=16;v=np.frombuffer(data,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);v[:,:3]+=anchor;offset+=n*20;texture=data[offset:offset+w*h*4];offset+=w*h*4;parts.append((v,texture))
 assert offset==len(data);return parts
parts=decode(folder/tile['file']);roof=decode(folder/plan['roofFile']);assert len(parts)==5 and len(roof)==1
assert np.array_equal(parts[4][0],roof[0][0]);assert parts[4][1]==roof[0][1]
expected=np.array(plan['roofTriangles']).reshape(-1,3);roof_error=float(np.max(np.abs(parts[4][0][:,:3]-expected)));assert roof_error<.0001
# Shoot a vertical ray at the centre, deliberately away from the four estimated piers.
body=Polygon(record['bodyFootprint']);centre=body.centroid;heights=[]
for vertices,_ in parts[:4]:
 for t in vertices[:,:3].reshape(-1,3,3):
  xz=t[:,[0,2]];poly=Polygon(xz)
  if poly.area<1e-9 or not poly.buffer(1e-8).covers(centre):continue
  coefficients=np.linalg.solve(np.column_stack([xz,np.ones(3)]),t[:,1]);heights.append(float(coefficients@[centre.x,centre.y,1]))
assert heights and abs(min(heights)-record['levelsMC']['underside'])<.0001
# A horizontal cut through the tapered edge must be one closed perimeter,
# including its mitred corners. Five independently offset walls failed this.
cut=(record['levelsMC']['underside']+record['levelsMC']['concreteEdgeTop'])/2
nodes=[];edges=[]
def node(point):
 for i,p in enumerate(nodes):
  if np.linalg.norm(p-point)<.0001:return i
 nodes.append(point);return len(nodes)-1
for t in parts[0][0][:,:3].reshape(-1,3,3):
 if t[:,1].min()>=cut or t[:,1].max()<=cut:continue
 hits=[]
 for a,b in zip(t,np.roll(t,-1,axis=0)):
  if (a[1]-cut)*(b[1]-cut)<0:hits.append(a+(b-a)*(cut-a[1])/(b[1]-a[1]))
 if len(hits)==2:edges.append(tuple(node(p[[0,2]])for p in hits))
assert len(edges)==8 and len(nodes)==8
assert all(sum(i in edge for edge in edges)==2 for i in range(len(nodes)))
seen={0}
while True:
 expanded=seen|{v for edge in edges if any(i in seen for i in edge)for v in edge}
 if expanded==seen:break
 seen=expanded
assert len(seen)==len(nodes)
assert record['columnCount']==4
assert all(w['reconstructed']for w in plan['walls'])and len(plan['walls'])==9
for c in record['openingControls']:
 assert c['part']==1 and len(c['position'])==3 and abs(np.linalg.norm(c['normal'])-1)<1e-7
# Ground exists under the body and bridge; it is a separate mineable surface.
ground=decode(folder/record['groundTiles'][0]);ground_heights=[]
for t in ground[0][0][:,:3].reshape(-1,3,3):
 poly=Polygon(t[:,[0,2]])
 if poly.area>1e-9 and poly.buffer(1e-8).covers(centre):
  c=np.linalg.solve(np.column_stack([t[:,[0,2]],np.ones(3)]),t[:,1]);ground_heights.append(float(c@[centre.x,centre.y,1]))
assert ground_heights and min(heights)-max(ground_heights)>2.2
result={'status':'PASS: preserved roof geometry/pixels, source provenance, central exterior clearance and finite glazing controls','manifestSha256':sha(folder/'manifest.json'),'sourceSha256':sha(source),'validatorSha256':sha(Path(__file__)),'roofMaximumCoordinateErrorMetres':roof_error,'centreGroundHeightMC':max(ground_heights),'centreUndersideHeightMC':min(heights),'centreClearanceMetres':min(heights)-max(ground_heights),'tileSha256':{t['file']:sha(folder/t['file'])for t in manifest['tiles']if t['runtimeId']in [spec['runtimeId'],spec['groundRuntimeId']]},'qualification':'Roof matches BVV-derived plan; this validates representation, not real-world architectural accuracy. Columns and facade dimensions remain estimates. Native collision and visual acceptance are separate.'}
(folder/'physics-library-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

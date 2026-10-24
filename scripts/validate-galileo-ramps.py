#!/usr/bin/env python3
"""Verify bounded ramp cuts, surrounding assets, source levels and collision planes."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
root=Path(__file__).resolve().parents[1];out=root/'dist-minecraft/exterior'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);args=p.parse_args();old=args.baseline/'exterior'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');before=read(old/'manifest.json');c=m['architecture']['galileoRamps'];cut=unary_union([Polygon(r)for r in c['cutRingsMC']])
assert cut.is_valid and 250<cut.area<400
assert sha(root/'minecraft/exterior'/c['sourceFile'])==c['sourceSha256']
for k in before:
 if k not in ['tiles','architecture','replacements','terrainOverrides']:assert before[k]==m[k],k
for k in before['architecture']:assert before['architecture'][k]==m['architecture'][k],k
assert m['replacements'][:len(before['replacements'])]==before['replacements']
assert m['terrainOverrides'][:len(before['terrainOverrides'])]==before['terrainOverrides']
changed={t['file'] for t in c['alteredGroundTiles']};assert len(changed)==2
for t in before['tiles']:
 if t['file'] not in changed:assert (old/t['file']).read_bytes()==(out/t['file']).read_bytes(),t['file']
assert len(m['tiles'])==len(before['tiles'])+1
def decode(path):
 raw=path.read_bytes();count=struct.unpack_from('<i',raw,4)[0];off=32;parts=[]
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',raw,off);off+=16;v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=off).reshape(-1,3,5).astype(float);off+=n*20;tex=raw[off:off+w*h*4];off+=w*h*4;parts.append((v,tex))
 assert off==len(raw);return parts
max_error=0.;removed_area=0.;remaining_intrusion=0.
for record in c['alteredGroundTiles']:
 name=record['file'];assert sha(old/name)==record['beforeSha256'] and sha(out/name)==record['afterSha256']
 (a,atex),=decode(old/name);(b,btex),=decode(out/name);assert atex==btex
 def area(t):
  d=t[:,1]-t[:,0];e=t[:,2]-t[:,0];return abs(d[:,0]*e[:,2]-d[:,2]*e[:,0])/2
 removed_area+=area(a).sum()-area(b).sum()
 # Distant triangles remain exactly intact, with no approximation or resampling.
 near=box(cut.bounds[0]-.1,cut.bounds[1]-.1,cut.bounds[2]+.1,cut.bounds[3]+.1)
 def split(v):
  selected=[];far=[]
  for t in v:
   poly=Polygon(t[:,[0,2]])
   (selected if poly.intersects(near) else far).append(t)
  return np.array(selected),np.array(far)
 an,af=split(a);bn,bf=split(b);assert np.array_equal(af,bf)
 polygons=[Polygon(t[:,[0,2]]) for t in an];tree=STRtree(polygons)
 for t in bn:remaining_intrusion+=Polygon(t[:,[0,2]]).intersection(cut).area
 for vertex in np.unique(bn.reshape(-1,5),axis=0):
  point=Point(vertex[[0,2]]);ids=tree.query(point.buffer(.00005));best=1e9
  for i in ids:
   t=an[i];matrix=np.column_stack((t[:,[0,2]],np.ones(3)));weights=np.array([vertex[0],vertex[2],1.])@np.linalg.inv(matrix)
   if min(weights)<-.0002:continue
   best=min(best,float(np.max(np.abs(weights@t-vertex))))
  assert best<.001,(name,vertex,best);max_error=max(max_error,best)
assert abs(removed_area-cut.area)<.02,(removed_area,cut.area)
assert remaining_intrusion<.01,remaining_intrusion
parts=decode(out/'galileo-east-ramps.ect');assert len(parts)==4
floors=parts[1][0];probes=[]
for ramp in c['ramps']:
 centre=np.array(ramp['centrelineMC']);assert np.all(np.diff(centre[:,1])<.03)
 assert ramp['upperHeightDHHN2016']-ramp['lowerHeightDHHN2016']>2.5
 for f in [.2,.5,.8]:
  point=centre[int(f*(len(centre)-1))];x,z=np.floor(point[[0,2]])+.5
  a=floors[:,0,:3];u=floors[:,1,:3]-a;v=floors[:,2,:3]-a;det=u[:,0]*v[:,2]-u[:,2]*v[:,0];f=((x-a[:,0])*v[:,2]-(z-a[:,2])*v[:,0])/det;g=(u[:,0]*(z-a[:,2])-u[:,2]*(x-a[:,0]))/det
  hits=(f>=0)&(g>=0)&(f+g<=1);heights=(a[:,1]+f*u[:,1]+g*v[:,1])[hits];assert len(heights)==1
  probe={'ramp':ramp['name'],'x':float(x),'z':float(z),'meshHeight':float(heights[0])};probes.append(probe)
  matches=[p for p in m['terrainOverrides'] if Polygon(p['ring']).contains(Point(x,z))];assert matches and 'plane'in matches[0]
  assert abs(np.dot(matches[0]['plane'],[x,z,1])-heights[0])<.0001
# Every ramp-floor triangle has a corresponding sloped collision override.
newplanes=m['terrainOverrides'][len(before['terrainOverrides']):];assert len(newplanes)==c['collisionPlaneCount']
for t in floors:
 pt=t[:,:3].mean(0);matches=[p for p in newplanes if Polygon(p['ring']).contains(Point(pt[0],pt[2]))];assert matches
 assert abs(np.dot(matches[0]['plane'],[pt[0],pt[2],1])-pt[1])<.0001
report={'status':'PASS: two bounded terrain cuts, other 97 render meshes unchanged, original clipped UVs preserved, both sloped floors match collision planes','changedGroundTiles':sorted(changed),'removedAreaSquareMetres':removed_area,'specifiedCutAreaSquareMetres':cut.area,'remainingGroundIntrusionSquareMetres':remaining_intrusion,'maximumClippedVertexInterpolationError':max_error,'nativeProbes':probes,'qualification':c['qualification']}
(out/'galileo-ramps-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

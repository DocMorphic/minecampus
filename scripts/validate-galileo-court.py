#!/usr/bin/env python3
"""Verify courtyard cut, bounded changes, source heights and surviving terrain UVs."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
root=Path(__file__).resolve().parents[1];out=root/'dist-minecraft/exterior'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);args=p.parse_args();old=args.baseline/'exterior'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');before=read(old/'manifest.json');c=m['architecture']['galileoCourt'];cut=Polygon(c['cutRingMC'],c['cutHolesMC'])
assert cut.is_valid and 500<cut.area<700
assert sha(root/'minecraft/exterior'/c['sourceFile'])==c['sourceSha256']
for k in ['terrainGuide','terrainSampling','siteGrading','surfaceGuide','protectedFootprints','groundSurfaces','vegetation','buildings','photoFacades']:
 assert before[k]==m[k],k
changed={t['file'] for t in c['alteredGroundTiles']};assert len(changed)==2
for t in before['tiles']:
 if t['file'] not in changed:assert (old/t['file']).read_bytes()==(out/t['file']).read_bytes(),t['file']
assert len(m['tiles'])==len(before['tiles'])+2

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
assert c['stairRisers']==sum(f['risers'] for f in c['stairFlights'])==27
assert len(c['stairFlights'])==5 and c['stairWidthMetres']==4
assert abs(c['floorHeightDHHN2016']-470.5589287)<.002
parts=decode(out/'galileo-north-court.ect');assert len(parts)==5
floor=parts[3][0];assert np.ptp(floor[:,:,1])<.003 and abs(np.median(floor[:,:,1])-c['floorHeightMC'])<.003
assert len(m['terrainOverrides'])==34
handrails=next(t for t in m['tiles'] if t.get('profile')=='galileo-court-handrails');assert handrails['collisionParts']==[]
for key,value in before['architecture'].items():assert m['architecture'][key]==value,key
# Tolerate float32 edge noise only; the lower landing must actually join the court.
joined=unary_union([Polygon(t[:,[0,2]])for t in floor]).buffer(.00005)
assert joined.geom_type=='Polygon','Disconnected lower landing / courtyard floor'
report={'status':'PASS: exact bounded terrain cut, unchanged surrounding assets, interpolated original terrain UV/positions, surveyed floor and 27 stepped risers','alteredGroundTiles':sorted(changed),'unchangedPriorRenderTiles':len(before['tiles'])-len(changed),'removedAreaSquareMetres':removed_area,'specifiedCutAreaSquareMetres':cut.area,'remainingGroundIntrusionSquareMetres':remaining_intrusion,'maximumClippedVertexInterpolationError':max_error,'floorHeightMC':c['floorHeightMC'],'note':c['qualification']}
(out/'galileo-court-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

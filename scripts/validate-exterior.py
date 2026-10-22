#!/usr/bin/env python3
"""Verify the complete generated render stream, not just source file existence."""
from pathlib import Path
import json,math,struct
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'dist-minecraft/exterior';manifest=json.loads((folder/'manifest.json').read_text())
triangles=0;texture_bytes=0
for spec in manifest['tiles']:
 data=(folder/spec['file']).read_bytes();assert data[:4]==b'ECT1',spec['file']
 count,*anchor=struct.unpack_from('<i3d',data,4);offset=32
 assert 0<count<100 and all(math.isfinite(x) for x in anchor)
 for part in range(count):
  vertices,w,h=struct.unpack_from('<3i',data,offset);offset+=16
  assert vertices>0 and vertices%3==0 and 0<w<=8192 and 0<h<=8192,(spec['file'],vertices,w,h)
  positions=[]
  for x,y,z,u,v in struct.iter_unpack('<5f',data[offset:offset+vertices*20]):
   assert all(math.isfinite(f) for f in [x,y,z,u,v]),spec['file']
   assert -.001<=u<=1.001 and -.001<=v<=1.001,(spec['file'],u,v)
   positions.append([x+anchor[0],y+anchor[1],z+anchor[2]])
  offset+=vertices*20+w*h*4;assert offset<=len(data),spec['file'];texture_bytes+=w*h*4;triangles+=vertices//3
  for p in positions:
   assert all(spec['bounds'][0][c]-.01<=p[c]<=spec['bounds'][1][c]+.01 for c in range(3)),(spec['file'],p,spec['bounds'])
 assert offset==len(data),(spec['file'],offset,len(data))
assert sum(t['kind']=='ground' for t in manifest['tiles'])==36
assert sum(t['kind']=='reconstruction' for t in manifest['tiles'])>=5
assert len(manifest.get('vegetation',{}).get('trees',[]))>100
assert len(manifest['buildings'])>=106
surface=manifest['surfaceGuide'];assert surface['width']==manifest['terrainGuide']['width'] and surface['height']==manifest['terrainGuide']['height']
assert len(surface['heights'])==surface['width']*surface['height'] and all(math.isfinite(v) for v in surface['heights'])
assert all(top>=point[1]-.01 for top,point in zip(surface['heights'],manifest['terrainGuide']['points']))
result={'renderTiles':len(manifest['tiles']),'triangles':triangles,'textureBytes':texture_bytes,'surveyedBuildingGuides':len(manifest['buildings']),'detailedBuildings':2+len(manifest.get('architecture',{}).get('buildings',[])),'landscapeStructures':3,'vegetationGroups':sum(t['kind']=='vegetation' for t in manifest['tiles']),'trees':len(manifest['vegetation']['trees']),'status':'PASS: binary integrity, finite positions, UV ranges, mesh bounds and intended coverage'}
(folder/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

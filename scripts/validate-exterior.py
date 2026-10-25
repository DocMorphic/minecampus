#!/usr/bin/env python3
"""Verify the complete generated render stream, not just source file existence."""
from pathlib import Path
import argparse,base64,json,math,struct
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory',type=Path,default=ROOT/'dist-minecraft/exterior')
folder=parser.parse_args().directory;manifest=json.loads((folder/'manifest.json').read_text())
triangles=0;texture_bytes=0;aux_triangles=0;aux_bytes=0
photo_spec=json.loads((folder/manifest['photoFacades']['file']).read_text()) if manifest.get('photoFacades') else {'plans':[]}
extra=[{'file':p['roofFile'],'bounds':p['bounds']}for p in photo_spec['plans']]+manifest.get('photoFacades',{}).get('collisionTiles',[])
for spec in [*manifest['tiles'],*extra]:
 data=(folder/spec['file']).read_bytes();assert data[:4]==b'ECT1',spec['file']
 count,*anchor=struct.unpack_from('<i3d',data,4);offset=32
 assert 0<count<100 and all(math.isfinite(x) for x in anchor)
 if 'fineCollisionMaterials' in spec:
  assert spec.get('kind')=='reconstruction' and len(spec['fineCollisionMaterials'])==count and all(v in [4,6] for v in spec['fineCollisionMaterials'])
 if "collisionParts" in spec:
  selected=spec["collisionParts"];assert isinstance(selected,list) and len(set(selected))==len(selected) and all(type(i) is int and 0<=i<count for i in selected),(spec["file"],selected)
 for part in range(count):
  vertices,w,h=struct.unpack_from('<3i',data,offset);offset+=16
  assert vertices>0 and vertices%3==0 and 0<w<=8192 and 0<h<=8192,(spec['file'],vertices,w,h)
  positions=[]
  for x,y,z,u,v in struct.iter_unpack('<5f',data[offset:offset+vertices*20]):
   assert all(math.isfinite(f) for f in [x,y,z,u,v]),spec['file']
   assert -.001<=u<=1.001 and -.001<=v<=1.001,(spec['file'],u,v)
   positions.append([x+anchor[0],y+anchor[1],z+anchor[2]])
  offset+=vertices*20+w*h*4;assert offset<=len(data),spec['file']
  if spec in extra:aux_bytes+=w*h*4;aux_triangles+=vertices//3
  else:texture_bytes+=w*h*4;triangles+=vertices//3
  for p in positions:
   assert all(spec['bounds'][0][c]-.01<=p[c]<=spec['bounds'][1][c]+.01 for c in range(3)),(spec['file'],p,spec['bounds'])
 assert offset==len(data),(spec['file'],offset,len(data))
original_ground=[t for t in manifest['tiles'] if t['kind']=='ground' and t['file'].startswith('ground-')]
supplemental_ground=list(manifest.get('architecture',{}).get('physicsISite',{}).get('groundTiles',[]))
supplemental_ground+=manifest.get('architecture',{}).get('physicsLibrary',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsContainer',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('p1Complex',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsWoodland',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsNewLaboratory',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsLaboratorySite',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsII',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsWSI',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsZNN',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('riverbank',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsZNNWest',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsCALA',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsLMU',{}).get('groundTiles',[])
supplemental_ground+=manifest.get('architecture',{}).get('physicsLMUCourtyard',{}).get('groundTiles',[])
assert len(original_ground)==36
assert {t['file'] for t in manifest['tiles'] if t['kind']=='ground'}=={t['file'] for t in original_ground}|set(supplemental_ground)
assert sum(t['kind']=='reconstruction' for t in manifest['tiles'])>=5
assert len(manifest.get('vegetation',{}).get('trees',[]))>100
assert len(manifest['buildings'])>=106
surface=manifest['surfaceGuide'];assert surface['width']==manifest['terrainGuide']['width'] and surface['height']==manifest['terrainGuide']['height']
assert len(surface['heights'])==surface['width']*surface['height'] and all(math.isfinite(v) for v in surface['heights'])
assert all(top>=point[1]-.01 for top,point in zip(surface['heights'],manifest['terrainGuide']['points']))
overhang=manifest.get('vegetationOverhang')
if overhang:
 assert (overhang['width'],overhang['height'])==(surface['width'],surface['height'])
 mask=base64.b64decode(overhang['mask'],validate=True)
 assert len(mask)==len(surface['heights']) and set(mask)<={0,1}
 assert len(overhang['roofCeilings'])==len(mask)
 assert all(math.isfinite(y) and y>=p[1]-.01 for y,p in zip(overhang['roofCeilings'],manifest['terrainGuide']['points']))
assert len({p['runtimeId'] for p in photo_spec['plans']})==len(photo_spec['plans'])
for plan in photo_spec['plans']:
 assert plan['walls'] and plan['roofTriangles']
 for wall in plan['walls']:
  assert all(math.isfinite(v) for p in wall['vertices'] for v in p)
  assert wall['indices'] and len(wall['indices'])%3==0
  assert all(0<=i<len(wall['vertices']) for i in wall['indices'])
  assert all(hi>lo for lo,hi in zip(*wall['bounds']))
  if 'groundProfile' in wall:
   profile=wall['groundProfile'];assert len(profile)>=2
   assert all(math.isfinite(v) for p in profile for v in p)
   assert all(a[0]<b[0] for a,b in zip(profile,profile[1:]))
   assert abs(profile[0][0]-wall['bounds'][0][0])<1e-6 and abs(profile[-1][0]-wall['bounds'][1][0])<1e-6
result={'renderTiles':len(manifest['tiles']),'photoFacadeCandidates':len(photo_spec['plans']),'triangles':triangles,'textureBytes':texture_bytes,'auxiliaryTriangles':aux_triangles,'auxiliaryTextureBytes':aux_bytes,'surveyedBuildingGuides':len(manifest['buildings']),'detailedBuildings':2+len(manifest.get('architecture',{}).get('buildings',[])),'landscapeStructures':3,'vegetationGroups':sum(t['kind']=='vegetation' for t in manifest['tiles']),'trees':len(manifest['vegetation']['trees']),'status':'PASS: binary integrity, finite positions, UV ranges, mesh bounds and intended coverage'}
(folder/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

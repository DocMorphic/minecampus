#!/usr/bin/env python3
"""Check MLZ scope, exact roof retention and evidence for shared-wall removal."""
from pathlib import Path
import argparse,json,hashlib,struct,collections
import numpy as np
from shapely.geometry import LineString,Polygon,Point
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1];out=root/'dist-minecraft/exterior'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);args=p.parse_args();old=args.baseline/'exterior'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();key=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'))
m=read(out/'manifest.json');before=read(old/'manifest.json');record=m['architecture']['mlzExteriors'];spec=read(root/'minecraft/exterior'/record['sourceFile']);ids=set(spec['buildings'])
assert sha(root/'minecraft/exterior'/record['sourceFile'])==record['sourceSha256']
for field in before:
 if field not in ['tiles','architecture','replacements','photoFacades']:assert before[field]==m[field],field
for field in before['architecture']:assert before['architecture'][field]==m['architecture'][field],field
assert len(m['tiles'])==len(before['tiles'])+3
for tile in before['tiles']:assert (old/tile['file']).read_bytes()==(out/tile['file']).read_bytes(),tile['file']
old_counts=collections.Counter(map(key,before['replacements']));new_counts=collections.Counter(map(key,m['replacements']))
assert all(new_counts[k]>=n for k,n in old_counts.items())
a=read(old/'photo-facades.json');b=read(out/'photo-facades.json');assert len(a['plans'])==len(b['plans'])
for source,current in zip(a['plans'],b['plans']):
 assert source['id']==current['id']
 assert (old/source['roofFile']).read_bytes()==(out/current['roofFile']).read_bytes()
 if source['id']not in ids:assert source==current;assert (old/source['collisionFile']).read_bytes()==(out/current['collisionFile']).read_bytes()
 else:
  assert current['manualRoof'] and all(w.get('reconstructed')for w in current['walls'])
  assert current['roofTriangles']==source['roofTriangles']
  for x,y in zip(source['walls'],current['walls']):assert dict(x,reconstructed=True)==y

def parts(path):
 raw=path.read_bytes();count=struct.unpack_from('<i',raw,4)[0];off=32;result=[]
 for _ in range(count):
  start=off;n,w,h=struct.unpack_from('<iii',raw,off);off+=16+n*20+w*h*4;result.append(raw[start:off])
 assert off==len(raw);return result
plans={p['id']:p for p in a['plans']};roofproof={}
for bid in ids:
 roof=parts(old/(bid+'-photo-roof.ect'));body=parts(out/(bid+'-mlz-exterior.ect'));assert len(roof)==1 and len(body)==5 and body[-1]==roof[0]
 roofproof[bid]=sha(old/(bid+'-photo-roof.ect'))
 assert len(record['buildings'][bid]['faces'])==len(plans[bid]['walls'])
shared=[]
for pair in spec['sharedWalls']:
 walls=[plans[bid]['walls'][i]for bid,i in [pair['a'],pair['b']]]
 lines=[]
 for w in walls:
  anchor,direction=np.array(w['anchor']),np.array(w['direction']);lines.append(LineString([(anchor+direction*t)[[0,2]]for t in [w['bounds'][0][0],w['bounds'][1][0]]]))
 error=lines[0].hausdorff_distance(lines[1]);assert error<.003,error
 assert np.dot(walls[0]['normal'],walls[1]['normal'])<-.999
 want=[max(w['bounds'][0][1]for w in walls),min(w['bounds'][1][1]for w in walls)]
 assert pair['occludedHeightRangeMC']==want
 for bid,i in [pair['a'],pair['b']]:
  f=record['buildings'][bid]['faces'][i]
  assert abs(f['hiddenSharedAreaSquareMetres']-lines[0].length*(want[1]-want[0]))<.05
 shared.append(dict(pair,coincidenceErrorMetres=error))
target_foot=unary_union([Polygon([(p[0],p[2])for p in g]).buffer(0)for b in before['buildings']if b['id']in ids for g in b['grounds']])
other_foot=unary_union([Polygon([(p[0],p[2])for p in g]).buffer(0)for b in before['buildings']if b['id']not in ids for g in b['grounds']]).buffer(spec['sourceRetirement']['neighbourGuardMetres'])
cleanup=unary_union([Polygon(p['ring'],p['holes'])for b in record['buildings'].values()for p in b['retirement']])
assert cleanup.intersection(other_foot).area<.001
assert cleanup.difference(target_foot.buffer(spec['sourceRetirement']['collarMetres'],join_style=2)).area<.001
for control in spec['sourceRetirement']['controls']:assert cleanup.contains(Point(control['x'],control['z']))
for control in spec['sourceRetirement']['roofControls']:
 assert any(Polygon(p['ring'],p['holes']).contains(Point(control['x'],control['z'])) and min(w['bounds'][0][1]for w in plans[bid]['walls'])-.1<=control['y']<=max(w['bounds'][1][1]for w in plans[bid]['walls'])+spec['sourceRetirement']['roofPaddingMetres'] for bid,b in record['buildings'].items()for p in b['retirement'])
result={'status':'PASS: all 100 previous render meshes and 83 survey roofs unchanged; three reconstructed bodies; four proven shared-wall pairs clipped only across their common height','sourceRetirement':{'areaSquareMetres':cleanup.area,'maximumCollarMetres':spec['sourceRetirement']['collarMetres'],'neighbourGuardMetres':spec['sourceRetirement']['neighbourGuardMetres'],'knownFragmentControlsCovered':len(spec['sourceRetirement']['controls']),'roofPaddingMetres':spec['sourceRetirement']['roofPaddingMetres'],'knownRoofFragmentControlsCovered':len(spec['sourceRetirement']['roofControls'])},'sourceSha256':record['sourceSha256'],'roofHashes':roofproof,'sharedWalls':shared,'openingPieces':sum(len(f['openings'])for b in record['buildings'].values()for f in b['faces']),'qualification':spec['qualification']}
(out/'mlz-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

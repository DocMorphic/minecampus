#!/usr/bin/env python3
"""Verify bounded Galileo paving changes against the preceding complete exterior."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import intersects,points
r=Path(__file__).resolve().parents[1];out=r/'dist-minecraft/exterior'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',required=True,type=Path);args=p.parse_args();old=args.baseline/'exterior'
m=json.loads((out/'manifest.json').read_text());before=json.loads((old/'manifest.json').read_text());spec_path=r/'minecraft/exterior/galileo-frontage-grade.json';spec=json.loads(spec_path.read_text())
assert m['frontageGrading']['sourceSha256']==hashlib.sha256(spec_path.read_bytes()).hexdigest()
assert m['frontageGrading']['patches']==spec['patches']
assert [(t['file'],t['runtimeId'])for t in m['tiles']]==[(t['file'],t['runtimeId'])for t in before['tiles']]
allowed=unary_union([Polygon(p['footprintUtm']).buffer(p['blendMetres']+.0001)for p in spec['patches']])
changed=[];changed_vertices=0;largest=0;triangles=[];previous_triangles=[]
for entry in m['tiles']:
 name=entry['file'];a=(old/name).read_bytes();b=(out/name).read_bytes()
 if a==b:continue
 assert entry['kind']=='ground';changed.append(name)
 assert a[:32]==b[:32];n=struct.unpack_from('<i',a,32)[0];assert a[32:48]==b[32:48] and a[48+n*20:]==b[48+n*20:]
 av=np.frombuffer(a,dtype='<f4',count=n*5,offset=48).reshape(-1,5);bv=np.frombuffer(b,dtype='<f4',count=n*5,offset=48).reshape(-1,5)
 np.testing.assert_array_equal(av[:,3:],bv[:,3:]);np.testing.assert_allclose(av[:,[0,2]],bv[:,[0,2]],rtol=0,atol=.00004)
 e,north=map(int,Path(name).stem.split('-')[1:]);xy=np.column_stack((e+100*av[:,3].astype(float),north+100-100*av[:,4].astype(float)))
 mask=np.any(av!=bv,axis=1);assert np.all(intersects(points(xy[mask]),allowed));np.testing.assert_array_equal(av[~mask],bv[~mask])
 changed_vertices+=int(np.count_nonzero(mask));largest=max(largest,float(np.max(np.abs(av[:,1]-bv[:,1]))));triangles.append(bv[:,:3].reshape(-1,3,3));previous_triangles.append(av[:,:3].reshape(-1,3,3))
assert changed==['ground-698200-5349200.ect'],changed
assert .5<largest<4,largest
for key in before:
 if key not in ['tiles','terrainGuide','surfaceGuide','vegetationOverhang']:assert m[key]==before[key],key
for name in ['ground_surfaces.png','path-surfaces.geojson','promenade-surfaces.geojson','crosspath-surfaces.geojson','cos-site-surfaces.geojson']:
 if (old/name).exists():assert (old/name).read_bytes()==(out/name).read_bytes(),name
oldguide=np.asarray(before['terrainGuide']['points']);newguide=np.asarray(m['terrainGuide']['points']);assert oldguide.shape==newguide.shape
w=m['terrainGuide']['width'];h=m['terrainGuide']['height'];left,bottom,right,top=m['boundsUtm'];xy=np.array([(e,n)for n in np.linspace(bottom,top,h)for e in np.linspace(left,right,w)])
mask=intersects(points(xy),allowed);np.testing.assert_array_equal(oldguide[~mask],newguide[~mask])
for key in ['surfaceGuide','vegetationOverhang']:
 for field in before[key]:
  a,b=before[key][field],m[key][field]
  if a==b:continue
  assert field in ['heights','roofCeilings'],(key,field)
  np.testing.assert_array_equal(np.asarray(a)[~mask],np.asarray(b)[~mask])
def height(tri,x,z):
 a=tri[:,0];u=tri[:,1]-a;v=tri[:,2]-a;det=u[:,0]*v[:,2]-u[:,2]*v[:,0];f=((x-a[:,0])*v[:,2]-(z-a[:,2])*v[:,0])/det;g=(u[:,0]*(z-a[:,2])-u[:,2]*(x-a[:,0]))/det;hits=(f>=0)&(g>=0)&(f+g<=1);y=(a[:,1]+f*u[:,1]+g*v[:,1])[hits];assert len(y)==1;return float(y[0])
controls=[]
for x,z in spec['nativeControlsMC']:
 old_y=height(np.concatenate(previous_triangles),x,z);new_y=height(np.concatenate(triangles),x,z);assert new_y>old_y+.5 and 64.65<new_y<65.5
 controls.append({'x':x,'z':z,'previousMeshY':old_y,'newMeshY':new_y,'expectedProxyY':round(new_y)})
report={'status':'PASS: one bounded ground tile changed; other 98 render meshes, all textures, courtyard and unrelated guides preserved','changedTiles':changed,'changedVertexRecords':changed_vertices,'maximumHeightChangeMetres':largest,'boundedAreaIncludingBlendSquareMetres':allowed.area,'nativeControls':controls,'qualification':spec['qualification']}
(out/'galileo-grade-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

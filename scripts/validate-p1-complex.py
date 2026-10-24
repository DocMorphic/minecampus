#!/usr/bin/env python3
"""Validate P1 source provenance, roof preservation, recess depth and terrain joins."""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');folder=p.parse_args().directory
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((folder/'manifest.json').read_text());record=manifest['architecture']['p1Complex'];source=root/'minecraft/exterior'/record['sourceFile'];spec=json.loads(source.read_text());assert sha(source)==record['sourceSha256'];assert sha(root/record['generatorFile'])==record['generatorSha256'];assert sha(root/'minecraft/exterior'/spec['reference'])==spec['referenceSha256']
plans=json.loads((folder/'photo-facades.json').read_text())['plans']
evidence=json.loads((root/'minecraft/exterior'/spec['reference']).read_text())['fixtureEvidence']
for key in ['surfaceModel','orthophoto']:
 item=evidence[key];assert sha(root/'.cache'/item['cachePath'])==item['sha256']
with rasterio.open(root/'.cache'/evidence['surfaceModel']['cachePath'])as dem:
 window=from_bounds(698663,5349472,698671,5349478,dem.transform).round_offsets().round_lengths();height=dem.read(1,window=window);rows,cols=np.where(height>478.65);east,north=rasterio.transform.xy(dem.window_transform(window),rows,cols);cap_points=np.column_stack([east,north]);cap_heights=height[rows,cols]
def decode(path):
 data=path.read_bytes();count,*anchor=struct.unpack_from('<i3d',data,4);offset=32;parts=[]
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',data,offset);offset+=16;v=np.frombuffer(data,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);v[:,:3]+=anchor;offset+=n*20;texture=data[offset:offset+w*h*4];offset+=w*h*4;assert np.isfinite(v).all();parts.append((v,texture))
 assert offset==len(data);return parts

def intersections(tri,origin,direction):
 a,b,c=tri[:,0],tri[:,1],tri[:,2];e1=b-a;e2=c-a;h=np.cross(np.broadcast_to(direction,e2.shape),e2);det=np.einsum('ij,ij->i',e1,h);valid=np.abs(det)>1e-8;inv=np.divide(1,det,out=np.zeros_like(det),where=valid);s=origin-a;u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=inv*(q@direction);d=inv*np.einsum('ij,ij->i',e2,q);mask=valid&(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&(d>=0);return d[mask],np.cross(e1,e2)[mask]@(-direction)
results=[];hashes={};ground_shapes=[]
for entry in record['buildings']:
 plan=next(p for p in plans if p['id']==entry['building']);parts=decode(folder/entry['meshFile']);roof=decode(folder/plan['roofFile']);assert len(parts)==(6 if entry.get('fixtures')else 5) and len(roof)==1
 assert np.array_equal(parts[4][0],roof[0][0]) and parts[4][1]==roof[0][1]
 error=float(np.max(np.abs(parts[4][0][:,:3]-np.array(plan['roofTriangles']).reshape(-1,3))));assert error<.0001
 assert len(parts[4][0])==entry['roofTriangles']*3
 assert all(w['reconstructed']for w in plan['walls'])
 keys=[(c['face'],*map(lambda v:round(v,4),c['position']))for c in entry['openingControls']];assert len(keys)==len(set(keys)), 'Duplicate clipped openings'
 for control in entry['openingControls']:
  target=np.array(control['position']);normal=np.array(control['normal']);part=control['part'];assert abs(np.linalg.norm(normal)-1)<1e-7
  distances,winding=intersections(parts[part][0][:,:3].reshape(-1,3,3),target+normal*.6,-normal)
  assert np.any((np.abs(distances-.6)<.0001)&(winding>0)),control
  # Concrete must actually be cut away in front of the recess.
  distances,_=intersections(parts[0][0][:,:3].reshape(-1,3,3),target+normal*1.6,-normal)
  assert not np.any(distances<1.5999),control
 ground=decode(folder/entry['groundFile']);shape=unary_union([Polygon(t[:,[0,2]])for v,_ in ground for t in v[:,:3].reshape(-1,3,3)]);ground_shapes.append(shape)
 for wall in entry['surveyWalls']:
  if wall['bounds'][0][1]>entry['surveyBaseMC']+.1:continue
  midpoint=np.array(wall['anchor'])+np.array(wall['direction'])*(wall['bounds'][1][0]/2)+np.array(wall['normal'])*.25
  assert shape.buffer(.0001).covers(Point(midpoint[0],midpoint[2])),wall
 cleanup=unary_union([Polygon(p['ring'],p['holes'])for p in entry['retirement']])
 for index,fixture in enumerate(entry.get('fixtures',[])):
  selected=cap_points[:,0]<698667 if index==0 else cap_points[:,0]>=698667
  assert sum(selected)==(108 if index==0 else 102)
  assert np.max(np.abs(np.mean(cap_points[selected],axis=0)-fixture['centreUTM']))<.00001
  assert abs(float(np.median(cap_heights[selected]))-fixture['capHeightUTM'])<.00001
  assert fixture['capHeightUTM']-fixture['baseHeightUTM']>6
  centre=np.array(fixture['capCentreMC']);tri=parts[fixture['part']][0][:,:3].reshape(-1,3,3)
  distances,winding=intersections(tri,centre+[0,1,0],np.array([0,-1,0]));assert np.any((np.abs(distances-1)<.0001)&(winding>0))
  assert cleanup.covers(Polygon(fixture['ring']).buffer(.6))
  assert plan['bounds'][1][1]>=centre[1]
  # All four cardinal sides need outward-facing walls, not floating caps.
  for normal in [np.array([1.,0,0]),np.array([-1.,0,0]),np.array([0.,0,1]),np.array([0.,0,-1])]:
   target=(centre+np.array(fixture['baseCentreMC']))/2;distances,winding=intersections(tri,target+normal*2,-normal)
   assert np.any((distances>.8)&(distances<1)&(winding>0)),fixture
 for other in plans:
  if other['id']==entry['building']:continue
  polys=[Polygon(np.array(t)[:,[0,2]])for t in other.get('roofTriangles',[])]
  if polys:assert cleanup.intersection(unary_union(polys)).area<.001,other['id']
 for name in [entry['meshFile'],entry['groundFile']]:hashes[name]=sha(folder/name)
 results.append({'building':entry['building'],'roofTriangles':entry['roofTriangles'],'roofMaximumCoordinateErrorMetres':error,'recessControls':len(entry['openingControls']),'sourceHeightVerifiedCylinders':len(entry.get('fixtures',[]))})
overlap=ground_shapes[0].intersection(ground_shapes[1]).area;assert overlap<.005
result={'status':'PASS: source provenance, both original roofs/pixels, concrete cutouts, outward recessed surfaces and joined ground','manifestSha256':sha(folder/'manifest.json'),'sourceSha256':sha(source),'validatorSha256':sha(Path(__file__)),'buildings':results,'newGroundOverlapSquareMetres':overlap,'tileSha256':hashes,'qualification':'Representation checks. Facade and apron materials, levels and rail dimensions are estimates. Native visual/collision acceptance remains separate.'};(folder/'p1-complex-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

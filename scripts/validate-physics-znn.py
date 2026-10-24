#!/usr/bin/env python3
"""Verify ZNN against raw public roof, wall, window and shading-rail geometry."""
from pathlib import Path
import argparse,hashlib,json,math,struct,xml.etree.ElementTree as ET
import numpy as np
import rasterio
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon,Point,box,shape,LineString
from shapely.ops import unary_union
from shapely import polygons,union_all
r=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,default=r/'dist-minecraft/exterior');out=parser.parse_args().directory;read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');rec=m['architecture']['physicsZNN'];spec=read(r/'minecraft/exterior'/rec['sourceFile']);plans=read(out/'photo-facades.json')['plans'];sources=read(r/'minecraft/exterior/sources.json')
assert sha(r/'minecraft/exterior'/rec['sourceFile'])==rec['sourceSha256'];assert sha(r/rec['generatorFile'])==rec['generatorSha256'];assert sha(r/'minecraft/exterior'/spec['reference'])==spec['referenceSha256']
lat,lon=map(math.radians,m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-math.sin(lon),math.cos(lon),0],[math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)],[math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]]);inverse=Transformer.from_crs(4978,25832,always_xy=True);geographic=Transformer.from_crs(25832,4258,always_xy=True);ecef=Transformer.from_crs(25832,4978,always_xy=True)
def sample(d,a,e,n):
 x,y=(~d.transform)*(e,n);return map_coordinates(a,[y-.5,x-.5],order=1,prefilter=False)
def world(xy,h):
 with rasterio.open(r/'.cache/de_bkg_gcg2016.tif')as geoid:
  lon,lat=geographic.transform(*xy.T);height=h+sample(geoid,geoid.read(1).astype(float),lon,lat)
 xyz=np.column_stack(ecef.transform(xy[:,0],xy[:,1],height));return (xyz-origin)@basis.T+[0,64,0]
ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'};surveys={};inputs={}
for item,file in zip(sources['lod2'],['campus-east.gml','campus-west.gml']):
 assert sha(r/'.cache'/file)==item['sha256'];inputs[file]=item['sha256']
 for b in ET.parse(r/'.cache'/file).findall('.//b:Building',ns):
  bid=b.get('{'+ns['g']+'}id');items=[]
  for kind in ['GroundSurface','RoofSurface','WallSurface']:
   for p in b.findall('.//b:'+kind+'//g:Polygon',ns):
    rings=[np.array(list(map(float,v.text.split()))).reshape(-1,3)for v in p.findall('.//g:LinearRing/g:posList',ns)]
    if rings:items.append((kind,rings))
  surveys[bid]=items
for key,file in [('dgm1','campus-dgm-east.tif'),('dop20','campus-dop-east.tif')]:
 item=sorted(sources[key],key=lambda v:v['name'])[1];assert sha(r/'.cache'/file)==item['sha256'];inputs[file]=item['sha256']
assert sha(r/'.cache/de_bkg_gcg2016.tif')==sources['geoid']['sha256']
for item in read(r/'minecraft/exterior/vegetation-sources.json')['inputs']:
 assert sha(r/'.cache'/item['cachePath'])==item['sha256'];inputs[item['cachePath']]=item['sha256']
def decode(path):
    data = path.read_bytes()
    count, *anchor = struct.unpack_from('<i3d', data, 4)
    offset, parts = 32, []
    for _ in range(count):
        n, w, h = struct.unpack_from('<3i', data, offset)
        offset += 16
        v = np.frombuffer(data, dtype='<f4', count=n*5, offset=offset).reshape(-1,5).astype(float)
        v[:, :3] += anchor
        offset += n*20
        texture = data[offset:offset+w*h*4]
        offset += w*h*4
        assert np.isfinite(v).all()
        parts.append((v, texture))
    assert offset == len(data)
    return parts


def ray_hits(triangles, origin, direction):
    a, b, c = triangles[:,0], triangles[:,1], triangles[:,2]
    e1, e2 = b-a, c-a
    h = np.cross(np.broadcast_to(direction,e2.shape),e2)
    det = np.einsum('ij,ij->i',e1,h)
    valid = np.abs(det)>1e-8
    inv = np.divide(1,det,out=np.zeros_like(det),where=valid)
    s = origin-a
    u = inv*np.einsum('ij,ij->i',s,h)
    q = np.cross(s,e1)
    v = inv*(q@direction)
    distance = inv*np.einsum('ij,ij->i',e2,q)
    mask = valid & (u>=-1e-7) & (v>=-1e-7) & (u+v<=1+1e-7) & (distance>=0)
    return distance[mask], (np.cross(e1,e2)@(-direction))[mask]


plan=next(p for p in plans if p['id']==spec['building']);parts=decode(out/rec['meshFile']);roof=decode(out/rec['roofFile']);assert len(parts)==6 and len(roof)==1
assert np.array_equal(parts[5][0],roof[0][0])and parts[5][1]==roof[0][1]
for part,colour in zip(parts[:5],spec['materialColours']):assert part[1]==bytes(colour)
raw=surveys[spec['building']];source_roof=[rings for kind,rings in raw if kind=='RoofSurface'];rawmc=[world(p[:,:2],p[:,2])for rings in source_roof for p in rings];rv=parts[5][0]
roof_vertex_error=float(cKDTree(np.concatenate(rawmc)).query(rv[:,:3])[0].max());assert roof_vertex_error<.0001
sourcepolys=[Polygon(q[0][:,[0,2]],[h[:,[0,2]]for h in q[1:]]).buffer(0)for q in [[world(p[:,:2],p[:,2])for p in rings]for rings in source_roof]]
roof_shape_error=union_all(polygons(rv[:,:3].reshape(-1,3,3)[:,:,[0,2]])).symmetric_difference(unary_union(sourcepolys)).area;assert roof_shape_error<.01
assert len(rv)==69 and rec['roofTriangles']==23
allraw=np.concatenate([p for rings in source_roof for p in rings])
with rasterio.open(r/'.cache/campus-dop-east.tif')as dop:
 c,y=(~dop.transform)*(allraw[:,0],allraw[:,1]);left,top=math.floor(c.min())-2,math.floor(y.min())-2;right,bottom=math.ceil(c.max())+2,math.ceil(y.max())+2;rgb=dop.read([1,2,3],window=rasterio.windows.Window(left,top,right-left,bottom-top)).transpose(1,2,0)
 assert np.array_equal(np.frombuffer(parts[5][1],dtype='uint8').reshape(bottom-top,right-left,4)[:,:,:3],rgb)
 e,n,_=inverse.transform(*((rv[:,:3]-[0,64,0])@basis+origin).T);c,y=(~dop.transform)*(e,n);assert np.max(np.abs(rv[:,3:]-np.column_stack([(c-left)/(right-left),(y-top)/(bottom-top)])))<.0001
assert len(plan['walls'])==len([1 for k,p in raw if k=='WallSurface'])==13 and all(w['reconstructed']for w in plan['walls'])
raw_wall_points=np.concatenate([world(p[:,:2],p[:,2])for k,rings in raw if k=='WallSurface'for p in rings])
wall_points=np.concatenate([np.asarray(w['vertices'])for w in plan['walls']])
assert cKDTree(raw_wall_points).query(wall_points)[0].max()<.0001
assert cKDTree(wall_points).query(raw_wall_points)[0].max()<.0001
arrays=[v[:,:3].reshape(-1,3,3)for v,_ in parts]
for control in rec['openingControls']:
 target,n=np.array(control['position']),np.array(control['normal']);hits=[]
 for i,tri in enumerate(arrays):
  ds,wind=ray_hits(tri,target+n*.8,-n)
  if len(ds):
   j=np.argmin(ds);hits.append((float(ds[j]),i,float(wind[j])))
 nearest=min(hits);assert nearest[1]==1 and abs(nearest[0]-.8)<.0001 and nearest[2]>0,(control,nearest)
assert len(rec['openingControls'])==sum(len(v)for v in spec['openings'].values())==17
assert all(len(spec['openings'][str(face)])==3 for face in [0,3,4,5,9])
assert len(spec['openings']['10'])==2
for control in rec['railControls']:
 q,n=np.array(control['position']),np.array(control['normal']);ds,wind=ray_hits(arrays[2],q+n*.6,-n);assert len(ds)and abs(min(ds)-.6)<.0001
# Check every elevated wall in local coordinates: no new opaque skirt below it.
wall_vertex_controls=0
for wall in plan['walls']:
 anchor,u,n=(np.asarray(wall[k])for k in ['anchor','direction','normal']);region=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0)
 for tri in np.concatenate([arrays[0],arrays[3]]):
  if np.max(np.abs((tri-anchor)@n))>.0001:continue
  xy=np.column_stack([(tri-anchor)@u,tri[:,1]])
  if not Polygon(xy).intersects(region):continue
  if region.bounds[1]>rec['baseMC']+.05:assert xy[:,1].min()>=region.bounds[1]-.0001
  wall_vertex_controls+=1
assert wall_vertex_controls>0
retirement=unary_union([Polygon(p['ring'],p['holes'])for p in rec['retirement']])
for other in plans:
 if other['id']==spec['building']:continue
 other_roofs=[Polygon(np.asarray(t)[:,[0,2]])for t in other.get('roofTriangles',[])]
 if other_roofs:assert retirement.intersection(unary_union(other_roofs)).area<.001,other['id']

for control in rec['opaqueControls']:
 target,n=np.array(control['position']),np.array(control['normal']);hits=[]
 for i,tri in enumerate(arrays):
  ds,wind=ray_hits(tri,target+n*.8,-n)
  if len(ds):hits.append((float(ds.min()),i))
 assert min(hits)[1]==4 and abs(min(hits)[0]-.8)<.0001,(control,hits)
assert len(rec['railControls'])==51 and len(rec['opaqueControls'])==1
result={'status':'PASS: surveyed ZNN shell/roof and source-informed facade geometry; native verification pending','manifestSha256':sha(out/'manifest.json'),'sourceSha256':sha(r/'minecraft/exterior'/rec['sourceFile']),'validatorSha256':sha(Path(__file__)),'generatorSha256':rec['generatorSha256'],'roofVertexErrorMetres':roof_vertex_error,'roofFootprintErrorSquareMetres':roof_shape_error,'roofTriangles':23,'surveyWallFaces':13,'windowBandControls':len(rec['openingControls']),'shadingRailControls':len(rec['railControls']),'opaquePanelControls':len(rec['opaqueControls']),'tileSha256':{name:sha(out/name)for name in [rec['meshFile'],rec['roofFile']]},'qualification':'Independent raw survey/roof pixel and mesh-ray checks. Does not verify surrounding terrain, gameplay, lighting or visual acceptance.'}
(out/'physics-znn-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

#!/usr/bin/env python3
"""Verify WSI against raw public roof, terrain, window and frame geometry."""
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
r=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,default=r/'dist-minecraft/exterior');out=parser.parse_args().directory;read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');rec=m['architecture']['physicsWSI'];spec=read(r/'minecraft/exterior'/rec['sourceFile']);plans=read(out/'photo-facades.json')['plans'];sources=read(r/'minecraft/exterior/sources.json')
assert sha(r/'minecraft/exterior'/rec['sourceFile'])==rec['sourceSha256'];assert sha(r/rec['generatorFile'])==rec['generatorSha256'];assert sha(r/'scripts/exterior_vegetation.py')==rec['vegetationGeneratorSha256'];assert sha(r/'minecraft/exterior'/spec['reference'])==spec['referenceSha256'];assert sha(out/rec['coverageFile'])==rec['coverageSha256']
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


assert sha(r/'scripts/exterior_physics_ii.py')==rec['transitionGeneratorSha256']
assert sha(r/'scripts/exterior_physics_ii_landscape.py')==rec['canopyGeneratorSha256']
plan=next(p for p in plans if p['id']==spec['building']);parts=decode(out/rec['meshFile']);roof=decode(out/rec['roofFile']);assert len(parts)==5 and len(roof)==1
assert np.array_equal(parts[4][0],roof[0][0])and parts[4][1]==roof[0][1]
for part,colour in zip(parts[:4],spec['materialColours']):assert part[1]==bytes(colour)
raw=surveys[spec['building']];source_roof=[rings for kind,rings in raw if kind=='RoofSurface'];rawmc=[world(p[:,:2],p[:,2])for rings in source_roof for p in rings];rv=parts[4][0]
roof_vertex_error=float(cKDTree(np.concatenate(rawmc)).query(rv[:,:3])[0].max());assert roof_vertex_error<.0001
sourcepolys=[Polygon(q[0][:,[0,2]],[h[:,[0,2]]for h in q[1:]]).buffer(0)for q in [[world(p[:,:2],p[:,2])for p in rings]for rings in source_roof]]
roof_shape_error=union_all(polygons(rv[:,:3].reshape(-1,3,3)[:,:,[0,2]])).symmetric_difference(unary_union(sourcepolys)).area;assert roof_shape_error<.01
assert len(rv)==99 and rec['roofTriangles']==33
allraw=np.concatenate([p for rings in source_roof for p in rings])
with rasterio.open(r/'.cache/campus-dop-east.tif')as dop:
 c,y=(~dop.transform)*(allraw[:,0],allraw[:,1]);left,top=math.floor(c.min())-2,math.floor(y.min())-2;right,bottom=math.ceil(c.max())+2,math.ceil(y.max())+2;rgb=dop.read([1,2,3],window=rasterio.windows.Window(left,top,right-left,bottom-top)).transpose(1,2,0)
 assert np.array_equal(np.frombuffer(parts[4][1],dtype='uint8').reshape(bottom-top,right-left,4)[:,:,:3],rgb)
 e,n,_=inverse.transform(*((rv[:,:3]-[0,64,0])@basis+origin).T);c,y=(~dop.transform)*(e,n);assert np.max(np.abs(rv[:,3:]-np.column_stack([(c-left)/(right-left),(y-top)/(bottom-top)])))<.0001
assert len(plan['walls'])==len([1 for k,p in raw if k=='WallSurface'])==26 and all(w['reconstructed']for w in plan['walls'])
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
assert len(rec['openingControls'])==sum(len(v)for v in spec['openings'].values())==11
assert all(len(spec['openings'][str(face)])==3 for face in [1,22])
for control in rec['frameControls']:
 q,n=np.array(control['position']),np.array(control['normal']);ds,wind=ray_hits(arrays[2],q+n*.6,-n);assert len(ds)and abs(min(ds)-.6)<.0001
# Check every elevated wall in local coordinates: no new opaque skirt below it.
wall_vertex_controls=0
for wall in plan['walls']:
 anchor,u,n=(np.asarray(wall[k])for k in ['anchor','direction','normal']);region=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0)
 for tri in arrays[0]:
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
def utm_ring(ring):
 q=np.asarray(ring);points=origin+q[:,0,None]*basis[0]+q[:,1,None]*basis[2]+basis[1];e,n,_=inverse.transform(*points.T);return np.column_stack([e,n])
def surface_area(items):
 return unary_union([box(*m['boundsUtm']),*[Polygon(utm_ring(p['ring']),[utm_ring(h)for h in p.get('holes',[])])for s in items for p in s['rings']]])
idx=next(i for i,s in enumerate(m['supplementalSurfaces'])if s['name']=='physics-wsi-site');prior=surface_area(m['supplementalSurfaces'][:idx]);oldidx=next(i for i,s in enumerate(m['supplementalSurfaces'])if s['name']=='physics-ii-site');prior_ground=surface_area(m['supplementalSurfaces'][:oldidx])
transition=read(r/'minecraft/exterior/physics-ii-ground-transition.json')
def independent_correction(record, earlier):
 valid_edges=[];missing_edges=[]
 for line in record['lines']:
  values=line.get('joinDelta',line['delta'])
  for i in range(len(values)-1):
   edge=LineString(line['utm'][i:i+2]);ds=values[i:i+2]
   if None in ds:missing_edges.append(edge)
   else:valid_edges.append((edge,ds))
 missing_geometry=unary_union(missing_edges)
 def calculate(xy):
  from shapely import points,distance,line_locate_point
  pts=points(xy);best=np.full(len(xy),np.inf);residual=np.zeros(len(xy))
  for edge,ds in valid_edges:
   d=distance(pts,edge);replace=d<best;along=line_locate_point(edge,pts,normalized=True);residual[replace]=(ds[0]*(1-along)+ds[1]*along)[replace];best[replace]=d[replace]
  def smooth(v):
   v=np.clip(v,0,1);return v*v*(3-2*v)
  missing_fade=smooth(distance(pts,missing_geometry)/record['priorFadeMetres'])if not missing_geometry.is_empty else np.ones(len(xy))
  return residual*smooth(1-best/record['widthMetres'])*smooth(distance(pts,earlier)/record['priorFadeMetres'])*missing_fade
 return calculate
inherited_correction=independent_correction(transition,prior_ground)
transition_path=r/'minecraft/exterior'/spec['groundTransition']['sourceFile'];assert sha(transition_path)==spec['groundTransition']['sha256'];assert sha(out/transition_path.name)==sha(transition_path);inputs[transition_path.name]=sha(transition_path)
outer_transition=read(transition_path);assert rec['groundTransition']==spec['groundTransition'];assert outer_transition['inheritedTransitionSha256']==sha(r/'minecraft/exterior/physics-ii-ground-transition.json')
outer_correction=independent_correction(outer_transition,prior)
accepted=missing=0
for line in outer_transition['lines']:
 xy=np.asarray(line['utm']);old=inherited_correction(xy);assert np.max(np.abs(old-line['inheritedCorrectionMetres']))<1e-7
 for i,(source,survey,delta,join)in enumerate(zip(line['sourceHeightMC'],line['surveyHeightMC'],line['delta'],line['joinDelta'])):
  if source is None:
   assert delta is None and join is None;assert abs(outer_correction(xy[i:i+1])[0])<1e-8;missing+=1
  else:
   assert abs(delta-(source-survey))<1e-8 and abs(join-(delta-old[i]))<1e-7 and abs(delta)<=outer_transition['maximumResidualMetres'];accepted+=1
assert accepted==outer_transition['acceptedSamples']==616 and missing==outer_transition['missingSamples']==662
def correction(xy):
 return inherited_correction(xy)+outer_correction(xy)
areas=[];mcareas=[];ground_error=0;hashes={name:sha(out/name)for name in [rec['meshFile'],rec['roofFile'],*rec['treeTiles']]}
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/campus-dop-east.tif')as dop:
 data=dem.read(1).astype(float)
 for name in rec['groundTiles']:
  v,texture=decode(out/name)[0];e,n=map(int,Path(name).stem.split('-')[-2:]);step=spec['groundTileMetres'];xy=np.column_stack([e+v[:,3]*step,n+step-v[:,4]*step]);expected=world(xy,sample(dem,data,xy[:,0],xy[:,1])+correction(xy));error=float(np.max(np.abs(expected-v[:,:3])));assert error<.001;ground_error=max(ground_error,error)
  areas.append(union_all(polygons(xy.reshape(-1,3,2))));mcareas.append(union_all(polygons(v[:,:3].reshape(-1,3,3)[:,:,[0,2]])));c,row=(~dop.transform)*(e,n+step);rgb=dop.read([1,2,3],window=rasterio.windows.Window(round(c),round(row),step*5,step*5)).transpose(1,2,0);assert np.array_equal(np.frombuffer(texture,dtype='uint8').reshape(step*5,step*5,4)[:,:,:3],rgb);hashes[name]=sha(out/name)
area=unary_union(areas);mcarea=unary_union(mcareas);coverage=read(out/rec['coverageFile']);assert area.symmetric_difference(shape(coverage['ground'])).area<.01
others=unary_union([Polygon(p[0][:,:2],[h[:,:2]for h in p[1:]]).buffer(0)for bid,items in surveys.items()if bid!=spec['building']for k,p in items if k=='GroundSurface'])
assert area.intersection(others.buffer(.4999)).area<.01
assert area.intersection(prior).area<.005
explicit_extent=unary_union([Polygon(rings[0][:,:2],[h[:,:2]for h in rings[1:]])for kind,rings in raw if kind=='GroundSurface']).buffer(spec['apronMetres']).union(shape(coverage['canopy']).buffer(spec['canopyExtent']['groundMarginMetres'])).union(box(*spec['northLandscapeBoundsUtm']))
assert shape(coverage['extent']).symmetric_difference(explicit_extent).area<.001
expected=shape(coverage['extent']).difference(others.buffer(.5)).difference(prior.buffer(.002));assert area.symmetric_difference(expected).area<.02
# Existing ground geometry remains disjoint, including at close footprint guards.
overlap=0
for tile in m['tiles']:
 if tile['kind']!='ground'or tile['file']in rec['groundTiles']:continue
 lo,hi=tile['bounds']
 if not mcarea.intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
 for v,_ in decode(out/tile['file']):overlap+=mcarea.intersection(union_all(polygons(v[:,:3].reshape(-1,3,3)[:,:,[0,2]]))).area
assert overlap<.005,overlap
surface=m['supplementalSurfaces'][idx];trees=surface['vegetation']['trees'];assert len(trees)==rec['treeCount']
oldtrees=[*m['vegetation']['trees'],*[t for s in m['supplementalSurfaces'][:idx]for t in s.get('vegetation',{}).get('trees',[])]]
with rasterio.open(r/'.cache/campus-dop-east.tif')as dop,rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/32698_5349_20_DOM.tif')as dom:
 for t in trees:
  q=np.asarray([t['utm']]);rgb=next(dop.sample(q));height=float(next(dom.sample(q))[0]-next(dem.sample(q))[0]);assert rgb[1]>rgb[0]*1.025 and rgb[1]>rgb[2]+2 and height>3
  assert area.buffer(.001).covers(Point(q[0]));assert not others.buffer(1.19).covers(Point(q[0]));assert all(np.linalg.norm(q[0]-np.array(old['utm']))>2 for old in oldtrees)
assert len({t['runtimeId']for t in m['tiles']if 'runtimeId'in t})==sum('runtimeId'in t for t in m['tiles'])
result={'status':'PASS: raw surveyed roof/pixels, recessed windows, projecting frames, source terrain and preserved neighboring ground','manifestSha256':sha(out/'manifest.json'),'sourceSha256':sha(r/'minecraft/exterior'/rec['sourceFile']),'validatorSha256':sha(Path(__file__)),'inputSha256':inputs,'roofVertexErrorMetres':roof_vertex_error,'roofFootprintErrorSquareMetres':roof_shape_error,'roofTriangles':33,'windowBandControls':len(rec['openingControls']),'frameControls':len(rec['frameControls']),'wallTriangleControls':wall_vertex_controls,'maximumGroundCoordinateErrorMetres':ground_error,'transitionControls':accepted,'unresolvedTransitionControls':missing,'oldGroundOverlapSquareMetres':overlap,'treeCount':len(trees),'tileSha256':hashes,'qualification':'Architectural detail remains source-informed estimation; outer joins and appearance need native visual review.'};(out/'physics-wsi-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['tileSha256','inputSha256']},indent=2))

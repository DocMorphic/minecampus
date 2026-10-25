#!/usr/bin/env python3
"""Verify riverbank terrain, source canopy coverage and protected channel/bridge."""
from pathlib import Path
from validate_ground_restoration import restoration_weights
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
r=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,default=r/'dist-minecraft/exterior');out=parser.parse_args().directory;read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');rec=m['architecture']['riverbank'];spec=read(r/'minecraft/exterior'/rec['sourceFile']);plans=read(out/'photo-facades.json')['plans'];sources=read(r/'minecraft/exterior/sources.json')
assert sha(r/'minecraft/exterior'/rec['sourceFile'])==rec['sourceSha256'];assert sha(r/rec['generatorFile'])==rec['generatorSha256']
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


def utm_ring(ring):
 q=np.asarray(ring);points=origin+q[:,0,None]*basis[0]+q[:,1,None]*basis[2]+basis[1];e,n,_=inverse.transform(*points.T);return np.column_stack([e,n])
def surface_area(items):
 return unary_union([box(*m['boundsUtm']),*[Polygon(utm_ring(p['ring']),[utm_ring(h)for h in p.get('holes',[])])for s in items for p in s['rings']]])
idx=next(i for i,s in enumerate(m['supplementalSurfaces'])if s['name']=='riverbank-site');prior=surface_area(m['supplementalSurfaces'][:idx]);wsi_idx=next(i for i,s in enumerate(m['supplementalSurfaces'])if s['name']=='physics-wsi-site');wsi_prior=surface_area(m['supplementalSurfaces'][:wsi_idx]);oldidx=next(i for i,s in enumerate(m['supplementalSurfaces'])if s['name']=='physics-ii-site');prior_ground=surface_area(m['supplementalSurfaces'][:oldidx])
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
  if 'nearestEdgeBlendMetres' in record:
   assert record['nearestEdgeBlendMetres']==.25
   numerator=np.zeros(len(xy));denominator=np.zeros(len(xy))
   for edge,ds in valid_edges:
    d=distance(pts,edge);along=line_locate_point(edge,pts,normalized=True)
    weight=smooth(1-(d-best)/record['nearestEdgeBlendMetres'])
    numerator+=weight*(ds[0]*(1-along)+ds[1]*along);denominator+=weight
   residual=numerator/denominator
  missing_fade=smooth(distance(pts,missing_geometry)/record['priorFadeMetres'])if not missing_geometry.is_empty else np.ones(len(xy))
  return residual*smooth(1-best/record['widthMetres'])*smooth(distance(pts,earlier)/record['priorFadeMetres'])*missing_fade
 return calculate
inherited_correction=independent_correction(transition,prior_ground)
wsi_spec=read(r/'minecraft/exterior/physics-wsi.json')
transition_path=r/'minecraft/exterior'/wsi_spec['groundTransition']['sourceFile'];assert sha(transition_path)==wsi_spec['groundTransition']['sha256'];assert sha(out/transition_path.name)==sha(transition_path);inputs[transition_path.name]=sha(transition_path)
outer_transition=read(transition_path);assert outer_transition['inheritedTransitionSha256']==sha(r/'minecraft/exterior/physics-ii-ground-transition.json')
outer_correction=independent_correction(outer_transition,wsi_prior)
def correction(xy):
 return (inherited_correction(xy)+outer_correction(xy))*restoration_weights(r,out,m,xy)
areas=[];mcareas=[];ground_error=0;hashes={name:sha(out/name)for name in rec['treeTiles']}
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/campus-dop-east.tif')as dop:
 data=dem.read(1).astype(float)
 for name in rec['groundTiles']:
  v,texture=decode(out/name)[0];e,n=map(int,Path(name).stem.split('-')[-2:]);step=spec['groundTileMetres'];xy=np.column_stack([e+v[:,3]*step,n+step-v[:,4]*step]);expected=world(xy,sample(dem,data,xy[:,0],xy[:,1])+correction(xy));error=float(np.max(np.abs(expected-v[:,:3])));assert error<.001,(name,error,xy[np.argmax(np.max(np.abs(expected-v[:,:3]),axis=1))].tolist());ground_error=max(ground_error,error)
  areas.append(union_all(polygons(xy.reshape(-1,3,2))));mcareas.append(union_all(polygons(v[:,:3].reshape(-1,3,3)[:,:,[0,2]])));c,row=(~dop.transform)*(e,n+step);rgb=dop.read([1,2,3],window=rasterio.windows.Window(round(c),round(row),step*5,step*5)).transpose(1,2,0);assert np.array_equal(np.frombuffer(texture,dtype='uint8').reshape(step*5,step*5,4)[:,:,:3],rgb);hashes[name]=sha(out/name)
area=unary_union(areas);mcarea=unary_union(mcareas);coverage=read(out/rec['coverageFile']);assert area.symmetric_difference(shape(coverage['ground'])).area<.01

def osm_geometry(source, way_id):
 path=r/'minecraft/exterior'/source['sourceFile'];assert sha(path)==source['sha256'];xml=ET.parse(path).getroot();project=Transformer.from_crs(4326,25832,always_xy=True).transform
 nodes={n.get('id'):project(float(n.get('lon')),float(n.get('lat')))for n in xml.findall('node')};way=next(w for w in xml.findall('way')if w.get('id')==way_id)
 return [nodes[n.get('ref')]for n in way.findall('nd')],{t.get('k'):t.get('v')for t in way.findall('tag')}
river_policy=read(r/'minecraft/exterior'/spec['riverSourceFile'])['northLandscapeBoundary']
xy,tags=osm_geometry(river_policy['osm'][0],river_policy['riverWay']);assert tags.get('water')=='river';river=Polygon(xy)
xy,tags=osm_geometry(spec['osm'][0],spec['bridgeWay']);assert tags.get('bridge')=='yes'and float(tags['width'])==2
bridge=LineString(xy).buffer(float(tags['width'])/2+spec['bridgeGuardMetres'],cap_style=3)
buildings=unary_union([Polygon(p[0][:,:2],[h[:,:2]for h in p[1:]]).buffer(0)for bid,items in surveys.items()for k,p in items if k=='GroundSurface'])
others=buildings.union(bridge)
owned=river.intersection(box(*spec['riverReachBoundsUtm']))
assert shape(coverage['protectedBridge']).symmetric_difference(bridge).area<.001
assert area.intersection(others.buffer(.4999)).area<.01
assert area.intersection(prior).area<.005
assert area.intersection(river).area<.001
explicit_extent=owned.buffer(spec['bankWidthMetres']).union(shape(coverage['canopy']).buffer(spec['canopyExtent']['groundMarginMetres']))
assert shape(coverage['extent']).symmetric_difference(explicit_extent).area<.001
assert sha(out/rec['coverageFile'])==rec['coverageSha256']
for path,key in [(rec['landscapeGeneratorFile'],'landscapeGeneratorSha256'),('scripts/exterior_vegetation.py','vegetationGeneratorSha256'),('scripts/exterior_physics_ii.py','transitionGeneratorSha256'),('scripts/exterior_physics_wsi.py','wsiTransitionGeneratorSha256'),('scripts/exterior_physics_ii_landscape.py','canopyGeneratorSha256')]:assert sha(r/path)==rec[key]
# Independently recover the selected complete canopy components from source rasters.
from scipy import ndimage
from rasterio.features import rasterize,shapes
from rasterio.transform import from_origin
cp=spec['canopyExtent'];left,bottom,right,top=cp['boundsUtm'];res=cp['resolutionMetres'];width,height=int((right-left)/res),int((top-bottom)/res);transform=from_origin(left,top,res,res)
xy=np.array([(left+(i+.5)*res,top-(j+.5)*res)for j in range(height)for i in range(width)])
with rasterio.open(r/'.cache/campus-dop-east.tif')as dop,rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/32698_5349_20_DOM.tif')as dom:
 rgb=np.array(list(dop.sample(xy))).astype(float);h=np.array(list(dom.sample(xy)))[:,0]-np.array(list(dem.sample(xy)))[:,0]
 occupied=rasterize([(others.buffer(.5),1)],out_shape=(height,width),transform=transform,dtype='uint8')>0
 mask=((rgb[:,1]>rgb[:,0]*1.025)&(rgb[:,1]>rgb[:,2]+2)&(h>3)).reshape(height,width)&~occupied
 labels,_=ndimage.label(ndimage.binary_closing(mask,iterations=2)&~occupied)
 components=[];seen=set()
 for e,n in cp['componentSeedsUTM']:
  lab=int(labels[int((top-n)/res),int((e-left)/res)]);assert lab>0 and lab not in seen;seen.add(lab);pixels=labels==lab
  assert not (pixels[0].any()or pixels[-1].any()or pixels[:,0].any()or pixels[:,-1].any())
  region=unary_union([shape(g)for g,v in shapes(pixels.astype('uint8'),mask=pixels,transform=transform)if v==1]);assert region.area>=3 and region.intersects(owned.buffer(spec['bankWidthMetres']));components.append(region)
 assert unary_union(components).symmetric_difference(shape(coverage['canopy'])).area<.001
assert len(components)==len(rec['canopyComponents'])==25
expected=shape(coverage['extent']).difference(river).difference(others.buffer(.5)).difference(prior.buffer(.002));assert area.symmetric_difference(expected).area<.02
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
  q=np.asarray([t['utm']]);rgb=next(dop.sample(q));height=float(next(dom.sample(q))[0]-next(dem.sample(q))[0]);green=rgb[1]>rgb[0]*1.025 and rgb[1]>rgb[2]+2;autumn=rgb[0]>rgb[1]*1.04 and rgb[0]<rgb[1]*1.5 and rgb[1]>rgb[2]*1.08 and rgb[1]<rgb[2]*1.7 and 35<rgb[1]<175;assert (green or autumn) and height>3
  assert area.buffer(.001).covers(Point(q[0]));assert not buildings.buffer(1.19).covers(Point(q[0]));assert not bridge.buffer(spec['neighbourGuardMetres']-.001).covers(Point(q[0]));assert all(np.linalg.norm(q[0]-np.array(old['utm']))>2 for old in oldtrees)
assert len({t['runtimeId']for t in m['tiles']if 'runtimeId'in t})==sum('runtimeId'in t for t in m['tiles'])

for entry in rec['sourceRetirement']:
 assert np.isfinite([entry['y0'],entry['y1']]).all()and entry['y0']<entry['y1']
 region=unary_union([Polygon(utm_ring(p['ring']),[utm_ring(h)for h in p['holes']])for p in entry['rings']])
 assert region.intersection(bridge.buffer(-.001)).area<.001
assert rec['sourceRetirement'][-1]['rings']==rec['waterGround']['rings']
assert m['pinnedWater']['features'][0]['surveyGround']==rec['waterGround']
water=rec['waterGround'];channel=unary_union([Polygon(utm_ring(p['ring']),[utm_ring(h)for h in p['holes']])for p in water['rings']]);expected_channel=river.intersection(explicit_extent).difference(bridge)
# Compare channel rings in their actual local frame. An inverse projection at
# an arbitrary height introduces a horizontal error along this long river edge.
channel_mc=unary_union([Polygon(p['ring'],p['holes'])for p in water['rings']])
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem:
 data=dem.read(1).astype(float)
 def project_ring(coords):
  xy=np.asarray(coords);return world(xy,sample(dem,data,xy[:,0],xy[:,1]))[:,[0,2]]
 components_expected=[expected_channel]if expected_channel.geom_type=='Polygon'else list(expected_channel.geoms)
 expected_mc=unary_union([Polygon(project_ring(p.exterior.coords),[project_ring(h.coords)for h in p.interiors])for p in components_expected])
 channel_error=channel_mc.symmetric_difference(expected_mc).area;assert channel_error<.001

assert channel.intersection(bridge.buffer(-.001)).area<.001
q=np.asarray(water['terrainGuide']['points']);e,n,_=inverse.transform(*((q-[0,64,0])@basis+origin).T);xy=np.column_stack([e,n])
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem:
 expected=world(xy,sample(dem,dem.read(1).astype(float),e,n));water_error=float(np.max(np.abs(expected-q)));assert water_error<.001
result={'status':'PASS: source terrain, canopy completeness, protected river/bridge and DGM-guided water samples; native integration pending','manifestSha256':sha(out/'manifest.json'),'sourceSha256':sha(r/'minecraft/exterior'/rec['sourceFile']),'validatorSha256':sha(Path(__file__)),'generatorSha256':rec['generatorSha256'],'maximumGroundCoordinateErrorMetres':ground_error,'waterGuideCoordinateErrorMetres':water_error,'channelProjectionErrorSquareMetres':channel_error,'groundAreaSquareMetres':area.area,'oldGroundOverlapSquareMetres':overlap,'riverLandOverlapSquareMetres':area.intersection(river).area,'treeCount':len(trees),'canopyComponents':len(components),'tileSha256':hashes,'qualification':'DGM channel elevation is a water-level estimate, not measured bathymetry. Visual/collision/water behavior remains unverified.'}
(out/'riverbank-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='tileSha256'},indent=2))

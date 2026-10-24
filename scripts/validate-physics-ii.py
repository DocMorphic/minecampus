#!/usr/bin/env python3
"""Verify Physik II envelopes, open bridge, source ground and courtyard planting."""
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
r=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,default=r/'dist-minecraft/exterior');out=parser.parse_args().directory;read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');rec=m['architecture']['physicsII'];spec=read(r/'minecraft/exterior'/rec['sourceFile']);plans=read(out/'photo-facades.json')['plans'];sources=read(r/'minecraft/exterior/sources.json')
assert sha(r/'minecraft/exterior'/rec['sourceFile'])==rec['sourceSha256'];assert sha(r/rec['generatorFile'])==rec['generatorSha256'];assert sha(r/'scripts/exterior_vegetation.py')==rec['vegetationGeneratorSha256'];assert sha(r/'scripts/exterior_physics_ii_planting.py')==rec['plantingGeneratorSha256'];assert sha(r/'minecraft/exterior'/spec['reference'])==spec['referenceSha256'];assert sha(out/rec['coverageFile'])==rec['coverageSha256']
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
  for kind in ['GroundSurface','RoofSurface']:
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


hashes={};roof_errors=[];pane_count=0;joint_count=0;meshes={};owned={b['building']for b in spec['bodies']};roof_controls=[]
for record in rec['bodies']:
 b=next(v for v in spec['bodies']if v['building']==record['building']);plan=next(p for p in plans if p['id']==b['building']);parts=decode(out/record['meshFile']);roof=decode(out/record['roofFile']);assert len(parts)==5 and np.array_equal(parts[4][0],roof[0][0])and parts[4][1]==roof[0][1];meshes[b['building']]=parts
 for part,colour in zip(parts[:4],b.get('materialColours',spec['materialColours'])):assert part[1]==bytes(colour)
 expected=np.asarray(plan['roofTriangles']).reshape(-1,3);error=float(np.max(np.abs(parts[4][0][:,:3]-expected)));assert error<.0001;roof_errors.append(error)
 # Compare emitted roof area and plane heights directly with raw CityGML rings.
 raw=[rings for kind,rings in surveys[b['building']]if kind=='RoofSurface'];allraw=np.concatenate([p for rings in raw for p in rings]);rv=parts[4][0];rawmc=[world(p[:,:2],p[:,2])for rings in raw for p in rings];sourcepolys=[];sourceplanes=[]
 for rings in raw:
  q=[world(p[:,:2],p[:,2])for p in rings];sourcepolys.append(Polygon(q[0][:,[0,2]],[h[:,[0,2]]for h in q[1:]]));sourceplanes.append(np.linalg.lstsq(np.column_stack([q[0][:,[0,2]],np.ones(len(q[0]))]),q[0][:,1],rcond=None)[0])
 shape_error=union_all(polygons(rv[:,:3].reshape(-1,3,3)[:,:,[0,2]])).symmetric_difference(unary_union([p.buffer(0) for p in sourcepolys])).area;assert shape_error<.01,shape_error
 # CityGML faces can be slightly nonplanar. Require original source vertices
 # and bound plane residual by that of the actual source face, not an ideal plane.
 assert cKDTree(np.concatenate(rawmc)).query(rv[:,:3])[0].max()<.0001
 tolerances=[]
 for rings,coef in zip(raw,sourceplanes):
  q=world(rings[0][:,:2],rings[0][:,2]);tolerances.append(float(np.max(np.abs(np.column_stack([q[:,[0,2]],np.ones(len(q))])@coef-q[:,1])))+.0001)
 for t in rv[:,:3].reshape(-1,3,3):
  centre=Point(*t[:,[0,2]].mean(0));matches=[(coef,tol)for p,coef,tol in zip(sourcepolys,sourceplanes,tolerances)if p.buffer(.0001).covers(centre)]
  assert any(float(np.max(np.abs(np.column_stack([t[:,[0,2]],np.ones(3)])@coef-t[:,1])))<=tol for coef,tol in matches),(b['name'],t.tolist())
 with rasterio.open(r/'.cache/campus-dop-east.tif')as dop:
  c,y=(~dop.transform)*(allraw[:,0],allraw[:,1]);left,top=math.floor(c.min())-2,math.floor(y.min())-2;right,bottom=math.ceil(c.max())+2,math.ceil(y.max())+2;rgb=dop.read([1,2,3],window=rasterio.windows.Window(left,top,right-left,bottom-top)).transpose(1,2,0);rgba=np.frombuffer(parts[4][1],dtype='uint8').reshape(bottom-top,right-left,4);assert np.array_equal(rgb,rgba[:,:,:3]);e,n,_=inverse.transform(*((rv[:,:3]-[0,64,0])@basis+origin).T);c,y=(~dop.transform)*(e,n);assert np.max(np.abs(rv[:,3:]-np.column_stack([(c-left)/(right-left),(y-top)/(bottom-top)])))<.0001
 arrays=[v[:,:3].reshape(-1,3,3)for v,_ in parts]
 for control in record['openingControls']:
  target,normal=np.array(control['position']),np.array(control['normal']);hits=[]
  for i,tri in enumerate(arrays):
   distances,windings=ray_hits(tri,target+normal*.6,-normal)
   if len(distances):
    j=np.argmin(distances);hits.append((float(distances[j]),i,float(windings[j])))
  nearest=min(hits);assert nearest[1]==1 and abs(nearest[0]-.6)<.0001 and nearest[2]>0,(record['name'],control,nearest);pane_count+=1
 for control in record['jointControls'][::max(1,len(record['jointControls'])//16)]:
  target,normal=np.array(control['position']),np.array(control['normal']);dist,_=ray_hits(arrays[3],target+normal*.6,-normal);assert len(dist)and abs(min(dist)-.6)<.0001;joint_count+=1
 retirement=unary_union([Polygon(p['ring'],p['holes'])for p in record['retirement']])
 for other in plans:
  if other['id']in owned:continue
  roofxy=[Polygon(np.array(t)[:,[0,2]])for t in other.get('roofTriangles',[])];assert not roofxy or retirement.intersection(unary_union(roofxy)).area<.001,other['id']
 for name in [record['meshFile'],record['roofFile']]:hashes[name]=sha(out/name)
 roof_controls.append({'building':b['building'],'roofTriangles':len(rv)//3,'sourceAreaErrorSquareMetres':shape_error})
# The separate northern container has a stepped envelope, not a full-height box.
container=next(b for b in spec['bodies']if b['name']=='north-container');container_record=next(b for b in rec['bodies']if b['name']=='north-container')
assert len(container_record['surveyWalls'])==8 and container_record['roofTriangles']==6
osm_ref=container['osmReference'];osm_path=r/'minecraft/exterior'/osm_ref['sourceFile'];assert sha(osm_path)==osm_ref['sha256']
osm=ET.parse(osm_path).getroot();project=Transformer.from_crs(4326,25832,always_xy=True)
nodes={n.get('id'):project.transform(float(n.get('lon')),float(n.get('lat')))for n in osm.findall('node')}
way=next(w for w in osm.findall('way')if w.get('id')==osm_ref['way']);assert {t.get('k'):t.get('v')for t in way.findall('tag')}['building']=='container'
osm_foot=Polygon([nodes[n.get('ref')]for n in way.findall('nd')]).buffer(0)
source_foot=unary_union([Polygon(v[0][:,:2],[h[:,:2]for h in v[1:]]).buffer(0)for kind,v in surveys[container['building']]if kind=='GroundSurface'])
container_osm_iou=osm_foot.intersection(source_foot).area/osm_foot.union(source_foot).area;assert container_osm_iou>.75
assert sum(c['face']==3 for c in container_record['openingControls'])==14
container_tri=np.concatenate([v[:,:3].reshape(-1,3,3)for v,_ in meshes[container['building']][:4]])
centres=container_tri.mean(axis=1);cross=np.cross(container_tri[:,1]-container_tri[:,0],container_tri[:,2]-container_tri[:,0]);areas=np.linalg.norm(cross,axis=1)/2;normals=cross/np.maximum(2*areas[:,None],1e-12)
upper_wall_spurious_area=0
for wall in container_record['surveyWalls']:
 (lo,bottom),(hi,top)=wall['bounds']
 if bottom<=container_record['baseMC']+.05:continue
 anchor,direction,normal=[np.asarray(wall[k])for k in ['anchor','direction','normal']]
 offset=centres-anchor;x=offset@direction;depth=offset@normal
 bad=(np.abs(depth)<.2)&(x>lo+.001)&(x<hi-.001)&(centres[:,1]<bottom-.01)&(np.abs(normals@normal)>.999)
 upper_wall_spurious_area+=float(areas[bad].sum())
assert upper_wall_spurious_area<.001,upper_wall_spurious_area

# The northern infill is enclosed by the main body on three sides. Its
# reconstructed facade must remain on the single exposed northern survey edge.
north=next(b for b in rec['bodies']if b['name']=='north-infill')
assert {c['face']for c in north['openingControls']} == {3}
assert {c['face']for c in north['sharedWallCuts']} == {0,1,2}
north_ground=next(rings for kind,rings in surveys[north['building']]if kind=='GroundSurface')
main_id=next(b['building']for b in rec['bodies']if b['name']=='main')
main_ground=next(rings for kind,rings in surveys[main_id]if kind=='GroundSurface')
q=world(north_ground[0][:,:2],north_ground[0][:,2]);north_foot=Polygon(q[:,[0,2]])
main_q=[world(p[:,:2],p[:,2])for p in main_ground];main_foot=Polygon(main_q[0][:,[0,2]],[h[:,[0,2]]for h in main_q[1:]])
assert north_foot.intersection(main_foot).area < .001
edges=[]
for a,b in zip(q[:-1],q[1:]):
 midpoint=(a+b)/2;direction=b-a;normal=np.array([direction[2],0,-direction[0]]);normal/=np.linalg.norm(normal)
 if north_foot.contains(Point(*(midpoint+normal*.02)[[0,2]])):normal=-normal
 if not main_foot.contains(Point(*(midpoint+normal*.02)[[0,2]])):edges.append((a,normal))
assert len(edges)==1
anchor,normal=edges[0];hidden_area=0
for vertices,_ in meshes[north['building']][:4]:
 tri=vertices[:,:3].reshape(-1,3,3);centre=tri.mean(axis=1);hidden=np.abs((centre-anchor)@normal)>.21
 hidden_area+=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)[hidden].sum()/2
assert hidden_area < .02,hidden_area

# Independently interpolate source residuals along Shapely line segments.
transition_file = r/'minecraft/exterior'/spec['groundTransition']['sourceFile']
assert sha(transition_file) == spec['groundTransition']['sha256']
assert sha(out/transition_file.name) == spec['groundTransition']['sha256']
transition = read(transition_file)
coverage = read(out/rec['coverageFile'])
prior_ground = shape(coverage['priorGround'])
# Reconstruct canopy cells independently from source samples and seed labels.
from scipy import ndimage
from shapely import contains_xy,prepare
canopy_spec=spec['landscape']['canopyExtent'];left,bottom,right,top=canopy_spec['boundsUtm'];resolution=canopy_spec['resolutionMetres']
cols,rows=int((right-left)/resolution),int((top-bottom)/resolution)
xx,yy=np.meshgrid(left+(np.arange(cols)+.5)*resolution,top-(np.arange(rows)+.5)*resolution)
source_xy=np.column_stack([xx.ravel(),yy.ravel()])
with rasterio.open(r/'.cache/campus-dop-east.tif')as dop,rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/32698_5349_20_DOM.tif')as dom:
 colors=np.array(list(dop.sample(source_xy))).astype(float);H=np.array(list(dom.sample(source_xy)))[:,0]-np.array(list(dem.sample(source_xy)))[:,0]
all_buildings=unary_union([Polygon(v[0][:,:2],[hole[:,:2]for hole in v[1:]]).buffer(0)for items in surveys.values()for kind,v in items if kind=='GroundSurface'])
# Prepare once: older GEOS bindings otherwise rebuild the building index
# for every raster cell. This leaves the exact containment predicate unchanged.
occupied_geometry=all_buildings.buffer(.5);prepare(occupied_geometry)
occupied=contains_xy(occupied_geometry,xx,yy)
source_mask=((colors[:,1]>colors[:,0]*1.025)&(colors[:,1]>colors[:,2]+2)&(H>3)).reshape(rows,cols)&~occupied
source_labels,_=ndimage.label(ndimage.binary_closing(source_mask,iterations=2)&~occupied)
canopy_parts=[];canopy_counts=[]
for e,n in canopy_spec['componentSeedsUTM']:
 label=source_labels[int((top-n)/resolution),int((e-left)/resolution)];assert label>0
 pixels=source_labels==label;assert not(pixels[0].any()or pixels[-1].any()or pixels[:,0].any()or pixels[:,-1].any())
 indices=np.argwhere(pixels);canopy_counts.append(len(indices)*resolution**2)
 canopy_parts.append(unary_union([box(left+i*resolution,top-(j+1)*resolution,left+(i+1)*resolution,top-j*resolution)for j,i in indices]))
expected_canopy=unary_union(canopy_parts)
assert expected_canopy.symmetric_difference(shape(coverage['canopySourceArea'])).area<.001
assert canopy_counts==[c['sourceAreaSquareMetres']for c in rec['canopyComponents']]
grid=Transformer.from_crs(4326,25832,always_xy=True);nodes={};ways={}
for source in spec['landscape']['osm']:
 path=r/'minecraft/exterior'/source['sourceFile'];assert sha(path)==source['sha256'];osm=ET.parse(path).getroot()
 nodes.update({n.get('id'):grid.transform(float(n.get('lon')),float(n.get('lat')))for n in osm.findall('node')})
 for w in osm.findall('way'):ways[w.get('id')]=([nodes[n.get('ref')]for n in w.findall('nd')],{t.get('k'):t.get('v')for t in w.findall('tag')})
base_regions=[];primary_regions=[]
for body in spec['bodies']:
 regions=[Polygon(v[0][:,:2]).buffer(0)for kind,v in surveys[body['building']]if kind=='GroundSurface']
 footprint=unary_union(regions)
 if 'landscapeApronMetres'in body:base_regions.append(footprint.buffer(body['landscapeApronMetres']))
 else:primary_regions.append(footprint)
base_regions.append(unary_union(primary_regions).buffer(spec['apronMetres']))
coverage_policy=spec['landscape']['coverage']
for wid in coverage_policy['osmWays']:
 xy,tags=ways[wid]
 if xy[0]==xy[-1]:base_regions.append(Polygon(xy).buffer(0))
 else:
  assert tags.get('highway')=='footway'
  width=float(tags.get('width',spec['landscape']['defaultPathWidthMetres']))
  base_regions.append(LineString(xy).buffer(width/2+coverage_policy['pathVergeMetres'],cap_style=2,join_style=2))
expected_extent=unary_union(base_regions).union(expected_canopy.buffer(canopy_spec['groundMarginMetres']))
parts=[expected_extent]if expected_extent.geom_type=='Polygon'else list(expected_extent.geoms)
patches=coverage_policy.get('continuityPatches',[]);patch_counts=[0]*len(patches);filled_regions=[];continuity_areas=[]
for polygon in parts:
 holes=[]
 for ring in polygon.interiors:
  hole=Polygon(ring);selected=False
  for i,patch in enumerate(patches):
   if hole.contains(Point(patch['seedUTM'])):
    assert hole.area<=patch['maximumEnclosedAreaSquareMetres'];patch_counts[i]+=1;selected=True;continuity_areas.append(hole.area)
  if not selected and hole.area>coverage_policy['maximumEnclosedVoidSquareMetres']:holes.append(ring)
 filled_regions.append(Polygon(polygon.exterior,holes))
assert all(count==1 for count in patch_counts)
expected_extent=unary_union(filled_regions)
assert expected_extent.symmetric_difference(shape(coverage['landscapeEnvelope'])).area<.001
exposed=expected_extent.boundary
valid_edges, missing_edges = [], []
accepted = missing = 0
estimated_count=0
for line in transition['lines']:
 raw=line['delta']; joined=line.get('joinDelta',raw); distances=np.concatenate([[0],np.cumsum(np.linalg.norm(np.diff(np.asarray(line['utm']),axis=0),axis=1))])
 assert len(raw)==len(joined)
 for i,(measured,used)in enumerate(zip(raw,joined)):
  if measured is not None:assert used==measured;continue
  if used is None:continue
  left=next((k for k in range(i-1,-1,-1)if raw[k]is not None),None)
  right=next((k for k in range(i+1,len(raw))if raw[k]is not None),None)
  assert left is not None and right is not None
  span=distances[right]-distances[left];difference=abs(raw[right]-raw[left]);rule=transition['gapInterpolation']
  assert span<=rule['maximumSpanMetres']<=2 and difference<=rule['maximumResidualDifferenceMetres']<=.5 and difference/span<=rule['maximumResidualGradient']<=.5
  assert abs(used-float(np.interp(distances[i],[distances[left],distances[right]],[raw[left],raw[right]])))<1e-9
  estimated_count+=1
 for xy,delta,source_y,survey_y in zip(line['utm'],line['delta'],line['sourceHeightMC'],line['surveyHeightMC']):
  assert exposed.distance(Point(xy)) < .0001
  if delta is None:
   assert source_y is None; missing += 1
  else:
   assert abs(delta) <= transition['maximumResidualMetres']
   assert abs(source_y-survey_y-delta) < 1e-9; accepted += 1
 for i in range(len(line['utm'])-1):
  edge=LineString(line['utm'][i:i+2]); ds=joined[i:i+2]
  assert edge.length <= transition['sampleSpacingMetres']+.0001
  if None in ds: missing_edges.append(edge)
  else: valid_edges.append((edge,ds))
assert accepted == transition['acceptedSamples'] and missing == transition['missingSamples']
assert estimated_count == len(transition.get('estimatedControls',[]))
missing_geometry=unary_union(missing_edges)
def independent_correction(xy):
 from shapely import points,distance,line_locate_point
 pts=points(xy); best=np.full(len(xy),np.inf); residual=np.zeros(len(xy))
 for edge,ds in valid_edges:
  d=distance(pts,edge); replace=d<best
  along=line_locate_point(edge,pts,normalized=True)
  residual[replace]=(ds[0]*(1-along)+ds[1]*along)[replace];best[replace]=d[replace]
 def smooth(v):
  v=np.clip(v,0,1);return v*v*(3-2*v)
 return residual*smooth(1-best/transition['widthMetres'])*smooth(distance(pts,prior_ground)/transition['priorFadeMetres'])*smooth(distance(pts,missing_geometry)/transition['priorFadeMetres'])

# Decode terrain independently from tile UVs and the pinned DGM1 raster.
area=[];mcarea=[];max_ground=0
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/campus-dop-east.tif')as dop:
 data=dem.read(1).astype(float)
 for name in rec['groundTiles']:
  v,texture=decode(out/name)[0];e,n=map(int,Path(name).stem.split('-')[-2:]);step=spec['groundTileMetres'];xy=np.column_stack([e+v[:,3]*step,n+step-v[:,4]*step]);expected=world(xy,sample(dem,data,xy[:,0],xy[:,1])+independent_correction(xy));error=float(np.max(np.abs(expected-v[:,:3])));assert error<.001;max_ground=max(max_ground,error);area.append(union_all(polygons(xy.reshape(-1,3,2))));mcarea.append(union_all(polygons(v[:,:3].reshape(-1,3,3)[:,:,[0,2]])));c,row=(~dop.transform)*(e,n+step);rgb=dop.read([1,2,3],window=rasterio.windows.Window(round(c),round(row),step*5,step*5)).transpose(1,2,0);assert np.array_equal(np.frombuffer(texture,dtype='uint8').reshape(step*5,step*5,4)[:,:,:3],rgb);hashes[name]=sha(out/name)
# The lookup guide must carry the same graded heights as rendered ground.
surface=next(s for s in m['supplementalSurfaces']if s['name']=='physics-ii-site')
guide=np.asarray(surface['terrainGuide']['points']);e,n,_=inverse.transform(*((guide-[0,64,0])@basis+origin).T);xy=np.column_stack([e,n])
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem:
 expected=world(xy,sample(dem,dem.read(1).astype(float),e,n)+independent_correction(xy))
 assert np.max(np.abs(expected-guide))<.001
# Interior samples remain exactly survey-derived, including the courtyard.
interior=shape(coverage['envelope']).buffer(-.01)
assert all(abs(float(v))<1e-12 for q,v in zip(xy,independent_correction(xy))if interior.covers(Point(q)))
area=unary_union(area);mcarea=unary_union(mcarea);coverage=read(out/rec['coverageFile']);assert area.symmetric_difference(shape(coverage['ground'])).area<.01
others=unary_union([Polygon(rings[0][:,:2],[h[:,:2]for h in rings[1:]]).buffer(0)for bid,items in surveys.items()if bid not in owned for k,rings in items if k=='GroundSurface']);assert area.intersection(others.buffer(.4999)).area<.01,[(bid,sum(area.intersection(Polygon(rings[0][:,:2],[h[:,:2]for h in rings[1:]]).buffer(0).buffer(.4999)).area for k,rings in items if k=='GroundSurface')) for bid,items in surveys.items()if bid not in owned and any(area.intersection(Polygon(rings[0][:,:2],[h[:,:2]for h in rings[1:]]).buffer(0).buffer(.4999)).area>.001 for k,rings in items if k=='GroundSurface')]
old_overlap=0
for t in m['tiles']:
 if t['kind']!='ground'or t['file']in rec['groundTiles']:continue
 lo,hi=t['bounds']
 if not mcarea.intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
 for v,_ in decode(out/t['file']):old_overlap+=mcarea.intersection(union_all(polygons(v[:,:3].reshape(-1,3,3)[:,:,[0,2]]))).area
assert old_overlap<.005,old_overlap
# Reconstruct the complete intended coverage from earlier manifest surfaces.
def prior_ring(ring):
 q=np.asarray(ring);ecef_points=origin+q[:,0,None]*basis[0]+q[:,1,None]*basis[2]+basis[1];e,n,_=inverse.transform(*ecef_points.T);return np.column_stack([e,n])
prior=unary_union([box(*m['boundsUtm']),*[Polygon(prior_ring(p['ring']),[prior_ring(h)for h in p.get('holes',[])])for s in m['supplementalSurfaces'][:next(i for i,s in enumerate(m['supplementalSurfaces'])if s['name']=='physics-ii-site')]for p in s['rings']]])
expected_coverage=expected_extent.difference(others.buffer(.5)).difference(prior.buffer(.002))
independent_coverage_error=area.symmetric_difference(expected_coverage).area
assert independent_coverage_error<.02,independent_coverage_error

# The bridge has a roof and real underside, with no mesh curtain below it.
bridge=next(b for b in rec['bodies']if b['name']=='bridge');bv=np.concatenate([v[:,:3]for v,_ in meshes[bridge['building']]]);assert bv[:,1].min()>=bridge['undersideMC']-.0001
foot=next(rings for k,rings in surveys[bridge['building']]if k=='GroundSurface');q=Polygon(foot[0][:,:2]).centroid
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem:
 xy=np.array([[q.x,q.y]]);floor=world(xy,np.array([next(dem.sample(xy))[0]]))[0];clearance=bridge['undersideMC']-floor[1];assert clearance>2.2,clearance
tri=np.concatenate([v[:,:3].reshape(-1,3,3)for v,_ in meshes[bridge['building']]]);hits,_=ray_hits(tri,floor+[0,.1,0],np.array([0,1,0]));assert len(hits)and abs(min(hits)-(clearance-.1))<.001
# Every planting sample remains in the measured courtyard; no arbitrary tree.
main=next(b for b in rec['bodies']if b['name']=='main');ground=next(rings for k,rings in surveys[main['building']]if k=='GroundSurface');court=Polygon(ground[1][:,:2]);planting_area=0
plant_points=[];plant_floors=[];plant_tops=[]
with rasterio.open(r/'.cache/campus-dop-east.tif')as dop,rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/32698_5349_20_DOM.tif')as dom:
 for control in rec['shrubControls']:
  region=shape(control['sourceRegionUTM']);assert region.difference(court.buffer(-.8)).area<.001;assert abs(region.area-control['areaSquareMetres'])<.001;assert .7<control['sourceHeightRangeMetres'][0]<=control['sourceHeightRangeMetres'][1]<4.2;planting_area+=region.area
  lo=np.floor(region.bounds[:2]);hi=np.ceil(region.bounds[2:]);xy=np.array([(e+.25,n+.25)for n in np.arange(lo[1],hi[1],.5)for e in np.arange(lo[0],hi[0],.5)if region.contains(Point(e+.25,n+.25))]);assert len(xy)==control['sampleCount'] and len(xy)*.25==control['areaSquareMetres']
  rgb=np.array(list(dop.sample(xy)));floors=np.array([p[0]for p in dem.sample(xy)]);tops=np.array([p[0]for p in dom.sample(xy)]);H=tops-floors
  assert np.all((rgb[:,1]>rgb[:,0]*1.025)&(rgb[:,1]>rgb[:,2]+2)&(H>.7)&(H<4.2));assert np.max(np.abs([H.min()-control['sourceHeightRangeMetres'][0],H.max()-control['sourceHeightRangeMetres'][1]]))<1e-6
  plant_points.extend(xy);plant_floors.extend(floors);plant_tops.extend(tops)
if rec['shrubTiles']:
 assert len(rec['shrubTiles'])==1
 assert all(t.get('collisionParts')==[]for t in m['tiles']if t['file']in rec['shrubTiles'])
 wood,leaves=decode(out/rec['shrubTiles'][0]);xy=np.asarray(plant_points);floors=world(xy,np.asarray(plant_floors));tops=world(xy,np.asarray(plant_tops));cards=leaves[0][:,:3].reshape(len(xy),16,6,3)
 assert np.max(np.abs(cards[:,:,:,0]-floors[:,None,None,0]))<=.401 and np.max(np.abs(cards[:,:,:,2]-floors[:,None,None,2]))<=.401
 assert np.all(cards[:,:,:,1]>=floors[:,None,None,1]) and np.all(cards[:,:,:,1]<=tops[:,None,None,1]+.0001)
 leaf=Image.open(r/'.cache/tree-source/textures/jacaranda_tree_leaves_diff_1k.jpg').convert('RGBA');leaf.putalpha(Image.open(r/'.cache/tree-source/textures/jacaranda_tree_leaves_alpha_1k.png').convert('L'));assert leaves[1]==leaf.tobytes()
for name in rec['treeTiles']+rec['shrubTiles']:hashes[name]=sha(out/name)
# Independent source classification and tree controls for the expanded site.
assert sha(r/rec['landscapeGeneratorFile'])==rec['landscapeGeneratorSha256']
for key,path in [('materialMaskSha256',r/'minecraft/exterior'/rec['materialMaskFile']),('materialDerivedSha256',out/rec['materialDerivedFile'])]:assert sha(path)==rec[key]
shader_mapping=(r/'minecraft/exterior/shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED PHYSICS II SITE MAPPING\n')[1].split('// END GENERATED PHYSICS II SITE MAPPING')[0]
assert hashlib.sha256(shader_mapping.encode()).hexdigest()==rec['shaderMappingSha256']
owned_footprints=unary_union([Polygon(rings[0][:,:2],[h[:,:2]for h in rings[1:]]).buffer(0)for bid,items in surveys.items()if bid in owned for kind,rings in items if kind=='GroundSurface'])
outdoor=shape(coverage['ground']).difference(owned_footprints);mapped={'grass':[],'asphalt':[]};path_guards=[]
for wid,(xy,tags)in ways.items():
 if tags.get('landuse')=='grass'and xy[0]==xy[-1]:mapped['grass'].append(Polygon(xy).buffer(0).intersection(outdoor))
 if tags.get('highway')=='footway':
  path=LineString(xy).buffer(float(tags.get('width',spec['landscape']['defaultPathWidthMetres']))/2,cap_style=2,join_style=2);path_guards.append(path.buffer(.35))
  if tags.get('surface')=='asphalt':mapped['asphalt'].append(path.intersection(outdoor))
mapped={k:unary_union(v)for k,v in mapped.items()};guard=unary_union(path_guards)
parking=spec['landscape']['gravelParking'];parking_xy,parking_tags=ways[parking['way']]
assert parking_tags.get('amenity')=='parking'and ways[parking['supportingAisleWay']][1].get('surface')=='pebblestone'
parking_region=Polygon(parking_xy).buffer(0).intersection(outdoor)
mask=np.asarray(Image.open(r/'minecraft/exterior'/rec['materialMaskFile']));assert mask.shape==(1024,1024,4)and np.all(mask[:,:,3]==255);low,high=np.array(rec['materialMaskBoundsMC']);pixels=np.array([(i,j)for j in range(3,1024,13)for i in range(3,1024,13)])
xz=np.column_stack([low[0]+(pixels[:,0]+.5)*(high[0]-low[0])/1024,high[1]-(pixels[:,1]+.5)*(high[1]-low[1])/1024]);ecef_points=origin+xz[:,0,None]*basis[0]+xz[:,1,None]*basis[2]+basis[1];e,n,_=inverse.transform(*ecef_points.T);xy=np.column_stack([e,n]);bounds=shape(coverage['ground']).bounds;lo=np.floor(bounds[:2]);hi=np.ceil(bounds[2:]);cell=np.column_stack([lo[0]+(np.floor((e-lo[0])/.5)+.5)*.5,hi[1]-(np.floor((hi[1]-n)/.5)+.5)*.5]);checked=0
with rasterio.open(r/'.cache/campus-dop-east.tif')as dop,rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/32698_5349_20_DOM.tif')as dom:
 rgb=np.array(list(dop.sample(cell)));H=np.array(list(dom.sample(cell)))[:,0]-np.array(list(dem.sample(cell)))[:,0]
 for k,((i,j),q,c)in enumerate(zip(pixels,xy,cell)):
  point=Point(q)
  if any(p.boundary.distance(point)<.012 for p in [outdoor,guard,parking_region,*mapped.values()]if not p.is_empty)or np.min(.25-np.abs(q-c))<.012:continue
  asphalt=mapped['asphalt'].contains(point)
  green=bool(rgb[k,1]>rgb[k,0]*1.025 and rgb[k,1]>rgb[k,2]+2 and -.3<=H[k]<=.7)
  grass=(mapped['grass'].contains(point)or(outdoor.contains(point)and not guard.contains(point)and green))and not asphalt
  gravel=parking_region.contains(point)and not grass and not asphalt
  assert bool(mask[j,i,1])==gravel,(i,j,q.tolist(),gravel,mask[j,i].tolist())
  assert bool(mask[j,i,0])==grass and bool(mask[j,i,2])==asphalt,(i,j,q.tolist(),grass,asphalt,mask[j,i].tolist())
  checked+=1
assert checked>4000,checked
surface=next(s for s in m['supplementalSurfaces']if s['name']=='physics-ii-site');trees=surface['vegetation']['trees'];assert len(trees)==rec['treeCount']
old_trees=[*m['vegetation']['trees'],*[t for s in m['supplementalSurfaces']if s is not surface for t in s.get('vegetation',{}).get('trees',[])]]
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem:
 data=dem.read(1).astype(float)
 for t in trees:
  q=np.array([t['utm']]);point=Point(*t['utm']);assert shape(coverage['ground']).covers(point)and not guard.contains(point)
  assert not owned_footprints.buffer(.5).contains(point)and 4<=t['height']<=26 and t['crownArea']>=3
  assert min(math.dist(t['utm'],old['utm'])for old in old_trees)>=3-1e-6
  expected=world(q,sample(dem,data,q[:,0],q[:,1])+independent_correction(q))[0];assert np.max(np.abs(expected-t['center']))<.001

assert len({t['runtimeId']for t in m['tiles']if 'runtimeId'in t})==sum('runtimeId'in t for t in m['tiles'])
result={'status':'PASS: source roof geometry/pixels, recessed outward panes, joint backing, neighbour retirement, ground separation and raised bridge clearance','manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'validatorSha256':sha(Path(__file__)),'inputSha256':inputs,'roofControls':roof_controls,'maximumRoofCoordinateErrorMetres':max(roof_errors),'paneControlsVerified':pane_count,'northInfillHiddenWallAreaSquareMetres':float(hidden_area),'northernContainer':{'osmFootprintIoU':container_osm_iou,'upperWallSpuriousAreaSquareMetres':upper_wall_spurious_area,'sourceWalls':8,'sourceRoofTriangles':6},'jointBackingControlsVerified':joint_count,'maximumGroundCoordinateErrorMetres':max_ground,'terrainTransition':{'acceptedSamples':accepted,'missingSamples':missing,'estimatedJoiningControls':estimated_count,'unresolvedJoiningControls':missing-estimated_count,'widthMetres':transition['widthMetres'],'sourceSha256':sha(transition_file)},'oldGroundOverlapSquareMetres':old_overlap,'independentCoverageErrorSquareMetres':independent_coverage_error,'canopySourceAreasSquareMetres':canopy_counts,'landscapeMaterialPixelControls':checked,'mappedExtentWays':coverage_policy['osmWays'],'sourceConfirmedEnclosedContinuityAreas':continuity_areas,'gravelMaterialPixels':int(np.count_nonzero(mask[:,:,1])),'treeCount':len(trees),'bridgeClearanceMetres':float(clearance),'shrubAreaSquareMetres':planting_area,'tileSha256':hashes,'qualification':'Source representation and estimated architectural geometry only. Native visual, movement, collision and reflection acceptance are separate.'};(out/'physics-ii-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['tileSha256','inputSha256']},indent=2))

#!/usr/bin/env python3
"""Independently check laboratory site terrain, source coverage, materials and railings."""
from pathlib import Path
import argparse,hashlib,json,math,struct,xml.etree.ElementTree as ET
import numpy as np
import rasterio
from scipy.ndimage import map_coordinates
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon,Point,LineString,shape,box
from shapely.ops import unary_union
from shapely import polygons,union_all
r=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=r/'dist-minecraft/exterior');out=p.parse_args().directory;read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');rec=m['architecture']['physicsLaboratorySite'];spec=read(r/'minecraft/exterior'/rec['sourceFile']);coverage=read(out/rec['coverageFile'])
assert sha(r/'minecraft/exterior'/rec['sourceFile'])==rec['sourceSha256']
for key,path in [('generatorSha256',r/rec['generatorFile']),('vegetationGeneratorSha256',r/'scripts/exterior_vegetation.py'),('coverageSha256',out/rec['coverageFile']),('materialMaskSha256',r/'minecraft/exterior'/rec['materialMaskFile']),('materialDerivedSha256',out/rec['materialDerivedFile'])]:assert sha(path)==rec[key],key
mapping=(r/'minecraft/exterior/shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED LABORATORY SITE MAPPING\n')[1].split('// END GENERATED LABORATORY SITE MAPPING')[0];assert hashlib.sha256(mapping.encode()).hexdigest()==rec['shaderMappingSha256']
assert sha(r/'minecraft/exterior'/spec['osm']['sourceFile'])==spec['osm']['sha256']
sources=read(r/'minecraft/exterior/sources.json');input_hashes={}
for key,file in [('dgm1','campus-dgm-east.tif'),('dop20','campus-dop-east.tif')]:
 item=sorted(sources[key],key=lambda v:v['name'])[1];assert sha(r/'.cache'/file)==item['sha256'];input_hashes[file]=item['sha256']
vegetation=read(r/'minecraft/exterior/vegetation-sources.json')
for item in vegetation['inputs']:
 assert sha(r/'.cache'/item['cachePath'])==item['sha256'];input_hashes[item['cachePath']]=item['sha256']
geo=Transformer.from_crs(4979,4978,always_xy=True);utm=Transformer.from_crs(25832,4978,always_xy=True);geographic=Transformer.from_crs(25832,4258,always_xy=True);grid=Transformer.from_crs(4326,25832,always_xy=True)
lat,lon=map(math.radians,m['origin'][:2]);origin=np.array(geo.transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-math.sin(lon),math.cos(lon),0],[math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)],[math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
def decode(file):
 data=file.read_bytes();count,*anchor=struct.unpack_from('<i3d',data,4);at=32;parts=[]
 for _ in range(count):
  n,w,h=struct.unpack_from('<3i',data,at);at+=16;v=np.frombuffer(data,dtype='<f4',count=n*5,offset=at).reshape(-1,5).astype(float);v[:,:3]+=anchor;at+=n*20;parts.append((v,(w,h),data[at:at+w*h*4]));at+=w*h*4
 assert at==len(data);return parts

def sample(d,data,e,n):
 x,y=(~d.transform)*(e,n);assert np.all(x>=.5)&np.all(y>=.5)&np.all(x<=d.width-.5)&np.all(y<=d.height-.5)
 return map_coordinates(data,[y-.5,x-.5],order=1,prefilter=False)
terrain_polys=[];mc_polys=[];tiles={t['file']:t for t in m['tiles']};maximum=0.;hashes={};vertex_count=0
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/de_bkg_gcg2016.tif')as geoid,rasterio.open(r/'.cache/campus-dop-east.tif')as dop:
 assert sha(r/'.cache/de_bkg_gcg2016.tif')==sources['geoid']['sha256'];heights=dem.read(1).astype(float);offsets=geoid.read(1).astype(float)
 for name in rec['groundTiles']:
  parts=decode(out/name);assert len(parts)==1;v,size,texture=parts[0];step=spec['groundTileMetres'];e,n=map(int,Path(name).stem.split('-')[-2:]);xy=np.column_stack([e+v[:,3]*step,n+step-v[:,4]*step]);h=sample(dem,heights,xy[:,0],xy[:,1]);longitude,latitude=geographic.transform(*xy.T);h+=sample(geoid,offsets,longitude,latitude);xyz=np.column_stack(utm.transform(xy[:,0],xy[:,1],h));expected=(xyz-origin)@basis.T;expected[:,1]+=64;error=float(np.max(np.abs(expected-v[:,:3])));maximum=max(maximum,error);assert error<.001,(name,error)
  col,row=(~dop.transform)*(e,n+step);rgb=dop.read([1,2,3],window=rasterio.windows.Window(round(col),round(row),step*5,step*5)).transpose(1,2,0);assert size==(step*5,step*5);rgba=np.frombuffer(texture,dtype='uint8').reshape(*size[::-1],4);assert np.array_equal(rgba[:,:,:3],rgb)
  terrain_polys.append(union_all(polygons(xy.reshape(-1,3,2))));mc_polys.append(union_all(polygons(v[:,:3].reshape(-1,3,3)[:,:,[0,2]])));hashes[name]=sha(out/name);vertex_count+=len(v)
area=unary_union(terrain_polys);mc_area=unary_union(mc_polys);intended=shape(coverage['ground']);error=area.symmetric_difference(intended).area;assert error<.01,error
osm=ET.parse(r/'minecraft/exterior'/spec['osm']['sourceFile']).getroot();nodes={n.get('id'):grid.transform(float(n.get('lon')),float(n.get('lat')))for n in osm.findall('node')};ways={w.get('id'):([nodes[n.get('ref')]for n in w.findall('nd')],{t.get('k'):t.get('v')for t in w.findall('tag')})for w in osm.findall('way')}
ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'};footprints=[]
for item,file in zip(sources['lod2'],['campus-east.gml','campus-west.gml']):
 assert sha(r/'.cache'/file)==item['sha256']
 for surface in ET.parse(r/'.cache'/file).findall('.//b:GroundSurface//g:Polygon',ns):
  loops=[np.array(list(map(float,p.text.split()))).reshape(-1,3)[:,:2]for p in surface.findall('.//g:LinearRing/g:posList',ns)]
  if not loops:continue
  poly=Polygon(loops[0],loops[1:]).buffer(0)
  if poly.intersects(box(*spec['boundsUTM'])):footprints.append(poly)
footprints=unary_union(footprints);osm_buildings=unary_union([Polygon(xy).buffer(0)for xy,t in ways.values()if 'building'in t and xy[0]==xy[-1]])
assert area.intersection(footprints.union(osm_buildings).buffer(spec['neighbourGuardMetres']-.0001)).area<.01
inverse=Transformer.from_crs(4978,25832,always_xy=True)
def old_ring(ring):
 q=np.asarray(ring);world=origin+q[:,0,None]*basis[0]+q[:,1,None]*basis[2]+basis[1];e,n,_=inverse.transform(*world.T);return np.column_stack([e,n])
surface=next(s for s in m['supplementalSurfaces']if s['name']=='physics-laboratory-west-site')
# Earlier layers own shared boundaries. Later extensions must not retroactively
# shrink the expected footprint of this already-built site. Actual overlap is
# still checked against every other encoded ground mesh below.
prior=unary_union([box(*m['boundsUtm']),*[Polygon(old_ring(p['ring']),[old_ring(h)for h in p.get('holes',[])])for s in m['supplementalSurfaces'][:m['supplementalSurfaces'].index(surface)]for p in s['rings']]])
expected=box(*spec['boundsUTM']).difference(footprints.union(osm_buildings).buffer(spec['neighbourGuardMetres'])).difference(prior.buffer(spec['oldSurfaceGuardMetres']))
source_error=area.symmetric_difference(expected).area;assert source_error<.01,source_error
# Both observed outdoor debris points must be covered without changing buildings.
for xy in [[698579.05154,5349537.16805],[698577.26056,5349532.82117]]:assert area.covers(Point(*xy)),xy
overlap=0
for tile in m['tiles']:
 if tile['kind']!='ground'or tile['file']in rec['groundTiles']:continue
 lo,hi=tile['bounds'];bound=box(lo[0],lo[2],hi[0],hi[2])
 if not mc_area.intersects(bound):continue
 for v,_,_ in decode(out/tile['file']):overlap+=mc_area.intersection(union_all(polygons(v[:,:3].reshape(-1,3,3)[:,:,[0,2]]))).area
assert overlap<.005,overlap
# Independently classify pixel centres against the source OSM geometry.
layers={'grass':[],'asphalt':[]};path_guards=[];fences=[]
for wid,(xy,tags)in ways.items():
 if tags.get('landuse')=='grass':layers['grass'].append(Polygon(xy).buffer(0).intersection(expected))
 if tags.get('highway')=='footway':
  path=LineString(xy).buffer(float(tags.get('width',spec['defaultPathWidthMetres']))/2,cap_style=2,join_style=2);path_guards.append(path.buffer(.35))
  if tags.get('surface')=='asphalt':layers['asphalt'].append(path.intersection(expected))
 if tags.get('barrier')=='fence'and tags.get('fence_type')=='railing':fences.append((wid,LineString(xy)))
layers={k:unary_union(v)for k,v in layers.items()};layers['grass']=layers['grass'].difference(layers['asphalt']);mask=np.array(Image.open(r/'minecraft/exterior'/rec['materialMaskFile']));assert mask.shape==(1024,1024,4) and np.all(mask[:,:,3]==255) and not np.any(mask[:,:,1]);lo,hi=np.array(rec['materialMaskBoundsMC']);checked=0
for iy in range(3,1024,11):
 for ix in range(3,1024,11):
  point=Point(old_ring([[lo[0]+(ix+.5)*(hi[0]-lo[0])/1024,hi[1]-(iy+.5)*(hi[1]-lo[1])/1024]])[0])
  if any(v.boundary.distance(point)<.01 for v in layers.values()):continue
  for key,channel in [('grass',0),('asphalt',2)]:assert bool(mask[iy,ix,channel])==layers[key].contains(point),(ix,iy,key)
  checked+=1
trees=surface['vegetation']['trees'];assert len(trees)==rec['treeCount'];oldtrees=[*m['vegetation']['trees'],*[t for s in m['supplementalSurfaces']if s is not surface for t in s.get('vegetation',{}).get('trees',[])]];trunk_exclusion=unary_union(path_guards+[line.buffer(.7)for _,line in fences]);minimum=math.inf
for t in trees:
 assert expected.covers(Point(*t['utm'])) and not trunk_exclusion.contains(Point(*t['utm']));assert 4<=t['height']<=26 and t['crownArea']>=3
 minimum=min(minimum,min(math.dist(t['utm'],o['utm'])for o in oldtrees))
assert minimum>=3-1e-6,minimum
assert len(fences)==len(rec['railingControls'])==len(rec['railingTiles'])==1
wid,line=fences[0];assert line.distance(footprints)>0;path_distance=min(line.distance(LineString(xy))for xy,t in ways.values()if t.get('highway')=='footway');assert path_distance>1.1,path_distance
v,_,_=decode(out/rec['railingTiles'][0])[0];world=(v[:,:3]-[0,64,0])@basis+origin;e,n,h=inverse.transform(*world.T);distance=max(line.distance(Point(x,y))for x,y in zip(e,n));assert distance<.027,distance
with rasterio.open(r/'.cache/campus-dgm-east.tif')as dem,rasterio.open(r/'.cache/de_bkg_gcg2016.tif')as geoid:
 lon,lat=geographic.transform(e,n);above=h-sample(geoid,geoid.read(1).astype(float),lon,lat)-sample(dem,dem.read(1).astype(float),e,n);assert above.min()>.04 and above.max()<1.14,(above.min(),above.max())
for name in rec['treeTiles']+rec['railingTiles']:hashes[name]=sha(out/name)
assert len({t['runtimeId']for t in m['tiles']if 'runtimeId'in t})==sum('runtimeId'in t for t in m['tiles'])
result={'status':'PASS: source-derived coverage, DGM1 heights, DOP20 pixels, old terrain separation, building guards, material classification, trees and railing alignment','manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'validatorSha256':sha(Path(__file__)),'inputSha256':input_hashes,'groundTiles':len(rec['groundTiles']),'groundVertices':vertex_count,'maximumCoordinateErrorMetres':maximum,'coverageSymmetricDifferenceSquareMetres':error,'independentCoverageErrorSquareMetres':source_error,'oldGroundOverlapSquareMetres':overlap,'materialPixelControls':checked,'treeCount':len(trees),'nearestOldTrunkMetres':minimum,'railingMaximumAlignmentErrorMetres':distance,'railingPathCentreDistanceMetres':path_distance,'railingHeightRangeMetres':[float(above.min()),float(above.max())],'tileSha256':hashes,'qualification':'Source representation checks only. Native walking, scan cleanup, visual quality and performance need separate evidence.'};(out/'physics-laboratory-site-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['tileSha256','inputSha256']},indent=2))

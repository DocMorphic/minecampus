#!/usr/bin/env python3
"""Build the surveyed Garching exterior and its aerial-image textures.

Run with .cache/geodata-venv/bin/python scripts/build-exterior.py.
Inputs are pinned in minecraft/exterior/sources.json (CC BY 4.0).
Output stays in ignored dist-minecraft/exterior; see native validation results.
"""
from pathlib import Path
import argparse,hashlib,json,math,struct,xml.etree.ElementTree as ET
import urllib.request,tempfile,os
import numpy as np
import rasterio
from PIL import Image,ImageDraw
from pyproj import Transformer
import mapbox_earcut

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache';CACHE.mkdir(parents=True,exist_ok=True); OUT=ROOT/'dist-minecraft/exterior';OUT.mkdir(parents=True,exist_ok=True)
NS={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'}
SPEC=json.loads((ROOT/'minecraft/exterior/sources.json').read_text())
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--download',action='store_true',help='Download only the pinned public survey/imagery inputs');args=parser.parse_args()
inputs=[]
for kind,names in [('lod2',['campus-east.gml','campus-west.gml']),('dgm1',['campus-dgm-west.tif','campus-dgm-east.tif']),('dop20',['campus-dop-west.tif','campus-dop-east.tif'])]:
 entries=sorted(SPEC[kind],key=lambda entry:entry['name']) if kind!='lod2' else SPEC[kind]
 inputs.extend(zip(entries,names))
inputs.append((SPEC['geoid'],SPEC['geoid']['name']))
vegetation_spec=json.loads((ROOT/'minecraft/exterior/vegetation-sources.json').read_text())
inputs.extend((item,item['cachePath']) for item in vegetation_spec['inputs'])
if args.download:
 for entry,name in inputs:
  target=CACHE/name;target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists() and target.stat().st_size==entry['size'] and hashlib.sha256(target.read_bytes()).hexdigest()==entry['sha256']:continue
  print('Downloading public input:',entry.get('name',name),flush=True)
  req=urllib.request.Request(entry['url'],headers={'User-Agent':'Minecampus/0.4 (https://github.com/DocMorphic/minecampus)'})
  with urllib.request.urlopen(req,timeout=120) as response,tempfile.NamedTemporaryFile(dir=CACHE,delete=False) as out:
   temporary=Path(out.name);digest=hashlib.sha256();size=0
   while chunk:=response.read(1024*1024):out.write(chunk);digest.update(chunk);size+=len(chunk)
  if size!=entry['size'] or digest.hexdigest()!=entry['sha256']:
   temporary.unlink();raise ValueError('Public source integrity check failed: '+name)
  temporary.replace(target)
ORIGIN=(48.265,11.671,519.7618173672081)
utm_to_ecef=Transformer.from_crs(25832,4978,always_xy=True)
geo_to_ecef=Transformer.from_crs(4979,4978,always_xy=True)
lat,lon=map(math.radians,ORIGIN[:2]);origin=np.array(geo_to_ecef.transform(ORIGIN[1],ORIGIN[0],ORIGIN[2]))
east=np.array([-math.sin(lon),math.cos(lon),0]);up=np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)]);south=np.array([math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)])
# DHHN2016 is a physical height. Fit the local vertical offset once against the
# existing world datum; do not silently interpret it as ellipsoid height.
geoid=rasterio.open(CACHE/'de_bkg_gcg2016.tif');geoid_values=geoid.read(1)
utm_to_geo=Transformer.from_crs(25832,4258,always_xy=True)
def undulation(e,n):
 lon,lat=utm_to_geo.transform(e,n);col,row=(~geoid.transform)*(lon,lat);col-=.5;row-=.5
 i=np.floor(col).astype(int);j=np.floor(row).astype(int);fx=col-i;fy=row-j
 return (geoid_values[j,i]*(1-fx)+geoid_values[j,i+1]*fx)*(1-fy)+(geoid_values[j+1,i]*(1-fx)+geoid_values[j+1,i+1]*fx)*fy

def mc(points):
 a=np.asarray(points);x,y,z=utm_to_ecef.transform(a[:,0],a[:,1],a[:,2]+undulation(a[:,0],a[:,1]));p=np.column_stack((x,y,z))-origin
 return np.column_stack((p@east,p@up+64,p@south))

spec=json.loads((ROOT/'minecraft/exterior/sources.json').read_text())
for kind,names in [('lod2',['campus-east.gml','campus-west.gml']),('dgm1',['campus-dgm-west.tif','campus-dgm-east.tif']),('dop20',['campus-dop-west.tif','campus-dop-east.tif'])]:
 entries=sorted(spec[kind],key=lambda s:s['name']) if kind!='lod2' else spec[kind]
 for entry,name in zip(entries,names):
  payload=(CACHE/name).read_bytes()
  if hashlib.sha256(payload).hexdigest()!=entry['sha256']:raise ValueError('Source checksum mismatch: '+name)

photo_spec=json.loads((ROOT/'minecraft/exterior/photos/galileo-north.json').read_text())
if hashlib.sha256((ROOT/'minecraft/exterior/photos/galileo-north.jpg').read_bytes()).hexdigest()!=photo_spec['sha256']:raise ValueError('Facade reference checksum mismatch')

if hashlib.sha256((CACHE/spec['geoid']['name']).read_bytes()).hexdigest()!=spec['geoid']['sha256']:raise ValueError('Geoid checksum mismatch')

# Work at campus scale; leave the distant world with its original provider.
BOUNDS=(697900,5349000,698500,5349600)
buildings=[]
for name in ['campus-east.gml','campus-west.gml']:
 for b in ET.parse(CACHE/name).findall('.//b:Building',NS):
  surfaces=[]
  for typ in ['GroundSurface','WallSurface','RoofSurface']:
   for surf in b.findall('.//b:'+typ,NS):
    for poly in surf.findall('.//g:Polygon',NS):
     rings=[]
     for ring in poly.findall('.//g:LinearRing',NS):
      pos=ring.find('g:posList',NS)
      if pos is None:continue
      p=np.array(list(map(float,pos.text.split()))).reshape(-1,3)
      if np.linalg.norm(p[0]-p[-1])<.001:p=p[:-1]
      if len(p)>=3:rings.append(p)
     if rings:surfaces.append((typ,rings))
  ground=[r[0] for t,r in surfaces if t=='GroundSurface']
  if not ground:continue
  points=np.concatenate(ground);c=points.mean(axis=0)
  if points[:,0].max()<BOUNDS[0] or points[:,0].min()>BOUNDS[2] or points[:,1].max()<BOUNDS[1] or points[:,1].min()>BOUNDS[3]:continue
  buildings.append((b.get('{'+NS['g']+'}id'),surfaces))

# The main Galileo facade uses explicit panel geometry; contractor photos are
# references only. The earlier repeated strip is no longer a texture asset.
from exterior_galileo_facade import wall as build_galileo_wall
facade_source=ROOT/'minecraft/exterior/photos/galileo-facade-reference.json'
facade_spec=json.loads(facade_source.read_text())
facade_records={}


rasters=[rasterio.open(CACHE/('campus-dop-'+s+'.tif')) for s in ['west','east']]
dems=[rasterio.open(CACHE/('campus-dgm-'+s+'.tif')) for s in ['west','east']]
from exterior_terrain import ElevationSampler,SiteGradedElevation,PlanarApronElevation,terrain_axis
survey_elevation=ElevationSampler(dems)
elevation=survey_elevation
# The DGM records the former COS construction site, including piles against the
# now-completed facade. The current TUM photo supports a level finished perimeter.
# Infer its grading from the surveyed building base; preserve other footprints.
from shapely.geometry import Polygon
from shapely.ops import unary_union
cos_grounds=[r[0]for bid,surfaces in buildings if bid=='DEBY_LOD2_108698313' for typ,r in surfaces if typ=='GroundSurface']
cos_foot=unary_union([Polygon(p[:,:2])for p in cos_grounds])
cos_neighbours=[Polygon(r[0][:,:2])for bid,surfaces in buildings if bid!='DEBY_LOD2_108698313' for typ,r in surfaces if typ=='GroundSurface' and Polygon(r[0][:,:2]).distance(cos_foot)<17]
cos_grade=float(np.median(np.concatenate(cos_grounds)[:,2]))+.12
elevation=SiteGradedElevation(elevation,cos_foot,cos_grade,cos_neighbours)
landscape=json.loads((ROOT/'minecraft/exterior/cos-site.json').read_text())['inferredLandscape'];apron_spec=landscape['grading']
cos_ring=np.asarray(cos_foot.exterior.coords);apron_origin=cos_ring[4];apron_east=cos_ring[1]-apron_origin;apron_east/=np.linalg.norm(apron_east);apron_outward=np.array([apron_east[1],-apron_east[0]])
apron_foot=Polygon([apron_origin+apron_east*x+apron_outward*y for x,y in apron_spec['ring']])
drive_xy=np.array([apron_origin+apron_east*x+apron_outward*apron_spec['drivewayDistanceMetres']for x in apron_spec['drivewaySamplesAlongFacadeMetres']]);drive_h=survey_elevation.sample(drive_xy)
apron_slope=(float(np.median(drive_h))-cos_grade)/apron_spec['drivewayDistanceMetres']
elevation=PlanarApronElevation(elevation,apron_foot,apron_origin,apron_outward,cos_grade,apron_slope,cos_neighbours,apron_spec['blendMetres'])


def orthophoto(points):
 out=np.zeros((len(points),3),dtype=np.uint8)
 for r in rasters:
  ids=[i for i,p in enumerate(points) if r.bounds.left<=p[0]<r.bounds.right and r.bounds.bottom<=p[1]<r.bounds.top]
  if ids:out[ids]=np.array(list(r.sample([points[i][:2] for i in ids])))[:,:3]
 return out

def height(e,n):
 return elevation(e,n)

# One true-resolution aerial image. Terrain and roofs share exactly the same
# projected image coordinates, so there is no independent texture drift.
w=int((BOUNDS[2]-BOUNDS[0])*5);h=int((BOUNDS[3]-BOUNDS[1])*5)
image=np.zeros((h,w,3),dtype=np.uint8)
for r in rasters:
 from rasterio.warp import reproject,Resampling
 from rasterio.transform import from_origin
 for band in range(3):
  reproject(rasterio.band(r,band+1),image[:,:,band],src_transform=r.transform,src_crs=r.crs,dst_transform=from_origin(BOUNDS[0],BOUNDS[3],.2,.2),dst_crs='EPSG:25832',resampling=Resampling.bilinear,init_dest_nodata=False)
Image.fromarray(image).save(OUT/'campus-orthophoto.jpg',quality=94)
photo=Image.fromarray(image)

def encode(parts):
 payload=bytearray(b'ECT1'+struct.pack('<i3d',len(parts),0,0,0))
 for vertices,tex in parts:
  tex=tex.convert('RGBA');payload+=struct.pack('<3i4B',len(vertices),tex.width,tex.height,255,255,255,255)
  payload+=np.asarray(vertices,dtype='<f4').tobytes()+tex.tobytes()
 return payload

def triangulate(rings):
 p=np.concatenate(rings);q=mc(p);normal=np.cross(q[1]-q[0],q[2]-q[0]);drop=int(np.argmax(np.abs(normal)))
 # Find a stable normal even for a collinear first triple.
 if np.linalg.norm(normal)<1e-8:
  for k in range(2,len(q)):
   normal=np.cross(q[k-1]-q[0],q[k]-q[0])
   if np.linalg.norm(normal)>1e-8:break
  drop=int(np.argmax(np.abs(normal)))
 flat=np.delete(q,drop,axis=1);ends=np.cumsum([len(r) for r in rings]).astype(np.uint32)
 indices=mapbox_earcut.triangulate_float64(flat,ends).reshape(-1,3)
 return p,q,indices

def photo_uv(p):return np.column_stack(((p[:,0]-BOUNDS[0])/(BOUNDS[2]-BOUNDS[0]),(BOUNDS[3]-p[:,1])/(BOUNDS[3]-BOUNDS[1])))

metadata={'walls':[],'boundsUtm':BOUNDS,'origin':ORIGIN,'verticalDatumNote':'Official GCG2016 grid (BKG / PROJ CDN), bilinear interpolation; DHHN2016 physical height plus geoid undulation gives ellipsoid height.','buildings':[],'tiles':[],'attribution':spec['attribution']+' (CC BY 4.0); façade material: Minecampus reconstruction'}
metadata['siteGrading']={'building':'DEBY_LOD2_108698313','footprintUtm':list(cos_foot.exterior.coords),'heightDHHN2016':cos_grade,'innerMetres':4,'outerMetres':8,'excludedNeighbourFootprintsUtm':[list(p.exterior.coords)for p in cos_neighbours],'neighbourBufferMetres':1,'source':'https://nav.tum.de/building/cos','note':'Approximate finished-site grading inferred from the current photo and survey base; replaces obsolete construction mounds, blends to DGM beyond 4m, leaves it unchanged beyond 8m except for the explicitly documented forecourt apron; neighbouring buildings are excluded.'}
metadata['siteGrading']['apron']={'footprintUtm':list(apron_foot.exterior.coords),'originUtm':apron_origin.tolist(),'outwardUtm':apron_outward.tolist(),'baseHeightDHHN2016':cos_grade,'slope':apron_slope,'blendMetres':apron_spec['blendMetres'],'drivewaySamplesUtm':drive_xy.tolist(),'drivewayHeightsDHHN2016':drive_h.tolist(),'note':apron_spec['qualification']}
from exterior_terrain import BoundedGradeElevation
frontage_source=ROOT/'minecraft/exterior/galileo-frontage-grade.json'
frontage_spec=json.loads(frontage_source.read_text())
frontage_excluded=unary_union([Polygon(r[0][:,:2],[h[:,:2] for h in r[1:]]).buffer(0) for _,surfaces in buildings for kind,r in surfaces if kind=='GroundSurface']).buffer(.5)
elevation=BoundedGradeElevation(elevation,frontage_spec['patches'],frontage_excluded)
metadata['frontageGrading']={'sourceFile':'galileo-frontage-grade.json','sourceSha256':hashlib.sha256(frontage_source.read_bytes()).hexdigest(),'patches':frontage_spec['patches'],'buildingExclusionMetres':.5,'qualification':frontage_spec['qualification']}
# A compact DEM grid also guides runtime removal of the noisy source ground.
guideXY=np.array([(e,n)for n in range(BOUNDS[1],BOUNDS[3]+1,2)for e in range(BOUNDS[0],BOUNDS[2]+1,2)])
metadata['terrainGuide']={'width':301,'height':301,'points':mc(np.column_stack((guideXY,elevation.sample(guideXY)))).tolist()}
metadata['terrainSampling']={'sourceMetres':1,'interiorVertexMetres':1,'pixelConvention':'Area raster values at half-pixel centres','boundaryMethod':'Bilinear interpolation across merged source tiles; nearest valid edge value at the dataset boundary','guideMetres':2}
# 100m terrain tiles avoid repeatedly uploading a 36MB single image.
for e in range(BOUNDS[0],BOUNDS[2],100):
 for n in range(BOUNDS[1],BOUNDS[3],100):
  xs,ys=terrain_axis(e),terrain_axis(n);stride=len(xs)
  xy=np.array([(x,y)for y in ys for x in xs]);p=np.column_stack((xy,elevation.sample(xy)));q=mc(p);v=[]
  for row in range(len(ys)-1):
   for col in range(len(xs)-1):
    a=row*stride+col
    for i in [a,a+1,a+stride,a+1,a+stride+1,a+stride]:v.append([*q[i],(p[i,0]-e)/100,(n+100-p[i,1])/100])
  box=(int((e-BOUNDS[0])*5),int((BOUNDS[3]-n-100)*5),int((e-BOUNDS[0]+100)*5),int((BOUNDS[3]-n)*5))
  name=f'ground-{e}-{n}.ect';(OUT/name).write_bytes(encode([(v,photo.crop(box))]));metadata['tiles'].append({'file':name,'bounds':[q.min(axis=0).tolist(),q.max(axis=0).tolist()],'kind':'ground','runtimeId':1_000_000_000+len(metadata['tiles'])})
from shapely.geometry import Polygon,box,Point
from shapely.ops import unary_union
GALILEO={'DEBY_LOD2_107614322':1_000_000_100,'DEBY_LOD2_107614323':1_000_000_101}
LANDSCAPE={'DEBY_LOD2_5284521':1_000_000_200,'DEBY_LOD2_5284523':1_000_000_201,'DEBY_LOD2_104552957':1_000_000_202}
REPLACE=set(GALILEO)|set(LANDSCAPE)
metadata['replacements']=[]
for bid,surfaces in buildings:
 wall=[];glazing=[];reveals=[];roof=[];grounds=[];allq=[]
 if bid in GALILEO:facade_records[bid]=[]
 footprints=[Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in r[1:]]) for typ,r in surfaces if typ=='GroundSurface']
 footprint=unary_union([p if p.is_valid else p.buffer(0) for p in footprints])
 for typ,rings in surfaces:
  p,q,indices=triangulate(rings);allq.extend(q.tolist())
  if typ=='GroundSurface':
   grounds.append(q.tolist())
   if bid in REPLACE:
    polygon=Polygon(mc(rings[0])[:,[0,2]], [mc(r)[:,[0,2]] for r in rings[1:]]).buffer(8 if bid in GALILEO else 3)
    if polygon.geom_type=='Polygon':metadata['replacements'].append({'ring':list(polygon.exterior.coords),'holes':[list(r.coords) for r in polygon.interiors],'y0':float(q[:,1].min())-3,'y1':300})
   continue
  if typ=='RoofSurface':
   uv=photo_uv(p);roof.extend([[*q[i],*uv[i]] for t in indices for i in t]);continue
  metadata['walls'].append({'building':bid,'points':q.tolist()})
  if bid not in REPLACE:continue
  if bid in LANDSCAPE:
   wall.extend([[*q[i],0,0] for t in indices for i in t]);continue
  build_galileo_wall(q,footprint,facade_spec['reconstruction']['floorLevelsMC'][bid],[wall,glazing,reveals],facade_records[bid])

 a=np.array(allq);entry={'id':bid,'grounds':grounds,'bounds':[a.min(axis=0).tolist(),a.max(axis=0).tolist()]};metadata['buildings'].append(entry)
 if bid not in REPLACE:continue
 parts=[]
 if wall:parts.append((wall,Image.new("RGB",(1,1),(177,179,173)) if bid in LANDSCAPE else Image.new("RGB",(1,1),(225,226,223))))
 if glazing:parts.append((glazing,Image.new("RGB",(1,1),(55,71,78))))
 if reveals:parts.append((reveals,Image.new("RGB",(1,1),(45,48,48))))
 if roof:
  roof=np.asarray(roof);uv=roof[:,3:5];low=np.maximum(0,np.floor(uv.min(axis=0)*[w,h]).astype(int)-2);high=np.minimum([w,h],np.ceil(uv.max(axis=0)*[w,h]).astype(int)+2)
  roof[:,3:5]=(uv*[w,h]-low)/(high-low)
  parts.append((roof,photo.crop((*low,*high))))
 name=bid+'.ect';(OUT/name).write_bytes(encode(parts));metadata['tiles'].append({'id':bid,'file':name,'bounds':entry['bounds'],'kind':'reconstruction','profile':'galileo' if bid in GALILEO else 'landscape','runtimeId':GALILEO.get(bid,LANDSCAPE.get(bid))})
# The promenade has an underground entrance not represented by LoD2. Retire
# low, melted source fragments here while testing the above-ground reconstruction.
walk=mc(np.array([(698235,5349110,473),(698275,5349110,473),(698275,5349380,473),(698235,5349380,473)]))
metadata['replacements'].append({'ring':walk[:,[0,2]].tolist(),'y0':0,'y1':100})
metadata['attribution']='© BVV / geodaten.bayern.de; GeoBasis-DE / BKG (CC BY 4.0); MaxEmanuel / Poly Haven (CC0); MW: Renardo la vulpo (CC BY-SA 4.0)'
for stale in OUT.glob('DEBY_LOD2_*.ect'):
 if stale.name not in {t['file'] for t in metadata['tiles']}:stale.unlink()
from exterior_architecture import build as build_architecture
build_architecture(globals())
from exterior_ias import build as build_ias
build_ias(globals())
from exterior_photo_surfaces import build as build_photo_surfaces
build_photo_surfaces(globals())
from exterior_vegetation import build as build_vegetation
build_vegetation(globals())
from exterior_ground_surfaces import build as build_ground_surfaces
build_ground_surfaces(globals())
from exterior_galileo_court import build as build_galileo_court
build_galileo_court(globals())
from exterior_galileo_ramps import build as build_galileo_ramps
build_galileo_ramps(globals())
from exterior_physics_i import build as build_physics_i
build_physics_i(globals())
from exterior_physics_site import build as build_physics_site
build_physics_site(globals())
from exterior_physics_vegetation import build as build_physics_vegetation
build_physics_vegetation(globals())
from exterior_physics_ground import build as build_physics_ground
build_physics_ground(globals())
from exterior_physics_library import build as build_physics_library
build_physics_library(globals())
from exterior_physics_container import build as build_physics_container
build_physics_container(globals())
from exterior_p1_complex import build as build_p1_complex
build_p1_complex(globals())
from exterior_physics_woodland import build as build_physics_woodland
build_physics_woodland(globals())
from exterior_physics_new_laboratory import build as build_physics_new_laboratory
build_physics_new_laboratory(globals())
from exterior_physics_laboratory_site import build as build_physics_laboratory_site
build_physics_laboratory_site(globals())
from exterior_physics_ii import build as build_physics_ii
build_physics_ii(globals())
from exterior_physics_wsi import build as build_physics_wsi
build_physics_wsi(globals())
from exterior_physics_znn import build as build_physics_znn
build_physics_znn(globals())
from exterior_riverbank import build as build_riverbank
build_riverbank(globals())
from exterior_pinned_water import build as build_pinned_water
build_pinned_water(globals())
from exterior_north_ground import build as build_north_ground
build_north_ground(globals())
from exterior_physics_znn_west import build as build_physics_znn_west
build_physics_znn_west(globals())
from exterior_physics_cala import build as build_physics_cala
build_physics_cala(globals())
from exterior_physics_lmu import build as build_physics_lmu
build_physics_lmu(globals())
from exterior_physics_lmu_courtyard import build as build_physics_lmu_courtyard
build_physics_lmu_courtyard(globals())
from exterior_physics_lmu_east import build as build_physics_lmu_east
build_physics_lmu_east(globals())
metadata['architecture']['galileoFacade']={'sourceFile':'photos/galileo-facade-reference.json','sourceSha256':hashlib.sha256(facade_source.read_bytes()).hexdigest(),'reconstruction':facade_spec['reconstruction'],'walls':facade_records}
for stale in ['galileo-facade-rectified.jpg']:
 if (OUT/stale).exists():(OUT/stale).unlink()
(OUT/'manifest.json').write_text(json.dumps(metadata,separators=(',',':')))
print(f'Built: {len(buildings)} survey guides, {len(metadata["tiles"])} render tiles, {len(metadata["architecture"]["buildings"])+2} detailed building components, 3 landscape structures and {len(metadata["vegetation"]["trees"])} reconstructed trees. Native visual validation required.')

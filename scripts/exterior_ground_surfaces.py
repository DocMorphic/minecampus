"""Mapped ground materials. OSM footprints, BVV coordinate frame; no new terrain.
Material grain/joints are approximate, not a survey of individual paving units.
"""
import json,hashlib
import numpy as np
from pathlib import Path
from PIL import Image,ImageDraw
from pyproj import Transformer
from shapely.geometry import shape,box,Polygon
from shapely.ops import transform
from rasterio.features import rasterize
from rasterio.transform import from_origin

def build(ctx):
 root,out,metadata,mc=[ctx[k]for k in ['ROOT','OUT','metadata','mc']]
 source=root/'minecraft/exterior/ground-surfaces.geojson';data=json.loads(source.read_text())
 from exterior_paths import derive
 paths,path_stats=derive(ctx,data)
 from exterior_cos_site import build as build_cos_site
 site,site_stats=build_cos_site(ctx,data,paths)
 from exterior_grs_courtyard import build as build_grs_courtyard
 grs_site,grs_stats=build_grs_courtyard(ctx,data["features"]+paths+site)
 from exterior_promenade import build as build_promenade
 promenade,promenade_stats=build_promenade(ctx,data['features']+paths+site+grs_site)
 toUtm=Transformer.from_crs(4326,25832,always_xy=True).transform
 bounds=metadata['boundsUtm'];limit=box(*bounds);size=4096;span=672
 layers={k:[]for k in ['grass','paving','asphalt','soil','preserve']};areas={k:0 for k in layers};features=[]
 preview=Image.open(out/'campus-orthophoto.jpg').convert('RGB');draw=ImageDraw.Draw(preview)
 for feature in data['features']+paths+site+grs_site+promenade:
  p=transform(toUtm,shape(feature['geometry']));p=p if p.is_valid else p.buffer(0);p=p.intersection(limit)
  if p.is_empty:continue
  material=feature['properties']['material'];areas[material]+=p.area
  polygons=[p]if p.geom_type=='Polygon'else list(p.geoms)
  for poly in polygons:
   if poly.geom_type!='Polygon':continue
   def ring(coords):
    xy=np.asarray(coords);return mc(np.column_stack((xy,np.full(len(xy),475))))[:,[0,2]]
   projected=Polygon(ring(poly.exterior.coords),[ring(h.coords)for h in poly.interiors])
   layers[material].append((projected,255))
   pixels=[((e-bounds[0])*5,(bounds[3]-n)*5)for e,n in poly.exterior.coords]
   draw.line(pixels,fill={'grass':(255,220,0),'paving':(255,80,80),'asphalt':(0,230,255),'preserve':(255,80,255),'soil':(130,70,20)}[material],width=4)
  if 'osmWay'in feature['properties']:features.append(feature['properties']['osmWay'])
 # Area coverage keeps diagonal boundaries smooth at walking height. Process
 # short strips so 4x sampling does not require a full 16384² RGBA allocation.
 pixels=np.zeros((size,size,4),dtype=np.uint8);pixels[:,:,3]=255
 samples=4;strip=256
 for row in range(0,size,strip):
  height=min(strip,size-row);raster_shape=(height*samples,size*samples)
  grid=from_origin(-352,256-row*span/size,span/size/samples,span/size/samples)
  keep=rasterize(layers['preserve'],out_shape=raster_shape,transform=grid,dtype='uint8')>0 if layers['preserve'] else None
  for i,material in enumerate(['grass','paving','asphalt','soil']):
   if not layers[material]:continue
   high=rasterize(layers[material],out_shape=raster_shape,transform=grid,dtype='uint8')
   if keep is not None:high[keep]=0
   coverage=np.rint(high.reshape(height,samples,size,samples).mean(axis=(1,3))).astype('uint8')
   pixels[row:row+height,:,i]=255-coverage if material=='soil' else coverage
 target=root/'minecraft/exterior/assets/textures/campus/ground_surfaces.png';Image.fromarray(pixels).save(target,optimize=True)
 preview.save(out/'ground-surfaces-overlay.jpg',quality=94)
 metadata['groundSurfaces']={'source':'OpenStreetMap contributors, ODbL 1.0','sourceFile':'ground-surfaces.geojson','sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'maskSha256':hashlib.sha256(target.read_bytes()).hexdigest(),'maskSize':[size,size],'maskBoundsMC':[[-352,-416],[320,256]],'maskChannels':['grass','paving','asphalt','soil = 1 - alpha'],'areasSquareMetres':{k:round(v,2)for k,v in areas.items()},'osmWays':features,'paths':path_stats,'note':'Mapped polygons plus explicit-width path/road strips, clipped away from buildings and mapped areas. Width-derived edges, textures and paving units are estimates; terrain and collision are unchanged.'}
 metadata['attribution']+='; land cover: © OpenStreetMap contributors (ODbL 1.0)'
 metadata['groundSurfaces']['cosSite']=site_stats
 metadata['groundSurfaces']['grsCourtyard']=grs_stats
 metadata['groundSurfaces']['promenade']=promenade_stats
 metadata['groundSurfaces']['maskSampling']={'samplesPerAxis':samples,'method':'Area-averaged polygon coverage; preserve masks applied before averaging','note':'Interior classifications unchanged; edge pixels contain fractional material coverage.'}
 print('Ground materials:',len(features),'mapped polygons;',metadata['groundSurfaces']['areasSquareMetres'],flush=True)

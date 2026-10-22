"""Source-informed canopy reconstruction. Positions/heights: BVV DOM20/DGM1/DOP20.
Branch/leaf placement is procedural; texture atlases: Poly Haven (CC0).
Called by build-exterior.py after survey preparation, not imported by the game.
"""
from pathlib import Path
import json,math,hashlib,base64
import numpy as np
import rasterio
from rasterio.warp import reproject,Resampling
from rasterio.transform import from_origin
from rasterio.features import rasterize
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from PIL import Image,ImageDraw

def build(ctx):
 root,cache,out,metadata,mc,encode,height,buildings=[ctx[k] for k in ['ROOT','CACHE','OUT','metadata','mc','encode','height','buildings']]
 spec=json.loads((root/'minecraft/exterior/vegetation-sources.json').read_text())
 for item in spec['inputs']:
  p=cache/item['cachePath']
  if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Vegetation input missing or changed: '+item['cachePath'])
 bounds=metadata['boundsUtm'];resolution=.5;w=h=1200;transform=from_origin(bounds[0],bounds[3],resolution,resolution)
 dom=np.zeros((h,w),np.float32);dem=dom.copy()
 for files,target in [(['32697_5349_20_DOM.tif','32698_5349_20_DOM.tif'],dom),(['campus-dgm-west.tif','campus-dgm-east.tif'],dem)]:
  for filename in files:
   with rasterio.open(cache/filename) as r:reproject(rasterio.band(r,1),target,src_transform=r.transform,src_crs=r.crs,dst_transform=transform,dst_crs='EPSG:25832',resampling=Resampling.bilinear,init_dest_nodata=False)
 footprints=[]
 for bid,surfaces in buildings:
  for typ,rings in surfaces:
   if typ=='GroundSurface':
    p=Polygon(rings[0][:,:2],[r[:,:2] for r in rings[1:]]).buffer(1.2)
    if not p.is_empty:footprints.append(p)
 metadata['protectedFootprints']=[]
 for p in footprints:
  polys=[p] if p.geom_type=='Polygon' else list(getattr(p,'geoms',[]))
  for shape in polys:
   if shape.geom_type!='Polygon':continue
   coords=np.asarray(shape.exterior.coords);ring=mc(np.column_stack((coords,np.full(len(coords),475))))[:,[0,2]]
   metadata['protectedFootprints'].append(ring.tolist())
 protectionShapes=[p.buffer(1.8)for p in footprints]
 for bid,surfaces in buildings:
  for kind,rings in surfaces:
   if kind!='RoofSurface':continue
   shape=Polygon(rings[0][:,:2],[r[:,:2]for r in rings[1:]])
   if not shape.is_valid:shape=shape.buffer(0)
   if not shape.is_empty and shape.area>.01:protectionShapes.append(shape.buffer(1.5))
 protection=rasterize([(p,1)for p in protectionShapes],out_shape=(600,600),transform=from_origin(bounds[0],bounds[3],1,1),dtype='uint8')
 metadata['protectionGrid']={'width':600,'height':600,'metresPerPixel':1,'data':base64.b64encode(protection.tobytes()).decode()}
 occupied=rasterize([(p,1) for p in footprints],out_shape=(h,w),transform=transform,dtype='uint8')>0
 rgb=np.array(Image.open(out/'campus-orthophoto.jpg').resize((w,h))).astype(float)
 green=(rgb[:,:,1]>rgb[:,:,0]*1.025)&(rgb[:,:,1]>rgb[:,:,2]+2)
 canopy=dom-dem
 # Conservative DOM20 top envelope, in the same 2m ENU grid as the terrain.
 # A small maximum neighbourhood retains roof edges and canopy overhangs;
 # it lets the runtime reject detached source fragments above surveyed objects.
 upper=ndimage.maximum_filter(np.maximum(0,canopy),size=7)
 tops=[];terrainPoints=metadata['terrainGuide']['points']
 for j in range(301):
  row=min(1199,max(0,1199-j*4))
  for i in range(301):
   col=min(1199,max(0,i*4));tops.append(round(float(terrainPoints[j*301+i][1]+upper[row,col]),3))
 metadata['surfaceGuide']={'width':301,'height':301,'heights':tops,'tolerance':3.0,'source':'BVV DOM20 top envelope; maximum 3.5m neighbourhood, compared only in the local survey footprint'}
 mask=(canopy>3)&green&~occupied
 mask=ndimage.binary_closing(mask,iterations=2)&~occupied
 labels,n=ndimage.label(mask)
 counts=np.bincount(labels.ravel());mask&=counts[labels]>=10
 smoothed=ndimage.gaussian_filter(canopy,1.3)
 maxima=(smoothed==ndimage.maximum_filter(smoothed,size=9))&mask&(smoothed>4)
 coords=np.argwhere(maxima);coords=coords[np.argsort(smoothed[tuple(coords.T)])[::-1]]
 chosen=[]
 for row,col in coords:
  value=smoothed[row,col]
  if not any((row-r)**2+(col-c)**2<(max(2.5,min(5.0,value*.23))/resolution)**2 for r,c in chosen):chosen.append((int(row),int(col)))
 centers=np.asarray(chosen);pixels=np.argwhere(mask);_,owner=cKDTree(centers).query(pixels)
 trees=[];preview=Image.fromarray(rgb.astype('uint8'));draw=ImageDraw.Draw(preview)
 for i,(row,col) in enumerate(centers):
  region=pixels[owner==i];region=region[np.linalg.norm(region-[row,col],axis=1)<16]
  if len(region)<12:continue
  delta=(region-[row,col])*resolution
  radius=max(.9,min(7.5,float(np.percentile(np.linalg.norm(delta,axis=1),85))))
  # Low shrubs and spurious slivers do not justify replacing a whole source tree.
  top=float(np.percentile(canopy[region[:,0],region[:,1]],98));top=max(4,min(26,top))
  e=bounds[0]+(col+.5)*resolution;north=bounds[3]-(row+.5)*resolution
  if any(p.contains(Point(e,north)) for p in footprints):continue
  base=mc(np.array([(e,north,height(e,north))]))[0]
  trees.append({'center':base.tolist(),'height':round(top,3),'radius':round(radius,3),'utm':[e,north],'shape':'columnar' if top/radius>4.5 else 'broad'})
  draw.ellipse((col-radius*2,row-radius*2,col+radius*2,row+radius*2),outline=(255,220,0),width=1)
 preview.save(out/'vegetation-survey.jpg',quality=94)
 metadata['vegetation']={'source':'BVV DOM20/DGM1/DOP20; algorithmic crowns, reconstructed branches and species appearance','trees':trees}
 leaf=Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_diff_1k.jpg').convert('RGBA')
 alpha=Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_alpha_1k.png').convert('L').resize(leaf.size)
 leaf.putalpha(alpha)
 bark=Image.open(cache/'tree-source/textures/jacaranda_tree_trunk_diff_1k.jpg').resize((512,512)).convert('RGBA')
 # Subtle per-leaf variation is in the photographed atlas; retain it instead of a solid green blob.
 groups={};rng=np.random.default_rng(74821)
 def tube(vertices,a,b,ra,rb,sides=7):
  axis=b-a;axis/=np.linalg.norm(axis);t=np.cross(axis,[0,1,0] if abs(axis[1])<.9 else [1,0,0]);t/=np.linalg.norm(t);v=np.cross(axis,t)
  for j in range(sides):
   angles=[2*math.pi*j/sides,2*math.pi*(j+1)/sides]
   corners=[a+ra*(t*math.cos(angles[0])+v*math.sin(angles[0])),a+ra*(t*math.cos(angles[1])+v*math.sin(angles[1])),b+rb*(t*math.cos(angles[1])+v*math.sin(angles[1])),b+rb*(t*math.cos(angles[0])+v*math.sin(angles[0]))]
   for k in (0,1,2,0,2,3):vertices.append([*corners[k],*[[(j/sides),1],[(j+1)/sides,1],[(j+1)/sides,0],[j/sides,0]][k]])
 for tree in trees:
  base=np.array(tree['center']);H=tree['height'];R=tree['radius'];key=(int((tree['utm'][0]-bounds[0])//100),int((tree['utm'][1]-bounds[1])//100));wood,leaves=groups.setdefault(key,([],[]))
  column=tree['shape']=='columnar';cy=H*(.58 if column else .67);ry=H*(.43 if column else .33)
  trunk_top=base+np.array([rng.uniform(-.2,.2),H*.72,rng.uniform(-.2,.2)]);trunk_radius=max(.07,min(.42,H*.016));tube(wood,base,trunk_top,trunk_radius,.045,9)
  # Divergent structural branches remain visible from below the canopy.
  for branch in range(10 if column else 16):
   angle=branch*2.399963;fraction=.34+.58*branch/(10 if column else 16)
   a=base+np.array([0,H*fraction*.82,0]);b=base+np.array([math.cos(angle)*R*.72,H*(.55+.35*rng.random()),math.sin(angle)*R*.72]);tube(wood,a,b,trunk_radius*.43,.016)
  count=int(max(180,min(900,R*R*28)))
  for card in range(count):
   az=rng.uniform(0,2*math.pi);z=rng.uniform(-1,1);rr=rng.uniform(.25,1)**(1/3);ring=math.sqrt(1-z*z)
   center=base+np.array([R*rr*ring*math.cos(az),cy+ry*rr*z,R*rr*ring*math.sin(az)])
   normal=rng.normal(size=3);normal/=np.linalg.norm(normal);right=np.cross(normal,[0,1,0] if abs(normal[1])<.9 else [1,0,0]);right/=np.linalg.norm(right);up=np.cross(normal,right)
   size=rng.uniform(.65,1.15)*max(.7,min(1.4,R*.3));right*=size;up*=size*.7
   corners=[center-right-up,center+right-up,center+right+up,center-right+up]
   # Three photographed branch sprigs, in their own non-overlapping atlas rectangles.
   u0,v0,u1,v1=[(0,.0,1,.53),(0,.34,.43,.73),(.18,.60,1,1)][card%3];uv=[(u0,v1),(u1,v1),(u1,v0),(u0,v0)]
   for k in (0,1,2,0,2,3):leaves.append([*corners[k],*uv[k]])
  # The matching source vegetation is removed only inside a crown footprint,
  # subtracting nearby surveyed building walls to prevent collateral clipping.
  centerUtm=Point(*tree['utm']);area=centerUtm.buffer(R+1.2,resolution=10)
  for p in footprints:
   if p.intersects(area):area=area.difference(p)
  shapes=[area] if area.geom_type=='Polygon' else list(getattr(area,'geoms',[]))
  for shape in shapes:
   if shape.geom_type!='Polygon' or shape.area<1:continue
   coords=np.asarray(shape.exterior.coords);ring=mc(np.column_stack((coords,np.full(len(coords),height(*tree['utm'])))))[:,[0,2]]
   holes=[]
   for hole in shape.interiors:
    coords=np.asarray(hole.coords);holes.append(mc(np.column_stack((coords,np.full(len(coords),height(*tree['utm'])))))[:,[0,2]].tolist())
   metadata['replacements'].append({'ring':ring.tolist(),'holes':holes,'y0':float(base[1])-1,'y1':float(base[1])+H+4,'kind':'vegetation'})
 for i,(key,(wood,leaves)) in enumerate(sorted(groups.items())):
  q=np.asarray(wood+leaves)[:,:3];name=f'vegetation-{key[0]}-{key[1]}.ect';(out/name).write_bytes(encode([(wood,bark),(leaves,leaf)]));metadata['tiles'].append({'file':name,'bounds':[q.min(axis=0).tolist(),q.max(axis=0).tolist()],'kind':'vegetation','runtimeId':1_000_010_000+i})
 print('Vegetation:',len(trees),'survey-informed trees in',len(groups),'groups',flush=True)

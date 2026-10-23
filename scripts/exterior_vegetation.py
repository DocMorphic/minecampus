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
from shapely.geometry import Polygon,Point,MultiPoint
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
 # The survey contains brown autumn crowns as well as green trees. Requiring
 # height above surveyed roofs below prevents brown roof materials becoming
 # canopy; the tree-placement pass also excludes building footprints.
 red,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
 autumn=(red>g*1.04)&(red<g*1.5)&(g>b*1.08)&(g<b*1.7)&(g>35)&(g<175)
 foliage=green|autumn
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
 # Detect photographed foliage overhanging low roofs and footprint buffers.
 # Keep the actual building below the surveyed roof ceiling, while allowing the
 # old scan canopy above it to be retired alongside the reconstructed trees.
 roofShapes=[]
 for bid,surfaces in buildings:
  for typ,rings in surfaces:
   if typ!='RoofSurface':continue
   shape=Polygon(rings[0][:,:2],[r[:,:2]for r in rings[1:]])
   if not shape.is_valid:shape=shape.buffer(0)
   if not shape.is_empty and shape.area>.01:roofShapes.append((shape,float(max(r[:,2].max()for r in rings))))
 roofElevation=rasterize(sorted(roofShapes,key=lambda x:x[1]),out_shape=(h,w),transform=transform,dtype='float32')
 roofElevation=np.maximum(roofElevation,dem)
 # Shadowed crowns can have nearly equal green/blue channels. This broader
 # colour test extends crown fitting but does not add trunk candidates.
 shadedFoliage=(g>red*1.05)&(g>=b)&(g>35)&(g<175)
 # Fit the foliage separately from the trunk candidates. A crown can extend
 # over a raised terrace, where height above the local ground is much lower
 # than height above its trunk. Only components attached to a tree seed below
 # will be retained, so this does not turn isolated terrace objects into trees.
 crownMask=ndimage.binary_closing((foliage|shadedFoliage)&(dom-roofElevation>1.5),iterations=1)
 ceiling=ndimage.maximum_filter(roofElevation-dem,size=7)
 roofCeilings=[]
 for j in range(301):
  row=min(1199,max(0,1199-j*4))
  for i in range(301):
   col=min(1199,max(0,i*4));roofCeilings.append(round(float(terrainPoints[j*301+i][1]+ceiling[row,col]),3))
 metadata['vegetationOverhang']={'width':301,'height':301,'roofCeilings':roofCeilings}

 mask=(canopy>3)&foliage&~occupied
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
 centers=np.asarray(chosen)
 crownLabels,_=ndimage.label(crownMask|mask)
 pixels=np.argwhere(crownMask|mask);pixelLabels=crownLabels[tuple(pixels.T)]
 seedLabels=crownLabels[tuple(centers.T)];owner=np.full(len(pixels),-1,dtype=int)
 for label in np.unique(seedLabels):
  if not label:continue
  seeds=np.flatnonzero(seedLabels==label);members=np.flatnonzero(pixelLabels==label)
  distance,nearest=cKDTree(centers[seeds]).query(pixels[members])
  nearby=distance<28 # 14m maximum; the old 8m cap amputated terrace overhangs.
  owner[members[nearby]]=seeds[nearest[nearby]]
 supported=np.zeros((h,w),bool)
 crownRegions=[]
 trees=[];preview=Image.fromarray(rgb.astype('uint8'));draw=ImageDraw.Draw(preview)
 for i,(row,col) in enumerate(centers):
  region=pixels[owner==i]
  if len(region)<12:continue
  delta=(region-[row,col])*resolution
  radius=max(.9,min(7.5,float(np.percentile(np.linalg.norm(delta,axis=1),85))))
  # Low shrubs and spurious slivers do not justify replacing a whole source tree.
  top=float(np.percentile(canopy[region[:,0],region[:,1]],98));top=max(4,min(26,top))
  e=bounds[0]+(col+.5)*resolution;north=bounds[3]-(row+.5)*resolution
  if any(p.contains(Point(e,north)) for p in footprints):continue
  base=mc(np.array([(e,north,height(e,north))]))[0]
  east=bounds[0]+(region[:,1]+.5)*resolution;norths=bounds[3]-(region[:,0]+.5)*resolution
  crown=mc(np.column_stack((east,norths,dom[tuple(region.T)])))
  floor=mc(np.column_stack((east,norths,roofElevation[tuple(region.T)])))[:,1]
  # DOM measures the upper surface, not a filled column down to the terrain.
  # A tree's tapered lower crown must stay above the exposed trunk. Low pixels
  # beneath that envelope may be a separate shrub; do not fit them as crown.
  lower=max(1.5,top*.36)
  valid=(crown[:,1]>base[1]+lower+.5)&(crown[:,1]>floor+1.5)
  if np.count_nonzero(valid)<12:continue
  region=region[valid];crown=crown[valid];floor=floor[valid];east=east[valid];norths=norths[valid]
  supported[tuple(region.T)]=True
  crownRegions.append((crown,floor,np.column_stack((east,norths))))
  trees.append({'center':base.tolist(),'height':round(top,3),'radius':round(radius,3),'utm':[e,north],'shape':'columnar' if top/radius>4.5 else 'broad','crownCenter':np.mean(crown,axis=0).round(3).tolist(),'crownBounds':[crown.min(axis=0).round(3).tolist(),crown.max(axis=0).round(3).tolist()],'crownArea':round(len(region)*resolution**2,2)})
  draw.ellipse((col-radius*2,row-radius*2,col+radius*2,row+radius*2),outline=(255,220,0),width=1)
 preview.save(out/'vegetation-survey.jpg',quality=94)
 # Cover each 2m guide cell before downsampling the 0.5m mask. Retire only
 # foliage belonging to a crown actually emitted above.
 overhang=ndimage.maximum_filter(supported&(dom-roofElevation>1.5),size=5)
 metadata['vegetationOverhang']['mask']=base64.b64encode(bytes(int(overhang[min(1199,max(0,1199-j*4)),min(1199,i*4)])for j in range(301)for i in range(301))).decode()
 metadata['vegetationOverhang']['source']='BVV DOP20/DOM20 foliage connected to surveyed tree candidates, at least 1.5m above the LoD2 roof or terrain; conservative local roof maximum'
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
 for tree,(crown,crownFloor,crownUtm) in zip(trees,crownRegions):
  base=np.array(tree['center']);H=tree['height'];R=tree['radius'];key=(int((tree['utm'][0]-bounds[0])//100),int((tree['utm'][1]-bounds[1])//100));wood,leaves=groups.setdefault(key,([],[]))
  column=tree['shape']=='columnar'
  trunk_top=base+np.array([rng.uniform(-.2,.2),H*.72,rng.uniform(-.2,.2)]);trunk_radius=max(.07,min(.42,H*.016));tube(wood,base,trunk_top,trunk_radius,.045,9)
  # Divergent structural branches remain visible from below the canopy.
  branchTargets=np.flatnonzero(crown[:,1]>base[1]+H*.65)
  for branch in range(10 if column else 16):
   if not len(branchTargets):break
   fraction=.42+.22*branch/(10 if column else 16)
   target=int(rng.choice(branchTargets));b=crown[target].copy()
   b[[0,2]]=base[[0,2]]+(b[[0,2]]-base[[0,2]])*.72
   a=base+np.array([0,H*fraction,0]);b[1]=max(a[1]+.3,crownFloor[target]+.8,b[1]-H*.12)
   # Keep branches on the trunk side of any raised roof/terrace. The foliage
   # may overhang it, but an inferred branch must not pierce the structure.
   if crownFloor[target]>a[1]-.8:continue
   tube(wood,a,b,trunk_radius*.43,.016)
  count=int(max(180,min(1200,tree['crownArea']*7)))
  for card in range(count):
   sample=int(rng.integers(len(crown)));center=crown[sample].copy()
   center[[0,2]]+=rng.uniform(-.23,.23,2)
   depth=max(.11,center[1]-max(crownFloor[sample]+.8,base[1]+max(1.5,H*.36)))
   center[1]-=rng.uniform(.1,max(.11,depth))
   normal=rng.normal(size=3);normal/=np.linalg.norm(normal);right=np.cross(normal,[0,1,0] if abs(normal[1])<.9 else [1,0,0]);right/=np.linalg.norm(right);up=np.cross(normal,right)
   size=rng.uniform(.65,1.15)*max(.7,min(1.4,R*.3));right*=size;up*=size*.7
   corners=[center-right-up,center+right-up,center+right+up,center-right+up]
   # Three photographed branch sprigs, in their own non-overlapping atlas rectangles.
   u0,v0,u1,v1=[(0,.0,1,.53),(0,.34,.43,.73),(.18,.60,1,1)][card%3];uv=[(u0,v1),(u1,v1),(u1,v0),(u0,v0)]
   for k in (0,1,2,0,2,3):leaves.append([*corners[k],*uv[k]])
  # The matching source vegetation is removed only inside a crown footprint,
  # subtracting nearby surveyed building walls to prevent collateral clipping.
  area=MultiPoint(crownUtm).convex_hull.buffer(1.2,resolution=10)
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

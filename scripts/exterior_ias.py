"""IAS exterior: surveyed envelope with reference-informed recesses and folding screens."""
import json, hashlib, math
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
import mapbox_earcut

BUILDING='DEBY_LOD2_8486677'

def build(ctx):
 root,out,meta,mc,encode,triangulate,photo_uv,photo,w,h,buildings=[ctx[k] for k in ['ROOT','OUT','metadata','mc','encode','triangulate','photo_uv','photo','w','h','buildings']]
 surfaces=next(s for bid,s in buildings if bid==BUILDING)
 source=root/'minecraft/exterior/photos/ias.jpg';info=json.loads(source.with_suffix('.json').read_text())
 assert hashlib.sha256(source.read_bytes()).hexdigest()==info['sha256']
 image=Image.open(source).convert('RGBA');scale=image.width/1930
 def crop(rect,size):return image.crop(tuple(round(v*scale) for v in rect)).resize(size,Image.Resampling.LANCZOS)
 metal=crop((750,493,771,510),(128,128));glass=crop((1043,517,1062,537),(128,128));atriumTexture=crop((836,489,954,584),(256,256))
 dark=Image.new('RGBA',(1,1),(91,99,103,255))
 clad=[];windows=[];frames=[];roof=[];atrium=[]
 ground=[mc(r[0])for t,r in surfaces if t=='GroundSurface'];footprint=unary_union([Polygon(q[:,[0,2]]) for q in ground])
 base=min(q[:,1].min()for q in ground);terrace=base+3.95;first=base+7.8;roofline=base+19.1
 # The long surveyed south wall establishes the building's local east/north axes.
 origin=np.array([57.1072535,base,-205.515]);east=np.array([.9845,0,.1754]);east/=np.linalg.norm(east);north=np.array([east[2],0,-east[0]])
 def pt(x,y,z):
  p=origin+east*x+north*z;p[1]=y;return p
 def quad(points,target,uv=None):
  uv=uv or [(0,1),(1,1),(1,0),(0,0)]
  for i in [0,1,2,0,2,3]:target.append([*points[i],*uv[i]])
 def cuboid(x0,y0,z0,x1,y1,z1,target):
  p=[pt(x,y,z)for z in [z0,z1]for y in [y0,y1]for x in [x0,x1]]
  for face in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]:quad([p[i]for i in face],target)
 def emit(poly,anchor,direction,normal,depth,target,uvrect=None):
  for shape in [poly]if poly.geom_type=='Polygon'else list(getattr(poly,'geoms',[])):
   if shape.geom_type!='Polygon' or shape.area<1e-6:continue
   rings=[np.asarray(shape.exterior.coords[:-1])]+[np.asarray(r.coords[:-1])for r in shape.interiors]
   xy=np.concatenate(rings);indices=mapbox_earcut.triangulate_float64(xy,np.cumsum([len(r)for r in rings]).astype(np.uint32))
   l,b,r,t=uvrect or shape.bounds
   for i in indices:
    x,y=xy[i];p=anchor+direction*x-normal*depth;p[1]=y
    target.append([*p,np.clip((x-l)/max(r-l,.01),0,1),np.clip(1-(y-b)/max(t-b,.01),0,1)])
 def returns(poly,anchor,direction,normal,depth):
  for shape in [poly]if poly.geom_type=='Polygon'else list(getattr(poly,'geoms',[])):
   if shape.geom_type!='Polygon':continue
   ring=np.asarray(shape.exterior.coords[:-1])
   for j in range(len(ring)):
    points=[]
    for k,d in [(j,0),((j+1)%len(ring),0),((j+1)%len(ring),depth),(j,depth)]:
     x,y=ring[k];p=anchor+direction*x-normal*d;p[1]=y;points.append(p)
    quad(points,frames)
 for typ,rings in surfaces:
  p,q,indices=triangulate(rings)
  if typ=='GroundSurface':continue
  if typ=='RoofSurface':
   uv=photo_uv(p);roof.extend([*q[i],*uv[i]]for tri in indices for i in tri);continue
  anchor=q[0].copy();delta=next((p-anchor for p in q if np.linalg.norm((p-anchor)[[0,2]])>.1),None)
  if delta is None:continue
  direction=np.array([delta[0],0,delta[2]]);direction/=np.linalg.norm(direction)
  poly=Polygon(np.column_stack(((q-anchor)@direction,q[:,1]))).buffer(0)
  if poly.geom_type!='Polygon':continue
  l,b,r,t=poly.bounds;normal=np.array([-direction[2],0,direction[0]])
  if footprint.contains(Point((q.mean(axis=0)+normal*.3)[[0,2]])):normal=-normal
  south=normal@(-north)>.8 and r-l>30
  body=poly.intersection(box(l,first,r,roofline))
  openings=[]
  if south:
   # The south atrium is the large recessed opening visible from the promenade.
   def along(x):return float((pt(x,base,0)-anchor)@direction)
   a,c=sorted([along(9),along(22)]);openings.append(box(a,first+1.0,c,roofline-.7))
   a,c=sorted([along(24),along(38.5)])
   for y in [first+1,first+4.8,first+8.6]:openings.append(box(a,y,c,min(y+2.15,roofline-.2)))
  else:
   for y in [first+.7,first+4.5,first+8.3]:
    for x in np.arange(l+.35,r,1.65):openings.append(box(x,y,min(x+1.4,r-.2),min(y+2.7,roofline-.2)))
  opening=unary_union(openings);glazing=body.intersection(opening)
  # Panel joints are geometry, with photographic metal detail inside each panel.
  solid=body.difference(opening)
  for x in np.arange(math.floor(l/1.65)*1.65,r,1.65):
   for y in np.arange(first,roofline,1.9):emit(solid.intersection(box(x+.025,y+.025,x+1.625,y+1.875)),anchor,direction,normal,0,clad,(x,y,x+1.65,y+1.9))
  emit(solid,anchor,direction,normal,.04,frames)
  if south:
   centre=body.intersection(openings[0]);emit(centre,anchor,direction,normal,1.25,atrium)
   regular=glazing.difference(openings[0])
  else:regular=glazing
  for x in np.arange(l,r,1.65):
   emit(regular.intersection(box(x+.045,b,x+1.605,t)),anchor,direction,normal,.24,windows)
  returns(glazing,anchor,direction,normal,1.25 if south else .24)
  # Thin real mullions in the glass entrance floor and set-back rooftop club.
  for low,high,inset in [(terrace,first,1.1),(roofline,t,.25)]:
   for x in np.arange(l,r,1.65):
    pane=poly.intersection(box(x+.055,low+.12,min(x+1.595,r),high-.12))
    emit(pane,anchor,direction,normal,inset,windows);returns(pane,anchor,direction,normal,inset)
  emit(poly.intersection(box(l,base,r,terrace)),anchor,direction,normal,0,clad)
  # Selected folded sunscreen leaves on side elevations: same modular spacing,
  # alternating open/closed panels, not a flat printed window pattern.
  if not south and r-l>10 and b<first:
   for floor,y in enumerate([first+.7,first+4.5,first+8.3]):
    for i,x in enumerate(np.arange(l+.35,r-1.4,1.65)):
     if (i+floor)%4!=1:continue
     edge=anchor+direction*x+normal*.04;edge[1]=y
     tip=edge+direction*.70+normal*.75
     quad([edge,tip,tip+np.array([0,2.65,0]),edge+np.array([0,2.65,0])],clad)
 # Broad raised terrace and the central stair to the promenade, in local axes.
 cuboid(0,terrace-.3,-3.1,39,terrace,0,clad)
 for i in range(10):
  top=terrace-(9-i)*.18;z=-7.1+i*.4
  cuboid(9,top-.18,z,22,top,z+.4,clad)
 # Slender terrace balustrades and handrails (no interior geometry).
 for x in [0.2,38.8]:
  for z in np.arange(-3,0,.9):cuboid(x-.025,terrace,z-.025,x+.025,terrace+1.05,z+.025,frames)
  cuboid(x-.035,terrace+1.02,-3.05,x+.035,terrace+1.08,0,frames)
 # Slim projecting sunshade above the rooftop club, as in the south reference.
 top=max(mc(r[0])[:,1].max()for typ,r in surfaces if typ=='RoofSurface')
 for x in np.arange(-.6,31.8,1.65):cuboid(x,top,-1.0,x+.075,top+.12,13.5,frames)
 for z in [-1,3.8,8.5,13.5]:cuboid(-.6,top,z,31.8,top+.12,z+.08,frames)
 # Retain the surveyed roof's silhouette and actual orthophoto coordinates.
 roof=np.asarray(roof);uv=roof[:,3:5];lo=np.maximum(0,np.floor(uv.min(axis=0)*[w,h]).astype(int)-2);hi=np.minimum([w,h],np.ceil(uv.max(axis=0)*[w,h]).astype(int)+2)
 roof[:,3:5]=(uv*[w,h]-lo)/(hi-lo)
 parts=[(clad,metal),(windows,glass),(frames,dark),(roof,photo.crop((*lo,*hi))),(atrium,atriumTexture)]
 points=np.concatenate([np.asarray(v)[:,:3]for v,t in parts]);name=BUILDING+'-ias.ect';(out/name).write_bytes(encode(parts))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'ias','runtimeId':1_000_030_004,'bounds':[points.min(axis=0).tolist(),points.max(axis=0).tolist()]})
 area=unary_union([footprint,Polygon([pt(x,base,z)[[0,2]]for x,z in [(0,-7.3),(39,-7.3),(39,0),(0,0)]])]).buffer(2.5)
 meta['replacements'].append({'ring':list(area.exterior.coords),'holes':[],'y0':float(base)-2,'y1':float(points[:,1].max())+8,'kind':'architecture'})
 meta['architecture']['buildings'].append(BUILDING)
 meta['architecture']['ias']={'source':info['source'],'license':info['license'],'reference':'https://fritsch-tschaidse.de/en/projects/tu-munich-institute-for-advanced-study.html','note':'BVV envelope, photographic material, reconstructed panel/opening/stair dimensions.'}
 meta['attribution']+='; IAS: High Contrast (CC BY 3.0 DE)'
 print('IAS: surveyed envelope, recessed atrium, folding screens and entrance terrace',flush=True)

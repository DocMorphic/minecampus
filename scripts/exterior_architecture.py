"""Detailed MW envelopes from BVV LoD2; reconstructed façade modules from site photos.
These measured roof and wall shapes are not generic building-box extrusions.
Window/louvre repetition is an architectural reconstruction, not an as-built survey.
"""
import json,math,hashlib
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box,Point,LineString
from shapely.ops import unary_union
import mapbox_earcut

def build(ctx):
 root,out,metadata,mc,encode,triangulate,photo_uv,photo,w,h,buildings=[ctx[k] for k in ['ROOT','OUT','metadata','mc','encode','triangulate','photo_uv','photo','w','h','buildings']]
 source=root/'minecraft/exterior/photos/mw-northeast.jpg'
 info=json.loads(source.with_suffix('.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==info['sha256']
 concrete=Image.open(source).crop((345,390,760,450)).resize((512,128)).convert('RGBA')
 steel=Image.new('RGBA',(1,1),(172,180,183,255));glass=Image.open(source).crop((466,590,550,735)).resize((256,512)).convert('RGBA')
 chosen={'DEBY_LOD2_62017':1_000_030_000,'DEBY_LOD2_5284427':1_000_030_001,'DEBY_LOD2_5284428':1_000_030_002,'DEBY_LOD2_8486675':1_000_030_003}
 for bid,surfaces in buildings:
  if bid not in chosen:continue
  grounds=[(p,mc(p)) for typ,rings in surfaces if typ=='GroundSurface' for p in [rings[0]]]
  footprint=unary_union([Polygon(q[:,[0,2]]) for p,q in grounds]);base=min(q[:,1].min() for p,q in grounds)
  gradschool=bid=='DEBY_LOD2_8486675'
  clad=[];windows=[];frames=[];roofs=[];allq=[];bands=[]
  def emit(poly,anchor,direction,normal,depth,target,uvOrigin=(0,0),scale=(2,3.7)):
   for shape in [poly] if poly.geom_type=='Polygon' else list(getattr(poly,'geoms',[])):
    if shape.geom_type!='Polygon' or shape.area<.0001:continue
    rings=[np.asarray(shape.exterior.coords[:-1])]+[np.asarray(r.coords[:-1]) for r in shape.interiors]
    xy=np.concatenate(rings);idx=mapbox_earcut.triangulate_float64(xy,np.cumsum([len(r) for r in rings]).astype(np.uint32))
    for i in idx:
     x,y=xy[i];q=anchor+direction*x-normal*depth;q[1]=y;target.append([*q,max(0,min(1,(x-uvOrigin[0])/scale[0])),max(0,min(1,1-(y-uvOrigin[1])/scale[1]))])
  def beam(line,anchor,direction,normal,target=None,u=0):
   target=frames if target is None else target
   for shape in [line] if line.geom_type=='LineString' else list(getattr(line,'geoms',[])):
    if shape.geom_type!='LineString' or shape.length<.1:continue
    xy=np.asarray(shape.coords)
    for i in range(len(xy)-1):
     a=anchor+direction*xy[i,0];a[1]=xy[i,1]
     b=anchor+direction*xy[i+1,0];b[1]=xy[i+1,1]
     axis=b-a
     if np.linalg.norm(axis)<.05:continue
     axis/=np.linalg.norm(axis);side=np.cross(axis,normal);side/=np.linalg.norm(side)
     v=[a-side*.065-normal*.065,a+side*.065-normal*.065,a+side*.065+normal*.065,a-side*.065+normal*.065,b-side*.065-normal*.065,b+side*.065-normal*.065,b+side*.065+normal*.065,b-side*.065+normal*.065]
     for quad in [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]:
      target.extend([*v[quad[k]],u,.5]for k in [0,1,2,0,2,3])
  for typ,rings in surfaces:
   p,q,indices=triangulate(rings);allq.extend(q.tolist())
   if typ=='GroundSurface':continue
   if typ=='RoofSurface':
    uv=photo_uv(p)
    if bid=='DEBY_LOD2_62017':
     zone=box(-55,-70,1000,1000);cap=base+13.5
     for triangle in indices:
      xyz=q[triangle];coords=xyz[:,[0,2]];outline=Polygon(coords)
      if outline.area<1e-7:continue
      pieces=[(outline.difference(zone),False),(outline.intersection(zone),True)]
      matrix=np.vstack([coords.T,np.ones(3)])
      for piece,lower in pieces:
       for shape in [piece] if piece.geom_type=='Polygon' else list(getattr(piece,'geoms',[])):
        if shape.geom_type!='Polygon' or shape.area<1e-6:continue
        rings2=[np.asarray(shape.exterior.coords[:-1])]+[np.asarray(r.coords[:-1])for r in shape.interiors]
        vertices=np.concatenate(rings2);flat=mapbox_earcut.triangulate_float64(vertices,np.cumsum([len(r)for r in rings2]).astype(np.uint32))
        for index in flat:
         x,z=vertices[index];weights=np.linalg.solve(matrix,[x,z,1]);y=float(weights@xyz[:,1]);tex=weights@uv[triangle]
         if lower:y=min(y,cap)
         roofs.append([x,y,z,*tex])
    else:roofs.extend([[*q[i],*uv[i]] for t in indices for i in t])
    continue
   if typ!='WallSurface':continue
   anchor=q[0];delta=next((p-anchor for p in q if np.linalg.norm((p-anchor)[[0,2]])>.1),None)
   if delta is None:continue
   direction=np.array([delta[0],0,delta[2]]);direction/=np.linalg.norm(direction);along=(q-anchor)@direction
   poly=Polygon(np.column_stack((along,q[:,1])))
   if not poly.is_valid:poly=poly.buffer(0)
   if poly.geom_type!='Polygon':continue
   left,bottom,right,top=poly.bounds;normal=np.array([-direction[2],0,direction[0]]);mid=q.mean(axis=0)
   if footprint.contains(Point((mid+normal*.3)[[0,2]])):normal=-normal
   curved=bid=='DEBY_LOD2_62017' and mid[0]>-55 and mid[2]>-70
   spacing=2.6 if curved else 1.5;floorHeight=3.7
   if curved:
    # The MW auditorium has a tall glazed ground storey, a white upper drum
    # and a separate open steel canopy. LoD2 closes that open volume; do not
    # turn it into an invented five-storey office façade.
    cap=base+13.5
    body=poly.intersection(box(left,base,right,cap))
    openings=[]
    for x in np.arange(math.floor(left/spacing)*spacing,right,spacing):
     openings.extend([box(x+.12,base+.25,x+spacing-.12,base+7.8),box(x+.72,base+8.9,x+spacing-.72,base+11.5)])
    opening=unary_union(openings)
    emit(body.difference(opening),anchor,direction,normal,0,clad,(left,base),(max(1,right-left),13.5))
    glazing=body.intersection(opening);emit(glazing,anchor,direction,normal,.16,windows,(left,base),(max(1,right-left),13.5))
    continue
   # Clip each façade module to the actual survey wall, including gables and curves.
   for x0 in np.arange(math.floor(left/spacing)*spacing,right,spacing):
    for y0 in np.arange(base,top,floorHeight):
     cell=poly.intersection(box(x0,y0,x0+spacing,y0+floorHeight))
     if cell.is_empty:continue
     sill=.55 if y0<base+.1 else .85
     window=box(x0+.13,y0+sill,x0+spacing-.13,y0+floorHeight-.25)
     if curved and y0>base+7.4:window=box(x0+.35,y0+.7,x0+spacing-.35,y0+2.9)
     glazing=cell.intersection(window);opaque=cell.difference(window)
     emit(opaque,anchor,direction,normal,0,clad,(x0,y0),(spacing,floorHeight))
     emit(glazing,anchor,direction,normal,.16,windows,(x0,y0),(spacing,floorHeight))
     # Inset returns around each opening give windows actual depth.
     for shape in [glazing] if glazing.geom_type=='Polygon' else list(getattr(glazing,'geoms',[])):
      if shape.geom_type!='Polygon':continue
      ring=np.asarray(shape.exterior.coords[:-1]);
      for j in range(len(ring)):
       verts=[]
       for k,depth in [(j,0),((j+1)%len(ring),0),((j+1)%len(ring),.16),(j,.16)]:
        x,y=ring[k];v=anchor+direction*x-normal*depth;v[1]=y;verts.append([*v,0,0])
       frames.extend(verts[k] for k in [0,1,2,0,2,3])
   if gradschool and (normal[0]>.5 or normal[2]>.5):
    for level in range(1,4):
     y0=base+level*3.7;strip=poly.intersection(box(left,y0,right,y0+.9))
     for shape in [strip] if strip.geom_type=='Polygon' else list(getattr(strip,'geoms',[])):
      if shape.geom_type!='Polygon' or shape.is_empty:continue
      lo,bottomBand,hi,topBand=shape.bounds
      # A measured wall envelope, with a reconstructed projecting metal band.
      middle=(lo+hi)*.5
      for a,b,colorIndex in [(lo,middle,1 if level==1 else (3 if level==3 else 0)),(middle,hi,level-1)]:
       corners=[]
       for depth in [0,.6]:
        for x,y in [(a,bottomBand),(b,bottomBand),(b,topBand),(a,topBand)]:
         point=anchor+direction*x+normal*depth;point[1]=y;corners.append(point)
       u=(colorIndex+.5)/4
       for face in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:bands.extend([*corners[face[k]],u,.5]for k in [0,1,2,0,2,3])
    for x in np.arange(left,right,3):beam(LineString([(x,base+3.5),(x,top)]),anchor+normal*.6,direction,normal,bands,.375)
   # Thin, projected horizontal shading fins, clipped to long straight façades.
   if not curved and not gradschool and right-left>6:
    for y in np.arange(base+3.0,top-.25,3.7):
     for rise in [0,.17,.34]:
      y1=y+rise
      section=poly.intersection(box(left,y1,right,y1+.045))
      for shape in [section] if section.geom_type=='Polygon' else list(getattr(section,'geoms',[])):
       if shape.geom_type!='Polygon' or shape.is_empty or shape.area<1e-8:continue
       lo,_,hi,_=shape.bounds
       corners=[]
       for x,depth in [(lo,-.3),(hi,-.3),(hi,.04),(lo,.04)]:
        v=anchor+direction*x-normal*depth;v[1]=y1;corners.append([*v,0,0])
       frames.extend(corners[k] for k in [0,1,2,0,2,3])
  palette=Image.new('RGBA',(4,1));palette.putdata([(224,164,20,255),(185,32,36,255),(215,220,220,255),(30,34,36,255)])
  metal=Image.new('RGBA',(128,128),(139,25,28,255))
  if gradschool:
   from PIL import ImageDraw
   draw=ImageDraw.Draw(metal)
   for x in range(0,128,8):draw.rectangle((x,0,x+1,127),fill=(82,16,19,255));draw.line((x+2,0,x+2,127),fill=(170,45,44,255))
  parts=[(clad,metal if gradschool else concrete),(windows,glass),(frames,steel)]
  if roofs:
   roof=np.asarray(roofs);uv=roof[:,3:5];low=np.maximum(0,np.floor(uv.min(axis=0)*[w,h]).astype(int)-2);high=np.minimum([w,h],np.ceil(uv.max(axis=0)*[w,h]).astype(int)+2)
   roof[:,3:5]=(uv*[w,h]-low)/(high-low);parts.append((roof,photo.crop((*low,*high))))
  if bands:parts.append((bands,palette))
  points=np.concatenate([np.asarray(v)[:,:3]for v,t in parts if len(v)])
  name=bid+'-facade.ect';(out/name).write_bytes(encode(parts));metadata['tiles'].append({'file':name,'kind':'reconstruction','profile':'gradschool' if gradschool else 'mw','runtimeId':chosen[bid],'bounds':[points.min(axis=0).tolist(),points.max(axis=0).tolist()]})
  # Canopies extend beyond the ground/wall outline. Include every measured
  # roof projection in source retirement, or detached corners survive outside
  # the façade replacement despite the new roof already covering that area.
  roofAreas=[]
  for typ,rings in surfaces:
   if typ!='RoofSurface':continue
   q=mc(rings[0]);shape=Polygon(q[:,[0,2]])
   if not shape.is_valid:shape=shape.buffer(0)
   if not shape.is_empty and shape.area>.01:roofAreas.append(shape)
  area=unary_union([footprint,*roofAreas]).buffer(4.0)
  for shape in [area] if area.geom_type=='Polygon' else list(getattr(area,'geoms',[])):
   if shape.geom_type!='Polygon':continue
   metadata['replacements'].append({'ring':list(shape.exterior.coords),'holes':[],'y0':float(points[:,1].min())-2,'y1':float(points[:,1].max())+16,'kind':'architecture'})
  # Retiring only the wall outline can leave detached pieces of the old photo
  # canopy just beyond the LoD2 envelope. Remove the high source fringe around
  # the reconstructed component; leave lower neighbouring building façades.
  fringe=footprint.buffer(20)
  for shape in [fringe] if fringe.geom_type=='Polygon' else list(getattr(fringe,'geoms',[])):
   if shape.geom_type=='Polygon':metadata['replacements'].append({'ring':list(shape.exterior.coords),'holes':[],'y0':0.0,'y1':float(points[:,1].max())+25,'kind':'architecture-fringe'})

 metadata['architecture']={'buildings':list(chosen),'source':'BVV LoD2 + architectural reconstruction of repeated windows/reveals/louvres; MW concrete material from Renardo la vulpo (CC BY-SA 4.0)','materialLicense':'CC BY-SA 4.0','photoSource':info['source']}
 print('Campus architecture:',len(chosen),'surveyed components with inset glazing and shading fins',flush=True)

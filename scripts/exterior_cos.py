"""COS exterior: surveyed 5132 envelope, licensed timber reference, no interiors."""
import hashlib,json,math,struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
import mapbox_earcut

BUILDING='DEBY_LOD2_108698313'

def build(ctx,bid,walls):
 if bid!=BUILDING:return
 root,out,meta,encode=[ctx[k]for k in ['ROOT','OUT','metadata','encode']]
 reference=json.loads((root/'minecraft/exterior/photos/cos-reference.json').read_text())
 photo=root/'minecraft/exterior/photos/cos-reference.webp'
 assert hashlib.sha256(photo.read_bytes()).hexdigest()==reference['sha256']
 # A clean, unobstructed timber patch. Quad order is TL, BL, BR, TR.
 timber=Image.open(photo).convert('RGBA').transform((384,256),Image.Transform.QUAD,reference['timberQuad'],Image.Resampling.BICUBIC)
 textures=[timber,Image.new('RGBA',(1,1),(54,85,103,255)),Image.new('RGBA',(1,1),(31,40,44,255)),Image.new('RGBA',(1,1),(161,170,175,255))]
 parts=[[]for _ in textures];evidence=[];base=min(w['bounds'][0][1]for w in walls);metalBase=base+18.05
 def pt(x,y,z=0):
  p=anchor+direction*x+normal*z;p[1]=y;return p
 def quad(points,part):
  for i in [0,1,2,0,2,3]:parts[part].append([*points[i],*[(0,1),(1,1),(1,0),(0,0)][i]])
 def block(x0,y0,z0,x1,y1,z1,part):
  p=[pt(x,y,z)for z in [z0,z1]for y in [y0,y1]for x in [x0,x1]]
  for face in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]:quad([p[i]for i in face],part)
 def surface(shape,part):
  if shape.is_empty:return
  # Explicit UV tiles remain in [0,1], independent of sampler wrap mode.
  for x0 in np.arange(math.floor(shape.bounds[0]/2.4)*2.4,shape.bounds[2],2.4):
   for y0 in np.arange(math.floor(shape.bounds[1]/2)*2,shape.bounds[3],2):
    cut=shape.intersection(box(x0,y0,x0+2.4,y0+2))
    for p in ([cut]if cut.geom_type=='Polygon'else getattr(cut,'geoms',[])):
     if p.geom_type!='Polygon' or p.area<1e-7:continue
     rings=[np.asarray(p.exterior.coords[:-1])]+[np.asarray(h.coords[:-1])for h in p.interiors];xy=np.concatenate(rings)
     for i in mapbox_earcut.triangulate_float64(xy,np.cumsum([len(r)for r in rings]).astype(np.uint32)):
      x,y=xy[i];parts[part].append([*pt(x,y),float(np.clip((x-x0)/2.4,0,1)),float(np.clip(1-(y-y0)/2,0,1))])
 # South's three survey sections form one elevation, with the roof step retained.
 groups=[([7],'west'),([8,11,16],'south')]+[([i],'inferred')for i in range(len(walls))if i not in [7,8,11,16]]
 for indices,kind in groups:
  if kind=='south':
   anchor=np.asarray(walls[7]['anchor']);direction=np.array([.984,.0,.178]);direction/=np.linalg.norm(direction);normal=np.array([-direction[2],0,direction[0]])
  else:anchor,direction,normal=[np.asarray(walls[indices[0]][k])for k in ['anchor','direction','normal']]
  polys=[]
  for i in indices:
   v=np.asarray(walls[i]['vertices']);assert np.max(np.abs((v-anchor)@normal))<.02
   polys.append(Polygon(np.column_stack(((v-anchor)@direction,v[:,1]))).buffer(0));walls[i]['reconstructed']=True
  # Sub-millimetre survey seams must not split a facade window.
  shape=unary_union(polys).buffer(.002).buffer(-.002);l,b,r,t=shape.bounds;length=r-l;windows=[]
  def window(cx,y0,y1,width,panes=4):
   x0,x1=cx-width/2,cx+width/2
   if shape.covers(box(x0,y0,x1,y1)):windows.append((x0,y0,x1,y1,panes))
  if kind=='west':
   assert 39.1<length<39.3 and 83.4<t<83.7
   for level in range(4):
    count=10 if level==0 else 9
    for centre in np.linspace(l+2.5,r-2.5,count):window(centre,base+[.85,4.65,8.7,12.55][level],base+[3.15,7.15,11.45,15.35][level],2.0 if level==0 else 2.85,4)
  elif kind=='south':
   for level in range(1,4):
    for centre in [14.0,24.0]:window(l+centre,base+level*3.9+.65,base+(level+1)*3.9-.35,.95,1)
   for centre,width in [(4.5,1.1),(9.2,2.6),(18.3,1.1),(24.6,1.2)]:window(l+centre,base+.25,base+3.2,width,2 if width>2 else 1)
  elif b<base+.5 and length>20:
   # No rear-photo schedule is available. Repeat the reference's modular rhythm
   # only on broad occupied rear walls, not on roof plant screens or recesses.
   count=max(2,round(length/3.8)-1)
   for level in range(4):
    for centre in np.linspace(l+2.5,r-2.5,count):window(centre,base+level*3.9+.85,base+(level+1)*3.9-.45,2.5,4)
  solid=shape.difference(unary_union([box(*w[:4])for w in windows]))
  surface(solid.intersection(box(l-.1,b-.1,r+.1,metalBase)),0)
  surface(solid.intersection(box(l-.1,metalBase,r+.1,t+.1)),3)
  for x0,y0,x1,y1,panes in windows:
   depth=-.18;quad([pt(x0,y0,depth),pt(x1,y0,depth),pt(x1,y1,depth),pt(x0,y1,depth)],1)
   for x in [x0,x1]:quad([pt(x,y0,0),pt(x,y1,0),pt(x,y1,depth),pt(x,y0,depth)],2)
   for y in [y0,y1]:quad([pt(x0,y,0),pt(x1,y,0),pt(x1,y,depth),pt(x0,y,depth)],2)
   for x in np.linspace(x0,x1,panes+1):block(x-.027,y0,-.17,x+.027,y1,-.06,2)
   for y in [y0,y1]:block(x0,y-.035,-.17,x1,y+.035,-.06,2)
   if y0>base+8 and panes>1:block(x0,y0+(y1-y0)*.30,-.16,x1,y0+(y1-y0)*.30+.045,-.07,2)
   block(x0-.04,y0-.06,-.06,x1+.04,y0,.10,2)
  # Continuous dark horizontal flashings, clipped to the stepped survey face.
  for y in [base+.12,base+3.9,base+7.9,base+11.8,base+15.6,metalBase,t-.04]:
   if not b-.05<=y<=t:continue
   cut=shape.intersection(box(l-.1,y-.045,r+.1,y+.045))
   for p in ([cut]if cut.geom_type=='Polygon'else getattr(cut,'geoms',[])):
    if p.geom_type=='Polygon' and p.area>.001:
     x0,y0,x1,y1=p.bounds;block(x0,y0,-.015,x1,y1,.13,2)
  # Standing seams on the exposed metal rooftop screen.
  if t>metalBase:
   for x in np.arange(l+.4,r,.55):
    segment=shape.intersection(box(x-.008,metalBase,x+.008,t))
    if segment.geom_type=='Polygon' and segment.area>.001:
     x0,y0,x1,y1=segment.bounds;block(x0,y0,0,x1,y1,.025,3)
  if kind=='south':
   # The photographed south rooftop screen has a dark horizontal louvre.
   x0,x1=l+3.0,l+5.7;y0,y1=metalBase+.45,metalBase+1.30
   assert shape.covers(box(x0,y0,x1,y1))
   block(x0,y0,-.01,x1,y1,.025,2)
   for y in np.arange(y0+.06,y1,.10):block(x0,y,0,x1,y+.025,.07,3)
  evidence.append({'surveyFaces':indices,'role':kind,'windowGroups':len(windows),'lengthMetres':length,'baseY':b,'topY':t})
 # Clear obsolete construction geometry inside the actual building footprint.
 grounds=[ctx['mc'](rings[0])for name,surfaces in ctx['buildings']if name==bid for typ,rings in surfaces if typ=='GroundSurface']
 foot=unary_union([Polygon(q[:,[0,2]])for q in grounds])
 for p in ([foot]if foot.geom_type=='Polygon'else foot.geoms):
  meta['replacements'].append({'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors],'y0':base-.5,'y1':84,'kind':'architecture','alwaysVisible':True})
 # Retire low construction debris and its old collision proxies over the graded
 # site. Neighbouring surveyed envelopes remain protected by an explicit gap.
 grade=meta['siteGrading'];site=Polygon(grade['footprintUtm']).buffer(grade['outerMetres'])
 if grade.get('apron'):site=site.union(Polygon(grade['apron']['footprintUtm']).buffer(grade['apron']['blendMetres']))
 neighbours=unary_union([Polygon(p)for p in grade['excludedNeighbourFootprintsUtm']]).buffer(grade['neighbourBufferMetres'])
 site=site.difference(neighbours)
 def projected(ring):
  xy=np.asarray(ring.coords);return ctx['mc'](np.column_stack((xy,np.full(len(xy),grade['heightDHHN2016']))))[:,[0,2]].tolist()
 for p in ([site]if site.geom_type=='Polygon'else site.geoms):
  meta['replacements'].append({'ring':projected(p.exterior),'holes':[projected(h)for h in p.interiors],'y0':base-3,'y1':base+6,'kind':'architecture','source':'COS inferred finished-site grading'})
 # Embed the byte-identical surveyed roof so this current building can remain
 # visible when the distant world switches to older aerial photogrammetry.
 raw=(out/(bid+'-photo-roof.ect')).read_bytes();assert raw[:4]==b'ECT1' and struct.unpack_from('<i',raw,4)[0]==1
 assert struct.unpack_from('<ddd',raw,8)==(0,0,0)
 count,width,height=struct.unpack_from('<iii',raw,32);roof=np.frombuffer(raw,dtype='<f4',count=count*5,offset=48).reshape((-1,5)).copy()
 parts.append(roof.tolist());textures.append(Image.frombytes('RGBA',(width,height),raw[48+count*20:]))
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);name=bid+'-cos-exterior.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'cos-exterior','alwaysVisible':True,'runtimeId':1_000_030_010,'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
 meta['architecture']['cosExterior']={'building':bid,'tumBuilding':'5132','faces':evidence,'source':reference['sourcePage'],'note':'Surveyed complete envelope and unchanged roof. West/south openings informed by photograph; exact dimensions/recess and other elevations inferred. Rectified timber patch repeated at estimated scale. No interiors.'}
 meta['attribution']+='; COS timber: Alexander Pach (CC BY 4.0)'
 print('COS: surveyed stepped envelope, timber material and west/south window groups; rear layouts inferred',flush=True)

"""GRS III: surveyed square office wing and rounded stair tower."""
import json,struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
import mapbox_earcut

BUILDING='DEBY_LOD2_5284472'

def build(ctx,bid,walls):
 if bid!=BUILDING:return
 root,out,meta,encode=[ctx[k]for k in ['ROOT','OUT','metadata','encode']]
 reference=json.loads((root/'minecraft/exterior/photos/grs-iii-reference.json').read_text())
 assert len(walls)==30
 base=min(w['bounds'][0][1]for w in walls);top=max(w['bounds'][1][1]for w in walls)
 assert 11.65<top-base<11.67
 main_top=72.299; floors=[(base+.28,base+2.55),(base+3.14,base+5.58),(base+6.23,main_top-.48)]
 textures=[Image.new('RGBA',(1,1),c)for c in [(190,192,186,255),(44,64,72,255),(57,63,64,255),(127,136,139,255)]]
 parts=[[]for _ in textures];evidence=[]
 def pt(x,y,z=0):
  p=anchor+direction*x+normal*z;p[1]=y;return p
 def quad(points,part):
  for i in [0,1,2,0,2,3]:parts[part].append([*points[i],*[(0,1),(1,1),(1,0),(0,0)][i]])
 def block(x0,y0,z0,x1,y1,z1,part):
  p=[pt(x,y,z)for z in [z0,z1]for y in [y0,y1]for x in [x0,x1]]
  for f in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]:quad([p[i]for i in f],part)
 def surface(shape,part,depth=0):
  for p in ([shape]if shape.geom_type=='Polygon'else getattr(shape,'geoms',[])):
   if p.geom_type!='Polygon' or p.area<1e-7:continue
   rings=[np.asarray(p.exterior.coords[:-1])]+[np.asarray(h.coords[:-1])for h in p.interiors];xy=np.concatenate(rings)
   for i in mapbox_earcut.triangulate_float64(xy,np.cumsum([len(r)for r in rings]).astype(np.uint32)):
    x,y=xy[i];parts[part].append([*pt(x,y,depth),float(np.clip((x-l)/(rgt-l),0,1)),float(np.clip((y-base)/(top-base),0,1))])
 def brace(a,b,part=3,radius=.035):
  a,b=np.asarray(a),np.asarray(b);axis=b-a;axis/=np.linalg.norm(axis);u=np.cross(axis,[0,1,0]);u/=np.linalg.norm(u);v=np.cross(axis,u)
  rings=[[p+radius*(np.cos(t)*u+np.sin(t)*v)for t in np.arange(8)*np.pi/4]for p in [a,b]]
  for i in range(8):quad([rings[0][i],rings[0][(i+1)%8],rings[1][(i+1)%8],rings[1][i]],part)
 # The plan's square main wing is south of the attached north-west tower.
 # Roof-upstand faces stay opaque; all 50 survey roof triangles are retained.
 main_faces={3,18,22,23,29}; corner_columns={}; main_corners=[]
 def column(centre,y0,y1):
  # Architect specifies square concrete supports set diagonally to the facade.
  c=np.array(centre);u=np.array([.984,0,.178]);v=np.array([-.178,0,.984]);radius=.36
  ring=[c+radius*d for d in [u,v,-u,-v]]
  for i in range(4):
   lo,hi=ring[i].copy(),ring[(i+1)%4].copy();lo[1]=hi[1]=y0
   lt,ht=lo.copy(),hi.copy();lt[1]=ht[1]=y1;quad([lo,hi,ht,lt],0)
 for index,w in enumerate(walls):
  anchor,direction,normal=[np.asarray(w[k])for k in ['anchor','direction','normal']]
  shape=Polygon(w['rings'][0],w['rings'][1:]).buffer(0);l,b,rgt,t=shape.bounds;length=rgt-l
  w['reconstructed']=True
  if index not in main_faces:
   if index in {13,25,2}: # Three short survey segments at the rounded east nose.
    opening=box(l,base+.35,rgt,base+2.65)
    surface(shape.difference(opening),0);surface(shape.intersection(opening),1,-.10)
    for y in [base+.35,base+2.35,base+2.65]:block(l,y-.035,-.12,rgt,y+.035,.015,2)
    if index==25:block((l+rgt)/2-.025,base+.35,-.11,(l+rgt)/2+.025,base+2.65,.015,2)
   elif index in {6,8,17,27}: # Short link to the square main wing.
    openings=unary_union([box(l+.08,y0,rgt-.08,y1)for y0,y1 in floors])
    surface(shape.difference(openings),0);surface(shape.intersection(openings),1,-.12)
    for y0,y1 in floors:
     for x in [l+.08,rgt-.08]:block(x-.025,y0,-.15,x+.025,y1,.02,2)
   elif index in {0,4,15,20,21}:
    # The tower's thin end glazing and pale walls are visible in courtyard context;
    # the unseen rear remains a conservative opaque surveyed envelope.
    surface(shape,0)
    if index==20:
     for x in [l+.20,rgt-.32]:
      block(x,base+2.85,.01,x+.12,t-.45,.025,2)
   else:surface(shape,0)
   if b<base+1 and t>74: block(l,t-.10,-.02,rgt,t+.035,.10,3)
   evidence.append({'surveyFace':index,'role':'tower, link or roof upstand','lengthMetres':length})
   continue
  count=max(1,round(length/1.5));spacing=length/count
  openings=unary_union([box(l+.08,y0,rgt-.08,y1)for y0,y1 in floors])
  surface(shape.difference(openings),0);surface(shape.intersection(openings),1,-.23)
  for floor,(y0,y1) in enumerate(floors):
   for x in [l+.08,rgt-.08]:quad([pt(x,y0),pt(x,y1),pt(x,y1,-.23),pt(x,y0,-.23)],2)
   for y in [y0,y1]:
    quad([pt(l+.08,y),pt(rgt-.08,y),pt(rgt-.08,y,-.23),pt(l+.08,y,-.23)],2)
    block(l+.04,y-.035,-.25,rgt-.04,y+.035,-.12,2)
   for x in np.linspace(l+.08,rgt-.08,count+1):block(x-.032,y0,-.25,x+.032,y1,-.08,3)
   # External horizontal blinds appear in the source photographs. Keep lower
   # glass exposed and vary the blind drop by bay instead of blacking out windows.
   for bay in range(count):
    x0=l+bay*spacing+.08;x1=l+(bay+1)*spacing-.08
    bottom=y0+(y1-y0)*[.30,.44,.55,.36][(bay+floor)%4]
    for y in np.arange(bottom,y1-.04,.12):block(x0,y-.012,-.07,x1,y+.012,.005,3)
  for y0,y1 in [(base+2.55,base+3.14),(base+5.58,base+6.23),(main_top-.48,main_top-.08)]:
   block(l,y0,-.02,rgt,y1,.32,0);block(l,y0-.03,-.03,rgt,y0,.34,2)
  block(l,main_top-.08,-.12,rgt,main_top+.025,.37,3)
  # Eight perimeter columns from the square plan: corners and wall centres.
  if length>23:
   for x in [l,(l+rgt)/2,rgt]:
    c=pt(x,base,.22);key=tuple(np.round(c[[0,2]],0))
    if not any(np.linalg.norm(c[[0,2]]-v[[0,2]])<.8 for v in corner_columns.values()):corner_columns[key]=c
   for centre in [l,(l+rgt)/2,rgt]:
    for sign in [-1,1]:
     end=centre+sign*3.6
     if l+.2<end<rgt-.2:brace(pt(centre,base+5.95,.49),pt(end,main_top-.55,.22),radius=.028)
  evidence.append({'surveyFace':index,'role':'main facade','lengthMetres':length,'bays':count,'windowBandsY':floors})
 # The north wall is split by the tower connection; recover its middle column
 # from the full square edge rather than treating each split as a new facade.
 nw=np.array(walls[3]["anchor"]);ne=np.array(walls[23]["anchor"])+np.array(walls[23]["direction"])*walls[23]["bounds"][1][0]
 centre=(nw+ne)/2+np.array(walls[22]["normal"])*.22;corner_columns["north-centre"]=centre
 assert len(corner_columns)==8
 for c in corner_columns.values():column(c,base,main_top-.36)
 grounds=[ctx['mc'](rings[0])for name,surfaces in ctx['buildings']if name==bid for typ,rings in surfaces if typ=='GroundSurface']
 foot=unary_union([Polygon(q[:,[0,2]])for q in grounds])
 # Protect the adjacent GRS II main wing and other buildings when retiring
 # the old source shell. The complete owned footprint always remains included.
 neighbours=[Polygon(ctx['mc'](rings[0])[:,[0,2]])for name,surfaces in ctx['buildings']if name!=bid for typ,rings in surfaces if typ=='GroundSurface']
 near=[p for p in neighbours if p.distance(foot)<4]
 boundary=foot.union(foot.buffer(2.75).difference(unary_union(near).buffer(.75)))
 rings=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in ([boundary]if boundary.geom_type=='Polygon'else boundary.geoms)]
 raw=(out/(bid+'-photo-roof.ect')).read_bytes();assert raw[:4]==b'ECT1' and struct.unpack_from('<i',raw,4)[0]==1
 count,width,height=struct.unpack_from('<iii',raw,32);roof=np.frombuffer(raw,dtype='<f4',count=count*5,offset=48).reshape((-1,5)).copy()
 for ring in rings:meta['replacements'].append(dict(ring,y0=base-.10,y1=max(top,float(roof[:,1].max()))+.40,kind='architecture',alwaysVisible=True))
 parts.append(roof.tolist());textures.append(Image.frombytes('RGBA',(width,height),raw[48+count*20:]))
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);name=bid+'-grs-iii-exterior.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'grs-iii-wing','alwaysVisible':True,'runtimeId':1_000_030_017,'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
 meta['architecture']['grsIIIExterior']={'building':bid,'faces':evidence,'source':reference['architectReference'],'columns':len(corner_columns),'note':'Square main wing, attached rounded tower, 30 survey walls and all 50 roof triangles preserved. Historical photos and plan inform three glazing bands, fascia, diagonal-set perimeter columns, upper braces and blinds. Dimensions, colours and less-visible elevations are estimated; no interiors.'}
 print('GRS III: surveyed square wing and rounded tower, three window bands, columns and blinds',flush=True)
 return rings

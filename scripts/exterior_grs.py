"""GRS north wing: surveyed envelope with reference-informed curtain walls."""
import json,struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
import mapbox_earcut

BUILDING='DEBY_LOD2_5284468'

def build(ctx,bid,walls):
 if bid!=BUILDING:return
 root,out,meta,encode=[ctx[k]for k in ['ROOT','OUT','metadata','encode']]
 reference=json.loads((root/'minecraft/exterior/photos/grs-reference.json').read_text())
 assert len(walls)==6
 base=min(w['bounds'][0][1]for w in walls);top=max(w['bounds'][1][1]for w in walls)
 assert 9.45<top-base<9.55
 textures=[Image.new('RGBA',(1,1),c)for c in [(183,187,184,255),(44,64,72,255),(57,63,64,255),(127,136,139,255)]]
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
 for index,w in enumerate(walls):
  anchor,direction,normal=[np.asarray(w[k])for k in ['anchor','direction','normal']]
  shape=Polygon(w['rings'][0],w['rings'][1:]).buffer(0);l,b,rgt,t=shape.bounds;length=rgt-l
  # East is split into two flanks and a recessed 1.75m bridge junction.
  if index==4:continue
  assert length>5
  w['reconstructed']=True
  count=round(length/1.25);spacing=length/count
  bands=[(base+2.45,base+5.05),(base+6.15,base+8.65)]
  openings=unary_union([box(l+.09,y0,rgt-.09,y1)for y0,y1 in bands])
  surface(shape.difference(openings),0)
  surface(shape.intersection(openings),1,-.18)
  for y0,y1 in bands:
   for x in [l+.09,rgt-.09]:quad([pt(x,y0),pt(x,y1),pt(x,y1,-.18),pt(x,y0,-.18)],2)
   for y in [y0,y1]:
    quad([pt(l+.09,y),pt(rgt-.09,y),pt(rgt-.09,y,-.18),pt(l+.09,y,-.18)],2)
    block(l+.04,y-.035,-.20,rgt-.04,y+.035,-.07,2)
   for x in np.linspace(l+.09,rgt-.09,count+1):block(x-.033,y0,-.20,x+.033,y1,-.06,2)
  # Panel joints and the three pale projecting horizontal edges.
  for y0,y1 in [(base+.10,base+2.45),(base+5.05,base+6.15),(base+8.65,t)]:
   for x in np.linspace(l,rgt,count+1)[1:-1]:block(x-.012,y0,-.005,x+.012,y1,.012,2)
  for y0,y1 in [(base+5.05,base+5.48),(base+8.65,t-.08)]:
   block(l,y0,-.02,rgt,y1,.28,0)
   block(l,y0-.035,-.03,rgt,y0,.30,2)
  block(l,t-.08,-.15,rgt,t+.02,.32,3)
  # Upper facade posts and paired tension rods visible in the architect photos.
  for x in np.linspace(l+.10,rgt-.10,count+1):block(x-.045,base+5.45,-.04,x+.045,base+8.65,.14,3)
  if index in [1,2,3]:
   for centre in np.arange(l+4*spacing,rgt-2*spacing,8*spacing):
    for sign in [-1,1]:brace(pt(centre,base+5.53,.36),pt(centre+sign*2*spacing,base+8.55,.20))
  evidence.append({'surveyFace':index,'lengthMetres':length,'bays':count,'baySpacingMetres':spacing,'windowBandsY':bands})
 grounds=[ctx['mc'](rings[0])for name,surfaces in ctx['buildings']if name==bid for typ,rings in surfaces if typ=='GroundSurface']
 foot=unary_union([Polygon(q[:,[0,2]])for q in grounds])
 # Bounded wall strips remove old projecting fragments without touching the
 # separately surveyed bridge, octagonal tower, COS or neighbouring wings.
 for index,w in enumerate(walls):
  if not w.get('reconstructed'):continue
  anchor,direction,normal=[np.asarray(w[k])for k in ['anchor','direction','normal']];(l,b),(rgt,t)=w['bounds']
  ring=[pt(x,base,z)[[0,2]].tolist()for x,z in [(l-.04,-.35),(rgt+.04,-.35),(rgt+.04,1.3),(l-.04,1.3)]]
  meta['replacements'].append({'ring':ring,'holes':[],'y0':base-.1,'y1':top+.4,'kind':'architecture','alwaysVisible':True})
 raw=(out/(bid+'-photo-roof.ect')).read_bytes();assert raw[:4]==b'ECT1' and struct.unpack_from('<i',raw,4)[0]==1
 count,width,height=struct.unpack_from('<iii',raw,32);roof=np.frombuffer(raw,dtype='<f4',count=count*5,offset=48).reshape((-1,5)).copy()
 parts.append(roof.tolist());textures.append(Image.frombytes('RGBA',(width,height),raw[48+count*20:]))
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);name=bid+'-grs-exterior.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'grs-north-wing','alwaysVisible':True,'runtimeId':1_000_030_012,'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
 meta['architecture']['grsExterior']={'building':bid,'faces':evidence,'source':reference['architectReference'],'note':'Survey envelope and roof preserved. Historical photographic facade rhythm; dimensions, colours and less-visible elevation details inferred. Bridge junction retained; no interiors.'}
 print('GRS: surveyed north wing, curtain-wall frames, fascia and upper braces; reference-informed estimates',flush=True)

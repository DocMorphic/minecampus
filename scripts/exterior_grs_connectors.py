"""Surveyed GRS stair tower and connectors, with historical exterior references."""
import json,struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
import mapbox_earcut

TOWER='DEBY_LOD2_5284470'
WEST='DEBY_LOD2_104553225'
SOUTH='DEBY_LOD2_104553232'
BUILDINGS={TOWER:1_000_030_013,WEST:1_000_030_014,SOUTH:1_000_030_015}

def build(ctx,bid,walls):
 if bid not in BUILDINGS:return None
 root,out,meta,encode=[ctx[k]for k in ['ROOT','OUT','metadata','encode']]
 reference=json.loads((root/'minecraft/exterior/photos/grs-connectors-reference.json').read_text())
 base=min(w['bounds'][0][1]for w in walls);top=max(w['bounds'][1][1]for w in walls)
 assert len(walls)==(20 if bid==TOWER else 4)
 textures=[Image.new('RGBA',(1,1),c)for c in [(188,190,182,255),(42,63,72,255),(51,56,56,255),(135,143,143,255)]]
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
    x,y=xy[i];parts[part].append([*pt(x,y,depth),float(np.clip((x-l)/(r-l),0,1)),float(np.clip((y-base)/(top-base),0,1))])
 for index,w in enumerate(walls):
  anchor,direction,normal=[np.asarray(w[k])for k in ['anchor','direction','normal']]
  shape=Polygon(w['rings'][0],w['rings'][1:]).buffer(0);l,b,r,t=shape.bounds;length=r-l;w['reconstructed']=True
  openings=[];louvre=None;door=None
  if bid==TOWER:
   if index in [6,7,16,18]:
    # Recessed cardinal faces are glazed stair strips, with top ventilation.
    openings=[(l+.09,base+1.40,r-.09,t-1.75)]
    louvre=(l+.09,t-1.70,r-.09,t-.12)
   if index==15:
    # Southwest courtyard door observed in the architect's oblique photograph.
    ground=float(np.interp((l+r)/2,*np.asarray(w['groundProfile']).T))
    door=((l+r)/2-.58,max(base+.15,ground+.03),(l+r)/2+.58,max(base+.15,ground+.03)+2.2)
  else:
   # Preserve the full LoD2 shell, including its below-grade foundation.
   # West is a single-level link; the short south junction spans both floors.
   levels=[(top-3.35,top-.40)]if bid==WEST else [(base+.60,base+3.55),(base+4.55,top-.40)]
   openings=[(l+.08,y0,r-.08,y1)for y0,y1 in levels]
  cuts=[box(*o)for o in openings]+([box(*louvre)]if louvre else [])+([box(*door)]if door else [])
  for cut in cuts:assert shape.buffer(.003).covers(cut),(bid,index,cut.bounds)
  surface(shape.difference(unary_union(cuts)),0)
  for x0,y0,x1,y1 in openings:
   surface(box(x0,y0,x1,y1),1,-.12)
   for x in [x0,x1]:quad([pt(x,y0),pt(x,y1),pt(x,y1,-.12),pt(x,y0,-.12)],3)
   for y in [y0,y1]:quad([pt(x0,y),pt(x1,y),pt(x1,y,-.12),pt(x0,y,-.12)],3)
   panes=max(1,round((x1-x0)/1.15))
   for x in np.linspace(x0,x1,panes+1):block(x-.025,y0,-.13,x+.025,y1,-.025,3)
   rows=np.linspace(y0,y1,6)if bid==TOWER else [y0,y1]
   for y in rows:block(x0,y-.025,-.13,x1,y+.025,-.025,3)
  if louvre:
   x0,y0,x1,y1=louvre;surface(box(*louvre),2,-.10)
   for y in np.arange(y0+.03,y1,.115):block(x0,y,-.09,x1,min(y+.032,y1),.035,3)
   for x in [x0,x1]:block(x-.025,y0,-.12,x+.025,y1,.04,3)
  if door:
   x0,y0,x1,y1=door;surface(box(*door),2,-.12)
   for x in [x0,x1]:block(x-.04,y0,-.13,x+.04,y1+.05,.025,3)
   block(x0-.18,y1+.06,-.04,x1+.18,y1+.20,.13,3)
   block(x1-.16,y0+.95,-.03,x1-.13,y0+1.28,.04,3)
  block(l,t-.07,-.04,r,t+.025,.07,3)
  evidence.append({'surveyFace':index,'lengthMetres':length,'glazingBands':[list(o)for o in openings],'topLouvre':list(louvre)if louvre else None,'door':list(door)if door else None})
 # Restrict source removal around this dense junction. Keep each owned footprint
 # but clip its outer cleanup margin away from unrelated surveyed buildings.
 own=[];neighbours=[]
 for name,surfaces in ctx['buildings']:
  for typ,rings in surfaces:
   if typ!='GroundSurface':continue
   poly=Polygon(ctx['mc'](rings[0])[:,[0,2]])
   if name==bid:own.append(poly)
   elif name not in {*BUILDINGS,'DEBY_LOD2_5284468'}:neighbours.append(poly)
 foot=unary_union(own);near=[p for p in neighbours if p.distance(foot)<4]
 boundary=foot.union(foot.buffer(2.75).difference(unary_union(near).buffer(.75)))
 rings=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in ([boundary]if boundary.geom_type=='Polygon'else boundary.geoms)]
 for ring in rings:meta['replacements'].append(dict(ring,y0=base-.10,y1=top+.35,kind='architecture',alwaysVisible=True))
 raw=(out/(bid+'-photo-roof.ect')).read_bytes();assert raw[:4]==b'ECT1' and struct.unpack_from('<i',raw,4)[0]==1 and struct.unpack_from('<ddd',raw,8)==(0,0,0)
 count,width,height=struct.unpack_from('<iii',raw,32);roof=np.frombuffer(raw,dtype='<f4',count=count*5,offset=48).reshape((-1,5)).copy()
 parts.append(roof.tolist());textures.append(Image.frombytes('RGBA',(width,height),raw[48+count*20:]))
 # Keep all five material slots in a stable order, including the embedded roof.
 assert all(parts[i]for i in [0,1,3,4])
 if not parts[2]:
  # The narrow gasket across each bridge head provides the dark-frame part.
  block(l,top-.12,-.01,r,top-.08,.02,2)
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);name=bid+'-grs-connector.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'grs-tower'if bid==TOWER else 'grs-bridge','alwaysVisible':True,'runtimeId':BUILDINGS[bid],'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
 meta['architecture'].setdefault('grsConnectors',[]).append({'building':bid,'faces':evidence,'source':reference['architectReference'],'note':'Survey envelope and roof preserved. Historical references inform glazed strips, louvres, pale walls and courtyard door. Dimensions, colours and connector glazing are inferred; no interiors.','retirementBoundary':rings})
 print('GRS connector:',bid,'survey envelope and reference-informed exterior; neighbour-safe cleanup',flush=True)
 return rings

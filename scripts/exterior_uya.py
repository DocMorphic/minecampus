"""UYA exterior on its BVV envelope; ESO 2017 reference, no interior geometry."""
import json,hashlib
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
import mapbox_earcut

BUILDING='DEBY_LOD2_5284443'
# The four outer faces, not the eight inner courtyard faces.
FACES={3:11,6:24,9:11,11:24}

def build(ctx,bid,walls):
 if bid!=BUILDING:return
 root,out,meta,encode=[ctx[k]for k in ['ROOT','OUT','metadata','encode']]
 reference=json.loads((root/'minecraft/exterior/photos/uya-eso-reference.json').read_text())
 assert hashlib.sha256((root/reference['cropFile']).read_bytes()).hexdigest()==reference['cropSha256']
 # Original neutral wall/glass/infill materials. The reference is not a texture.
 grain=np.asarray(Image.open(root/'minecraft/exterior/assets/textures/campus/concrete_diff.png').convert('RGB').resize((128,128))).mean(2)
 def material(base,strength):
  a=np.empty((128,128,4),np.uint8)
  for k,v in enumerate(base):a[:,:,k]=np.clip(v+(grain-grain.mean())*strength,0,255)
  a[:,:,3]=255;return Image.fromarray(a)
 textures=[material([207,205,193],.18),material([54,66,69],.06),Image.new('RGBA',(1,1),(145,151,149,255)),material([166,137,94],.15)]
 parts=[[]for _ in textures];evidence=[]
 def pt(x,y,z):
  p=anchor+direction*x+normal*z;p[1]=y;return p
 def quad(coords,part):
  uv=[(0,1),(1,1),(1,0),(0,0)]
  for i in [0,1,2,0,2,3]:parts[part].append([*coords[i],*uv[i]])
 def block(x0,y0,z0,x1,y1,z1,part):
  p=[pt(x,y,z)for z in [z0,z1]for y in [y0,y1]for x in [x0,x1]]
  for face in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]:quad([p[i]for i in face],part)
 def surface(shape,part,depth=0):
  if shape.is_empty:return
  for x0 in np.arange(shape.bounds[0],shape.bounds[2],2):
   for y0 in np.arange(shape.bounds[1],shape.bounds[3],2):
    cut=shape.intersection(box(x0,y0,x0+2,y0+2))
    for poly in ([cut]if cut.geom_type=='Polygon'else getattr(cut,'geoms',[])):
     if poly.geom_type!='Polygon' or poly.area<1e-8:continue
     rings=[np.asarray(poly.exterior.coords[:-1])]+[np.asarray(h.coords[:-1])for h in poly.interiors]
     xy=np.concatenate(rings);indices=mapbox_earcut.triangulate_float64(xy,np.cumsum([len(r)for r in rings]).astype(np.uint32))
     for i in indices:
      x,y=xy[i];parts[part].append([*pt(x,y,depth),(x-x0)/2,1-(y-y0)/2])
 for index,count in FACES.items():
  wall=walls[index];anchor=np.asarray(wall['anchor']);direction=np.asarray(wall['direction']);normal=np.asarray(wall['normal']);l,b=wall['bounds'][0];r,t=wall['bounds'][1];length=r-l
  assert abs(length-(32 if count==11 else 51))<.25 and 63<b<65 and 72<t<73,(index,length,b,t)
  shape=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0)
  # The short elevations' surveyed eaves dip to about Y=71.42 between
  # the raised outer roof edges. Keep a common window head below that dip.
  floor=b+3.85;winBottom=b+5.02;winTop=b+7.20
  # Photo-counted rhythm: the short side has broad solid end sections.
  margin=length*.165 if count==11 else 1.0
  centres=np.linspace(l+margin,r-margin,count);openings=[];windows=[]
  for centre in centres:
   x0,x1=centre-.59,centre+.59;opening=box(x0,winBottom,x1,winTop)
   assert shape.covers(opening),(index,centre)
   openings.append(opening);windows.append((x0,winBottom,x1,winTop,True))
  # The visible lower level alternates glazed bays and ochre infill. Exact
  # divisions on obscured/opposite elevations are estimates, not survey data.
  bays=6 if count==24 else 4;step=length/bays
  for i in range(bays):
   centre=l+(i+.5)*step;half=step*.25
   x0,x1=centre-half,centre+half;y0,y1=b+.25,floor-.25
   opening=box(x0,y0,x1,y1)
   if shape.covers(opening):openings.append(opening);windows.append((x0,y0,x1,y1,False))
  solid=shape.difference(unary_union(openings))
  surface(solid.intersection(box(l,b,r,floor)),3)
  surface(solid.intersection(box(l,floor,r,t+.1)),0)
  for x0,y0,x1,y1,upper in windows:
   depth=-.18
   quad([pt(x0,y0,depth),pt(x1,y0,depth),pt(x1,y1,depth),pt(x0,y1,depth)],1)
   # Recess reveals prevent see-through gaps around the framed glazing.
   for coords in [[pt(x0,y0,0),pt(x0,y1,0),pt(x0,y1,depth),pt(x0,y0,depth)],
                  [pt(x1,y0,depth),pt(x1,y1,depth),pt(x1,y1,0),pt(x1,y0,0)],
                  [pt(x0,y0,0),pt(x0,y0,depth),pt(x1,y0,depth),pt(x1,y0,0)],
                  [pt(x0,y1,depth),pt(x0,y1,0),pt(x1,y1,0),pt(x1,y1,depth)]]:quad(coords,0 if upper else 3)
   border=.055
   block(x0-border,y0-border,-.045,x0+border,y1+border,.035,2)
   block(x1-border,y0-border,-.045,x1+border,y1+border,.035,2)
   block(x0,y0-border,-.045,x1,y0+border,.035,2)
   block(x0,y1-border,-.045,x1,y1+border,.035,2)
   if upper:
    block(x0,y0+(y1-y0)*.33,-.06,x1,y0+(y1-y0)*.33+.035,-.015,2)
    block(x0-.07,y0-.08,-.03,x1+.07,y0-.025,.16,2)
   else:
    for at in np.arange(x0+.95,x1,.95):block(at-.025,y0,-.07,at+.025,y1,-.015,2)
  block(l,floor-.06,-.08,r,floor+.06,.08,0)
  ring=[pt(x,b,z)[[0,2]].tolist()for x,z in [(l-.15,-.6),(r+.15,-.6),(r+.15,.6),(l-.15,.6)]]
  meta['replacements'].append({'ring':ring,'holes':[],'y0':b-.2,'y1':t+.2,'kind':'architecture'})
  wall['reconstructed']=True
  evidence.append({'surfaceIndex':index,'lengthMetres':length,'upperWindows':count,'lowerBays':bays,'baseY':b,'upperFloorY':floor,'windowBottomY':winBottom,'windowTopY':winTop,'recessMetres':.18})
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);name=bid+'-uya-exterior.ect'
 (out/name).write_bytes(encode(list(zip(parts,textures))))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'uya-exterior','runtimeId':1_000_030_006,'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
 meta['architecture']['uyaExterior']={'building':bid,'reference':reference['sourcePage'],'faces':evidence,'note':'Four outer facades on surveyed envelope. Roof and two courts retained. Visible photo rhythm is 24/11 upper windows; opposite elevations repeat that rhythm by inference. Lower subdivisions, window dimensions, recesses and materials are estimates. Inner courtyard walls retain source photography. No interior.'}
 print('UYA: four surveyed outer faces, 70 upper windows; roof courts retained; no interior',flush=True)

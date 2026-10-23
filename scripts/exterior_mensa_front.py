"""Former Mensa terrace frontage: BVV dimensions, TUM 2025 exterior reference.
Only the observed south-facing bays are reconstructed; no interior is generated.
"""
import json,hashlib
import numpy as np
from PIL import Image

BUILDING='DEBY_LOD2_5284422'
REFERENCE='https://www.ed.tum.de/ed/news-single-view-start/article/tum-ed-bezieht-alte-mensa-in-garching-nach-umbau/'
# Surface indices in the pinned BVV source, checked geometrically below. The
# broad six-bay frontage and its stepped returns are identifiable in DOP20.
FRONTS={49:6,48:1,11:1,41:1,6:2}

def build(ctx,bid,walls):
 if bid!=BUILDING:return
 root,out,meta,encode=[ctx[k]for k in ['ROOT','OUT','metadata','encode']]
 source=root/'minecraft/exterior/assets/textures/campus/concrete_diff.png'
 material=next(x for x in json.loads((root/'minecraft/exterior/material-sources.json').read_text())['materials']if x['name']=='concrete_diff')
 assert hashlib.sha256(source.read_bytes()).hexdigest()==material['resourceSha256']
 concrete=Image.open(source).convert('RGBA').resize((256,256))
 pixels=np.array(concrete);luminance=pixels[:,:,:3].mean(axis=2)
 for k,offset in enumerate([75,73,67]):pixels[:,:,k]=np.clip(luminance*.72+offset,0,255)
 concrete=Image.fromarray(pixels)
 # Original material approximation, not a photograph of an unobserved facade.
 # Muted vertical reflection and seal variation keep glass distinct from opaque
 # concrete; the measured geometry and reference determine the visible bays.
 y,x=np.mgrid[0:256,0:128];reflection=6*np.cos(x/128*np.pi*2)+4*np.cos(y/256*np.pi)
 glass=np.empty((256,128,4),np.uint8)
 for k,base in enumerate([43,59,62]):glass[:,:,k]=np.clip(base+reflection,0,255)
 glass[:,:,3]=255
 textures=[concrete,Image.fromarray(glass),Image.new('RGBA',(1,1),(43,59,54,255)),Image.new('RGBA',(1,1),(171,179,174,255)),Image.new('RGBA',(1,1),(127,116,96,255))]
 parts=[[]for _ in textures];faceEvidence=[]
 for index,bays in FRONTS.items():
  wall=walls[index];anchor=np.asarray(wall['anchor']);direction=np.asarray(wall['direction']);l,b=wall['bounds'][0];r,t=wall['bounds'][1]
  assert 67<b<68 and 70<t<72 and abs((r-l)/bays-7.16)<.8,(index,wall['bounds'])
  normal=np.array([-direction[2],0,direction[0]])
  if normal[2]<0:normal=-normal
  assert normal[2]>.95
  # LoD2 uses the canopy envelope. The glass is recessed behind its columns.
  def pt(along,height,depth):
   p=anchor+direction*along+normal*depth;p[1]=height;return p
  def quad(coords,target,uv=None):
   uv=uv or [(0,1),(1,1),(1,0),(0,0)]
   for i in [0,1,2,0,2,3]:target.append([*coords[i],*uv[i]])
  def block(x0,y0,z0,x1,y1,z1,part):
   points=[pt(x,y,z)for z in [z0,z1]for y in [y0,y1]for x in [x0,x1]]
   for face in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]:quad([points[i]for i in face],parts[part])
  step=(r-l)/bays;top=t-.08;lintel=top-.52
  for i in range(bays+1):
   at=l+i*step
   block(at-.23,b,-.40,at+.23,top+.62,.22,0)
  # Continuous beam, deep soffit and cap; joints remain aligned with the bays.
  for i in range(bays):
   x0=l+i*step;x1=x0+step
   block(x0,lintel,-1.3,x1,top,.16,0)
   block(x0+.23,lintel-.045,-1.28,x1-.23,lintel,.04,4)
   block(x0,b-.15,-1.4,x1,b+.03,.6,0)
   # Four full-height glazed divisions per structural bay, with a low opaque
   # kick panel and real mullion/transom depth. This subdivision is estimated
   # from the reference, not a surveyed pane-by-pane inventory.
   span=step/4
   for pane in range(4):
    a=x0+pane*span;c=a+span
    quad([pt(a,b+.36,-1.1),pt(c,b+.36,-1.1),pt(c,lintel-.1,-1.1),pt(a,lintel-.1,-1.1)],parts[1])
    block(a,b+.08,-1.15,c,b+.36,-1.08,3)
    block(a-.035,b+.08,-1.06,a+.035,lintel,-.99,2)
    block(a,b+.36,-1.06,c,b+.415,-.99,2)
   block(x1-.035,b+.08,-1.06,x1+.035,lintel,-.99,2)
   block(x0,lintel-.14,-1.06,x1,lintel-.07,-.99,2)
   # Rooftop maintenance railing, visible in the reference photo.
   for at in np.linspace(x0,x1,5):block(at-.025,top,-.38,at+.025,top+.95,-.33,3)
   block(x0,top+.9,-.39,x1,top+.95,-.32,3)
   block(x0,top+.43,-.39,x1,top+.475,-.32,3)
  # Bound cleanup to this facade, leaving the plaza sculptures and other
  # facades intact. The photographic pipeline also recognizes its ownership.
  ring=[pt(x,b,z)[[0,2]].tolist()for x,z in [(l-.4,-2.1),(r+.4,-2.1),(r+.4,1.3),(l-.4,1.3)]]
  meta['replacements'].append({'ring':ring,'holes':[],'y0':b-.2,'y1':top+1.2,'kind':'architecture'})
  wall['reconstructed']=True
  faceEvidence.append({'surfaceIndex':index,'bays':bays,'lengthMetres':r-l,'baseY':b,'roofY':t,'glazingRecessMetres':1.1})
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts if p]);name=BUILDING+'-terrace-front.ect'
 (out/name).write_bytes(encode([(p,t)for p,t in zip(parts,textures)if p]))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'former-mensa-front','runtimeId':1_000_030_005,'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
 meta['architecture']['formerMensaFront']={'building':bid,'reference':REFERENCE,'faces':faceEvidence,'note':'Partial exterior reconstruction. Survey fixes envelope and bay lengths; columns, recess depth, pane divisions and material tones are reference-informed estimates. No reference photograph bundled; glass is an original approximate material. Other faces retain runtime photography.'}
 print('Former Mensa: five surveyed terrace faces, eleven reference-informed concrete bays; no interior',flush=True)

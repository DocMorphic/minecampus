"""Prepare public survey surfaces for transient, provider-textured wall reconstruction.
No provider image or tile content is used by this build step or put in the release.
"""
import json
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union

# Keep hand-reconstructed landmarks and tall reactor domes on their existing
# geometry. Other fully covered survey envelopes are photographic candidates.
PILOT='DEBY_LOD2_5284443'
EXCLUDED={'DEBY_LOD2_5284450','DEBY_LOD2_5323135'}

def build(ctx):
 out,meta,buildings,mc,triangulate,photo_uv,photo,w,h,encode=[ctx[k]for k in ['OUT','metadata','buildings','mc','triangulate','photo_uv','photo','w','h','encode']]
 plans=[]
 terrain=meta['terrainGuide'];grid=np.asarray(terrain['points']).reshape(terrain['height'],terrain['width'],3)
 a=grid[0,0];inverse=np.linalg.inv(np.column_stack(((grid[0,1]-a)[[0,2]],(grid[1,0]-a)[[0,2]])))
 def terrain_y(x,z):
  s,t=inverse@(np.array([x,z])-a[[0,2]])
  s=np.clip(s,0,terrain['width']-1.000001);t=np.clip(t,0,terrain['height']-1.000001);i,j=int(s),int(t);fx,fz=s-i,t-j
  return float((grid[j,i,1]*(1-fx)+grid[j,i+1,1]*fx)*(1-fz)+(grid[j+1,i,1]*(1-fx)+grid[j+1,i+1,1]*fx)*fz)
 manual=set(meta['architecture']['buildings'])|{'DEBY_LOD2_107614322','DEBY_LOD2_107614323','DEBY_LOD2_5284521','DEBY_LOD2_5284523','DEBY_LOD2_104552957'}
 protected=unary_union([Polygon(mc(r[0])[:,[0,2]])for bid,surfaces in buildings if bid in manual for typ,r in surfaces if typ=='GroundSurface'])
 for bid,surfaces in sorted(buildings,key=lambda b:(b[0]!=PILOT,b[0])):
  if bid in manual or bid in EXCLUDED:continue
  grounds=[mc(r[0])for typ,r in surfaces if typ=='GroundSurface'];foot=unary_union([Polygon(q[:,[0,2]])for q in grounds]);walls=[];roofs=[];allq=[]
  if foot.area<20 or foot.intersection(protected).area>foot.area*.1:continue
  survey=np.concatenate([r[0]for typ,r in surfaces]);xmin,ymin,xmax,ymax=meta['boundsUtm']
  if survey[:,0].min()<xmin or survey[:,0].max()>xmax or survey[:,1].min()<ymin or survey[:,1].max()>ymax:continue
  for typ,rings in surfaces:
   p,q,indices=triangulate(rings);allq.extend(q.tolist())
   if typ=='RoofSurface':
    uv=photo_uv(p);roofs.extend([*q[i],*uv[i]]for tri in indices for i in tri);continue
   if typ!='WallSurface':continue
   anchor=q[0].copy();delta=next((v-anchor for v in q if np.linalg.norm((v-anchor)[[0,2]])>.1),None)
   if delta is None:continue
   direction=np.array([delta[0],0,delta[2]]);direction/=np.linalg.norm(direction);normal=np.array([-direction[2],0,direction[0]])
   if foot.contains(Point((q.mean(axis=0)+normal*.3)[[0,2]])):normal=-normal
   xy=np.column_stack(((q-anchor)@direction,q[:,1]));lo=xy.min(axis=0);hi=xy.max(axis=0)
   if hi[0]-lo[0]<.1 or hi[1]-lo[1]<.1:continue
   planrings=[]
   for ring in rings:
    v=mc(ring);planrings.append(np.column_stack(((v-anchor)@direction,v[:,1])).tolist())
   profile=[]
   for along in np.linspace(lo[0],hi[0],max(2,int(np.ceil((hi[0]-lo[0])/.5))+1)):
    point=anchor+direction*along;profile.append([float(along),terrain_y(point[0],point[2])])
   walls.append({'anchor':anchor.tolist(),'direction':direction.tolist(),'normal':normal.tolist(),'bounds':[lo.tolist(),hi.tolist()],'rings':planrings,'vertices':q.tolist(),'indices':indices.reshape(-1).tolist(),'groundProfile':profile})
  if not walls or not roofs:continue
  roof=np.array(roofs);uv=roof[:,3:5];low=np.maximum(0,np.floor(uv.min(axis=0)*[w,h]).astype(int)-2);high=np.minimum([w,h],np.ceil(uv.max(axis=0)*[w,h]).astype(int)+2)
  if np.any(high<=low)or uv.min()<0 or uv.max()>1:continue
  roof[:,3:5]=(uv*[w,h]-low)/(high-low);name=bid+'-photo-roof.ect';(out/name).write_bytes(encode([(roof,photo.crop((*low,*high)))]))
  points=np.array(allq);shape=foot.buffer(2.75)
  rings=[{'ring':list(p.exterior.coords),'holes':[list(r.coords)for r in p.interiors]}for p in ([shape]if shape.geom_type=='Polygon'else shape.geoms)if p.geom_type=='Polygon']
  from exterior_mensa_front import build as build_mensa_front
  build_mensa_front(ctx,bid,walls)
  from exterior_uya import build as build_uya
  build_uya(ctx,bid,walls)
  from exterior_uye import build as build_uye
  build_uye(ctx,bid,walls)
  from exterior_warehouse import build as build_warehouse
  build_warehouse(ctx,bid,walls)
  from exterior_telefonzentrale import build as build_telefonzentrale
  build_telefonzentrale(ctx,bid,walls)
  from exterior_cos import build as build_cos
  build_cos(ctx,bid,walls)
  collisionName=bid+'-photo-collision.ect'
  vertices=[[*wall['vertices'][i],0,0]for wall in walls if not wall.get('reconstructed') for i in wall['indices']]
  collisionParts=[(vertices,Image.new('RGBA',(1,1),(150,150,145,255)))]if vertices else []
  (out/collisionName).write_bytes(encode(collisionParts+[(roof,photo.crop((*low,*high)))]))
  plans.append({'manualRoof':bid=='DEBY_LOD2_108698313','collisionFile':collisionName,'id':bid,'runtimeId':1_000_050_000+len(plans),'roofFile':name,'bounds':[points.min(axis=0).tolist(),points.max(axis=0).tolist()],'walls':walls,'roofTriangles':[roof[i:i+3,:3].tolist()for i in range(0,len(roof),3)],'retirement':rings})
 (out/'photo-facades.json').write_text(json.dumps({'pixelsPerMetre':10,'maxProjectionDistance':6,'minimumCoverage':.80,'plans':plans},separators=(',',':')))
 meta['photoFacades']={'file':'photo-facades.json','roofFiles':[p['roofFile']for p in plans],'collisionTiles':[{'file':p['collisionFile'],'bounds':p['bounds'],'kind':'reconstruction'}for p in plans],'collisionRetirement':[dict(r,y0=p['bounds'][0][1]-2,y1=p['bounds'][1][1]+5)for p in plans for r in p['retirement']],'buildings':[p['id']for p in plans],'note':'Provider material is reprojected in memory at runtime; public package contains survey geometry and orthophoto roofs only.'}
 print('Transient photo facade candidates:',len(plans),flush=True)

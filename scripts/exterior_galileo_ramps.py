"""Bounded exterior access ramps; survey profiles with explicit inferred wall details."""
import hashlib,json,struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union
from exterior_galileo_court import triangles


def build(ctx):
 root,out,meta,mc,encode=[ctx[k] for k in ['ROOT','OUT','metadata','mc','encode']]
 source=root/'minecraft/exterior/galileo-east-ramps.json';spec=json.loads(source.read_text())
 reference=root/'minecraft/exterior'/spec['reference']
 assert hashlib.sha256(reference.read_bytes()).hexdigest()==spec['referenceSha256']
 features={f['way']:f for f in json.loads(reference.read_text())['features']}
 parts=[[],[],[],[]] # concrete, asphalt, dark portal boundary, original-colour collar
 overrides=[];records=[];cuts=[];floors=[];wall_footprints=[];grade_edges=[]
 def xyz(xy,h):return mc(np.column_stack((xy,np.broadcast_to(h,len(xy)))))
 def emit(index,q,uv=None):
  if uv is None:uv=np.full((len(q),2),.5)
  for p,t in zip(q,uv):parts[index].append([*p,*t])
 def quad(index,q):
  q=np.asarray(q);emit(index,q[[0,1,2,0,2,3]])
 def plane_override(q):
  for ids in [[0,1,2],[0,2,3]] if len(q)==4 else [[0,1,2]]:
   t=q[ids];coef=np.linalg.solve(np.column_stack((t[:,[0,2]],np.ones(3))),t[:,1])
   overrides.append({'ring':t[:,[0,2]].tolist(),'plane':coef.tolist()})
 def wall_strip(a,b,lo,hi,width):
  d=b-a;d/=np.linalg.norm(d);n=np.array([-d[1],d[0]])*width/2
  xy=np.array([a-n,b-n,b+n,a+n]);lower=xyz(xy,[lo[0],lo[1],lo[1],lo[0]]);upper=xyz(xy,[hi[0],hi[1],hi[1],hi[0]])
  quad(0,upper)
  for i,j in [(0,1),(1,2),(2,3),(3,0)]:quad(0,[lower[i],lower[j],upper[j],upper[i]])
  wall_footprints.append(Polygon(upper[:,[0,2]]))
 for ramp in spec['ramps']:
  feature=features[ramp['way']];line=LineString(feature['utm']);start,end=ramp['startStation'],ramp['endStation']
  count=int(np.ceil(abs(end-start)));stations=np.linspace(start,end,count+1)
  centres=np.array([line.interpolate(float(s)).coords[0] for s in stations])
  tangent=np.array(line.interpolate(min(start+.1,line.length)).coords[0])-np.array(line.interpolate(max(start-.1,0)).coords[0]);tangent/=np.linalg.norm(tangent)
  normal=np.array([-tangent[1],tangent[0]])
  centres+=normal*ramp['normalOffsetMetres'];width=ramp['clearWidthMetres'];half=width/2;thick=spec['wallThicknessMetres']
  profile=feature['profile'];h=np.interp(stations,[p['station']for p in profile],[p['dgmHeightDHHN2016']for p in profile])
  # Retain the gentler entry transition as well as the steep main run. Each
  # strip follows the piecewise-linear source centreline, with a level section
  # across its width instead of the raster's smoothed lateral retaining bank.
  levels=h;assert np.all(np.diff(levels)<.03) and np.max(abs(np.diff(levels)))<.25
  left=centres+normal*half;right=centres-normal*half
  for i in range(count):
   q=xyz([left[i],right[i],right[i+1],left[i+1]],[levels[i],levels[i],levels[i+1],levels[i+1]])
   quad(1,q);plane_override(q);floors.append(Polygon(q[:,[0,2]]))
  entry=xyz([left[0],right[0]],levels[0]);grade_edges.append((LineString(entry[:,[0,2]]),entry[:,1]))
  terminal_tops=[]
  for side in [-1,1]:
   edge=centres+normal*side*(half+thick/2)
   # Upper surfaces are sampled safely outside each wall, not in the raster's
   # smeared retaining face. Fit the adjacent grade rather than copying spikes.
   controls=centres+normal*side*4
   measured=ctx.get('galileo_east_elevation',ctx['survey_elevation']).sample(controls)
   upper=np.linspace(float(np.median(measured[:4])),float(np.median(measured[-4:])),len(measured))
   top=np.maximum(upper+spec['parapetHeightMetres'],levels+.16)
   terminal_tops.append(float(top[-1])+.07)
   for i in range(count):
    wall_strip(edge[i],edge[i+1],levels[i:i+2]-.15,top[i:i+2],thick)
    wall_strip(edge[i],edge[i+1],top[i:i+2],top[i:i+2]+.07,thick+2*spec['copingOverhangMetres'])
    outer=centres[i:i+2]+normal*side*(half+thick+spec['copingOverhangMetres'])
    q=xyz(outer,upper[i:i+2]);grade_edges.append((LineString(q[:,[0,2]]),q[:,1]))
  # Model only the shallow exterior opening. A dark terminal boundary avoids
  # implying a reconstructed underground interior beyond the available evidence.
  down=(centres[-1]-centres[-2]);down/=np.linalg.norm(down);rear=centres[-1]+down*spec['portalRecessMetres']
  mouth=np.array([left[-1],right[-1]]);back=np.array([rear+normal*half,rear-normal*half]);floor=levels[-1];ceiling=floor+spec['portalClearanceMetres']
  q=xyz([*mouth,*back[::-1]],floor);quad(1,q);plane_override(q);floors.append(Polygon(q[:,[0,2]]))
  quad(2,xyz([*back,*back[::-1]],[floor,floor,ceiling,ceiling]))
  quad(0,xyz([*mouth,*back[::-1]],ceiling))
  terminal_top=max(*terminal_tops,ceiling+.3)
  quad(0,xyz([*mouth,*mouth[::-1]],[ceiling,ceiling,terminal_top,terminal_top]))
  quad(0,xyz([*mouth,*back[::-1]],terminal_top))
  wall_strip(back[0],back[1],[ceiling,ceiling],[terminal_top,terminal_top],.28)
  for side in [-1,1]:
   a=centres[-1]+normal*side*(half+thick/2);b=rear+normal*side*(half+thick/2)
   wall_strip(a,b,[floor-.15]*2,[terminal_top]*2,thick)
  ring=np.concatenate((left,right[::-1]));foot=Polygon(xyz(ring,levels[0])[:,[0,2]])
  foot=unary_union([foot,Polygon(q[:,[0,2]])]);cuts.append(foot.buffer(thick+spec['copingOverhangMetres']+spec['collarMetres'],join_style=2))
  records.append({'name':ramp['name'],'sourceWay':ramp['way'],'clearWidthMetres':width,'sourceStations':stations.tolist(),'centrelineMC':xyz(centres,levels).tolist(),'profileMethod':'Piecewise linear interpolation of pinned centreline DGM samples; level transverse sections','upperHeightDHHN2016':float(levels[0]),'lowerHeightDHHN2016':float(levels[-1])})
 cut=unary_union(cuts).buffer(0)
 buildings=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0) for _,surfaces in ctx['buildings']for kind,r in surfaces if kind=='GroundSurface'])
 assert cut.intersection(buildings).area<.001,'Ramp envelope intersects surveyed building'
 footprint=unary_union([*floors,*wall_footprints]).buffer(0);collar=cut.difference(footprint)
 altered=[]
 for entry in meta['tiles']:
  if entry['kind']!='ground':continue
  path=out/entry['file'];raw=path.read_bytes();n,w,h=struct.unpack_from('<3i',raw,32);v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=48).reshape(-1,3,5)
  lo=v[:,:,[0,2]].min(axis=(0,1));hi=v[:,:,[0,2]].max(axis=(0,1))
  if hi[0]<cut.bounds[0] or lo[0]>cut.bounds[2] or hi[1]<cut.bounds[1] or lo[1]>cut.bounds[3]:continue
  kept=[];changed=0;area_removed=0;collar_start=len(parts[3])
  mins=v[:,:,[0,2]].min(axis=1);maxs=v[:,:,[0,2]].max(axis=1)
  candidates=(maxs[:,0]>=cut.bounds[0])&(mins[:,0]<=cut.bounds[2])&(maxs[:,1]>=cut.bounds[1])&(mins[:,1]<=cut.bounds[3])
  for index,t in enumerate(v):
   if not candidates[index]:kept.extend(t);continue
   original=Polygon(t[:,[0,2]])
   if not original.intersects(cut):kept.extend(t);continue
   clipped=original.difference(cut);changed+=1;area_removed+=original.area-clipped.area
   inverse=np.linalg.inv(np.column_stack((t[:,[0,2]],np.ones(3))))
   for xy in triangles(clipped):kept.extend(np.column_stack((xy,np.ones(3)))@inverse@t)
   for xy in triangles(original.intersection(collar)):
    values=np.column_stack((xy,np.ones(3)))@inverse@t
    for j,p in enumerate(xy):
     point=Point(p);edge,heights=min(grade_edges,key=lambda e:e[0].distance(point));fraction=edge.project(point,normalized=True);target=heights[0]*(1-fraction)+heights[1]*fraction
     inner=footprint.distance(point);outer=cut.boundary.distance(point);weight=outer/max(inner+outer,1e-10)
     values[j,1]+=weight*(target-values[j,1])
    parts[3].extend(values);plane_override(values[:,:3])
  if not changed:continue
  vertices=np.asarray(kept,dtype='<f4');payload=raw[:32]+struct.pack('<3i4B',len(vertices),w,h,255,255,255,255)+vertices.tobytes()+raw[48+n*20:];path.write_bytes(payload)
  altered.append({'file':entry['file'],'beforeSha256':hashlib.sha256(raw).hexdigest(),'afterSha256':hashlib.sha256(payload).hexdigest(),'cutAreaSquareMetres':area_removed})
  # Convert this tile's collar UVs into the shared true-resolution orthophoto.
  e,north=map(int,path.stem.split('-')[1:])
  for p in parts[3][collar_start:]:
   p[3:5]=[(e+100*p[3]-ctx['BOUNDS'][0])/(ctx['BOUNDS'][2]-ctx['BOUNDS'][0]),(ctx['BOUNDS'][3]-north-100+100*p[4])/(ctx['BOUNDS'][3]-ctx['BOUNDS'][1])]
 textures=[Image.new('RGBA',(1,1),c)for c in [(184,182,174,255),(71,71,67,255),(22,23,23,255)]]+[ctx['photo']]
 arr=np.asarray(parts[3]);uv=arr[:,3:5];size=np.array(ctx['photo'].size);low=np.maximum(0,np.floor(uv.min(axis=0)*size).astype(int)-2);high=np.minimum(size,np.ceil(uv.max(axis=0)*size).astype(int)+2)
 arr[:,3:5]=(uv*size-low)/(high-low);parts[3]=arr.tolist();textures[3]=ctx['photo'].crop((*low,*high))
 name='galileo-east-ramps.ect';(out/name).write_bytes(encode(list(zip(parts,textures))));all_xyz=np.concatenate([np.asarray(p)[:,:3]for p in parts])
 meta['tiles'].append({'file':name,'runtimeId':1_000_030_022,'kind':'reconstruction','profile':'galileo-east-ramps','collisionHeightfieldParts':[1,3],'bounds':[all_xyz.min(0).tolist(),all_xyz.max(0).tolist()]})
 meta.setdefault('terrainOverrides',[]).extend(overrides)
 rings=[list(p.exterior.coords)for p in cut.geoms]if cut.geom_type=='MultiPolygon'else[list(cut.exterior.coords)]
 for ring in rings:meta['replacements'].append({'ring':ring,'y0':float(all_xyz[:,1].min())-2,'y1':float(all_xyz[:,1].max())+1})
 meta['architecture']['galileoRamps']={'sourceFile':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'ramps':records,'cutRingsMC':rings,'cutAreaSquareMetres':cut.area,'alteredGroundTiles':altered,'collisionPlaneCount':len(overrides),'qualification':spec['qualification']}
 print('Galileo ramps:',round(cut.area,2),'m² bounded cut;',len(altered),'ground tiles;',len(overrides),'collision planes',flush=True)

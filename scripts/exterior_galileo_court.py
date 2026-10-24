"""Bounded Galileo Tiefhof reconstruction from OSM, BVV heights and exterior references.

The mapped envelope/27 risers are source facts. Flight stations, wall thickness,
parapets and lower exterior glazing are explicitly inferred, not as-built survey.
"""
import hashlib,json,struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union,nearest_points
import mapbox_earcut


def triangles(poly):
 for p in ([poly] if poly.geom_type=='Polygon' else getattr(poly,'geoms',[])):
  if p.geom_type!='Polygon' or p.area<1e-10:continue
  rings=[np.asarray(r.coords[:-1]) for r in [p.exterior,*p.interiors]]
  xy=np.concatenate(rings);ends=np.cumsum([len(r) for r in rings]).astype('uint32')
  for t in mapbox_earcut.triangulate_float64(xy,ends).reshape(-1,3):yield xy[t]


def build(ctx):
 root,out,meta,mc,encode=[ctx[k] for k in ['ROOT','OUT','metadata','mc','encode']]
 source=root/'minecraft/exterior/photos/galileo-north-court-reference.json';spec=json.loads(source.read_text())
 features={f['osmWay']:f for f in spec['osmSource']['features']}
 court=Polygon(features[579584070]['coordinatesMC'])
 wall=np.array(features[983606071]['coordinatesMC']);a,b=np.array(features[983606072]['coordinatesMC'])
 direction=(b-a)/np.linalg.norm(b-a);left=np.array([-direction[1],direction[0]])
 # OSM centreline and 4m width overlap the mapped retaining wall by ~0.5m.
 # Register the stair 0.65m west so its eastern edge meets the wall face.
 a=a+left*.65;b=b+left*.65
 # Calibrate only horizontal conversion; all new physical heights still go
 # through the same GCG2016 / local ECEF datum conversion as the survey mesh.
 utm=np.array([[698200,5349300],[698300,5349300],[698200,5349400]],float)
 projected=mc(np.column_stack((utm,np.full(3,475))))[:,[0,2]]
 inverse=np.linalg.solve(np.column_stack((projected,np.ones(3))),utm)
 def to_utm(xy):return np.column_stack((xy,np.ones(len(xy))))@inverse
 def at(xy,heights):return mc(np.column_stack((to_utm(np.asarray(xy)),np.broadcast_to(heights,len(xy)))))
 def surveyed(xy):return ctx['elevation'].sample(to_utm(np.asarray(xy)))
 floor=470.56;upper=474.86
 # Five stair flights and four intermediate landings follow the repeated
 # plateaux in DGM1. Exact individual tread positions cannot be surveyed at 1m.
 flights=[(0.,2.,6,473.91),(4.,5.8,5,473.10),(7.8,9.6,5,472.29),(11.5,13.3,5,471.48),(15.,17.2,6,floor)]
 stair=Polygon([a+direction*s+left*t for s,t in [(-1,-2),(22.2,-2),(22.2,2),(-1,2)]])
 # Lower turning apron connects the mapped stair endpoint to the open end of
 # the west retaining wall. All cut geometry stays in this explicit envelope.
 turn=Polygon([a+direction*s+left*t for s,t in [(19.9,-2.35),(22.2,-2.35),(22.2,2),(19.9,2)]])
 footprint=unary_union([court,stair,turn]).buffer(0)
 wall_foot=LineString(wall).buffer(.18,cap_style=2,join_style=2)
 cut=footprint.buffer(1.8,join_style=2)
 # Do not reconstruct inside any surveyed building footprint. Keep the court
 # south edge exactly at its mapped exterior and clip its exterior collar.
 buildings=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in r[1:]]).buffer(0) for _,surfaces in ctx['buildings'] for kind,r in surfaces if kind=='GroundSurface'])
 cut=cut.difference(buildings).buffer(0)
 assert cut.geom_type=='Polygon' and cut.is_valid
 parts=[[],[],[],[],[]] # concrete, glazing, metal, floor, terrain collar
 def quad(index,xyz):
  xyz=np.asarray(xyz)
  for k in [0,1,2,0,2,3]:parts[index].append([*xyz[k],*[(0,1),(1,1),(1,0),(0,0)][k]])
 def slab(poly,height,index=0):
  for xy in triangles(poly):
   q=at(xy,height)
   for p in q:parts[index].append([*p,0.5,0.5])
 def box_line(start,end,width,bottom,top,index=0):
  u=end-start;u=u/np.linalg.norm(u);n=np.array([-u[1],u[0]])*width/2
  xy=np.array([start-n,end-n,end+n,start+n]);lo=at(xy,bottom);hi=at(xy,top)
  quad(index,hi)
  for i,j in [(0,1),(1,2),(2,3),(3,0)]:quad(index,[lo[i],lo[j],hi[j],hi[i]])
 # Floor is a restrained, explicit plane at the median of 874 interior DGM
 # samples. Real aerial colour and mapped surface detail remain registered.
 floor_poly=court.difference(wall_foot)
 # Include the small turn at the southern stair end, bounded by mapped court.
 floor_poly=unary_union([floor_poly,turn,stair.intersection(Polygon([a+direction*s+left*t for s,t in [(17.2,-2),(22.2,-2),(22.2,2),(17.2,2)]]))])
 for xy in triangles(floor_poly):
  q=at(xy,floor);uv=ctx['photo_uv'](np.column_stack((to_utm(xy),np.full(len(xy),floor))))
  for p,t in zip(q,uv):parts[3].append([*p,*t])
 # Upper grade is measured outside the east/north retaining walls. Use a
 # continuous plane rather than following the smoothed DGM down the wall face.
 def upper_at(xy):
  xy=np.asarray(xy);return upper+np.clip((xy[:,1]+168.5)/26,0,1)*.22
 for start,end in zip(wall[:-1],wall[1:]):
  steps=max(1,int(np.ceil(np.linalg.norm(end-start)/2.5)))
  for i in range(steps):
   p=start+(end-start)*i/steps;q=start+(end-start)*(i+1)/steps
   h=float(upper_at([(p+q)/2])[0]);box_line(p,q,.36,floor-.12,h+.85)
   # Slightly projecting coping, with actual depth and shadow at the wall top.
   box_line(p,q,.42,h+.85,h+.92)
 # Outer stair retaining wall and grade collar. Wall dimensions are estimates.
 outer_a=a+left*2.16;outer_b=a+direction*22.2+left*2.16
 box_line(outer_a,outer_b,.32,floor-.12,upper+.85)
 box_line(outer_a,outer_b,.40,upper+.85,upper+.92)
 # Closed rear retaining face; the bottom landing turns east into the court.
 box_line(a+direction*22.2-left*2.35,a+direction*22.2+left*2.16,.32,floor-.12,upper+.12)
 stair_surfaces=[];cursor=-1.;previous=upper
 for start,end,count,landing in flights:
  if start>cursor:stair_surfaces.append((cursor,start,previous))
  for i in range(count):
   lo=start+(end-start)*i/count;hi=start+(end-start)*(i+1)/count;h=previous+(landing-previous)*(i+1)/count
   stair_surfaces.append((lo,hi,h))
   xy=np.array([a+direction*lo-left*2,a+direction*lo+left*2])
   top=previous+(landing-previous)*i/count
   quad(0,[*at(xy,h),*at(xy[::-1],top)])
  cursor=end;previous=landing
 stair_surfaces.append((cursor,22.2,floor))
 overrides=[]
 for lo,hi,h in stair_surfaces:
  ring=np.array([a+direction*s+left*t for s,t in [(lo,-2),(hi,-2),(hi,2),(lo,2)]])
  if lo<17.2:slab(Polygon(ring),h)
  overrides.append({'ring':ring.tolist(),'height':float(at([ring.mean(axis=0)],h)[0,1])})
 # Slim tubular handrails follow the stair profile; render-only so their
 # centimetre widths do not turn into metre-wide invisible game barriers.
 railing=[]
 def rail(p,q,radius=.024):
  d=q-p;d/=np.linalg.norm(d);u=np.cross(d,[0,1,0]);u/=np.linalg.norm(u);v=np.cross(d,u)
  ring=[u*np.cos(t)+v*np.sin(t) for t in np.linspace(0,2*np.pi,9)[:-1]]
  for i in range(8):
   pts=[p+ring[i]*radius,q+ring[i]*radius,q+ring[(i+1)%8]*radius,p+ring[(i+1)%8]*radius]
   for k in [0,1,2,0,2,3]:railing.append([*pts[k],.5,.5])
 for side in [-1.8,1.8]:
  for start,end,count,landing in flights:
   above=upper if start==0 else next(h for lo,hi,h in stair_surfaces if abs(hi-start)<1e-6)
   xy=np.array([a+direction*start+left*side,a+direction*end+left*side]);q=at(xy,[above+.88,landing+.88]);rail(q[0],q[1])
  for lo,hi,h in stair_surfaces:
   if hi-lo<.6:continue
   xy=np.array([a+direction*lo+left*side,a+direction*hi+left*side]);q=at(xy,h+.88);rail(q[0],q[1])
 # Lower north-facing exterior glazing closes the missing survey-base band;
 # its pane rhythm is inferred from completed exterior photos, not interiors.
 south_a=np.array(court.exterior.coords[5]);south_b=np.array(court.exterior.coords[2]);length=np.linalg.norm(south_b-south_a);u=(south_b-south_a)/length
 bays=int(round(length/1.45))
 for i in range(bays):
  p=south_a+u*length*i/bays;q=south_a+u*length*(i+1)/bays
  xyz=np.concatenate([at([p,q],floor+.15),at([q,p],474.67)])
  quad(1,xyz);box_line(p,q,.13,floor, floor+.15,2);box_line(p,q,.15,474.60,474.75,2)
  box_line(p,p+u*.06,.15,floor,474.75,2)
 # Clip the original ground mesh exactly, retaining original XYZ and UVs
 # through barycentric interpolation at the cut boundary. Outside triangles
 # remain byte-identical; no broad flattening or vertex deletion shortcut.
 altered=[];collar=cut.difference(footprint.union(wall_foot))
 collar_values=[]
 for entry in meta['tiles']:
  if entry['kind']!='ground':continue
  path=out/entry['file'];raw=path.read_bytes();n,w,h=struct.unpack_from('<3i',raw,32)
  v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=48).reshape(-1,3,5)
  lo=v[:,:,[0,2]].min(axis=(0,1));hi=v[:,:,[0,2]].max(axis=(0,1))
  if hi[0]<cut.bounds[0] or lo[0]>cut.bounds[2] or hi[1]<cut.bounds[1] or lo[1]>cut.bounds[3]:continue
  kept=[];changed=0;area_removed=0
  mins=v[:,:,[0,2]].min(axis=1);maxs=v[:,:,[0,2]].max(axis=1)
  candidates=(maxs[:,0]>=cut.bounds[0])&(mins[:,0]<=cut.bounds[2])&(maxs[:,1]>=cut.bounds[1])&(mins[:,1]<=cut.bounds[3])
  for index,t in enumerate(v):
   if not candidates[index]:kept.extend(t);continue
   original=Polygon(t[:,[0,2]])
   if not original.intersects(cut):kept.extend(t);continue
   clipped=original.difference(cut);changed+=1;area_removed+=original.area-clipped.area
   matrix=np.column_stack((t[:,[0,2]],np.ones(3)))
   for xy in triangles(clipped):
    weights=np.column_stack((xy,np.ones(3)))@np.linalg.inv(matrix)
    kept.extend(weights@t)
   # Rebuild only the narrow outer collar on the same triangles, rising to
   # the surveyed upper promenade at the new wall and matching every cut edge.
   for xy in triangles(original.intersection(collar)):
    weights=np.column_stack((xy,np.ones(3)))@np.linalg.inv(matrix);values=weights@t
    for j,p in enumerate(xy):
     inner=footprint.distance(Point(p));outer=cut.boundary.distance(Point(p));weight=outer/max(inner+outer,1e-10)
     target=at([p],upper_at([p]))[0,1]
     values[j,1]+=weight*(target-values[j,1])
    parts[4].extend(values);collar_values.extend(values)
  if not changed:continue
  pixels=raw[48+n*20:];vertices=np.asarray(kept,dtype='<f4');payload=raw[:32]+struct.pack('<3i4B',len(vertices),w,h,255,255,255,255)+vertices.tobytes()+pixels
  path.write_bytes(payload);altered.append({'file':entry['file'],'beforeSha256':hashlib.sha256(raw).hexdigest(),'afterSha256':hashlib.sha256(payload).hexdigest(),'intersectedTriangles':changed,'cutAreaSquareMetres':area_removed})
 # Collar UVs came from 100m tiles; convert to the shared true-resolution image.
 # Recover UTM from XY instead of depending on which original tile supplied it.
 if parts[4]:
  arr=np.asarray(parts[4]);xy=to_utm(arr[:,[0,2]]);arr[:,3:5]=ctx['photo_uv'](np.column_stack((xy,np.zeros(len(xy)))));parts[4]=arr.tolist()
 assert all(parts) and len(altered)<=2
 textures=[Image.new('RGBA',(1,1),c)for c in [(191,189,180,255),(43,55,57,255),(79,83,80,255)]]+[ctx['photo'],ctx['photo']]
 # Crop aerial textures to this courtyard while preserving exact registration.
 for index in [3,4]:
  arr=np.asarray(parts[index]);uv=arr[:,3:5];size=np.array(ctx['photo'].size);low=np.maximum(0,np.floor(uv.min(axis=0)*size).astype(int)-2);high=np.minimum(size,np.ceil(uv.max(axis=0)*size).astype(int)+2)
  arr[:,3:5]=(uv*size-low)/(high-low);parts[index]=arr.tolist();textures[index]=ctx['photo'].crop((*low,*high))
 name='galileo-north-court.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
 xyz=np.concatenate([np.asarray(p)[:,:3] for p in parts]);meta['tiles'].append({'file':name,'runtimeId':1_000_030_020,'kind':'reconstruction','profile':'galileo-court','bounds':[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()]})
 if railing:
  name='galileo-court-handrails.ect';(out/name).write_bytes(encode([(railing,Image.new('RGBA',(1,1),(104,108,104,255)))]));xyz=np.asarray(railing)[:,:3]
  meta['tiles'].append({'file':name,'runtimeId':1_000_030_021,'kind':'reconstruction','profile':'galileo-court-handrails','collisionParts':[],'bounds':[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()]})
 floor_y=float(at([np.array(court.centroid.coords[0])],floor)[0,1]);overrides.append({'ring':list(court.exterior.coords),'height':floor_y})
 meta.setdefault('terrainOverrides',[]).extend(overrides)
 meta['replacements'].append({'ring':list(cut.exterior.coords),'holes':[list(r.coords)for r in cut.interiors],'y0':floor_y-2,'y1':float(at([[104,-156]],upper+1.2)[0,1])})
 meta['architecture']['galileoCourt']={'sourceFile':str(source.relative_to(root/'minecraft/exterior')),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'courtRingMC':list(court.exterior.coords),'cutRingMC':list(cut.exterior.coords),'cutHolesMC':[list(r.coords)for r in cut.interiors],'cutAreaSquareMetres':cut.area,'floorHeightDHHN2016':floor,'floorHeightMC':floor_y,'upperNorthHeightDHHN2016':upper,'stairWidthMetres':4,'stairCentrelineOffsetWestMetres':.65,'stairLowerLandingExtensionMetres':22.2-float(np.linalg.norm(b-a)),'stairRisers':27,'stairFlights':[{'startMetres':s,'endMetres':e,'risers':n,'lowerHeightDHHN2016':h}for s,e,n,h in flights],'alteredGroundTiles':altered,'terrainGuideUnchanged':True,'collisionOverrideCount':len(overrides),'qualification':'OSM envelope, 4m stair width and 27 risers; BVV floor/landing/upper heights. Flight endpoints, concrete thickness/parapets/handrails and lower exterior glazing rhythm are estimates supported by completed exterior photo and landscape design, not an as-built survey. No interior; no reference photographs redistributed.'}
 print('Galileo courtyard:',round(cut.area,2),'m² bounded terrain cut;',len(altered),'ground tiles; 27 risers / 5 flights',flush=True)

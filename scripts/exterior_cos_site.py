"""COS ground surfaces and mapped furniture; dimensions/layout details inferred."""
import hashlib,json,math
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon,LineString,box,mapping,shape
from shapely.ops import transform,unary_union
import mapbox_earcut


def build(ctx,mapped,existing_paths):
 root,out,meta,mc,encode=[ctx[k]for k in ['ROOT','OUT','metadata','mc','encode']]
 source=root/'minecraft/exterior/cos-site.json';spec=json.loads(source.read_text());ways={w['osmWay']:w for w in spec['ways']};est=spec['estimates']
 to_utm=Transformer.from_crs(4326,25832,always_xy=True).transform;to_geo=Transformer.from_crs(25832,4326,always_xy=True).transform
 xy={key:np.array([to_utm(*p)for p in way['coordinates']])for key,way in ways.items()}
 footprint=Polygon(meta['siteGrading']['footprintUtm']);limit=footprint.buffer(22).intersection(box(*meta['boundsUtm']))
 buildings=unary_union([Polygon(np.asarray(r[0])[:,:2],[np.asarray(h)[:,:2]for h in r[1:]]).buffer(0)for _,surfaces in ctx['buildings']for kind,r in surfaces if kind=='GroundSurface'])
 mapped_area=unary_union([transform(to_utm,shape(f['geometry'])).buffer(0)for f in mapped['features']+existing_paths])
 exclusion=buildings.union(mapped_area);claimed=exclusion;features=[];stats=[]
 def add(key,geom,material,qualification,**details):
  nonlocal claimed
  geom=geom.intersection(limit).difference(claimed)
  if geom.is_empty:return
  claimed=claimed.union(geom);way=ways[key]
  features.append({'type':'Feature','properties':{'osmWay':key,'version':way['version'],'timestamp':way['timestamp'],'tags':way['tags'],'material':material,'qualification':qualification,**details},'geometry':mapping(transform(to_geo,geom))})
  stats.append({'osmWay':key,'material':material,'areaSquareMetres':round(geom.area,2),'qualification':qualification,**details})
 # This closed mapped walk surrounds the completed building. The current photo
 # supports infilling the apron between its outer half-width and the facade.
 add(1489202329,Polygon(xy[1489202329]).buffer(est['perimeterWalkWidthMetres']/2,join_style=2),'paving','Mapped perimeter centre-line plus estimated outer half-width; facade apron infilled from current exterior reference.')
 for key,width in [(28038705,est['northDriveWidthMetres']),(1365740003,est['southDriveWidthMetres']),(172828680,est['mainWestWalkWidthMetres']),(1489202326,est['entrancePathWidthMetres']),(1489202330,est['entrancePathWidthMetres']),(1365740352,1.8),(1365740353,1.8),(1365740354,1.8)]:
  material='asphalt'if ways[key]['tags']['surface']=='asphalt'else'paving'
  add(key,LineString(xy[key]).buffer(width/2,cap_style=2,join_style=2),material,f'Mapped centre-line and surface; estimated {width:g}m width, bounded to COS surroundings.')
 add(1489202325,Polygon(xy[1489202325]),'paving','Mapped bicycle-parking boundary; paving inferred from finished forecourt context.')
 # Plan-informed infill uses the surveyed south edge as its local frame.
 # Existing mapped polygons, paths and building footprints retain precedence.
 ring=np.asarray(meta['siteGrading']['footprintUtm']);anchor=ring[4];east=ring[1]-anchor;east/=np.linalg.norm(east);outward=np.array([east[1],-east[0]])
 assert np.linalg.norm(ring[1]-anchor)>28
 for feature in spec['inferredLandscape']['surfaces']:
  polygon=Polygon([anchor+east*x+outward*y for x,y in feature['ring']])
  add(feature['relatedOsmWay'],polygon,feature['material'],feature['qualification'],inferred=True,reconstructionId=feature['id'])
 result={'type':'FeatureCollection','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','qualification':est['note'],'features':features}
 surface_file=out/'cos-site-surfaces.geojson';surface_file.write_text(json.dumps(result,separators=(',',':')))
 assert unary_union([transform(to_utm,shape(f['geometry']))for f in features]).intersection(exclusion).area<.001

 # Wood grain is a narrow part of the already licensed COS timber photograph.
 ref=json.loads((root/'minecraft/exterior/photos/cos-reference.json').read_text());photo=root/'minecraft/exterior/photos/cos-reference.webp'
 assert hashlib.sha256(photo.read_bytes()).hexdigest()==ref['sha256']
 timber=Image.open(photo).convert('RGBA').transform((384,256),Image.Transform.QUAD,ref['timberQuad'],Image.Resampling.BICUBIC).crop((64,0,80,256))
 textures=[timber,Image.new('RGBA',(1,1),(176,178,170,255)),Image.new('RGBA',(1,1),(137,148,151,255)),Image.new('RGBA',(1,1),(176,178,170,255))];parts=[[],[],[],[]]
 def quad(p,part):
  for i in [0,1,2,0,2,3]:parts[part].append([*p[i],*[(0,1),(1,1),(1,0),(0,0)][i]])
 def extrude(poly,bottom,top,part):
  for p in ([poly]if poly.geom_type=='Polygon'else getattr(poly,'geoms',[])):
   if p.geom_type!='Polygon' or p.area<1e-7:continue
   rings=[np.array(p.exterior.coords[:-1])]+[np.array(h.coords[:-1])for h in p.interiors];points=np.concatenate(rings)
   lo=points.min(0);span=np.maximum(points.max(0)-lo,.001)
   indices=mapbox_earcut.triangulate_float64(points,np.cumsum([len(r)for r in rings]).astype(np.uint32))
   for y in [bottom,top]:
    for i in indices:
     x,z=points[i];parts[part].append([x,y,z,*((points[i]-lo)/span)])
   for ring in rings:
    for a,b in zip(ring,np.roll(ring,-1,axis=0)):quad([[a[0],bottom,a[1]],[b[0],bottom,b[1]],[b[0],top,b[1]],[a[0],top,a[1]]],part)
 def ground(points):return mc(np.column_stack((points,ctx['elevation'].sample(points))))
 benches=[]
 for key in [1489202327,1489202328]:
  p=ground(xy[key]);line=LineString(p[:,[0,2]]);width=est['benchWidthMetres'];bottom=float(p[:,1].min())-.03;top=float(p[:,1].max())+est['benchSeatHeightMetres']
  base=line.buffer(width/2-.045,cap_style=2,join_style=2);extrude(base,bottom,top-.07,1)
  owned=Polygon()
  for a,b in zip(p,p[1:]):
   direction=(b-a)[[0,2]];length=np.linalg.norm(direction);direction/=length;normal=np.array([-direction[1],direction[0]])
   for offset in np.linspace(-width/2+.045,width/2-.045,5):
    start=a[[0,2]]+normal*offset;end=b[[0,2]]+normal*offset
    plank=LineString([start,end]).buffer(.045,cap_style=2,join_style=2).difference(owned);extrude(plank,top-.06,top,0);owned=owned.union(plank)
  target=np.array(line.interpolate(.5,normalized=True).coords[0]);benches.append({'osmWay':key,'lengthMetres':line.length,'seatTopY':top,'baseGroundYRange':[float(p[:,1].min()),float(p[:,1].max())],'rayTargetMC':[float(target[0]),top-.02,float(target[1])],'note':'Mapped backless wooden bench line; slats, concrete support and dimensions inferred.'})
 def tube(a,b,radius=.022):
  a,b=np.array(a),np.array(b);axis=b-a;axis/=np.linalg.norm(axis);seed=np.array([0.,1.,0.])if abs(axis[1])<.9 else np.array([1.,0.,0.]);u=np.cross(axis,seed);u/=np.linalg.norm(u);v=np.cross(axis,u)
  circle=[radius*(math.cos(t)*u+math.sin(t)*v)for t in np.linspace(0,2*math.pi,9)]
  for x,y in zip(circle,circle[1:]):quad([a+x,b+x,b+y,a+y],2)
 rack=xy[1489202325][:-1];edges=np.roll(rack,-1,axis=0)-rack;edge=edges[np.argmax(np.linalg.norm(edges,axis=1))];length=np.linalg.norm(edge);u=edge/length;v=np.array([-u[1],u[0]]);centre=rack.mean(axis=0);stands=[]
 for offset in np.linspace(-length/2+.35,length/2-.35,est['bicycleStands']):
  pos=centre+u*offset
  # A small tubular inverted-U stand. Its inferred arrangement fits the mapped
  # parking footprint and 20-bicycle capacity; no invented parked bicycles.
  path=[(-.4,0),(-.4,.64),(-.37,.72),(-.3,.78),(-.2,.8),(.2,.8),(.3,.78),(.37,.72),(.4,.64),(.4,0)]
  footprint_xy=np.array([pos+v*s for s,_ in path]);base=float(ground(np.array([pos]))[0,1]);q=mc(np.column_stack((footprint_xy,np.full(len(path),ctx['height'](*pos)))));q[:,1]=base+np.array([h for _,h in path])
  for a,b in zip(q,q[1:]):tube(a,b)
  stands.append(q[4].tolist())
 # Follow the sloping ground with short curb sections, leaving gaps where
 # the mapped benches already bound the bed. Thin edging is render-only.
 bed=next(transform(to_utm,shape(f['geometry']))for f in features if f['properties'].get('reconstructionId')=='entrance-planting-bed')
 occupied=unary_union([LineString(xy[k]).buffer(est['benchWidthMetres']/2+.08)for k in [1489202327,1489202328]])
 border=bed.boundary.difference(occupied);curb=spec['inferredLandscape']['curb'];curb_targets=[]
 for line in ([border]if border.geom_type=='LineString'else border.geoms):
  for lo,hi in zip(np.arange(0,line.length,.5),np.minimum(np.arange(0,line.length,.5)+.5,line.length)):
   a=np.array(line.interpolate(lo).coords[0]);b=np.array(line.interpolate(hi).coords[0]);direction=b-a;direction/=np.linalg.norm(direction);normal=np.array([-direction[1],direction[0]])*curb['widthMetres']/2
   xy4=np.array([a-normal,b-normal,b+normal,a+normal]);bottom=ground(xy4);bottom[:,1]-=.025;top=bottom.copy();top[:,1]+=curb['heightMetres']+.025
   quad(top,3)
   for i,j in [(0,1),(1,2),(2,3),(3,0)]:quad([bottom[i],bottom[j],top[j],top[i]],3)
   curb_targets.append(top.mean(0).tolist())
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);name='cos-site-furniture.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'cos-site','runtimeId':1_000_030_011,'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()],'collisionParts':[0,1]})
 data={'sourceFile':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'derivedFile':surface_file.name,'derivedSha256':hashlib.sha256((out/'cos-site-surfaces.geojson').read_bytes()).hexdigest(),'surfaces':stats,'benches':benches,'bicycleStands':len(stands),'rackTargetsMC':stands,'curbLengthMetres':border.length,'curbTargetsMC':curb_targets,'note':est['note']+' Thin rack tubes are decorative and do not create metre-wide invisible collision barriers; benches retain collision.'}
 meta['architecture']['cosSite']=data
 print('COS site:',len(features),'surface patches, two mapped benches and',len(stands),'inferred bicycle stands',flush=True)
 return features,data

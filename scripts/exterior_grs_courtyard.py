"""Bounded, reference-informed GRS courtyard path; preserve survey terrain."""
import hashlib,json
import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon,LineString,shape,mapping
from shapely.ops import unary_union,transform

def build(ctx,mapped):
 root,out,meta,mc,encode=[ctx[k]for k in ['ROOT','OUT','metadata','mc','encode']]
 source=root/'minecraft/exterior/photos/grs-courtyard-reference.json';spec=json.loads(source.read_text());path_spec=spec['path']
 # Invert the local horizontal survey frame at constant physical elevation.
 utm=np.array([[698000,5349300],[698100,5349300],[698000,5349400]],dtype=float)
 projected=mc(np.column_stack((utm,np.full(3,475))))[:,[0,2]]
 inverse=np.linalg.solve(np.column_stack((projected,np.ones(3))),utm)
 def to_utm(x,z,z_unused=None):
  result=np.column_stack((np.atleast_1d(x),np.atleast_1d(z),np.ones(np.size(x))))@inverse
  return result[:,0],result[:,1]
 to_geo=Transformer.from_crs(25832,4326,always_xy=True).transform
 geo_to_utm=Transformer.from_crs(4326,25832,always_xy=True).transform
 building_footprints=unary_union([Polygon(np.asarray(r[0])[:,:2],[np.asarray(h)[:,:2]for h in r[1:]]).buffer(0)for _,surfaces in ctx['buildings']for kind,r in surfaces if kind=='GroundSurface'])
 occupied=unary_union([transform(geo_to_utm,shape(f['geometry'])).buffer(0)for f in mapped])
 line=transform(to_utm,LineString(path_spec['centrelineMC']))
 candidate=line.buffer(path_spec['widthMetres']/2,cap_style=2,join_style=2)
 path=candidate.difference(building_footprints.buffer(.05)).difference(occupied)
 assert not path.is_empty and path.intersection(building_footprints).area<1e-6 and path.intersection(occupied).area<1e-6
 feature={'type':'Feature','properties':{'reconstructionId':'grs-courtyard-approach','material':'paving','inferred':True,'qualification':'Historical courtyard photograph and survey-aligned door/east path; estimated 1.8m width. Existing mapped surfaces and building footprints excluded.'},'geometry':mapping(transform(to_geo,path))}
 target=out/'grs-courtyard-surfaces.geojson';target.write_text(json.dumps({'type':'FeatureCollection','features':[feature]},separators=(',',':')))
 # Low longitudinal edging follows the same DGM sample used by the ground mesh.
 # Keep the two ends open, and avoid neighbouring buildings/mapped surfaces.
 vertices=[];targets=[];length=0
 def quad(points):
  for i in [0,1,2,0,2,3]:vertices.append([*points[i],*[(0,1),(1,1),(1,0),(0,0)][i]])
 def ground(xy):return mc(np.column_stack((xy,ctx['elevation'].sample(xy))))
 for offset in [-path_spec['widthMetres']/2,path_spec['widthMetres']/2]:
  edge=line.parallel_offset(abs(offset),'left'if offset>0 else'right',join_style=2).difference(building_footprints.buffer(.12)).difference(occupied)
  for seg in ([edge]if edge.geom_type=='LineString'else edge.geoms):
   length+=seg.length
   for lo in np.arange(0,seg.length,.4):
    hi=min(lo+.4,seg.length);a=np.array(seg.interpolate(lo).coords[0]);b=np.array(seg.interpolate(hi).coords[0]);u=b-a;u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])*path_spec['edgeWidthMetres']/2
    xy=np.array([a-n,b-n,b+n,a+n]);bottom=ground(xy);bottom[:,1]-=.025;top=bottom.copy();top[:,1]+=path_spec['edgeHeightMetres']+.025
    quad(top)
    for i,j in [(0,1),(1,2),(2,3),(3,0)]:quad([bottom[i],bottom[j],top[j],top[i]])
    targets.append(top.mean(axis=0).tolist())
 assert vertices
 name='grs-courtyard-edging.ect';(out/name).write_bytes(encode([(vertices,Image.new('RGBA',(1,1),(166,169,160,255)))]))
 xyz=np.asarray(vertices)[:,:3];meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'grs-courtyard','alwaysVisible':True,'runtimeId':1_000_030_019,'bounds':[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()],'collisionParts':[]})
 data={'sourceFile':str(source.relative_to(root/'minecraft/exterior')),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'derivedFile':target.name,'derivedSha256':hashlib.sha256(target.read_bytes()).hexdigest(),'pavingAreaSquareMetres':path.area,'estimatedPathWidthMetres':path_spec['widthMetres'],'edgeLengthMetres':length,'edgeHeightMetres':path_spec['edgeHeightMetres'],'edgeTargetsMC':targets,'terrainUnchanged':True,'note':'Inferred narrow path and low edging from historical exterior reference. Mapped surfaces/building footprints excluded. Edging is render-only to avoid metre-wide invisible barriers; no new terrain, interiors or courtyard-wide paving.'}
 meta['architecture']['grsCourtyard']=data
 print('GRS courtyard:',round(path.area,2),'m² bounded paving and low edging; terrain unchanged',flush=True)
 return [feature],data

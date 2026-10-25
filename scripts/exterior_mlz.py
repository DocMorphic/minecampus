"""MLZ workshop/laboratory exteriors: surveyed bodies and individually sourced openings."""
import hashlib,json,math,struct
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
import mapbox_earcut


def build(ctx,bid,walls):
 root,out,meta,encode=[ctx[k]for k in ['ROOT','OUT','metadata','encode']]
 source=root/'minecraft/exterior/mlz-exteriors.json';spec=json.loads(source.read_text())
 if bid not in spec['buildings']:return
 config=spec['buildings'][bid]
 assert hashlib.sha256((root/'minecraft/exterior'/spec['reference']).read_bytes()).hexdigest()==spec['referenceSha256']
 assert len(walls)==config['expectedWallCount']
 assert hashlib.sha256(json.dumps(walls,sort_keys=True,separators=(',',':')).encode()).hexdigest()==config['surveyWallsSha256']
 base=min(w['bounds'][0][1]for w in walls);top=max(w['bounds'][1][1]for w in walls)
 textures=[Image.new('RGBA',(1,1),c)for c in [(221,223,219,255),(49,67,74,255),(49,53,54,255),(27,30,31,255)]]
 parts=[[]for _ in textures];evidence=[];depth=spec['recessMetres'];frame=spec['frameMetres']
 def pt(x,y,z=0):
  p=anchor+direction*x+normal*z;p[1]=y;return p
 def quad(points,part):
  for i in [0,1,2,0,2,3]:parts[part].append([*points[i],*[(0,1),(1,1),(1,0),(0,0)][i]])
 def polygons(shape):return [shape]if shape.geom_type=='Polygon'else [p for p in getattr(shape,'geoms',[])if p.geom_type=='Polygon']
 def surface(shape,part,inset=0):
  for poly in polygons(shape):
   if poly.area<1e-7:continue
   rings=[np.asarray(poly.exterior.coords[:-1])]+[np.asarray(h.coords[:-1])for h in poly.interiors];xy=np.concatenate(rings)
   for i in mapbox_earcut.triangulate_float64(xy,np.cumsum([len(r)for r in rings]).astype(np.uint32)):
    x,y=xy[i];parts[part].append([*pt(x,y,-inset),float((x-l)/max(rgt-l,.01)),float((y-base)/max(top-base,.01))])
 for index,w in enumerate(walls):
  anchor,direction,normal=[np.asarray(w[k])for k in ['anchor','direction','normal']]
  shape=Polygon(w['rings'][0],w['rings'][1:]).buffer(0);l,b,rgt,t=shape.bounds;original_area=shape.area
  # Only proven coincident portions are removed. UYL's taller body retains its
  # exposed upper wall above the lower body's roof.
  for pair in spec['sharedWalls']:
   if [bid,index]in [pair['a'],pair['b']]:
    low,high=pair['occludedHeightRangeMC'];shape=shape.difference(box(l-.01,low,rgt+.01,high))
  face=config['faces'].get(str(index),{'openings':[],'basis':spec['unlistedFaces']})
  features=[]
  for opening in face['openings']:
   low,high=opening['heightAboveBase'];x0,x1=opening['alongFraction'];left,right=l+(rgt-l)*x0,l+(rgt-l)*x1
   if 'axisEndpointsMC'in face:
    a,c=map(np.asarray,face['axisEndpointsMC']);axis=c-a
    points=[a+axis*f for f in [x0,x1]]
    left,right=sorted(float((np.array([p[0],0,p[1]])-anchor)@direction)for p in points)
   patch=shape.intersection(box(left,base+low,right,base+high))
   if patch.area<1e-5:continue
   features.append((patch,opening))
  opening_union=unary_union([p for p,_ in features]);solid=shape.difference(opening_union)
  # Thin geometrical joints between large concrete panels. Dark backing closes
  # every joint; it is not a hole through the surveyed wall.
  surface(solid,2,.02);module=spec['panelModuleMetres'];gap=spec['panelJointMetres']/2
  for x in np.arange(math.floor(l/module)*module,rgt,module):
   for y in np.arange(base,top,module):surface(solid.intersection(box(x+gap,y+gap,x+module-gap,y+module-gap)),0)
  controls=[]
  for patch,opening in features:
   kind=opening['kind'];inset=.65 if kind=='entrance'else depth
   surface(patch,3 if kind=='service-door'else 1,inset)
   for poly in polygons(patch):
    ring=np.asarray(poly.exterior.coords[:-1]);
    for i in range(len(ring)):
     a,c=ring[i],ring[(i+1)%len(ring)];quad([pt(*a),pt(*c),pt(*c,-inset),pt(*a,-inset)],0)
    # Border frames follow the clipped opening, so split survey faces cannot
    # produce an exposed strip of glass outside the actual wall polygon.
    surface(poly.difference(poly.buffer(-frame,join_style=2)),2,max(0,inset-.06))
    x0,y0,x1,y1=poly.bounds
    if kind!='service-door':
     count=max(1,round((x1-x0)/1.2))
     for x in np.linspace(x0,x1,count+1)[1:-1]:surface(poly.intersection(box(x-frame/2,y0,x+frame/2,y1)),2,inset-.06)
     if y1-y0>1.8:surface(poly.intersection(box(x0,y1-.55,x1,y1-.55+frame)),2,inset-.06)
    else:
     # A quiet seam establishes the closed service door without inventing an interior.
     surface(poly.intersection(box((x0+x1)/2-frame/2,y0,(x0+x1)/2+frame/2,y1)),2,inset-.03)
    point=poly.representative_point();controls.append({'kind':kind,'positionMC':pt(point.x,point.y,-inset).tolist(),'normalMC':normal.tolist(),'areaSquareMetres':poly.area})
  w['reconstructed']=True
  evidence.append({'surveyPhotoFace':index,'sourceBasis':face['basis'],'originalAreaSquareMetres':original_area,'hiddenSharedAreaSquareMetres':original_area-shape.area,'openings':controls})
 raw=(out/(bid+'-photo-roof.ect')).read_bytes();assert raw[:4]==b'ECT1'and struct.unpack_from('<i',raw,4)[0]==1
 count,width,height=struct.unpack_from('<iii',raw,32);roof=np.frombuffer(raw,dtype='<f4',count=count*5,offset=48).reshape((-1,5)).copy()
 parts.append(roof.tolist());textures.append(Image.frombytes('RGBA',(width,height),raw[48+count*20:]))
 assert all(parts),'Each MLZ body must contain wall, glazing, frame, service/entry and roof parts'
 vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);name=bid+'-mlz-exterior.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
 meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'mlz-exterior','fineCollisionMaterials':spec['fineCollisionMaterials'],'alwaysVisible':True,'runtimeId':config['runtimeId'],'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
 grounds=[ctx['mc'](rings[0])for name,surfaces in ctx['buildings']if name==bid for typ,rings in surfaces if typ=='GroundSurface']
 foot=unary_union([Polygon(q[:,[0,2]])for q in grounds]).buffer(spec['sourceRetirement']['collarMetres'],join_style=2)
 neighbours=unary_union([Polygon(ctx['mc'](r[0])[:,[0,2]],[ctx['mc'](h)[:,[0,2]]for h in r[1:]]).buffer(0)for name,surfaces in ctx['buildings']if name not in spec['buildings']for typ,r in surfaces if typ=='GroundSurface']).buffer(spec['sourceRetirement']['neighbourGuardMetres'])
 foot=foot.difference(neighbours)
 rings=[{'ring':list(p.exterior.coords),'holes':[list(r.coords)for r in p.interiors]}for p in polygons(foot)]
 for ring in rings:meta['replacements'].append(dict(ring,y0=base-.1,y1=top+spec['sourceRetirement']['roofPaddingMetres'],kind='architecture',alwaysVisible=True))
 record=meta['architecture'].setdefault('mlzExteriors',{'sourceFile':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'qualification':spec['qualification'],'buildings':{}})
 record['buildings'][bid]={'name':config['name'],'runtimeId':config['runtimeId'],'faces':evidence,'roofSourceSha256':hashlib.sha256(raw).hexdigest(),'retirement':rings}
 print('MLZ:',bid,len(controls),'last-face controls;',sum(len(f['openings'])for f in evidence),'opening pieces; exact survey roof retained',flush=True)
 return rings

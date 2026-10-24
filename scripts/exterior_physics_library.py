"""Source-informed Physics library exterior with an open, column-supported base."""
import hashlib,json,math
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
import mapbox_earcut
from exterior_physics_i import nearby_surveys,survey_plan,roof_texture,polygons
from exterior_terrain import ElevationSampler


def triangles(shape):
    for p in polygons(shape):
        if p.area<1e-8:continue
        rings=[np.asarray(r.coords[:-1]) for r in [p.exterior,*p.interiors]]
        xy=np.concatenate(rings)
        for t in mapbox_earcut.triangulate_float64(xy,np.cumsum([len(r)for r in rings]).astype(np.uint32)).reshape(-1,3):yield xy[t]


def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    source=root/'minecraft/exterior/physics-library.json';spec=json.loads(source.read_text());bid=spec['building']
    assert hashlib.sha256((root/'minecraft/exterior'/spec['reference']).read_bytes()).hexdigest()==spec['referenceSha256']
    surveys=nearby_surveys(cache);surfaces=next(s for key,s in surveys if key==bid)
    footprint,walls,roof,points=survey_plan(ctx,surfaces);assert len(walls)==9
    base=float(points[:,1].min());levels={k:base+v for k,v in spec['levelsAboveSurveyBase'].items()}
    parts=[[],[],[],[]];textures=[Image.new('RGBA',(1,1),tuple(c))for c in spec['materialColours']]
    controls=[]
    def emit(q,part,normal=None):
        q=np.asarray(q)
        if normal is not None and np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0:q=q[::-1]
        for i in ([0,1,2]if len(q)==3 else [0,1,2,0,2,3]):parts[part].append([*q[i],.5,.5])
    def horizontal(poly,y,part=0,up=True):
        for xy in triangles(poly):emit(np.column_stack((xy[:,0],np.full(3,y),xy[:,1])),part,[0,1 if up else -1,0])
    def post(x,z,bottom,top):
        h=spec['columnWidthMetres']/2;ring=np.array([[x-h,z-h],[x+h,z-h],[x+h,z+h],[x-h,z+h]])
        for a,b in zip(ring,np.roll(ring,-1,axis=0)):emit([[a[0],bottom,a[1]],[b[0],bottom,b[1]],[b[0],top,b[1]],[a[0],top,a[1]]],0)
        horizontal(Polygon(ring),top)
    # Local body basis follows the measured south edge and west side.
    front=walls[6];a=np.array(front['anchor']);u=np.array(front['direction']);south=np.array(front['normal']);width=front['bounds'][1][0]
    corners=np.array([walls[6]['vertices'][0],walls[6]['vertices'][1],walls[7]['vertices'][0],walls[3]['vertices'][3]])[:,[0,2]]
    body=Polygon(corners)
    assert body.difference(footprint).area<.01
    # Thin bottom diaphragm closes the upper volume; the outside remains open below.
    inset=spec['lowerEdgeInsetMetres'];lower=body.buffer(-inset,join_style=2)
    horizontal(lower,levels['underside'],up=False);horizontal(body,levels['concreteEdgeTop'])
    # Join the mitred inset corners, rather than independently offsetting each
    # wall's edge, which would leave triangular gaps at the four corners.
    upper_ring=np.asarray(body.exterior.coords[:-1]);lower_ring=np.asarray(lower.exterior.coords[:-1])
    assert len(upper_ring)==len(lower_ring)==4
    paired=[lower_ring[np.argmin(np.linalg.norm(lower_ring-p,axis=1))]for p in upper_ring]
    for i in range(4):
        j=(i+1)%4;p,q=upper_ring[i],upper_ring[j];a0,b0=paired[i],paired[j]
        emit([[a0[0],levels['underside'],a0[1]],[b0[0],levels['underside'],b0[1]],
              [q[0],levels['concreteEdgeTop'],q[1]],[p[0],levels['concreteEdgeTop'],p[1]]],0)
    for t in [spec['columnInsetMetres'],width-spec['columnInsetMetres']]:
        for depth in [spec['columnInsetMetres'],19.136-spec['columnInsetMetres']]:
            q=a+u*t-south*depth;post(q[0],q[2],base-.2,levels['underside'])
    # Bridge remains attached at the surveyed rear wall; its lower volume is open.
    bridge=footprint.difference(body)
    horizontal(bridge,levels['bridgeFloor']-.25,up=False);horizontal(bridge,levels['bridgeFloor'])
    for index,wall in enumerate(walls):
        anchor,direction,normal=[np.asarray(wall[k])for k in ['anchor','direction','normal']]
        shape=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0);left,bottom,right,top=shape.bounds
        def pt(x,y,depth=0):
            p=anchor+direction*x+normal*depth;p[1]=y;return p
        def surface(poly,part,depth=0):
            for tri in triangles(poly):emit([pt(x,y,depth)for x,y in tri],part,normal)
        if index in [0,5,8]:
            # Bridge side glazing uses the survey's stepped upper silhouette.
            wallshape=shape.intersection(box(left,levels['bridgeFloor'],right,top))
            opening=wallshape.intersection(box(left+.14,levels['bridgeFloor']+.18,right-.14,top-.25))
            surface(wallshape.difference(opening),2);surface(opening,1,-spec['recessMetres'])
            for x in np.arange(left+1.45,right,1.45):surface(opening.intersection(box(x-.045,bottom,x+.045,top)),2,-.11)
        else:
            wallshape=shape.intersection(box(left,levels['concreteEdgeTop'],right,top))
            surface(wallshape.intersection(box(left,levels['fasciaBottom'],right,top)),2)
            windows=[];pitch=(right-left)/spec['facadeBays'] if index in [3,6,7] else 3.18
            count=max(1,round((right-left)/pitch));pitch=(right-left)/count
            for bay in range(count):
                x0,x1=left+bay*pitch+.09,left+(bay+1)*pitch-.09
                for y0,y1 in [(levels['concreteEdgeTop']+.10,levels['lowerGlassTop']),(levels['upperGlassBottom'],levels['fasciaBottom']-.1)]:
                    opening=wallshape.intersection(box(x0,y0,x1,y1))
                    if opening.is_empty:continue
                    windows.append(opening)
                    louvres=y0==levels['upperGlassBottom'] and(index!=6 or bay in spec['southUpperLouvreBays'])
                    surface(opening,3 if louvres else 1,-spec['recessMetres'])
                    surface(opening.difference(opening.buffer(-.055,join_style=2)),2,-.10)
                    if louvres:
                        for y in np.arange(y0+.06,y1,.19):
                            band=opening.intersection(box(x0,y,x1,min(y+.075,y1)))
                            for tri in triangles(band):
                                emit([pt(x,h,-.10+(h-y)/.075*.125)for x,h in tri],2,normal)
                    elif y0==levels['upperGlassBottom']:
                        for y in np.arange(y0+.65,y1,.65):surface(opening.intersection(box(x0,y-.035,x1,y+.035)),2,-.1)
                    # The lower window is the externally testable pane on each face.
                    if not louvres:
                        p=opening.representative_point();controls.append({'face':index,'part':1,'position':pt(p.x,p.y,-spec['recessMetres']).tolist(),'normal':normal.tolist()})
            surface(wallshape.difference(unary_union(windows)).intersection(box(left,levels['concreteEdgeTop'],right,levels['fasciaBottom'])),2)
            for x in np.arange(left+pitch,right-.02,pitch):
                surface(wallshape.intersection(box(x-.012,levels['fasciaBottom'],x+.012,top)),3,.01)
        wall['reconstructed']=True
    roof_vertices,roof_photo=roof_texture(cache,roof);parts.append(roof_vertices.tolist());textures.append(roof_photo)
    assert all(parts)
    name=bid+'-physics-library.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
    vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
    meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'physics-library','runtimeId':spec['runtimeId'],'bounds':bounds})
    roofname=bid+'-photo-roof.ect';(out/roofname).write_bytes(encode([(roof_vertices,roof_photo)]))
    # Retire only this building's source scan; preserve adjacent surveyed bodies.
    neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface']).buffer(.35)
    cleanup=footprint.buffer(spec['cleanupMarginMetres'],join_style=2).difference(neighbours)
    rings=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(cleanup)]
    plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id']for p in plans['plans']]
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roofname,'collisionFile':roofname,'bounds':[points.min(0).tolist(),points.max(0).tolist()],'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':rings,'retirementBoundary':rings})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roofname)
    meta['photoFacades']['collisionRetirement'].extend(dict(r,y0=base-2,y1=float(points[:,1].max())+4)for r in rings)
    # Fill only the half-metre footprint guard omitted by the surrounding ground.
    original_utm=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for kind,r in surfaces if kind=='GroundSurface'])
    other_utm=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface'])
    ground_area=original_utm.buffer(.5,join_style=1).difference(other_utm);lo=np.floor(np.array(ground_area.bounds[:2])).astype(int);hi=np.ceil(np.array(ground_area.bounds[2:])).astype(int)
    with rasterio.open(cache/'campus-dgm-east.tif')as dem:
        sampler=ElevationSampler([dem]);ground_vertices=[]
        def xyz(xy):return mc(np.column_stack([xy,sampler.sample(xy)]))
        for n in range(lo[1],hi[1]):
            for e in range(lo[0],hi[0]):
                for xy in triangles(ground_area.intersection(box(e,n,e+1,n+1))):ground_vertices.extend(np.column_stack([xyz(xy),np.full((3,2),.5)]).tolist())
        guide_xy=np.array([(e,n)for n in range(lo[1],hi[1]+1)for e in range(lo[0],hi[0]+1)])
        guide={'width':int(hi[0]-lo[0]+1),'height':int(hi[1]-lo[1]+1),'points':xyz(guide_xy).tolist()}
        gr=[{'ring':xyz(np.asarray(p.exterior.coords))[:,[0,2]].tolist(),'holes':[]}for p in polygons(ground_area)]
    floorname='physics-library-ground.ect';(out/floorname).write_bytes(encode([(ground_vertices,Image.new('RGBA',(1,1),(138,134,121,255)))]))
    gv=np.asarray(ground_vertices)[:,:3];meta['tiles'].append({'file':floorname,'kind':'ground','runtimeId':spec['groundRuntimeId'],'bounds':[gv.min(0).tolist(),gv.max(0).tolist()]})
    meta.setdefault('supplementalSurfaces',[]).append({'name':'physics-library-undercroft','rings':gr,'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':False,'qualification':'DGM1 ground beneath raised library. Paving appearance is an estimate; no interior.'})
    meta['architecture']['physicsLibrary']={'building':bid,'generatorFile':'scripts/exterior_physics_library.py','generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'sourceFile':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'qualification':spec['qualification'],'groundTiles':[floorname],'surveyWalls':walls,'openingControls':controls,'retirement':rings,'levelsMC':levels,'bodyFootprint':list(body.exterior.coords),'columnCount':4,'roofTriangles':len(roof)//3}
    print('Physics library:',len(walls),'survey faces,',len(controls),'glazed controls, open undercroft, estimated columns/louvres',flush=True)

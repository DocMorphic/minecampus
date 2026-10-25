"""CALA's surveyed shell, planted roof and explicitly approximate facade detail."""
import hashlib
import json
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ('ROOT','CACHE','OUT','metadata','mc','encode')]
    source = root/'minecraft/exterior/physics-cala.json'
    spec = json.loads(source.read_text()); bid = spec['building']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert spec['runtimeId'] not in [t.get('runtimeId') for t in meta['tiles']]
    surveys = nearby_surveys(cache, spec['surveyBoundsUTM'])
    raw = next(s for key,s in surveys if key == bid)
    footprint, walls, roof, points = survey_plan(ctx,raw)
    assert len(walls)==8 and len(roof)==18
    parts=[[],[],[],[]]; textures=[Image.new('RGBA',(1,1),tuple(c)) for c in spec['materialColours']]
    controls=[];base=float(points[:,1].min())
    from exterior_terrain import ElevationSampler
    with rasterio.open(cache/'campus-dgm-east.tif') as raster: entrance_elevation=ElevationSampler([raster])
    latitude,longitude=np.radians(meta['origin'][:2])
    frame_origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    frame_basis=np.array([[-np.sin(longitude),np.cos(longitude),0],[np.cos(latitude)*np.cos(longitude),np.cos(latitude)*np.sin(longitude),np.sin(latitude)],[np.sin(latitude)*np.cos(longitude),np.sin(latitude)*np.sin(longitude),-np.cos(latitude)]])
    entrance_inverse=Transformer.from_crs(4978,25832,always_xy=True)
    def road_height(p):
        en=np.array(entrance_inverse.transform(*((p-[0,64,0])@frame_basis+frame_origin)))[:2]
        return float(mc(np.array([[*en,entrance_elevation(*en)]]))[0,1])

    def emit(q,part,normal):
        q=np.asarray(q,dtype=float)
        if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0:q=q[::-1]
        for i in ([0,1,2] if len(q)==3 else [0,1,2,0,2,3]):parts[part].append([*q[i],.5,.5])
    for index,wall in enumerate(walls):
        anchor,direction,normal=[np.asarray(wall[k]) for k in ('anchor','direction','normal')]
        region=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0);left,bottom,right,top=region.bounds
        region=region.union(box(left,base-spec['wallBaseExtensionMetres'],right,base+.01))
        def pt(x,y,depth=0):
            p=anchor+direction*x+normal*depth;p[1]=y;return p
        def surface(poly,part,depth=0):
            for tri in triangles(poly):emit([pt(x,y,depth) for x,y in tri],part,normal)
        openings=[]
        for x0,y0,x1,y1 in spec['openings'].get(str(index),[]):
            ground_opening=y0<.2
            y0+=base;y1+=base
            if ground_opening:y0=max(y0,road_height(pt((x0+x1)/2,base,.5))+.04)
            assert y1-y0>2.0 or not ground_opening
            opening=box(x0,y0,x1,y1).intersection(region)
            assert abs(opening.area-(x1-x0)*(y1-y0))<.001
            openings.append(opening);inner=opening.buffer(-spec['frameWidthMetres'],join_style=2)
            surface(inner,2,-spec['recessMetres']);surface(opening.difference(inner),3,-.02)
            centre=(x0+x1)/2;surface(inner.intersection(box(centre-.035,y0,centre+.035,y1)),3,-.04)
            for a,b in zip(opening.exterior.coords[:-1],opening.exterior.coords[1:]):
                emit([pt(*a),pt(*b),pt(*b,-spec['recessMetres']),pt(*a,-spec['recessMetres'])],3,normal)
            # Shallow slab above ground-level doors; it has sides and an underside.
            if ground_opening and not (index==6 or (index==1 and x0<4)):
                a,b=x0-.25,x1+.25;y=y1+.12;d=spec['canopyDepthMetres'];thickness=.12
                emit([pt(a,y,d),pt(b,y,d),pt(b,y,0),pt(a,y,0)],3,[0,1,0])
                emit([pt(a,y-thickness,0),pt(b,y-thickness,0),pt(b,y-thickness,d),pt(a,y-thickness,d)],3,[0,-1,0])
                emit([pt(a,y-thickness,d),pt(b,y-thickness,d),pt(b,y,d),pt(a,y,d)],3,normal)
                for xx,side in [(a,-direction),(b,direction)]:emit([pt(xx,y-thickness,0),pt(xx,y-thickness,d),pt(xx,y,d),pt(xx,y,0)],3,side)
            controls.append({'kind':'estimated-opening','face':index,'part':2,'position':pt(x0+(x1-x0)*.3,(y0+y1)/2,-spec['recessMetres']).tolist(),'normal':normal.tolist()})
        cladding=region.difference(unary_union(openings));surface(cladding,1 if index in spec['lightEndFaces'] else 0)
        surface(cladding.intersection(box(left,top-.10,right,top+.01)),3,.01)
        if index in spec['southFaces']:
            # Reference-inspired marks are original geometry, not projected photo pixels.
            # Their spacing and shape are qualified approximations, deliberately not a logo transcription.
            for j,x in enumerate(np.arange(left+1.4,right-1.3,spec['motifPitchMetres'])):
                if j%3==0:motif=Point(x,base+2.8).buffer(2.35,resolution=24).intersection(box(x-2.5,base+.35,x,base+5.2))
                elif j%3==1:motif=box(x-.35,base+3.7,x+.35,base+5.2).union(box(x-.35,base+.5,x+.35,base+1.55))
                else:motif=Polygon([(x-1.1,base+.5),(x+1.1,base+.5),(x,base+3.4)])
                surface(motif.intersection(cladding),1,.006)
        wall['reconstructed']=True
        controls.append({'kind':'survey-wall','face':index,'part':1 if index in spec['lightEndFaces'] else 0,'position':pt(left+(right-left)*.43,top-.3).tolist(),'normal':normal.tolist()})
    rv,rp=roof_texture(cache,roof);parts.append(rv.tolist());textures.append(rp)
    parts.append([]);textures.append(Image.new('RGBA',(1,1),(195,195,185,255)))
    # The two main canopy outlines are estimated from elevated bright DOP/DOM
    # features. Their flat slab height and thickness remain qualified estimates.
    front_wall=walls[6];ca,cu,cn=[np.array(front_wall[k])for k in ('anchor','direction','normal')]
    for canopy in spec['canopies']:
        x0,x1=canopy['frontStartMetres'],canopy['frontEndMetres'];depth=canopy['depthMetres'];top=base+canopy['heightAboveBaseMetres'];bottom=top-.18
        def cpoint(x,y,d):
            p=ca+cu*x+cn*d;p[1]=y;return p
        emit([cpoint(x0,top,0),cpoint(x1,top,0),cpoint(x1,top,depth),cpoint(x0,top,depth)],5,[0,1,0])
        emit([cpoint(x0,bottom,depth),cpoint(x1,bottom,depth),cpoint(x1,bottom,0),cpoint(x0,bottom,0)],3,[0,-1,0])
        emit([cpoint(x0,bottom,depth),cpoint(x1,bottom,depth),cpoint(x1,top,depth),cpoint(x0,top,depth)],3,cn)
        for xx,side in [(x0,-cu),(x1,cu)]:emit([cpoint(xx,bottom,0),cpoint(xx,bottom,depth),cpoint(xx,top,depth),cpoint(xx,top,0)],3,side)
        controls.append({'kind':'estimated-canopy-top','part':5,'position':cpoint((x0+x1)/2,top,depth*.6).tolist(),'normal':[0,1,0]})
    assert all(parts)
    mesh=bid+'-cala.ect';(out/mesh).write_bytes(encode(list(zip(parts,textures))))
    vertices=np.concatenate([np.asarray(p)[:,:3] for p in parts]);bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','runtimeId':spec['runtimeId'],'bounds':bounds})
    roof_file=bid+'-photo-roof.ect';(out/roof_file).write_bytes(encode([(rv,rp)]))
    neighbours=unary_union([Polygon(mc(p[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in p[1:]]).buffer(0) for key,s in surveys if key!=bid for kind,p in s if kind=='GroundSurface']).buffer(.35)
    # Replace the old north/east earth slope as well as the shell. The hill is
    # measured terrain; reconstruct its DGM heights rather than flattening it.
    land=footprint.buffer(spec['cleanupMarginMetres'])
    for face,distance in [(0,spec['northSlopeMetres']),(5,spec['eastSlopeMetres'])]:
        w=walls[face];a=np.array(w['anchor']);direction=np.array(w['direction']);normal=np.array(w['normal'])
        left,_,right,_=Polygon(w['rings'][0],w['rings'][1:]).bounds
        p,q=a+direction*left,a+direction*right
        land=land.union(Polygon(np.array([p,q,q+normal*distance,p+normal*distance])[:,[0,2]]))
    # Rebuild the full street-side approach, excluding adjoining surveyed bodies.
    front=Polygon()
    for face in spec['southFaces']:
        w=walls[face];a,u,n=[np.array(w[k])for k in ('anchor','direction','normal')]
        left,_,right,_=Polygon(w['rings'][0],w['rings'][1:]).bounds;p,q=a+u*left,a+u*right
        front=front.union(Polygon(np.array([p,q,q+n*spec['southApronMetres'],p+n*spec['southApronMetres']])[:,[0,2]]))
    front=front.difference(neighbours.buffer(.85))
    land=land.union(front).difference(neighbours)
    lat,lon=np.radians(meta['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
    inverse=Transformer.from_crs(4978,25832,always_xy=True)
    def to_utm(ring):
        p=np.array([[x,0,z] for x,z in ring.coords]);return np.column_stack(inverse.transform(*(origin+p@basis).T))[:,:2]
    land_utm=unary_union([Polygon(to_utm(p.exterior),[to_utm(h) for h in p.interiors]) for p in polygons(land.difference(footprint.buffer(-.005)))])
    from exterior_ground_extension import build as extend_ground
    ground=extend_ground(ctx,land_utm,'physics-cala-ground',spec['groundRuntimeId'],spec['groundBlendMetres'])
    front_utm=unary_union([Polygon(to_utm(p.exterior),[to_utm(h)for h in p.interiors])for p in polygons(front)])
    from exterior_cala_site import build as build_site
    site=build_site(ctx,spec,front_utm,surveys)
    cleanup=land
    retirement=[{'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]} for p in polygons(cleanup)]
    plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id'] for p in plans['plans']]
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':bounds,'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roof_file)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=bounds[0][1]-2,y1=bounds[1][1]+3) for p in retirement)
    meta['architecture']['physicsCALA']={'building':bid,'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_cala.py','generatorSha256':sha(Path(__file__)),'meshFile':mesh,'roofFile':roof_file,'surveyWalls':walls,'roofTriangles':6,'retirement':retirement,'controls':controls,'groundTiles':ground['groundTiles'],'ground':ground,'site':site,'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),'qualification':spec['qualification'],'status':'Source-derived shell and survey-height slope; native visual acceptance required'}
    print('CALA:',len(walls),'survey walls, six original roof triangles,',sum(c['kind']=='estimated-opening'for c in controls),'estimated openings;',site['treeCount'],'street trees',flush=True)

"""Surveyed east-hall envelope with qualified exterior corrugation and glazing."""
import hashlib,json,math
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys,survey_plan,roof_texture,polygons
from exterior_physics_library import triangles
from exterior_terrain import ElevationSampler


def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ('ROOT','CACHE','OUT','metadata','mc','encode')]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/reactor-east.json';spec=json.loads(source.read_text());bid=spec['building']
    reference=root/'minecraft/exterior'/spec['reference'];surveys=nearby_surveys(cache,spec['siteBoundsUTM'])
    raw=next(s for key,s in surveys if key==bid);foot,walls,roof,points=survey_plan(ctx,raw)
    assert len(walls)==44 and len(roof)//3==67
    assert spec['runtimeId']not in [t['runtimeId']for t in meta['tiles']]
    parts=[[]for _ in spec['parts']];textures=[Image.new('RGBA',(1,1),c)for c in [(187,194,198,255),(189,196,199,255),(144,148,144,255),(64,83,89,255),(160,160,150,255),(120,131,137,255)]]
    def emit(q,part,normal):
        q=np.asarray(q,dtype=float);normal=np.asarray(normal,dtype=float);normal/=np.linalg.norm(normal)
        if np.cross(q[1]-q[0],q[2]-q[0])@normal<0:q=q[::-1]
        stored=q.astype(np.float32).astype(float)
        if np.linalg.norm(np.cross(stored[1]-stored[0],stored[2]-stored[0]))<1e-8:return
        octa=normal[[0,2]]/np.abs(normal).sum()
        if normal[1]<0:octa=(1-np.abs(octa[::-1]))*np.where(octa>=0,1,-1)
        uv=octa*.5+.5 if part in [0,1,5]else [.5,.5]
        parts[part].extend([[*p,*uv]for p in q])
    base=float(points[:,1].min());controls=[]
    for index,wall in enumerate(walls):
        anchor,direction,normal=[np.asarray(wall[k])for k in ('anchor','direction','normal')]
        region=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0);left,bottom,right,top=region.bounds
        def pt(x,y,depth=0):
            p=anchor+direction*x-normal*depth;p[1]=y;return p
        def surface(poly,part,depth=0):
            for tri in triangles(poly):emit([pt(x,y,depth)for x,y in tri],part,normal)
        openings=[];style='unobserved corrugated surface'
        if index in spec['westMainWalls']:
            openings.append(box(left+.18,base+7.0,right-.18,base+9.25));style='reactor-facing narrow glazing, estimated height'
        elif index in spec['endProjectionWalls']:
            openings.append(box(left+.18,top-4.6,right-.18,top-.3));style='stepped end projection glazing, inferred assignment'
        elif index in spec['endMainWalls']:
            openings.append(box(left+.5,base+10.1,right-.5,base+12.8));style='estimated end elevation glazing'
        windows=region.intersection(unary_union(openings))if openings else Polygon()
        plinth=region.intersection(box(left,bottom,right,base+.35)).difference(windows)
        # A closed service panel remains an exterior solid; no unmeasured entry.
        doors=Polygon()
        if index in spec['endMainWalls']:
            centre=(left+right)/2;doors=region.intersection(box(centre-2.3,base+.35,centre+2.3,base+4.7)).difference(windows)
        opaque=region.difference(windows.union(plinth).union(doors));surface(opaque,0);surface(plinth,2);surface(doors,5,.035)
        surface(windows,3,spec['windowRecessMetres'])
        frames=[]
        for p in polygons(windows):frames.append(p.difference(p.buffer(-spec['windowFrameMetres'],join_style=2)))
        for x in np.arange(left+spec['windowPitchMetres'],right,spec['windowPitchMetres']):frames.append(windows.intersection(box(x-.025,bottom,x+.025,top)))
        for p in polygons(windows):
            lo,bo,hi,to=p.bounds
            if to-bo>3.2:frames.append(p.intersection(box(lo,bo+1.5,hi,bo+1.56)))
        frame=unary_union(frames)if frames else Polygon();surface(frame,1,spec['windowRecessMetres']-.025)
        for p in polygons(windows.union(doors)):
            depth=.035 if doors.covers(p.representative_point())else spec['windowRecessMetres']
            for ring in [p.exterior,*p.interiors]:
                for a,b in zip(ring.coords[:-1],ring.coords[1:]):
                    q=[pt(*a),pt(*b),pt(*b,depth),pt(*a,depth)]
                    for ids in [(0,1,2),(0,2,3)]:
                        tri=np.asarray([q[k]for k in ids]);n=np.cross(tri[1]-tri[0],tri[2]-tri[0])
                        if np.linalg.norm(n)>1e-9:emit(tri,1,n)
        wall['reconstructed']=True
        p=opaque.representative_point();controls.append({'wall':index,'position':pt(p.x,p.y).tolist(),'normal':normal.tolist(),'part':0,'sourceArea':region.area,'opaqueArea':opaque.area,'glassArea':windows.area,'plinthArea':plinth.area,'doorArea':doors.area,'style':style})
    roof_vertices,roof_pixels=roof_texture(cache,roof);parts[4]=roof_vertices.tolist();textures[4]=roof_pixels;assert all(parts)
    mesh=bid+'-reactor-east.ect';(out/mesh).write_bytes(encode(list(zip(parts,textures))))
    vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','profile':'reactor-east','runtimeId':spec['runtimeId'],'fineCollisionMaterials':spec['fineCollisionMaterials'],'bounds':bounds})
    roof_file=bid+'-photo-roof.ect';assert not(out/roof_file).exists();(out/roof_file).write_bytes(encode([(roof_vertices,roof_pixels)]))
    neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface'])
    owned=foot.buffer(spec['cleanupMarginMetres']).difference(neighbours.buffer(spec['neighbourGuardMetres']))
    serialize=lambda shape:[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(shape)]
    retirement=serialize(owned);plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id']for p in plans['plans']]
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':bounds,'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roof_file)
    volumes=[dict(p,y0=bounds[0][1]-2,y1=bounds[1][1]+3)for p in retirement];meta['photoFacades']['collisionRetirement'].extend(volumes)
    # Measured datum enables wall/roof collision beyond the old terrain extent.
    datum_region=foot.buffer(spec['cleanupMarginMetres']).difference(neighbours);datum_rings=serialize(datum_region)
    lo=np.floor(np.array(datum_region.bounds[:2])/2)*2;hi=np.ceil(np.array(datum_region.bounds[2:])/2)*2
    flat=np.array([[x,64,z]for z in np.arange(lo[1],hi[1]+1,2)for x in np.arange(lo[0],hi[0]+1,2)])
    lat,lon=np.radians(meta['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]));basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
    inverse=Transformer.from_crs(4978,25832,always_xy=True);en=np.column_stack(inverse.transform(*((flat-[0,64,0])@basis+origin).T))[:,:2]
    with rasterio.open(cache/'campus-dgm-east.tif')as dem:flat[:,1]=mc(np.column_stack([en,ElevationSampler([dem]).sample(en)]))[:,1]
    meta['supplementalSurfaces'].append({'name':'reactor-east-envelope-datum','rings':datum_rings,'terrainGuide':{'width':int((hi[0]-lo[0])/2+1),'height':int((hi[1]-lo[1])/2+1),'points':flat.tolist()},'protectedFootprints':[],'outdoorReconstructed':False})
    record={'facades':controls,'partTriangles':[len(p)//3 for p in parts],'roofTriangles':len(roof)//3,'datumRings':datum_rings,'datumSourceSha256':sha(cache/'campus-dgm-east.tif'),'retirement':retirement,'protectedNeighbourOverlapSquareMetres':owned.intersection(neighbours).area,'qualification':spec['qualification']}
    derived=out/'reactor-east-surfaces.json';derived.write_text(json.dumps(record,indent=2)+'\n')
    meta['architecture']['reactorEast']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_reactor_east.py','generatorSha256':sha(Path(__file__)),'referenceFile':spec['reference'],'referenceSha256':sha(reference),'derivedFile':derived.name,'derivedSha256':sha(derived),'meshFile':mesh,'meshSha256':sha(out/mesh),'roofFile':roof_file,'roofSha256':sha(out/roof_file),'sourceRetirement':[{'rings':retirement,'y0':bounds[0][1]-2,'y1':bounds[1][1]+3}],'qualification':spec['qualification']}
    print('East hall:',len(walls),'walls;',len(roof)//3,'retained roof triangles',flush=True)

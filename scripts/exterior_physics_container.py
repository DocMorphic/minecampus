"""Survey-bounded TUM 5140 envelope; estimated openings from private source review."""
import hashlib,json
from pathlib import Path
import numpy as np
import rasterio
from exterior_terrain import ElevationSampler
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys,survey_plan,roof_texture,polygons
from exterior_physics_library import triangles


def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    source=root/'minecraft/exterior/physics-container.json';spec=json.loads(source.read_text());bid=spec['building']
    assert hashlib.sha256((root/'minecraft/exterior'/spec['reference']).read_bytes()).hexdigest()==spec['referenceSha256']
    surveys=nearby_surveys(cache);surfaces=next(s for key,s in surveys if key==bid)
    footprint,walls,roof,points=survey_plan(ctx,surfaces);assert len(walls)==8 and len(roof)==18
    parts=[[],[],[],[]];textures=[Image.new('RGBA',(1,1),tuple(c))for c in spec['materialColours']];controls=[]
    base=float(points[:,1].min())
    def emit(q,part,normal):
        q=np.asarray(q)
        if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0:q=q[::-1]
        for i in ([0,1,2]if len(q)==3 else [0,1,2,0,2,3]):parts[part].append([*q[i],.5,.5])
    for index,wall in enumerate(walls):
        anchor,direction,normal=[np.asarray(wall[k])for k in ['anchor','direction','normal']]
        shape=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0);left,bottom,right,top=shape.bounds
        shape=shape.union(box(left,base-.3,right,base+.01));bottom=base-.3
        def pt(x,y,depth=0):
            p=anchor+direction*x+normal*depth;p[1]=y;return p
        def surface(poly,part,depth=0):
            for tri in triangles(poly):emit([pt(x,y,depth)for x,y in tri],part,normal)
        openings=[]
        for rectangle in spec['openings'].get(str(index),[]):
            x0,y0,x1,y1=rectangle;y0+=base;y1+=base
            opening=box(x0,y0,x1,y1).intersection(shape);assert opening.area>0
            openings.append(opening)
            # Actual holes in the cladding with inset glass, white frame and reveals.
            inner=opening.buffer(-spec['frameWidthMetres'],join_style=2)
            surface(inner,1,-spec['recessMetres']);surface(opening.difference(inner),2,-.015)
            centre=(x0+x1)/2
            surface(inner.intersection(box(centre-.025,y0,centre+.025,y1)),2,-.035)
            for a,b in zip(np.asarray(opening.exterior.coords[:-1]),np.asarray(opening.exterior.coords[1:])):
                emit([pt(*a),pt(*b),pt(*b,-spec['recessMetres']),pt(*a,-spec['recessMetres'])],2,normal)
            # Thin sill, with a top surface, gives visible depth without a flat decal.
            emit([pt(x0,y0,.065),pt(x1,y0,.065),pt(x1,y0,-.13),pt(x0,y0,-.13)],2,[0,1,0])
            q=pt(x0+(x1-x0)*.25,(y0+y1)/2,-spec['recessMetres'])
            controls.append({'face':index,'part':1,'position':q.tolist(),'normal':normal.tolist()})
        cladding=shape.difference(unary_union(openings))
        surface(cladding.intersection(box(left,base+.27,right,top-.15)),0)
        surface(cladding.intersection(box(left,bottom-.01,right,base+.27)),3)
        surface(cladding.intersection(box(left,top-.15,right,top+.01)),3)
        # Panel joints are explicit, subtle geometry in local wall coordinates.
        for x in np.arange(left+spec['panelPitchMetres'],right-.05,spec['panelPitchMetres']):
            surface(cladding.intersection(box(x-.006,base+.27,x+.006,top-.15)),3,.004)
        surface(cladding.intersection(box(left,base+3.01,right,base+3.035)),3,.004)
        wall['reconstructed']=True
    roof_vertices,roof_photo=roof_texture(cache,roof);parts.append(roof_vertices.tolist());textures.append(roof_photo)
    assert all(parts)
    name=bid+'-physics-container.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
    vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
    meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'physics-container','runtimeId':spec['runtimeId'],'bounds':bounds})
    roofname=bid+'-photo-roof.ect';(out/roofname).write_bytes(encode([(roof_vertices,roof_photo)]))
    neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface']).buffer(.35)
    cleanup=footprint.buffer(spec['cleanupMarginMetres'],join_style=2).difference(neighbours)
    rings=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(cleanup)]
    plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id']for p in plans['plans']]
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roofname,'collisionFile':roofname,'bounds':[points.min(0).tolist(),points.max(0).tolist()],'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':rings,'retirementBoundary':rings})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roofname)
    meta['photoFacades']['collisionRetirement'].extend(dict(r,y0=base-2,y1=float(points[:,1].max())+4)for r in rings)
    # The surrounding survey ground excludes a half-metre guard around this
    # neighbouring footprint. Fill that exact omission so the solid body meets
    # terrain without a visible sky slit. The skirt material is an estimate.
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
        gr=[{'ring':xyz(np.asarray(p.exterior.coords))[:,[0,2]].tolist(),'holes':[xyz(np.asarray(h.coords))[:,[0,2]].tolist()for h in p.interiors]}for p in polygons(ground_area)]
    floorname='physics-container-ground.ect';(out/floorname).write_bytes(encode([(ground_vertices,Image.new('RGBA',(1,1),(138,134,121,255)))]))
    gv=np.asarray(ground_vertices)[:,:3];meta['tiles'].append({'file':floorname,'kind':'ground','runtimeId':spec['groundRuntimeId'],'bounds':[gv.min(0).tolist(),gv.max(0).tolist()]})
    meta.setdefault('supplementalSurfaces',[]).append({'name':'physics-container-footing','rings':gr,'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':False,'qualification':'DGM1 continuation into footprint guard; narrow concrete skirt appearance estimated. No interiors.'})
    meta['architecture']['physicsContainer']={'building':bid,'generatorFile':'scripts/exterior_physics_container.py','generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'sourceFile':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'qualification':spec['qualification'],'groundTiles':[floorname],'groundRings':gr,'surveyWalls':walls,'openingControls':controls,'retirement':rings,'roofTriangles':len(roof)//3,'surveyBaseMC':base}
    print('Physics container:',len(walls),'survey faces,',len(controls),'estimated paired windows; six original roof triangles',flush=True)

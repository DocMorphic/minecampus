"""Surveyed ZNN shell with qualified facade bands and projecting shading rails."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/physics-znn.json'
    spec = json.loads(source.read_text())
    assert sha(root/'minecraft/exterior'/spec['reference']) == spec['referenceSha256']
    bid = spec['building']
    surveys = nearby_surveys(cache, spec['surveyBoundsUtm'])
    raw = next(s for key,s in surveys if key == bid)
    footprint, walls, roof, points = survey_plan(ctx,raw)
    assert len(walls) == 13 and len(roof)//3 == 23
    base = float(points[:,1].min())
    parts = [[] for _ in spec['materialColours']]
    textures = [Image.new('RGBA',(1,1),tuple(c)) for c in spec['materialColours']]
    controls, rails, opaque_controls = [], [], []
    def emit(q, part, normal):
        q = np.asarray(q)
        if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal) < 0:
            q = q[::-1]
        for i in ([0,1,2] if len(q)==3 else [0,1,2,0,2,3]):
            parts[part].append([*q[i],.5,.5])
    for index, wall in enumerate(walls):
        anchor, direction, normal = [np.asarray(wall[k]) for k in ['anchor','direction','normal']]
        region = Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0)
        left,bottom,right,top = region.bounds
        if bottom <= base+.05:
            region = region.union(box(left,base-.6,right,base+.01))
        def point(x,y,depth=0):
            p = anchor+direction*x+normal*depth
            p[1] = y
            return p
        def surface(shape,part,depth=0):
            for tri in triangles(shape):
                emit([point(x,y,depth) for x,y in tri],part,normal)
        def projected(shape,part,depth):
            surface(shape,part,depth)
            for poly in polygons(shape):
                for ring in [poly.exterior,*poly.interiors]:
                    q = np.asarray(ring.coords)
                    for a,b in zip(q[:-1],q[1:]):
                        edge = direction*(b[0]-a[0])+np.array([0,b[1]-a[1],0])
                        side = np.cross(edge,normal)
                        if np.linalg.norm(side)>1e-9:
                            emit([point(*a),point(*b),point(*b,depth),point(*a,depth)],part,side)
        cuts = []
        for rectangle in spec['openings'].get(str(index),[]):
            x0,y0,x1,y1 = rectangle
            y0 += base; y1 += base
            opening = region.intersection(box(x0,y0,x1,y1))
            assert opening.area>0
            cuts.append(opening)
            inner = opening.buffer(-spec['frameWidthMetres'],join_style=2)
            bars = unary_union([box(x-.025,y0,x+.025,y1) for x in np.arange(x0+spec['mullionPitchMetres'],x1-.05,spec['mullionPitchMetres'])])
            glass = inner.difference(bars)
            surface(glass,1,-spec['windowRecessMetres'])
            surface(opening.difference(inner).union(inner.intersection(bars)),2,-.015)
            for poly in polygons(opening):
                q = np.asarray(poly.exterior.coords)
                for a,b in zip(q[:-1],q[1:]):
                    emit([point(*a),point(*b),point(*b,-spec['windowRecessMetres']),point(*a,-spec['windowRecessMetres'])],2,normal)
            rail = spec['shadingRail']
            for offset in rail['offsetsBelowOpeningTopMetres']:
                height = y1-offset
                strip = opening.intersection(box(x0,height-rail['heightMetres']/2,x1,height+rail['heightMetres']/2))
                projected(strip,2,rail['depthMetres'])
                q = strip.representative_point()
                rails.append({'face':index,'position':point(q.x,q.y,rail['depthMetres']).tolist(),'normal':normal.tolist(),'depthMetres':rail['depthMetres']})
            # Select a visible pane below the upper shading rails.
            pane = glass.intersection(box(x0,y0,x1,y1-1))
            q = pane.representative_point()
            controls.append({'face':index,'part':1,'position':point(q.x,q.y,-spec['windowRecessMetres']).tolist(),'normal':normal.tolist(),'rectangleAboveBase':rectangle})
        for rectangle in spec['opaqueOchrePanels'].get(str(index),[]):
            x0,y0,x1,y1 = rectangle
            panel = region.intersection(box(x0,base+y0,x1,base+y1))
            assert panel.area>0
            cuts.append(panel);surface(panel,4,-.035)
            panel_joints = unary_union([box(x-.008,base+y0,x+.008,base+y1) for x in np.arange(x0+spec['panelPitchMetres'],x1,spec['panelPitchMetres'])])
            surface(panel.intersection(panel_joints),3,-.03)
            q=panel.difference(panel_joints).representative_point()
            opaque_controls.append({'face':index,'part':4,'position':point(q.x,q.y,-.035).tolist(),'normal':normal.tolist()})
        solid = region.difference(unary_union(cuts))
        plant = index in spec['roofPlantFaces']
        surface(solid,3 if plant else 0)
        # Fine joints and shallow plant louvres remain estimated facade detail.
        if plant:
            for y in np.arange(bottom+.18,top,.18):
                projected(solid.intersection(box(left,y,right,y+.025)),2,.045)
        else:
            joints = unary_union([box(x-.006,bottom-.6,x+.006,top+.01) for x in np.arange(left+spec['panelPitchMetres'],right,spec['panelPitchMetres'])])
            surface(solid.intersection(joints),3,.002)
        wall['reconstructed'] = True
    roof_vertices, roof_image = roof_texture(cache,roof)
    parts.append(roof_vertices.tolist());textures.append(roof_image)
    assert all(parts)
    mesh = bid+'-znn-exterior.ect'
    (out/mesh).write_bytes(encode(list(zip(parts,textures))))
    vertices = np.concatenate([np.asarray(p)[:,:3] for p in parts])
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','runtimeId':spec['runtimeId'],'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
    roof_file = bid+'-photo-roof.ect'
    (out/roof_file).write_bytes(encode([(roof_vertices,roof_image)]))
    other = unary_union([Polygon(mc(p[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in p[1:]]).buffer(0) for key,s in surveys if key!=bid for kind,p in s if kind=='GroundSurface'])
    cleanup = footprint.buffer(spec['cleanupMarginMetres'],join_style=2).difference(other.buffer(spec['neighbourGuardMetres']))
    retirement = [{'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]} for p in polygons(cleanup)]
    plans = json.loads((out/'photo-facades.json').read_text())
    assert bid not in [p['id'] for p in plans['plans']]
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':[points.min(0).tolist(),points.max(0).tolist()],'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roof_file)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=base-2,y1=float(points[:,1].max())+4) for p in retirement)
    meta['architecture']['physicsZNN']={'building':bid,'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_znn.py','generatorSha256':sha(Path(__file__)),'meshFile':mesh,'roofFile':roof_file,'surveyWalls':walls,'roofTriangles':len(roof)//3,'baseMC':base,'openingControls':controls,'railControls':rails,'opaqueControls':opaque_controls,'retirement':retirement,'qualification':spec['qualification'],'status':'Unintegrated development geometry; surrounding ground, native materials and visual validation still required'}
    print('ZNN:',len(walls),'survey walls;',len(roof)//3,'roof triangles;',len(controls),'window bands;',len(rails),'projecting shading rails',flush=True)
    from exterior_physics_znn_landscape import build as build_landscape
    build_landscape(ctx, spec, surveys)

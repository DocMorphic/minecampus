"""Survey-envelope LMU physics/workshop facade reconstruction.

Photographs guide the concrete frame and recessed glazing. Exact subdivisions
are estimated and recorded independently of the original survey envelope.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely import set_precision
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union

from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles


def surface_triangles(poly):
    # Near-coincident cuts at a stepped survey corner can leave a vanishing
    # bridge between window holes. Earcut then fills those windows. Normalize
    # below mesh float32 precision before triangulating this facade only.
    yield from triangles(set_precision(poly,1e-7))


def build(ctx):
    root, cache, out, meta, encode = [ctx[k] for k in ('ROOT','CACHE','OUT','metadata','encode')]
    source = root/'minecraft/exterior/physics-lmu.json'
    spec = json.loads(source.read_text()); bid = spec['building']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert spec['runtimeId'] not in [t.get('runtimeId') for t in meta['tiles']]
    surveys = nearby_surveys(cache, spec['siteBoundsUTM'])
    surfaces = next(s for key,s in surveys if key == bid)
    footprint, walls, roof, points = survey_plan(ctx, surfaces)
    assert len(walls) == spec['wallCount'] and len(roof) == spec['roofTriangles']*3
    base = float(points[:,1].min())
    parts = [[],[],[],[]]
    textures = [Image.new('RGBA',(1,1),tuple(c)) for c in spec['materialColours']]
    controls, facade_records = [], []

    def emit(q, part, normal):
        q = np.asarray(q, dtype=float)
        if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal) < 0: q = q[::-1]
        for ids in ([[0,1,2]] if len(q)==3 else [[0,1,2],[0,2,3]]):
            t=q[ids].astype(np.float32).astype(float)
            if np.linalg.norm(np.cross(t[1]-t[0],t[2]-t[0]))<=1e-9:continue
            parts[part].extend([*v,.5,.5] for v in q[ids])

    for face,wall in enumerate(walls):
        a,u,n = [np.array(wall[k]) for k in ('anchor','direction','normal')]
        shape = Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0)
        left,bottom,right,top = shape.bounds
        width = right-left

        def pt(x,y,depth=0):
            q=a+u*x+n*depth; q[1]=y; return q

        def surface(poly,part,depth=0):
            for t in surface_triangles(poly): emit([pt(x,y,depth) for x,y in t],part,n)

        def edge_sides(poly,part,front,back,boundary=None):
            # Close every external and hole boundary so recesses/bands have
            # real depth when seen from the adjacent pavement.
            for p in polygons(poly):
                for ring in [p.exterior,*p.interiors]:
                    for c,d in zip(ring.coords[:-1],ring.coords[1:]):
                        tangent=np.array(d)-np.array(c)
                        side=u*tangent[1]-np.array([0,1,0])*tangent[0]
                        edge=LineString([c,d])
                        if boundary is not None:edge=edge.intersection(boundary)
                        segments=[edge] if edge.geom_type=='LineString' else list(getattr(edge,'geoms',[]))
                        for segment in segments:
                            if segment.geom_type!='LineString' or segment.length<1e-8:continue
                            for c0,d0 in zip(segment.coords[:-1],segment.coords[1:]):
                                emit([pt(*c0,front),pt(*d0,front),pt(*d0,back),pt(*c0,back)],part,side)

        is_plant=face in spec['plantFaces']
        is_office=face in spec['officeFaces']
        if is_plant:
            # The three surveyed rooftop volumes remain distinct. Their
            # weather screens are inferred, not photographic louvre detail.
            surface(shape,1)
            for y in np.arange(bottom+.12,top,.24):
                surface(shape.intersection(box(left,y,right,y+.035)),3,.02)
            facade_records.append({'face':face,'style':'estimated rooftop screen','bays':0})
            p=shape.intersection(box(left,bottom+.04,right,bottom+.08)).representative_point()
            controls.append({'kind':'survey-wall','face':face,'part':1,'position':pt(p.x,p.y).tolist(),'normal':n.tolist()})
            wall['reconstructed']=True
            continue

        if is_office:
            levels=[base+v for v in spec['officeLevelsAboveBase']]
        else:
            # Workshop lower and setback upper tiers are independently
            # bounded by survey rings, not stretched into four storeys.
            levels=[bottom,top]
        beams=[]
        for y in levels[1:]:
            beams.append(shape.intersection(box(left,y-spec['beamHeightMetres'],right,y)))
        if not beams or top > levels[-1]+.1:
            beams.append(shape.intersection(box(left,top-spec['beamHeightMetres'],right,top)))
        beam_shape=unary_union(beams)
        surface(beam_shape,0)
        front_pieces=[(beam_shape,0)]
        fill=shape.difference(beam_shape)
        windows=[]
        bays=max(1,round(width/spec['bayPitchMetres']))
        pitch=width/bays
        local_controls=[]
        for level,(y0,y1) in enumerate(zip(levels,levels[1:])):
            low=max(y0,bottom);high=min(y1-spec['beamHeightMetres'],top)
            if high-low<1.0: continue
            for bay in range(bays):
                x0=left+bay*pitch+.14;x1=left+(bay+1)*pitch-.14
                if x1-x0<.35:continue
                # Dark lower panels sit beneath the window; the unusually
                # tall workshop bays have a separate transom.
                sill=low+(.65 if is_office else .48)
                window=fill.intersection(box(x0,sill,x1,high-.12)).intersection(shape.buffer(-spec['recessMetres']-.15,join_style=2))
                if window.is_empty or window.area<.25:continue
                windows.append(window)
                recess=spec['recessMetres'];frame=spec['frameWidthMetres']
                pane=window.buffer(-frame,join_style=2)
                if pane.is_empty:continue
                surface(pane,2,-recess)
                surface(window.difference(pane),3,-recess+.035)
                edge_sides(window,3,-recess+.035,-recess)
                center=(x0+x1)/2
                surface(window.intersection(box(center-frame/2,sill,center+frame/2,high)),3,-recess+.04)
                transom=high-min(.65,(high-sill)*.3)
                surface(window.intersection(box(x0,transom-frame/2,x1,transom+frame/2)),3,-recess+.04)
                # A few blinds break repetition, following the observed
                # office facade. Their exact state is deliberately inferred.
                blind=is_office and (bay+level*3+face)%7==2
                if blind:
                    shade=window.intersection(box(x0,high-.8,x1,high))
                    surface(shade,3,-recess+.06)
                    for y in np.arange(high-.8,high,.10):
                        surface(shade.intersection(box(x0,y,x1,y+.018)),1,-recess+.065)
                p=pane.representative_point()
                # Shift away from the central mullion and top blind.
                target=window.intersection(box(x0+frame,sill+frame,center-frame,min(transom-frame,high-.85 if blind else high)))
                if not target.is_empty and target.area>.1:
                    p=target.representative_point()
                    local_controls.append({'kind':'estimated-window','face':face,'part':2,'position':pt(p.x,p.y,-recess).tolist(),'normal':n.tolist()})
        surface(fill.difference(unary_union(windows)),1,-spec['recessMetres'])
        # Ground concrete piers and finer upper metal posts sit at the outer
        # survey envelope, leaving the glass visibly recessed behind them.
        for k in range(bays+1):
            x=left+k*pitch
            for y0,y1 in zip(levels,levels[1:]):
                ground=y0 < base+.6
                half=(spec['groundColumnWidthMetres'] if ground else spec['upperPostWidthMetres'])/2
                post=fill.intersection(box(x-half,y0,x+half,y1))
                surface(post,0 if ground else 3)
                front_pieces.append((post,0 if ground else 3))
            for y0,y1 in zip(levels,levels[1:]):
                if y0<base+.6:continue
                rail=fill.intersection(box(left,y0+.78,right,y0+.86))
                if k==0:
                    surface(rail,3,-.04);edge_sides(rail,3,-.04,-.10)
        # Shared beam/post interfaces are internal. Infill used to close those
        # same planes again, producing visible coplanar stripes under every
        # band. Only the exposed frame perimeter owns these return surfaces.
        frame=unary_union([p for p,part in front_pieces])
        for piece,part in front_pieces:
            edge_sides(piece,part,0,-spec['recessMetres'],frame.boundary)
        edge_sides(shape,1,0,-spec['recessMetres'],shape.boundary.difference(frame))
        controls.extend(local_controls[::max(1,len(local_controls)//3)][:3])
        facade_records.append({'face':face,'style':'estimated office frame' if is_office else 'estimated workshop frame','bays':bays,'windowCount':len(windows),'levels':levels,'surveyArea':shape.area})
        wall['reconstructed']=True

    rv,rp=roof_texture(cache,roof);parts.append(rv.tolist());textures.append(rp)
    assert all(parts)
    mesh=bid+'-lmu.ect';(out/mesh).write_bytes(encode(list(zip(parts,textures))))
    vertices=np.concatenate([np.array(p)[:,:3] for p in parts])
    bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','runtimeId':spec['runtimeId'],'fineCollisionMaterials':spec['fineCollisionMaterials'],'bounds':bounds})
    roof_file=bid+'-photo-roof.ect';(out/roof_file).write_bytes(encode([(rv,rp)]))
    # Preserve the courtyard and neighbouring buildings. This is envelope
    # replacement only; landscaping and equipment remain separate work.
    neighbours=unary_union([Polygon(ctx['mc'](r[0])[:,[0,2]],[ctx['mc'](h)[:,[0,2]] for h in r[1:]]).buffer(0) for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface'])
    owned=footprint.buffer(spec['cleanupMarginMetres'],join_style=2).difference(neighbours.buffer(.25))
    # Connect the measured north frontage to the existing CALA street mesh.
    # A narrow foundation collar left unsupported pavement between the two.
    street=Polygon()
    for face in spec.get('streetApronFaces',[]):
        w=walls[face];a,u,n=[np.array(w[k]) for k in ('anchor','direction','normal')]
        left,_,right,_=Polygon(w['rings'][0],w['rings'][1:]).bounds
        p,q=a+u*left,a+u*right
        street=street.union(Polygon(np.array([p,q,q+n*spec['streetApronMetres'],p+n*spec['streetApronMetres']])[:,[0,2]]))
    owned=owned.union(street).difference(neighbours.buffer(.25))
    # Survey-height ground beneath the envelope also supplies the runtime's
    # bounded foundation datum. Without it, source collision cannot be migrated
    # outside the original campus grid. The open courtyard remains excluded.
    lat,lon=np.radians(meta['origin'][:2])
    origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
    inverse=Transformer.from_crs(4978,25832,always_xy=True)
    def utm_ring(ring):
        q=np.array([[x,64,z] for x,z in ring.coords])
        return np.column_stack(inverse.transform(*((q-[0,64,0])@basis+origin).T))[:,:2]
    owned_utm=unary_union([Polygon(utm_ring(p.exterior),[utm_ring(h) for h in p.interiors]) for p in polygons(owned)])
    from exterior_ground_extension import build as extend_ground
    ground=extend_ground(ctx,owned_utm,'physics-lmu-ground',spec['groundRuntimeId'],spec['groundBlendMetres'])
    retirement=[{'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]} for p in polygons(owned)]
    plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id'] for p in plans['plans']]
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':bounds,'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roof_file)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=bounds[0][1]-2,y1=bounds[1][1]+3) for p in retirement)
    meta['architecture']['physicsLMU']={'building':bid,'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_lmu.py','generatorSha256':sha(Path(__file__)),'meshFile':mesh,'roofFile':roof_file,'surveyWalls':walls,'roofTriangles':len(roof)//3,'groundTiles':ground['groundTiles'],'ground':ground,'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),'facades':facade_records,'retirement':retirement,'controls':controls,'qualification':spec['qualification'],'status':'Development geometry; native visual acceptance required'}
    print('LMU:',len(walls),'survey walls,',len(roof)//3,'roof triangles,',sum(x.get('windowCount',0) for x in facade_records),'estimated window panels',flush=True)

"""Measured west roof with qualified open projection and blue exterior glazing."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, survey_plan, polygons
from exterior_physics_library import triangles


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ('ROOT', 'CACHE', 'OUT', 'metadata', 'mc', 'encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/atom-ei-west-entrance.json'
    spec = json.loads(source.read_text()); bid = spec['building']
    surveys = dict(nearby_surveys(cache, spec['siteBoundsUTM']))
    foot, walls, roof, points = survey_plan(ctx, surveys[bid])
    assert len(roof)//3 == 10 and spec['runtimeId'] not in [t['runtimeId'] for t in meta['tiles']]
    roof_surfaces = [r for k,r in surveys[bid] if k == 'RoofSurface']
    assert len(roof_surfaces) == 1 and len(roof_surfaces[0]) == 1
    outline = mc(roof_surfaces[0][0]); region = Polygon(outline[:,[0,2]])
    plane = np.linalg.lstsq(np.column_stack([outline[:,[0,2]], np.ones(len(outline))]), outline[:,1], rcond=None)[0]
    assert np.max(np.abs(np.column_stack([outline[:,[0,2]],np.ones(len(outline))])@plane-outline[:,1])) < .0001
    roof_normal = np.array([-plane[0], 1, -plane[1]])
    parts = [[], [], [], []]
    colours = [(113,124,130,255), (76,87,94,255), (32,66,87,255), (51,70,78,255)]

    def emit(q, part, normal):
        q = np.asarray(q, dtype=float)
        normal = np.asarray(normal, dtype=float); normal /= np.linalg.norm(normal)
        if np.cross(q[1]-q[0],q[2]-q[0])@normal < 0: q = q[::-1]
        octa = normal[[0,2]]/np.abs(normal).sum()
        if normal[1] < 0: octa = (1-np.abs(octa[::-1]))*np.where(octa >= 0,1,-1)
        uv = octa*.5+.5 if part != 3 else np.array([.5,.5])
        stored = q.astype(np.float32).astype(float)
        if np.linalg.norm(np.cross(stored[1]-stored[0],stored[2]-stored[0])) < 1e-9: return
        parts[part].extend([*p,*uv] for p in q)

    # Preserve source triangle connectivity as well as all top positions.
    for q in roof[:,3:6].reshape(-1,3,3):
        normal = roof_normal if np.cross(q[1]-q[0],q[2]-q[0])@roof_normal > 0 else -roof_normal
        emit(q, 0, normal)

    def slab(poly, bottom, top, part, include_top=True):
        def lift(xz,dy): return [xz[0],float(np.dot([*xz,1],plane))+dy,xz[1]]
        for tri in triangles(poly):
            if include_top: emit([lift(x,top) for x in tri],part,roof_normal)
            emit([lift(x,bottom) for x in tri],part,-roof_normal)
        for p in polygons(poly):
            for ring in [p.exterior,*p.interiors]:
                coords = np.asarray(ring.coords)
                for a,b in zip(coords[:-1],coords[1:]):
                    q = [lift(a,bottom),lift(b,bottom),lift(b,top),lift(a,top)]
                    normal = [a[1]-b[1],0,b[0]-a[0]]
                    for indices in [(0,1,2),(0,2,3)]: emit([q[i] for i in indices],part,normal)

    slab(region,-spec['roofThicknessMetres'],0,1,False)
    inner = outline[:spec['innerRoofVertexCount'],[0,2]]
    line = LineString(inner); base = float(points[:,1].min())
    glass_bottom = base+.07; glass_top = base+spec['glazingHeightMetres']
    rib_regions = []
    for u in np.linspace(.3,line.length-.3,spec['ribCount']):
        p = np.array(line.interpolate(u).coords[0]); a = np.array(line.interpolate(max(0,u-.01)).coords[0]); b = np.array(line.interpolate(min(line.length,u+.01)).coords[0])
        direction = b-a; direction /= np.linalg.norm(direction)
        outward = np.array([direction[1],-direction[0]])
        rib = region.intersection(LineString([p-outward*.1,p+outward*4]).buffer(spec['ribWidthMetres']/2,cap_style=2))
        assert not rib.is_empty
        slab(rib,-spec['roofThicknessMetres']-spec['ribDepthMetres'],-spec['roofThicknessMetres'],1)
        rib_regions.append({'ring':list(rib.exterior.coords),'holes':[]})

    # The photographed glazing is a closed exterior surface at the existing
    # base, not an opening into a fabricated interior. Offset it just outside
    # the measured main wall to avoid coincident brick and pane surfaces.
    glass_controls = []; distance = 0.0; facade_regions = []
    for a,b in zip(inner[:-1],inner[1:]):
        delta = b-a; length = np.linalg.norm(delta); direction = delta/length
        normal = np.array([direction[1],0,-direction[0]])
        anchor = np.array([a[0],0,a[1]])+normal*spec['glazingOffsetMetres']
        u = np.array([direction[0],0,direction[1]])
        shape = box(0,glass_bottom,length,glass_top)
        strips = [box(0,glass_bottom,length,glass_bottom+spec['frameWidthMetres']),box(0,glass_top-spec['frameWidthMetres'],length,glass_top),box(0,base+spec['transomAboveBaseMetres']-.025,length,base+spec['transomAboveBaseMetres']+.025)]
        for x in np.arange(math.floor(distance/spec['mullionPitchMetres'])*spec['mullionPitchMetres'],distance+length+spec['mullionPitchMetres'],spec['mullionPitchMetres']):
            local=x-distance;half=spec['frameWidthMetres']/2;strips.append(box(local-half,glass_bottom,local+half,glass_top))
        if distance == 0: strips.append(box(0,glass_bottom,.055,glass_top))
        if distance+length >= line.length-1e-6: strips.append(box(length-.055,glass_bottom,length,glass_top))
        frame = shape.intersection(unary_union(strips)); glass = shape.difference(frame)
        def surface(poly,part,offset):
            for tri in triangles(poly):
                q = [anchor+u*x+normal*offset+[0,y,0] for x,y in tri]
                emit(q,part,normal)
        surface(frame,2,.02);surface(glass,3,0)
        for poly in polygons(glass):
            p=poly.representative_point();glass_controls.append({'position':(anchor+u*p.x+[0,p.y,0]).tolist(),'normal':normal.tolist(),'part':3})
        facade_regions.append({'anchor':anchor.tolist(),'direction':u.tolist(),'normal':normal.tolist(),'length':float(length),'bottom':glass_bottom,'top':glass_top})
        distance += length

    mesh = bid+'-atom-west-entrance.ect'
    (out/mesh).write_bytes(encode([(p,Image.new('RGBA',(1,1),c)) for p,c in zip(parts,colours)]))
    vertices = np.concatenate([np.asarray(p)[:,:3] for p in parts]);bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','profile':'atom-ei-west-entrance','runtimeId':spec['runtimeId'],'fineCollisionMaterials':spec['fineCollisionMaterials'],'bounds':bounds})
    protect = unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in r[1:]]).buffer(0)
        for key,s in surveys.items() if key not in {bid,spec['mainBuilding']} for k,r in s if k == 'GroundSurface'])
    owned = foot.buffer(spec['cleanupMarginMetres']).difference(protect.buffer(spec['neighbourGuardMetres']))
    retirement=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(owned)]
    plans=json.loads((out/'photo-facades.json').read_text());plan=next(p for p in plans['plans']if p['id']==bid)
    plan.update(manualRoof=True,completeEnvelope=True,retirement=retirement,retirementBoundary=retirement)
    for wall in plan['walls']:
        wall['reconstructed']=True;wall['reconstructionRole']='Open roof projection; glazing remains at the main base behind the covered approach.'
    retired=plan['collisionFile'];meta['photoFacades']['collisionTiles']=[t for t in meta['photoFacades']['collisionTiles']if t['file']!=retired]
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=plan['bounds'][0][1]-2,y1=plan['bounds'][1][1]+3)for p in retirement)
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    record={'building':bid,'runtimeId':spec['runtimeId'],'roofTriangles':10,'partTriangles':[len(p)//3 for p in parts],'roofPlane':plane.tolist(),'roofRegion':list(region.exterior.coords),'ribRegions':rib_regions,'glazingFaces':facade_regions,'glassControls':glass_controls,'retirement':retirement,'protectedNeighbourOverlapSquareMetres':owned.intersection(protect).area,'retiredVolumeWalls':len(walls),'retiredCollisionFile':retired,'qualification':spec['qualification']}
    derived=out/'atom-ei-west-entrance-surfaces.json';derived.write_text(json.dumps(record,indent=2)+'\n')
    meta['architecture']['atomEiWestEntrance']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_atom_ei_west_entrance.py','generatorSha256':sha(Path(__file__)),'referenceFile':spec['reference'],'referenceSha256':sha(root/'minecraft/exterior'/spec['reference']),'derivedFile':derived.name,'derivedSha256':sha(derived),'meshFile':mesh,'meshSha256':sha(out/mesh),'retiredCollisionFile':retired,'qualification':spec['qualification']}
    print('Atom-Ei west entrance:',len(walls),'false volume walls retired; exact 10-triangle roof; estimated open projection and blue glazing',flush=True)

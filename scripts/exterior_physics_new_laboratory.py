"""Survey-bounded TUM5117 exterior with photo-informed metal screens and glazing."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from exterior_physics_i import polygons, roof_texture, survey_plan
from exterior_physics_library import triangles
from exterior_physics_woodland import surveys
from exterior_terrain import ElevationSampler


def build(ctx):
    root, cache, out, meta, mc, encode = (ctx[k] for k in ['ROOT', 'CACHE', 'OUT', 'metadata', 'mc', 'encode'])
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    source = root / 'minecraft/exterior/physics-new-laboratory.json'
    spec = json.loads(source.read_text())
    reference = root / 'minecraft/exterior' / spec['reference']
    assert sha(reference) == spec['referenceSha256']
    buildings = surveys(cache, [698575, 5349490, 698680, 5349590])
    surfaces = next(s for bid, s in buildings if bid == spec['building'])
    footprint, walls, roof, points = survey_plan(ctx, surfaces)
    base = float(points[:, 1].min())
    main_top = float(np.median([walls[i]['bounds'][1][1] for i in spec['outerFaces']]))
    parts = [[] for _ in range(6)]
    textures = [Image.new('RGBA', (1, 1), tuple(c)) for c in spec['materialColours']]
    controls, fins, joint_controls = [], [], []

    def emit(vertices, part, normal):
        vertices = np.asarray(vertices)
        if np.dot(np.cross(vertices[1]-vertices[0], vertices[2]-vertices[0]), normal) < 0:
            vertices = vertices[::-1]
        for i in ([0, 1, 2] if len(vertices) == 3 else [0, 1, 2, 0, 2, 3]):
            parts[part].append([*vertices[i], .5, .5])

    for index, wall in enumerate(walls):
        anchor, direction, normal = (np.asarray(wall[k]) for k in ['anchor', 'direction', 'normal'])
        shape = Polygon(wall['rings'][0], wall['rings'][1:]).buffer(0)
        left, bottom, right, top = shape.bounds
        outer, courtyard = index in spec['outerFaces'], index in spec['courtyardFaces']
        if outer or courtyard:
            shape = shape.union(box(left, base-.6, right, base+.02))

        def point(x, y, depth=0):
            result = anchor + direction*x + normal*depth
            result[1] = y
            return result

        def surface(polygon, part, depth=0):
            for triangle in triangles(polygon):
                emit([point(x, y, depth) for x, y in triangle], part, normal)

        openings, perforated = [], []
        bands = spec['ribbonBandsBelowRoof'] if outer else spec['courtyardBandsBelowRoof'] if courtyard else []
        if outer:
            bands = [*bands, spec['groundScreenBelowRoof']]
        for band_index, (low, high) in enumerate(bands):
            y0, y1 = main_top-low, main_top-high
            opening = shape.intersection(box(left, y0, right, y1))
            if opening.is_empty:
                continue
            screen = outer and band_index == len(bands)-1
            recess = spec['finDepthMetres']+.06 if screen else spec['windowRecessMetres']
            openings.append(opening)
            surface(opening, 1, -recess)
            # A shallow opaque glazing plane closes the exterior; no interior geometry.
            for polygon in polygons(opening):
                coords = np.asarray(polygon.exterior.coords)
                for a, b in zip(coords[:-1], coords[1:]):
                    emit([point(*a), point(*b), point(*b, -recess), point(*a, -recess)], 2, normal)
            frame = spec['frameWidthMetres']
            surface(opening.difference(opening.buffer(-frame, join_style=2)), 3, -recess+.015)
            phase = float(np.dot(anchor, direction))
            pitch = spec['windowMullionPitchMetres']
            for x in np.arange(math.ceil((left+phase)/pitch)*pitch-phase, right, pitch):
                surface(opening.intersection(box(x-frame/2, y0, x+frame/2, y1)), 3, -recess+.025)
            # Select controls away from frames and fin blades.
            inset = opening.buffer(-.12)
            if not inset.is_empty:
                sample = inset.representative_point()
                controls.append({'face': index, 'part': 1, 'position': point(sample.x, sample.y, -recess).tolist(), 'normal': normal.tolist(), 'screened': screen})
            if outer and not screen:
                perforated.append(shape.intersection(box(left, y1, right, y1+spec['perforatedStripHeightMetres'])))
            if screen:
                pitch, half = spec['finPitchMetres'], spec['finThicknessMetres']/2
                for x in np.arange(math.ceil((left+phase)/pitch)*pitch-phase, right, pitch):
                    if x-half < left or x+half > right:
                        continue
                    front = [point(x-half,y0), point(x+half,y0), point(x+half,y1), point(x-half,y1)]
                    back = [point(x-half,y0,-spec['finDepthMetres']), point(x+half,y0,-spec['finDepthMetres']), point(x+half,y1,-spec['finDepthMetres']), point(x-half,y1,-spec['finDepthMetres'])]
                    emit(front, 2, normal)
                    emit(back, 2, -normal)
                    for k, side in enumerate([-np.array([0.,1,0]), direction, np.array([0.,1,0]), -direction]):
                        j = (k+1) % 4
                        emit([front[k], front[j], back[j], back[k]], 2, side)
                    fins.append({'face': index, 'centre': point(x,(y0+y1)/2).tolist(), 'normal': normal.tolist(), 'depth': spec['finDepthMetres']})

        solid = shape.difference(unary_union(openings))
        perf = unary_union(perforated).intersection(solid)
        # Cut physical gaps for panel joints. Coplanar dark overlays shimmer
        # against the metal with the game's long-distance depth precision.
        joints = []
        if not courtyard:
            joint = spec['panelJointMetres']/2
            pitch = spec['panelWidthMetres']
            phase = float(np.dot(anchor, direction))
            for x in np.arange(math.ceil((left+phase)/pitch)*pitch-phase, right, pitch):
                joints.append(solid.intersection(box(x-joint, base-1, x+joint, top)))
            levels = [top-.06]
            if outer:
                for low, high in spec['ribbonBandsBelowRoof']:
                    start = main_top-high
                    levels += [start+spec['perforatedStripHeightMetres'], start+2*spec['perforatedStripHeightMetres']]
                levels += [main_top-10.3]
            for y in levels:
                joints.append(solid.intersection(box(left, y-joint, right, y+joint)))
        joint_shape = unary_union(joints)
        # Courtyard spandrels remain dark; outer joints have a recessed backing.
        surface(solid.difference(perf).difference(joint_shape), 3 if courtyard else 0)
        surface(perf.difference(joint_shape), 5)
        if not courtyard:
            surface(solid, 3, -spec['jointBackingDepthMetres'])
        if not joint_shape.is_empty:
            for polygon in polygons(joint_shape):
                sample = polygon.representative_point()
                joint_controls.append({'face':index,'position':point(sample.x,sample.y,-spec['jointBackingDepthMetres']).tolist(),'normal':normal.tolist()})
        wall['reconstructed'] = True

    roof_vertices, roof_photo = roof_texture(cache, roof)
    parts[4], textures[4] = roof_vertices.tolist(), roof_photo
    mesh_name = spec['building']+'-laboratory-exterior.ect'
    (out/mesh_name).write_bytes(encode(list(zip(parts, textures))))
    vertices = np.concatenate([np.asarray(p)[:, :3] for p in parts if p])
    meta['tiles'].append({'file': mesh_name, 'kind': 'reconstruction', 'profile': 'new-physics-laboratory', 'runtimeId': spec['runtimeId'], 'bounds': [vertices.min(0).tolist(), vertices.max(0).tolist()]})
    roof_name = spec['building']+'-photo-roof.ect'
    (out/roof_name).write_bytes(encode([(roof_vertices, roof_photo)]))
    neighbours = unary_union([Polygon(mc(r[0])[:, [0,2]], [mc(h)[:, [0,2]] for h in r[1:]]).buffer(0) for bid, s in buildings if bid != spec['building'] for kind, r in s if kind == 'GroundSurface']).buffer(.35)
    cleanup = footprint.buffer(spec['cleanupMarginMetres'], join_style=2).difference(neighbours)
    cleanup_rings = [{'ring': list(p.exterior.coords), 'holes': [list(h.coords) for h in p.interiors]} for p in polygons(cleanup)]
    plans = json.loads((out/'photo-facades.json').read_text())
    assert spec['building'] not in [p['id'] for p in plans['plans']]
    plans['plans'].append({'id': spec['building'], 'runtimeId': 1_000_050_000+len(plans['plans']), 'manualRoof': True, 'completeEnvelope': True, 'roofFile': roof_name, 'collisionFile': roof_name, 'bounds': [vertices.min(0).tolist(), vertices.max(0).tolist()], 'walls': walls, 'roofTriangles': roof[:,3:6].reshape(-1,3,3).tolist(), 'retirement': cleanup_rings, 'retirementBoundary': cleanup_rings})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',', ':')))
    meta['photoFacades']['buildings'].append(spec['building'])
    meta['photoFacades']['roofFiles'].append(roof_name)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=base-2,y1=float(vertices[:,1].max())+4) for p in cleanup_rings)

    # Preserve all existing ground; add only the previously excluded footprint
    # guard and uncovered retirement apron. The courtyard hole remains open.
    original = unary_union([Polygon(r[0][:,:2], [h[:,:2] for h in r[1:]]).buffer(0) for kind,r in surfaces if kind == 'GroundSurface'])
    other = unary_union([Polygon(r[0][:,:2], [h[:,:2] for h in r[1:]]).buffer(0) for bid,s in buildings if bid != spec['building'] for kind,r in s if kind == 'GroundSurface'])
    lat,lon = map(math.radians, meta['origin'][:2])
    origin = np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    east = np.array([-math.sin(lon),math.cos(lon),0])
    up = np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)])
    south = np.array([math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)])
    to_utm = Transformer.from_crs(4978,25832,always_xy=True)
    def old_ring(ring):
        q = np.asarray(ring)
        ecef = origin+q[:,0,None]*east+q[:,1,None]*south+up
        e,n,_ = to_utm.transform(*ecef.T)
        return np.column_stack([e,n])
    prior = unary_union([box(*meta['boundsUtm']), *[Polygon(old_ring(p['ring']),[old_ring(h) for h in p.get('holes',[])]) for s in meta.get('supplementalSurfaces',[]) for p in s['rings']]])
    ground_area = original.buffer(spec['cleanupMarginMetres']+.5,join_style=2).difference(other.buffer(.5)).difference(prior.buffer(.002))
    lo = np.floor(ground_area.bounds[:2]).astype(int)
    hi = np.ceil(ground_area.bounds[2:]).astype(int)
    ground_vertices = []
    with rasterio.open(cache/'campus-dgm-east.tif') as dem:
        elevation = ElevationSampler([dem])
        def xyz(xy):
            xy = np.asarray(xy)
            return mc(np.column_stack([xy,elevation.sample(xy)]))
        for n in range(lo[1],hi[1]):
            for e in range(lo[0],hi[0]):
                for xy in triangles(ground_area.intersection(box(e,n,e+1,n+1))):
                    ground_vertices.extend(np.column_stack([xyz(xy),np.full((3,2),.5)]).tolist())
        xy = np.array([(e,n) for n in range(lo[1],hi[1]+1) for e in range(lo[0],hi[0]+1)])
        guide = {'width': int(hi[0]-lo[0]+1), 'height': int(hi[1]-lo[1]+1), 'points': xyz(xy).tolist()}
        ground_rings = [{'ring': xyz(p.exterior.coords)[:,[0,2]].tolist(), 'holes': [xyz(h.coords)[:,[0,2]].tolist() for h in p.interiors]} for p in polygons(ground_area)]
    ground_name = 'physics-new-laboratory-ground.ect'
    (out/ground_name).write_bytes(encode([(ground_vertices,Image.new('RGBA',(1,1),(135,135,129,255)))]))
    gv = np.asarray(ground_vertices)[:,:3]
    meta['tiles'].append({'file':ground_name,'kind':'ground','runtimeId':spec['groundRuntimeId'],'bounds':[gv.min(0).tolist(),gv.max(0).tolist()]})
    meta.setdefault('supplementalSurfaces',[]).append({'name':'physics-new-laboratory-apron','rings':ground_rings,'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':False,'qualification':'DGM1 continuation into footprint guard and uncovered apron. Finished construction grade is unverified; estimated pavement appearance.'})
    meta['architecture']['physicsNewLaboratory'] = {'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_new_laboratory.py','generatorSha256':sha(Path(__file__)),'building':spec['building'],'runtimeId':spec['runtimeId'],'meshFile':mesh_name,'groundTiles':[ground_name],'roofFile':roof_name,'surveyWalls':walls,'openingControls':controls,'jointControls':joint_controls,'fins':fins,'retirement':cleanup_rings,'groundRings':ground_rings,'groundAreaSquareMetres':ground_area.area,'roofTriangles':len(roof)//3,'surveyBaseMC':base,'mainRoofMC':main_top,'qualification':spec['qualification']}
    print('New laboratory:',len(walls),'survey walls;',len(roof)//3,'roof triangles;',len(fins),'fins;',len(controls),'glazing controls',flush=True)

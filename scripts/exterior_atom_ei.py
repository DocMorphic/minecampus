"""Atom-Ei: source-constrained smooth dome and qualified lower exterior.

The 25-point roof section is not a perfect circle. Preserve those observations
instead of forcing a nominal diameter from a historical description.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.interpolate import CubicSpline
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles


def dome_model(surfaces, spec):
    roofs = [r[0] for k, r in surfaces if k == 'RoofSurface']
    points = np.unique(np.concatenate(roofs), axis=0)
    apex = points[np.argmax(points[:, 2])]
    base = spec['domeBaseHeight']
    radius = np.linalg.norm(points[:, :2] - apex[:2], axis=1)
    lower, upper = spec['domeRadiusRangeMetres']
    section = points[(np.abs(points[:, 2] - base) < 1e-5) & (radius > lower) & (radius < upper)]
    assert len(section) == 25
    theta = np.mod(np.arctan2(section[:, 1]-apex[1], section[:, 0]-apex[0]), 2*np.pi)
    order = np.argsort(theta); theta, section = theta[order], section[order]
    radius = np.linalg.norm(section[:, :2]-apex[:2], axis=1)
    angles = np.r_[theta, theta[0]+2*np.pi]
    spline = CubicSpline(angles, np.r_[radius, radius[0]], bc_type='periodic')
    height = apex[2]-base

    def radii(angle, smooth=True):
        angle = (np.asarray(angle)-theta[0]) % (2*np.pi)+theta[0]
        if smooth:
            return spline(angle)
        # Ray intersection with the exact straight survey edge, not linear
        # interpolation of radius. This closes the lower skirt without a gap.
        index = np.searchsorted(angles, angle, side='right')-1
        index = np.clip(index, 0, len(theta)-1)
        a = (section[:, :2]-apex[:2])[index]
        b = (section[:, :2]-apex[:2])[(index+1) % len(theta)]
        direction = np.stack([np.cos(angle), np.sin(angle)], axis=-1)
        delta = b-a
        return (a[..., 0]*delta[..., 1]-a[..., 1]*delta[..., 0])/(direction[..., 0]*delta[..., 1]-direction[..., 1]*delta[..., 0])

    def evaluate(angle, latitude):
        angle, latitude = np.broadcast_arrays(angle, latitude)
        z = base+height*np.sin(latitude)
        blend = np.clip((z-base)/spec['baseTransitionMetres'], 0, 1)
        blend = blend*blend*(3-2*blend)
        r = (radii(angle, False)*(1-blend)+radii(angle)*blend)*np.cos(latitude)
        return np.stack([apex[0]+r*np.cos(angle), apex[1]+r*np.sin(angle), z], axis=-1)

    def is_dome(rings):
        p = rings[0]
        return p[:, 2].min() >= base-1e-5 and np.linalg.norm(p[:, :2]-apex[:2], axis=1).max() < upper

    observed = np.unique(np.concatenate([r[0] for k, r in surfaces if k == 'RoofSurface' and is_dome(r)]), axis=0)
    a = np.arctan2(observed[:, 1]-apex[1], observed[:, 0]-apex[0])
    lat = np.arcsin(np.clip((observed[:, 2]-base)/height, 0, 1))
    error = np.linalg.norm(evaluate(a, lat)-observed, axis=1)
    assert error.max() < spec['sourceVertexToleranceMetres'], error.max()
    record = {'apexUTM': apex.tolist(), 'baseHeightDHHN2016': base, 'heightMetres': height,
              'baseSectionUTM': section.tolist(), 'observedDomeVertices': len(observed),
              'maximumObservedVertexErrorMetres': float(error.max()),
              'rmsObservedVertexErrorMetres': float(np.sqrt(np.mean(error**2))),
              'method': 'Periodic cubic radial interpolation of surveyed section, scaled by cosine latitude; surveyed ellipsoidal height law; exact polygon boundary at the skirt.'}
    return evaluate, is_dome, theta, record


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ('ROOT', 'CACHE', 'OUT', 'metadata', 'mc', 'encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/atom-ei.json'
    spec = json.loads(source.read_text()); bid = spec['building']
    # Fail closed on source updates; this fit is tied to the pinned BVV survey.
    sources = json.loads((root/'minecraft/exterior/sources.json').read_text())
    survey_hashes = {}
    for entry, name in zip(sources['lod2'], ['campus-east.gml', 'campus-west.gml']):
        survey_hashes[name] = sha(cache/name)
        assert survey_hashes[name] == entry['sha256']
    assert spec['runtimeId'] not in [t['runtimeId'] for t in meta['tiles']]
    surveys = nearby_surveys(cache, spec['siteBoundsUTM'])
    surfaces = next(s for key, s in surveys if key == bid)
    foot, walls, _, points = survey_plan(ctx, surfaces)
    evaluate, is_dome, observed_angles, model = dome_model(surfaces, spec)
    parts = [[] for _ in range(6)]
    textures = [Image.new('RGBA', (1, 1), c) for c in [(193,194,189,255), (171,137,87,255),
                (221,220,207,255), (57,73,76,255), (152,157,154,255), (170,170,170,255)]]
    # Include every original section direction, avoiding chord cuts at corners.
    angles = np.unique(np.r_[np.linspace(0, 2*np.pi, spec['angularSegments'], endpoint=False), observed_angles])
    angles = np.r_[angles, angles[0]+2*np.pi]
    latitudes = np.linspace(0, np.pi/2, spec['latitudeSegments']+1)
    aa, ll = np.meshgrid(angles, latitudes)
    grid = mc(evaluate(aa, ll).reshape(-1, 3)).reshape(*aa.shape, 3)
    # Smooth normals travel in the otherwise-unused UV pair of the solid-colour
    # dome part. Octahedral encoding requires no change to the ECT mesh format.
    epsilon = 1e-5
    du = mc(evaluate(aa+epsilon, ll).reshape(-1, 3))-mc(evaluate(aa-epsilon, ll).reshape(-1, 3))
    dv = mc(evaluate(aa, ll+epsilon).reshape(-1, 3))-mc(evaluate(aa, ll-epsilon).reshape(-1, 3))
    normal = np.cross(du, dv).reshape(*aa.shape, 3)
    # Minecraft's east/up/south basis reverses the UTM easting/northing/height basis.
    radial = grid-mc(np.asarray([model['apexUTM']]))[0]
    radial[..., 1] = grid[..., 1]-grid[0, :, 1]
    sign = np.where(np.sum(normal*radial, axis=-1) < 0, -1, 1)
    normal *= sign[..., None]
    normal[-1] = [0, 1, 0]
    normal /= np.linalg.norm(normal, axis=-1)[..., None]
    encoded = normal[..., [0, 2]]/np.abs(normal).sum(axis=-1)[..., None]
    lower = normal[..., 1] < 0
    encoded[lower] = (1-np.abs(encoded[lower, ::-1]))*np.sign(encoded[lower])
    uv = encoded*.5+.5
    for j in range(len(latitudes)-1):
        for i in range(len(angles)-1):
            corners = [(j,i),(j,i+1),(j+1,i+1),(j+1,i)]
            for ids in ([(0,1,2)] if j == len(latitudes)-2 else [(0,1,2),(0,2,3)]):
                indices = [corners[k] for k in ids]
                q = np.asarray([grid[k] for k in indices])
                if np.cross(q[1]-q[0], q[2]-q[0]) @ np.mean([normal[k] for k in indices], axis=0) < 0:
                    indices = indices[::-1]
                parts[0].extend([*grid[k], *uv[k]] for k in indices)

    base = float(points[:, 1].min()); cfg = spec['baseFacade']; apex = np.asarray(model['apexUTM'])
    centre = mc(np.asarray([[*apex[:2], spec['domeBaseHeight']]]))[0]
    exterior_walls = []; other_walls = []
    # Keep each surveyed roof below the dome unchanged, including steps and returns.
    low_surfaces = [(kind, r) for kind, r in surfaces if kind == 'RoofSurface' and not is_dome(r)]
    _, _, low_roof, _ = survey_plan(ctx, low_surfaces)
    roof_vertices, roof_pixels = roof_texture(cache, low_roof)
    parts[5] = roof_vertices.tolist(); textures[5] = roof_pixels

    def surface(region, part, depth=0):
        for tri in triangles(region):
            q = np.asarray([anchor+direction*x-normal*depth for x,y in tri]); q[:,1] = np.asarray(tri)[:,1]
            if np.cross(q[1]-q[0], q[2]-q[0]) @ normal < 0: q = q[::-1]
            stored = q.astype(np.float32).astype(float)
            if np.linalg.norm(np.cross(stored[1]-stored[0], stored[2]-stored[0])) < 1e-9: continue
            parts[part].extend(np.column_stack([q, np.full((3,2), .5)]).tolist())

    for index, wall in enumerate(walls):
        anchor, direction, normal = [np.asarray(wall[k]) for k in ('anchor','direction','normal')]
        region = Polygon(wall['rings'][0], wall['rings'][1:]).buffer(0)
        left, bottom, right, top = region.bounds
        outer = bottom < base+.05 and np.linalg.norm((anchor-centre)[[0,2]]) > 20
        if outer:
            exterior_walls.append(index)
            # The upper glazing is an observed feature; subdivision is an
            # estimate, continuous across the survey's short polygon segments.
            midpoint = anchor+direction*(left+right)/2
            bearing = math.atan2(midpoint[2]-centre[2], midpoint[0]-centre[0])
            circumference_u = bearing*24.5
            tangent = np.array([-(midpoint-centre)[2],0,(midpoint-centre)[0]])
            tangent /= np.linalg.norm(tangent)
            u_sign = 1 if tangent@direction > 0 else -1
            u_start = circumference_u-u_sign*(left+right)/2
            sill = base+cfg['windowSillAboveGroundMetres']
            head = min(top-cfg['fasciaMetres'], sill+cfg['windowHeightMetres'])
            window = region.intersection(box(left,sill,right,head))
            piers = []
            for pitch, width, lo, hi in [(cfg['pierPitchMetres'],cfg['pierWidthMetres'],base,top),
                                       (cfg['mullionPitchMetres'],cfg['mullionWidthMetres'],sill,head)]:
                bounds = sorted([u_start+u_sign*left,u_start+u_sign*right])
                for u in np.arange(math.floor(bounds[0]/pitch)*pitch, bounds[1]+pitch, pitch):
                    x = (u-u_start)/u_sign
                    piers.append(box(x-width/2,lo,x+width/2,hi))
            piers.extend([box(left,sill-.08,right,sill+.04),box(left,head-.04,right,top)])
            frame = region.intersection(unary_union(piers))
            glass = window.difference(frame)
            surface(region.difference(window.union(frame)),1)
            surface(frame,2)
            surface(glass,3,cfg['recessMetres'])
            # Close shallow reveals; the visible pane is not a hole into an interior.
            for poly in polygons(glass):
                for ring in [poly.exterior,*poly.interiors]:
                    coords = np.asarray(ring.coords)
                    for a,b in zip(coords[:-1],coords[1:]):
                        q = np.array([anchor+direction*a[0],anchor+direction*b[0]])
                        q[:,1] = [a[1],b[1]]
                        corners = [q[0],q[1],q[1]-normal*cfg['recessMetres'],q[0]-normal*cfg['recessMetres']]
                        for ids in [(0,1,2),(0,2,3)]:
                            stored = np.asarray([corners[k] for k in ids],dtype=np.float32).astype(float)
                            if np.linalg.norm(np.cross(stored[1]-stored[0],stored[2]-stored[0])) < 1e-9: continue
                            for k in ids: parts[2].append([*corners[k],.5,.5])
        else:
            other_walls.append(index); surface(region,4)
        wall['reconstructed'] = True
    # survey_plan omits facade strips under 10 cm tall. This body has one
    # surveyed 6 cm roof return: retain it explicitly to close the envelope.
    small_returns = 0
    for kind, rings in surfaces:
        if kind != 'WallSurface': continue
        _, q, indices = ctx['triangulate'](rings)
        if np.ptp(q[:,1]) >= .1: continue
        for tri in q[indices]:
            parts[4].extend(np.column_stack([tri,np.full((3,2),.5)]).tolist())
            small_returns += 1
    assert small_returns == 1
    assert all(parts)
    mesh = bid+'-atom-ei.ect'; (out/mesh).write_bytes(encode(list(zip(parts,textures))))
    vertices = np.concatenate([np.asarray(p)[:,:3] for p in parts])
    bounds = [vertices.min(0).tolist(), vertices.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','profile':'atom-ei','runtimeId':spec['runtimeId'],
                         'fineCollisionMaterials':spec['fineCollisionMaterials'],'bounds':bounds})
    roof_file = bid+'-photo-roof.ect'
    (out/roof_file).write_bytes(encode([(parts[0],textures[0]),(parts[5],textures[5])]))
    neighbours = unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in r[1:]]).buffer(0)
                    for key,s in surveys if key != bid for kind,r in s if kind == 'GroundSurface'])
    owned = foot.buffer(spec['cleanupMarginMetres']).difference(neighbours.buffer(spec['neighbourGuardMetres']))
    retirement = [{'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]} for p in polygons(owned)]
    plans = json.loads((out/'photo-facades.json').read_text())
    assert bid not in [p['id'] for p in plans['plans']]
    roofs = np.concatenate([np.asarray(parts[0])[:,:3],low_roof[:,3:6]])
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']), 'manualRoof':True,
        'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':bounds,
        'walls':walls,'roofTriangles':roofs.reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid); meta['photoFacades']['roofFiles'].append(roof_file)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=bounds[0][1]-2,y1=bounds[1][1]+3) for p in retirement)
    record = {**model,'surveyHashes':survey_hashes,'outerBaseWalls':exterior_walls,'skirtAndReturnWalls':other_walls,
              'smallReturnTriangles':small_returns,'lowerRoofTriangles':len(low_roof)//3,'domeTriangles':len(parts[0])//3,
              'partTriangles':[len(p)//3 for p in parts],'retirement':retirement,
              'protectedNeighbourOverlapSquareMetres':owned.intersection(neighbours).area,
              'baseCentreMC':centre.tolist(),'qualification':spec['qualification']}
    derived = out/'atom-ei-surfaces.json'; derived.write_text(json.dumps(record,indent=2)+'\n')
    meta['architecture']['atomEi'] = {'building':bid,'sourceFile':source.name,'sourceSha256':sha(source),
        'generatorFile':'scripts/exterior_atom_ei.py','generatorSha256':sha(Path(__file__)),
        'referenceFile':spec['reference'],'referenceSha256':sha(root/'minecraft/exterior'/spec['reference']),
        'derivedFile':derived.name,'derivedSha256':sha(derived),'meshFile':mesh,'meshSha256':sha(out/mesh),
        'roofFile':roof_file,'roofSha256':sha(out/roof_file),'qualification':spec['qualification']}
    print('Atom-Ei:',len(parts[0])//3,'dome triangles;',len(exterior_walls),'lower walls;',
          model['maximumObservedVertexErrorMetres'],'m maximum source-vertex residual',flush=True)

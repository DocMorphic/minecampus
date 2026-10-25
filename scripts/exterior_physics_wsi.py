"""Surveyed WSI envelope, estimated facade details and adjoining public-data terrain."""
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, LineString, box, mapping
from shapely.ops import unary_union

from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles
from exterior_physics_ii import ground_transition
from exterior_physics_ii_landscape import canopy_extension, osm_ways
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation
from exterior_ground_restoration import restored_transition


def north_land_extent(root, spec, original, extent):
    """Keep connected south-bank terrain clear of the mapped river."""
    policy = spec['northLandscapeBoundary']
    ways = osm_ways(root, policy)
    woodland = Polygon(ways[policy['woodlandWay']][0]).buffer(0)
    river = Polygon(ways[policy['riverWay']][0]).buffer(0)
    land = extent.union(woodland.buffer(policy['woodlandMarginMetres'])).difference(river.buffer(policy['riverGuardMetres']))
    connected = [p for p in polygons(land) if p.intersects(original)]
    assert len(connected) == 1, 'WSI must have one connected land component'
    assert connected[0].intersection(river).area < 1e-6
    return connected[0]


def blended_outer_transition(root, spec, prior):
    """Blend nearby boundary residuals continuously at equidistant corners."""
    from shapely import points, distance
    source = root/'minecraft/exterior'/spec['groundTransition']['sourceFile']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == spec['groundTransition']['sha256']
    record = json.loads(source.read_text())
    segments, residuals, missing = [], [], []
    for line in record['lines']:
        for i in range(len(line['utm'])-1):
            edge = line['utm'][i:i+2]
            values = line['joinDelta'][i:i+2]
            if None in values:
                missing.append(LineString(edge))
            else:
                segments.append(edge); residuals.append(values)
    segments, residuals = np.asarray(segments), np.asarray(residuals)
    a = segments[:,0]; direction = segments[:,1]-a
    length2 = np.sum(direction**2, axis=1)
    assert np.all(length2 > 0)
    missing = unary_union(missing)
    blend = record['nearestEdgeBlendMetres']
    assert 0 < blend <= record['widthMetres']
    def smooth(v):
        v = np.clip(v,0,1)
        return v*v*(3-2*v)
    def correction(xy):
        xy = np.asarray(xy); result = np.zeros(len(xy))
        for start in range(0,len(xy),1024):
            q = xy[start:start+1024]
            t = np.clip(np.sum((q[:,None,:]-a)*direction,axis=2)/length2,0,1)
            distances = np.linalg.norm(q[:,None,:]-a-t[:,:,None]*direction,axis=2)
            nearest = distances.min(axis=1)
            weights = smooth(1-(distances-nearest[:,None])/blend)
            values = residuals[:,0]*(1-t)+residuals[:,1]*t
            residual = np.sum(weights*values,axis=1)/weights.sum(axis=1)
            pts = points(q)
            missing_fade = smooth(distance(pts,missing)/record['priorFadeMetres']) if not missing.is_empty else 1
            result[start:start+len(q)] = residual*smooth(1-nearest/record['widthMetres'])*smooth(distance(pts,prior)/record['priorFadeMetres'])*missing_fade
        return result
    return restored_transition(root, correction), record


def build(ctx):
    root, cache, out, meta, mc, encode = (ctx[k] for k in ['ROOT','CACHE','OUT','metadata','mc','encode'])
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/physics-wsi.json'
    spec = json.loads(source.read_text())
    assert sha(root/'minecraft/exterior'/spec['reference']) == spec['referenceSha256']
    surveys = nearby_surveys(cache, spec['surveyBoundsUtm'])
    surfaces = next(s for bid,s in surveys if bid == spec['building'])
    foot, walls, roof, points = survey_plan(ctx, surfaces)
    # The shared helper omits walls shorter than 10 cm. WSI has a 55 m-long,
    # 8 cm-high roof-edge strip: keep it so the roof does not acquire a slit.
    # Append rather than renumber the established facade reference planes.
    for kind, rings in surfaces:
        if kind != 'WallSurface':
            continue
        q = mc(rings[0])
        if not 1e-4 < np.ptp(q[:,1]) < .1:
            continue
        anchor = q[0].copy()
        delta = next((v-anchor for v in q if np.linalg.norm((v-anchor)[[0,2]])>.1), None)
        if delta is None:
            continue
        direction = np.array([delta[0],0,delta[2]])
        direction /= np.linalg.norm(direction)
        normal = np.array([-direction[2],0,direction[0]])
        if np.dot(normal,np.sum(np.cross(q,np.roll(q,-1,axis=0)),axis=0))<0:
            normal = -normal
        local = [np.column_stack([(mc(r)-anchor)@direction,mc(r)[:,1]]) for r in rings]
        _, vertices, indices = ctx['triangulate'](rings)
        xy = np.concatenate(local)
        walls.append({'anchor':anchor.tolist(),'direction':direction.tolist(),'normal':normal.tolist(),
                      'bounds':[xy.min(0).tolist(),xy.max(0).tolist()],
                      'rings':[p.tolist() for p in local],'vertices':vertices.tolist(),
                      'indices':indices.reshape(-1).tolist(),'thinSurveyStrip':True})
    base = float(points[:,1].min())
    parts = [[] for _ in range(4)]
    textures = [Image.new('RGBA',(1,1),tuple(c)) for c in spec['materialColours']]
    openings_record, beams_record = [], []

    def emit(q, part, normal):
        q = np.asarray(q)
        if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal) < 0:
            q = q[::-1]
        for i in ([0,1,2] if len(q)==3 else [0,1,2,0,2,3]):
            parts[part].append([*q[i],.5,.5])

    for index, wall in enumerate(walls):
        anchor, direction, normal = (np.asarray(wall[k]) for k in ['anchor','direction','normal'])
        region = Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0)
        left,bottom,right,top = region.bounds
        # Elevated roof-side walls must not grow curtains down to the terrain.
        if bottom <= base+.05:
            region = region.union(box(left,base-.6,right,base+.01))
        def point(x,y,depth=0):
            p = anchor+direction*x+normal*depth
            p[1] = y
            return p
        def surface(shape,part,depth=0):
            for tri in triangles(shape):
                emit([point(x,y,depth) for x,y in tri],part,normal)
        def beam(x0,y0,x1,y1,depth):
            shape = region.intersection(box(x0,y0,x1,y1))
            if shape.is_empty:
                return
            surface(shape,2,depth)
            # Side faces make the frame a projecting volume, not a painted line.
            for poly in polygons(shape):
                coords = np.asarray(poly.exterior.coords)
                for a,b in zip(coords[:-1],coords[1:]):
                    delta = direction*(b[0]-a[0])+np.array([0,b[1]-a[1],0])
                    side = np.cross(delta,normal)
                    if np.linalg.norm(side)>1e-9:
                        emit([point(*a),point(*b),point(*b,depth),point(*a,depth)],2,side)
            sample = shape.representative_point()
            beams_record.append({'face':index,'position':point(sample.x,sample.y,depth).tolist(),'normal':normal.tolist(),'depth':depth})
        openings = []
        for rectangle in spec['openings'].get(str(index),[]):
            x0,y0,x1,y1 = rectangle
            y0 += base; y1 += base
            opening = region.intersection(box(x0,y0,x1,y1))
            assert not opening.is_empty
            inner = opening.buffer(-spec['frameWidthMetres'],join_style=2)
            strips = [box(x-.025,y0,x+.025,y1) for x in np.arange(x0+spec['mullionPitchMetres'],x1-.05,spec['mullionPitchMetres'])]
            strips.append(box(x0,y0+(y1-y0)*.42-.025,x1,y0+(y1-y0)*.42+.025))
            frames = inner.intersection(unary_union(strips))
            glass = inner.difference(frames)
            surface(glass,1,-spec['windowRecessMetres'])
            surface(opening.difference(inner),2,-.01)
            surface(frames,2,-.06)
            for poly in polygons(opening):
                coords = np.asarray(poly.exterior.coords)
                for a,b in zip(coords[:-1],coords[1:]):
                    emit([point(*a),point(*b),point(*b,-spec['windowRecessMetres']),point(*a,-spec['windowRecessMetres'])],2,normal)
            # Control each window band away from its mullions and exterior columns.
            candidates = sorted(polygons(glass),key=lambda p:p.area,reverse=True)
            framing = spec['externalFrames'].get(str(index))
            for candidate in candidates:
                p = candidate.representative_point()
                if framing and min(abs(p.x-x) for x in np.arange(left+framing['verticalStartMetres'],right,framing['verticalPitchMetres'])) < framing['widthMetres']:
                    continue
                openings_record.append({'face':index,'part':1,'position':point(p.x,p.y,-spec['windowRecessMetres']).tolist(),'normal':normal.tolist(),'rectangle':rectangle})
                break
            else:
                raise AssertionError('No unobstructed glazing control')
            openings.append(opening)
        solid = region.difference(unary_union(openings))
        seams = unary_union([box(x-.006,bottom-.7,x+.006,top+.01) for x in np.arange(left+spec['panelPitchMetres'],right-.05,spec['panelPitchMetres'])])
        surface(solid.difference(seams),0)
        surface(solid,3,-spec['jointDepthMetres'])
        framing = spec['externalFrames'].get(str(index))
        if framing:
            half = framing['widthMetres']/2
            for x in np.arange(left+framing['verticalStartMetres'],right,framing['verticalPitchMetres']):
                beam(x-half,base-.1,x+half,base+framing['topAboveBase'],framing['depthMetres'])
            for height in framing['horizontalBandsAboveBase']:
                beam(left,base+height-half,right,base+height+half,framing['depthMetres'])
        wall['reconstructed'] = True

    roof_vertices, roof_photo = roof_texture(cache,roof)
    parts.append(roof_vertices.tolist()); textures.append(roof_photo)
    assert all(parts)
    mesh_name = spec['building']+'-wsi-exterior.ect'
    (out/mesh_name).write_bytes(encode(list(zip(parts,textures))))
    vertices = np.concatenate([np.asarray(p)[:,:3] for p in parts])
    meta['tiles'].append({'file':mesh_name,'kind':'reconstruction','runtimeId':spec['runtimeId'],'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
    roof_name = spec['building']+'-photo-roof.ect'
    (out/roof_name).write_bytes(encode([(roof_vertices,roof_photo)]))
    other_mc = unary_union([Polygon(mc(p[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in p[1:]]).buffer(0) for bid,s in surveys if bid!=spec['building'] for kind,p in s if kind=='GroundSurface'])
    cleanup = foot.buffer(spec['cleanupMarginMetres'],join_style=2).difference(other_mc.buffer(.5))
    retirement = [{'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]} for p in polygons(cleanup)]
    plans = json.loads((out/'photo-facades.json').read_text())
    assert spec['building'] not in [p['id'] for p in plans['plans']]
    plans['plans'].append({'id':spec['building'],'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roof_name,'collisionFile':roof_name,'bounds':[points.min(0).tolist(),points.max(0).tolist()],'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(spec['building']); meta['photoFacades']['roofFiles'].append(roof_name)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=base-2,y1=float(points[:,1].max())+4) for p in retirement)

    original = unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for kind,p in surfaces if kind=='GroundSurface'])
    others = unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for bid,s in surveys if bid!=spec['building'] for kind,p in s if kind=='GroundSurface'])
    lat,lon = map(math.radians,meta['origin'][:2])
    origin = np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    east = np.array([-math.sin(lon),math.cos(lon),0]); up = np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)])
    south = np.array([math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)])
    inverse = Transformer.from_crs(4978,25832,always_xy=True)
    def utm(ring):
        q = np.asarray(ring); xyz = origin+q[:,0,None]*east+q[:,1,None]*south+up
        e,n,_ = inverse.transform(*xyz.T)
        return np.column_stack([e,n])
    def prior_area(surfaces):
        return unary_union([box(*meta['boundsUtm']),*[Polygon(utm(p['ring']),[utm(h) for h in p.get('holes',[])]) for s in surfaces for p in s['rings']]])
    prior = prior_area(meta['supplementalSurfaces'])
    old_index = next(i for i,s in enumerate(meta['supplementalSurfaces']) if s['name']=='physics-ii-site')
    inherited_correction,_ = ground_transition(root,json.loads((root/'minecraft/exterior/physics-ii.json').read_text()),prior_area(meta['supplementalSurfaces'][:old_index]))
    outer_correction,transition = blended_outer_transition(root,spec,prior)
    def correction(xy):
        return inherited_correction(xy)+outer_correction(xy)
    extent = original.buffer(spec['apronMetres'])
    if 'northLandscapeBoundsUtm' in spec:
        extent = extent.union(box(*spec['northLandscapeBoundsUtm']))
    canopy, canopy_records = canopy_extension(cache,spec,unary_union([original,others]),extent)
    extent = extent.union(canopy.buffer(spec['canopyExtent']['groundMarginMetres']))
    extent = north_land_extent(root, spec, original, extent)
    area = extent.difference(others.buffer(.5)).difference(prior.buffer(.002))
    step = spec['groundTileMetres']; lo=(np.floor(np.array(area.bounds[:2])/step)*step).astype(int); hi=(np.ceil(np.array(area.bounds[2:])/step)*step).astype(int)
    ground_tiles, tree_tiles = [], []
    with rasterio.open(cache/'campus-dgm-east.tif') as dem, rasterio.open(cache/'campus-dop-east.tif') as dop:
        sampler = ElevationSampler([dem])
        def xyz(xy):
            xy = np.asarray(xy)
            return mc(np.column_stack([xy,sampler.sample(xy)+correction(xy)]))
        def rings(region):
            return [{'ring':xyz(p.exterior.coords)[:,[0,2]].tolist(),'holes':[xyz(h.coords)[:,[0,2]].tolist() for h in p.interiors]} for p in polygons(region)]
        for n in range(lo[1],hi[1],step):
            for e in range(lo[0],hi[0],step):
                region = area.intersection(box(e,n,e+step,n+step))
                if region.area < .001: continue
                ground_vertices = []
                for y in range(n,n+step):
                    for x in range(e,e+step):
                        for xy in triangles(region.intersection(box(x,y,x+1,y+1))):
                            ground_vertices.extend(np.column_stack([xyz(xy),(xy[:,0]-e)/step,(n+step-xy[:,1])/step]).tolist())
                col,row=(~dop.transform)*(e,n+step)
                rgb=dop.read([1,2,3],window=Window(round(col),round(row),step*5,step*5)).transpose(1,2,0)
                name=f'physics-wsi-ground-{e}-{n}.ect'; (out/name).write_bytes(encode([(ground_vertices,Image.fromarray(rgb))]))
                v=np.asarray(ground_vertices)[:,:3]
                ground_tiles.append({'file':name,'kind':'ground','runtimeId':spec['groundRuntimeStart']+len(ground_tiles),'bounds':[v.min(0).tolist(),v.max(0).tolist()]})
        xy=np.array([(e,n) for n in range(lo[1],hi[1]+1,2) for e in range(lo[0],hi[0]+1,2)])
        guide={'width':int((hi[0]-lo[0])//2+1),'height':int((hi[1]-lo[1])//2+1),'points':xyz(xy).tolist()}
        surface={'name':'physics-wsi-site','rings':rings(area),'terrainGuide':guide,'protectedFootprints':rings(others.buffer(3)),'outdoorReconstructed':True,'qualification':'BVV DGM1/DOP20 terrain with estimated12m apron and explicit north landscape extent. Inherited Physik II transition preserves earlier joins; an estimated2.5m outer shoulder joins sampled source heights, fading at prior terrain and unresolved samples. Native review remains required.'}
        previous=[*meta['vegetation']['trees'],*[t for s in meta['supplementalSurfaces'] for t in s.get('vegetation',{}).get('trees',[])]]
        with tempfile.TemporaryDirectory(prefix='wsi-',dir=cache) as temp:
            folder=Path(temp); col,row=(~dop.transform)*(lo[0],hi[1]); rgb=dop.read([1,2,3],window=Window(round(col),round(row),int((hi[0]-lo[0])*5),int((hi[1]-lo[1])*5))).transpose(1,2,0)
            Image.fromarray(rgb).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':[*map(int,lo),*map(int,hi)],'terrainGuide':guide,'tiles':[],'replacements':[]}
            height=lambda e,n: float(sampler.sample(np.array([[e,n]]))[0]+correction(np.array([[e,n]]))[0])
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':height,'buildings':surveys,'allowedTreeRegionUTM':area.difference(original.buffer(1.2)),'excludedTreeCentresUTM':[t['utm'] for t in previous]})
            for i,t in enumerate(sub['tiles']):
                name='wsi-'+t['file'];shutil.copy2(folder/t['file'],out/name);tree_tiles.append({**t,'file':name,'runtimeId':spec['treeRuntimeStart']+i})
            mc_area=unary_union([Polygon(p['ring'],p['holes']) for p in surface['rings']])
            for replacement in sub['replacements']:
                for p in polygons(Polygon(replacement['ring'],replacement.get('holes',[])).intersection(mc_area)):
                    meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]})
            for key in ['surfaceGuide','vegetationOverhang','vegetation']: surface[key]=sub[key]
            shutil.copy2(folder/'vegetation-survey.jpg',out/'physics-wsi-vegetation-survey.jpg')
    meta['tiles'].extend(ground_tiles+tree_tiles);meta['supplementalSurfaces'].append(surface)
    coverage=out/'physics-wsi-coverage.geojson';coverage.write_text(json.dumps({'ground':mapping(area),'envelope':mapping(original),'extent':mapping(extent),'canopy':mapping(canopy)},separators=(',',':'))+'\n')
    meta['architecture']['physicsWSI']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_wsi.py','generatorSha256':sha(Path(__file__)),'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),'transitionGeneratorSha256':sha(root/'scripts/exterior_physics_ii.py'),'canopyGeneratorSha256':sha(root/'scripts/exterior_physics_ii_landscape.py'),'building':spec['building'],'runtimeId':spec['runtimeId'],'meshFile':mesh_name,'roofFile':roof_name,'groundTiles':[t['file'] for t in ground_tiles],'treeTiles':[t['file'] for t in tree_tiles],'treeCount':len(surface['vegetation']['trees']),'canopyComponents':canopy_records,'groundAreaSquareMetres':area.area,'coverageFile':coverage.name,'coverageSha256':sha(coverage),'surveyWalls':walls,'roofTriangles':len(roof)//3,'baseMC':base,'openingControls':openings_record,'frameControls':beams_record,'retirement':retirement,'qualification':spec['qualification']}
    meta['architecture']['physicsWSI']['groundTransition']=spec['groundTransition']
    shutil.copy2(root/'minecraft/exterior'/spec['groundTransition']['sourceFile'],out/spec['groundTransition']['sourceFile'])
    for item in spec['northLandscapeBoundary']['osm']:
        shutil.copy2(root/'minecraft/exterior'/item['sourceFile'],out/item['sourceFile'])
    meta['architecture']['physicsWSI']['northLandscapeBoundary'] = spec['northLandscapeBoundary']
    print('WSI:',len(walls),'walls;',len(roof)//3,'roof triangles;',len(openings_record),'window bands;',len(beams_record),'projecting frame members;',len(ground_tiles),'ground tiles;',len(surface['vegetation']['trees']),'trees',flush=True)

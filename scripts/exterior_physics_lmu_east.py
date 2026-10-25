"""Surveyed LMU east service envelope, mapped access ground and fitted lawn tree."""
import hashlib
import json
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, LineString, box, mapping
from shapely.ops import unary_union

from exterior_ground_extension import build as extend_ground
from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ('ROOT','CACHE','OUT','metadata','mc','encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/physics-lmu-east.json'
    spec = json.loads(source.read_text()); bid = spec['building']
    osm_path = root/'minecraft/exterior'/spec['osm']['sourceFile']
    assert sha(osm_path) == spec['osm']['sha256']
    osm = ET.parse(osm_path).getroot()
    project = Transformer.from_crs(4326,25832,always_xy=True).transform
    nodes = {n.get('id'): project(float(n.get('lon')),float(n.get('lat'))) for n in osm.findall('node')}
    ways = {w.get('id'): [nodes[n.get('ref')] for n in w.findall('nd')] for w in osm.findall('way')}
    lawn = Polygon(ways[spec['osm']['lawnWay']])
    driveway = LineString(ways[spec['osm']['drivewayWay']]).buffer(spec['drivewayHalfWidthMetres'])
    footway = LineString(ways[spec['osm']['footwayWay']]).buffer(spec['footwayHalfWidthMetres'])
    bounds = spec['boundsUTM']; surveys = nearby_surveys(cache,bounds)
    surfaces = next(s for key,s in surveys if key == bid)
    footprint, walls, roof, points = survey_plan(ctx,surfaces)
    raw_foot = unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0)
                           for kind,p in surfaces if kind == 'GroundSurface'])
    others = unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0)
                          for key,s in surveys if key != bid for kind,p in s if kind == 'GroundSurface'])
    assert len(walls) == spec['wallCount'] and len(roof)//3 == spec['roofTriangles']
    parts = [[],[],[]]
    textures = [Image.new('RGBA',(1,1),tuple(c)) for c in spec['materialColours']]
    base = float(points[:,1].min()); controls = []
    for index, wall in enumerate(walls):
        anchor, direction, normal = [np.asarray(wall[k]) for k in ('anchor','direction','normal')]
        region = Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0)
        left,bottom,right,top = region.bounds
        region = region.union(box(left,base-spec['wallBaseExtensionMetres'],right,base+.01))
        plinth = region.intersection(box(left,base-spec['wallBaseExtensionMetres'],right,base+spec['plinthHeightMetres']))
        fascia = region.intersection(box(left,top-spec['roofFasciaHeightMetres'],right,top+.01))
        # Each patch owns a disjoint wall area, avoiding coincident finish layers.
        for part, area in [(0,region.difference(plinth.union(fascia))),(1,fascia),(2,plinth)]:
            for tri in triangles(area):
                q = np.array([anchor+direction*x for x,y in tri]); q[:,1] = np.array(tri)[:,1]
                if np.cross(q[1]-q[0],q[2]-q[0])@normal < 0: q = q[::-1]
                parts[part].extend(np.column_stack([q,np.full((3,2),.5)]).tolist())
        wall['reconstructed'] = True
        target = anchor+direction*(left+(right-left)*.37); target[1] = base+1.4
        controls.append({'kind':'survey-wall','face':index,'part':0,'position':target.tolist(),'normal':normal.tolist()})
    rv,rp = roof_texture(cache,roof); parts.append(rv.tolist()); textures.append(rp)
    assert all(parts)
    mesh = bid+'-lmu-east.ect'; (out/mesh).write_bytes(encode(list(zip(parts,textures))))
    all_points = np.concatenate([np.asarray(p)[:,:3] for p in parts])
    mesh_bounds = [all_points.min(0).tolist(),all_points.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','runtimeId':spec['runtimeId'],
                          'fineCollisionMaterials':spec['fineCollisionMaterials'],'bounds':mesh_bounds})
    roof_file = bid+'-photo-roof.ect'; (out/roof_file).write_bytes(encode([(rv,rp)]))
    collar = raw_foot.buffer(spec['cleanupMarginMetres']).difference(others.buffer(.25))
    region = collar.union(lawn).union(driveway).union(footway).difference(others.buffer(.25))
    ground = extend_ground(ctx,region,'physics-lmu-east-ground',spec['groundRuntimeId'],spec['groundBlendMetres'])
    assert spec['groundRuntimeId']+len(ground['groundTiles']) < 1_000_061_000
    with rasterio.open(cache/'campus-dgm-east.tif') as dem, rasterio.open(cache/'campus-dop-east.tif') as dop:
        elevation = ElevationSampler([dem])
        def rings(region):
            def ring(r):
                xy=np.asarray(r.coords);return mc(np.column_stack([xy,elevation.sample(xy)]))[:,[0,2]].tolist()
            return [{'ring':ring(p.exterior),'holes':[ring(h) for h in p.interiors]} for p in polygons(region)]
        retirement = rings(collar)
        plans = json.loads((out/'photo-facades.json').read_text())
        assert bid not in [p['id'] for p in plans['plans']]
        plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,
            'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':mesh_bounds,
            'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
        (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
        meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roof_file)
        meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=mesh_bounds[0][1]-2,y1=mesh_bounds[1][1]+3) for p in retirement)
        xy = np.array([(e,n) for n in range(bounds[1],bounds[3]+1,2) for e in range(bounds[0],bounds[2]+1,2)])
        guide = {'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,
                 'points':mc(np.column_stack([xy,elevation.sample(xy)])).tolist()}
        with tempfile.TemporaryDirectory(prefix='lmu-east-',dir=cache) as temporary:
            folder = Path(temporary)
            pixels = dop.read([1,2,3],window=from_bounds(*bounds,dop.transform)).transpose(1,2,0)
            Image.fromarray(pixels).save(folder/'campus-orthophoto.jpg',quality=94)
            sub = {'boundsUtm':bounds,'terrainGuide':guide,'tiles':[],'replacements':[]}
            previous = [*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[]) for t in s.get('vegetation',{}).get('trees',[])]]
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':elevation,'buildings':surveys,
                'allowedTreeRegionUTM':lawn.buffer(-spec['trunkInsetMetres']).difference(others),
                'excludedTreeCentresUTM':[t['utm'] for t in previous]})
            tree_tiles=[]
            for i,tile in enumerate(sub['tiles']):
                name='lmu-east-'+tile['file'];shutil.copy2(folder/tile['file'],out/name)
                tree_tiles.append({**tile,'file':name,'runtimeId':spec['treeRuntimeId']+i})
            meta['tiles'].extend(tree_tiles)
            # Retire fitted crowns only inside the reconstructed outdoor footprint.
            region_mc=unary_union([Polygon(p['ring'],p['holes']) for p in rings(region)])
            for replacement in sub['replacements']:
                clipped=Polygon(replacement['ring'],replacement.get('holes',[])).intersection(region_mc)
                for p in polygons(clipped):meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]})
            next(s for s in meta['supplementalSurfaces'] if s['name']=='physics-lmu-east-ground')['vegetation']=sub['vegetation']
            shutil.copy2(folder/'vegetation-survey.jpg',out/'lmu-east-vegetation-survey.jpg')
    coverage=out/'lmu-east-coverage.json'
    coverage.write_text(json.dumps({'building':mapping(raw_foot),
        'mappedBuilding':mapping(Polygon(ways[spec['osm']['buildingWay']])),
        'lawn':mapping(lawn),'region':mapping(region),'retirement':mapping(collar),
        'protectedNeighbours':mapping(others),'trees':sub['vegetation']['trees']},separators=(',',':'))+'\n')
    meta['architecture']['physicsLMUEast']={'building':bid,'sourceFile':source.name,'sourceSha256':sha(source),
        'generatorFile':'scripts/exterior_physics_lmu_east.py','generatorSha256':sha(Path(__file__)),
        'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),
        'meshFile':mesh,'roofFile':roof_file,'surveyWalls':walls,'roofTriangles':len(roof)//3,'controls':controls,
        'groundTiles':ground['groundTiles'],'ground':ground,'treeTiles':[t['file'] for t in tree_tiles],
        'trees':sub['vegetation']['trees'],'coverageFile':coverage.name,'coverageSha256':sha(coverage),
        'qualification':spec['qualification']}
    print('LMU east:',len(walls),'survey walls;',len(ground['groundTiles']),'ground tiles;',len(sub['vegetation']['trees']),'trees',flush=True)

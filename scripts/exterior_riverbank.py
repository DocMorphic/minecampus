"""Riverbank terrain and complete public-raster canopy groups."""
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
from exterior_physics_i import polygons
from exterior_physics_library import triangles
from exterior_physics_ii import ground_transition
from exterior_physics_wsi import blended_outer_transition
from exterior_physics_ii_landscape import canopy_extension, osm_ways
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/riverbank.json'
    spec = json.loads(source.read_text())
    from exterior_physics_i import nearby_surveys
    surveys = nearby_surveys(cache, spec['surveyBoundsUtm'])
    river_spec = json.loads((root/'minecraft/exterior'/spec['riverSourceFile']).read_text())['northLandscapeBoundary']
    river = Polygon(osm_ways(root,river_spec)[river_spec['riverWay']][0])
    original = river.intersection(box(*spec['riverReachBoundsUtm']))
    bridge_xy, bridge_tags = osm_ways(root,spec)[spec['bridgeWay']]
    assert bridge_tags.get('bridge')=='yes' and float(bridge_tags['width'])==2
    assert spec['bridgeEndGuardMetres']==float(bridge_tags['width'])/2+spec['bridgeGuardMetres']
    bridge = LineString(bridge_xy).buffer(float(bridge_tags['width'])/2+spec['bridgeGuardMetres'],cap_style=3)
    others = unary_union([bridge,*[Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for bid,s in surveys for kind,p in s if kind=='GroundSurface']])
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
    wsi_index = next(i for i,s in enumerate(meta['supplementalSurfaces']) if s['name']=='physics-wsi-site')
    outer_correction,_ = blended_outer_transition(root,json.loads((root/'minecraft/exterior/physics-wsi.json').read_text()),prior_area(meta['supplementalSurfaces'][:wsi_index]))
    def correction(xy):
        return inherited_correction(xy)+outer_correction(xy)
    extent = original.buffer(spec['bankWidthMetres'])
    canopy, canopy_records = canopy_extension(cache,spec,others,extent)
    extent = extent.union(canopy.buffer(spec['canopyExtent']['groundMarginMetres']))
    area = extent.difference(river.buffer(spec['riverGuardMetres'])).difference(others.buffer(spec['neighbourGuardMetres'])).difference(prior.buffer(.002))
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
                name=f'riverbank-ground-{e}-{n}.ect'; (out/name).write_bytes(encode([(ground_vertices,Image.fromarray(rgb))]))
                v=np.asarray(ground_vertices)[:,:3]
                ground_tiles.append({'file':name,'kind':'ground','runtimeId':spec['groundRuntimeStart']+len(ground_tiles),'bounds':[v.min(0).tolist(),v.max(0).tolist()]})
        xy=np.array([(e,n) for n in range(lo[1],hi[1]+1,2) for e in range(lo[0],hi[0]+1,2)])
        guide={'width':int((hi[0]-lo[0])//2+1),'height':int((hi[1]-lo[1])//2+1),'points':xyz(xy).tolist()}
        surface={'name':'riverbank-site','rings':rings(area),'terrainGuide':guide,'protectedFootprints':rings(others.buffer(3)),'outdoorReconstructed':True,'qualification':spec['qualification']}
        previous=[*meta['vegetation']['trees'],*[t for s in meta['supplementalSurfaces'] for t in s.get('vegetation',{}).get('trees',[])]]
        with tempfile.TemporaryDirectory(prefix='riverbank-',dir=cache) as temp:
            folder=Path(temp); col,row=(~dop.transform)*(lo[0],hi[1]); rgb=dop.read([1,2,3],window=Window(round(col),round(row),int((hi[0]-lo[0])*5),int((hi[1]-lo[1])*5))).transpose(1,2,0)
            Image.fromarray(rgb).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':[*map(int,lo),*map(int,hi)],'terrainGuide':guide,'tiles':[],'replacements':[]}
            height=lambda e,n: float(sampler.sample(np.array([[e,n]]))[0]+correction(np.array([[e,n]]))[0])
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':height,'buildings':surveys,'allowedTreeRegionUTM':area.difference(river.buffer(1.2)),'excludedTreeCentresUTM':[t['utm'] for t in previous]})
            for i,t in enumerate(sub['tiles']):
                name='riverbank-'+t['file'];shutil.copy2(folder/t['file'],out/name);tree_tiles.append({**t,'file':name,'runtimeId':spec['treeRuntimeStart']+i})
            mc_area=unary_union([Polygon(p['ring'],p['holes']) for p in surface['rings']])
            for replacement in sub['replacements']:
                for p in polygons(Polygon(replacement['ring'],replacement.get('holes',[])).intersection(mc_area)):
                    meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]})
            for key in ['surfaceGuide','vegetationOverhang','vegetation']: surface[key]=sub[key]
            shutil.copy2(folder/'vegetation-survey.jpg',out/'riverbank-vegetation-survey.jpg')
        channel = river.intersection(extent).difference(bridge)
        def channel_rings(region):
            def project(coords):
                xy=np.asarray(coords);return mc(np.column_stack([xy,sampler.sample(xy)]))[:,[0,2]].tolist()
            return [{'ring':project(p.exterior.coords),'holes':[project(h.coords)for h in p.interiors]}for p in polygons(region)]
        xy=np.array([(e,n) for n in range(lo[1],hi[1]+1,2) for e in range(lo[0],hi[0]+1,2)])
        raw_guide={'width':guide['width'],'height':guide['height'],'points':mc(np.column_stack([xy,sampler.sample(xy)])).tolist()}
        water_ground={'rings':channel_rings(channel),'terrainGuide':raw_guide,'qualification':'DGM-guided channel elevation, not bathymetry. Uses upstream voxel-centre quantization and median water estimation; bridge footprint excluded.'}
        # Retire the complete emitted crowns, including their overhang over water.
        # The bridge guard is subtracted in both the rendered and native plans.
        bridge_mc=unary_union([Polygon(p['ring'],p['holes'])for p in channel_rings(bridge)])
        retirement=[]
        for replacement in sub['replacements']:
            region=Polygon(replacement['ring'],replacement.get('holes',[])).difference(bridge_mc)
            for polygon in polygons(region):
                retirement.append({'rings':[{'ring':list(polygon.exterior.coords),'holes':[list(h.coords)for h in polygon.interiors]}],'y0':replacement['y0'],'y1':replacement['y1']})
        heights=np.asarray(raw_guide['points'])[:,1]
        retirement.append({'rings':water_ground['rings'],'y0':float(heights.min())-1,'y1':float(heights.max())+32})
    meta['tiles'].extend(ground_tiles+tree_tiles);meta['supplementalSurfaces'].append(surface)
    coverage=out/'riverbank-coverage.geojson';coverage.write_text(json.dumps({'ground':mapping(area),'riverReach':mapping(original),'extent':mapping(extent),'canopy':mapping(canopy),'protectedBridge':mapping(bridge),'river':mapping(river.intersection(extent))},separators=(',',':'))+'\n')
    record = meta['architecture']['riverbank'] = {'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_riverbank.py','generatorSha256':sha(Path(__file__)),'qualification':spec['qualification']}
    record.update({'waterGround':water_ground, 'sourceRetirement':retirement, 'groundTiles':[t['file'] for t in ground_tiles], 'treeTiles':[t['file'] for t in tree_tiles],
                   'treeCount':len(surface['vegetation']['trees']), 'canopyComponents':canopy_records,
                   'groundAreaSquareMetres':area.area, 'coverageFile':coverage.name, 'coverageSha256':sha(coverage),
                   'landscapeGeneratorFile':'scripts/exterior_riverbank.py', 'landscapeGeneratorSha256':sha(Path(__file__)),
                   'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),
                   'transitionGeneratorSha256':sha(root/'scripts/exterior_physics_ii.py'),
                   'wsiTransitionGeneratorSha256':sha(root/'scripts/exterior_physics_wsi.py'),
                   'canopyGeneratorSha256':sha(root/'scripts/exterior_physics_ii_landscape.py'),
                   'status':'Unintegrated development bank geometry; channel canopy clipping, native water/collision integration and visual checks pending'})
    ids = [t['runtimeId'] for t in meta['tiles'] if 'runtimeId' in t]
    assert len(ids)==len(set(ids)), 'Runtime tile ID collision'
    assert area.intersection(prior).area < 1e-6
    assert area.intersection(others).area < 1e-6
    print('Riverbank surroundings:',len(ground_tiles),'ground tiles;',len(surface['vegetation']['trees']),'trees;',round(area.area,2),'square metres',flush=True)
    assert area.intersection(river).area < 1e-6
    for item in spec['osm']:shutil.copy2(root/'minecraft/exterior'/item['sourceFile'],out/item['sourceFile'])

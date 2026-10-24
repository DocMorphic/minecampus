"""ZNN approach terrain and complete public-raster canopy groups."""
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
from shapely.geometry import Polygon, box, mapping
from shapely.ops import unary_union
from exterior_physics_i import polygons
from exterior_physics_library import triangles
from exterior_physics_ii import ground_transition
from exterior_physics_wsi import blended_outer_transition
from exterior_physics_ii_landscape import canopy_extension
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx, spec, surveys):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    surfaces = next(s for bid,s in surveys if bid == spec['building'])
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
    wsi_index = next(i for i,s in enumerate(meta['supplementalSurfaces']) if s['name']=='physics-wsi-site')
    outer_correction,_ = blended_outer_transition(root,json.loads((root/'minecraft/exterior/physics-wsi.json').read_text()),prior_area(meta['supplementalSurfaces'][:wsi_index]))
    def correction(xy):
        return inherited_correction(xy)+outer_correction(xy)
    extent = original.buffer(spec['apronMetres'])
    canopy, canopy_records = canopy_extension(cache,spec,unary_union([original,others]),extent)
    extent = extent.union(canopy.buffer(spec['canopyExtent']['groundMarginMetres']))
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
                name=f'physics-znn-ground-{e}-{n}.ect'; (out/name).write_bytes(encode([(ground_vertices,Image.fromarray(rgb))]))
                v=np.asarray(ground_vertices)[:,:3]
                ground_tiles.append({'file':name,'kind':'ground','runtimeId':spec['groundRuntimeStart']+len(ground_tiles),'bounds':[v.min(0).tolist(),v.max(0).tolist()]})
        xy=np.array([(e,n) for n in range(lo[1],hi[1]+1,2) for e in range(lo[0],hi[0]+1,2)])
        guide={'width':int((hi[0]-lo[0])//2+1),'height':int((hi[1]-lo[1])//2+1),'points':xyz(xy).tolist()}
        surface={'name':'physics-znn-site','rings':rings(area),'terrainGuide':guide,'protectedFootprints':rings(others.buffer(3)),'outdoorReconstructed':True,'qualification':'BVV DGM1/DOP20 terrain with estimated 20m apron and complete selected canopy groups. Inherits existing Physik II and WSI height corrections without changing earlier surfaces. Outer joins, source vegetation retirement and visual appearance require native verification.'}
        previous=[*meta['vegetation']['trees'],*[t for s in meta['supplementalSurfaces'] for t in s.get('vegetation',{}).get('trees',[])]]
        with tempfile.TemporaryDirectory(prefix='znn-',dir=cache) as temp:
            folder=Path(temp); col,row=(~dop.transform)*(lo[0],hi[1]); rgb=dop.read([1,2,3],window=Window(round(col),round(row),int((hi[0]-lo[0])*5),int((hi[1]-lo[1])*5))).transpose(1,2,0)
            Image.fromarray(rgb).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':[*map(int,lo),*map(int,hi)],'terrainGuide':guide,'tiles':[],'replacements':[]}
            height=lambda e,n: float(sampler.sample(np.array([[e,n]]))[0]+correction(np.array([[e,n]]))[0])
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':height,'buildings':surveys,'allowedTreeRegionUTM':area.difference(original.buffer(1.2)),'excludedTreeCentresUTM':[t['utm'] for t in previous]})
            for i,t in enumerate(sub['tiles']):
                name='znn-'+t['file'];shutil.copy2(folder/t['file'],out/name);tree_tiles.append({**t,'file':name,'runtimeId':spec['treeRuntimeStart']+i})
            mc_area=unary_union([Polygon(p['ring'],p['holes']) for p in surface['rings']])
            for replacement in sub['replacements']:
                for p in polygons(Polygon(replacement['ring'],replacement.get('holes',[])).intersection(mc_area)):
                    meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]})
            for key in ['surfaceGuide','vegetationOverhang','vegetation']: surface[key]=sub[key]
            shutil.copy2(folder/'vegetation-survey.jpg',out/'physics-znn-vegetation-survey.jpg')
    meta['tiles'].extend(ground_tiles+tree_tiles);meta['supplementalSurfaces'].append(surface)
    coverage=out/'physics-znn-coverage.geojson';coverage.write_text(json.dumps({'ground':mapping(area),'envelope':mapping(original),'extent':mapping(extent),'canopy':mapping(canopy)},separators=(',',':'))+'\n')
    record = meta['architecture']['physicsZNN']
    record.update({'groundTiles':[t['file'] for t in ground_tiles], 'treeTiles':[t['file'] for t in tree_tiles],
                   'treeCount':len(surface['vegetation']['trees']), 'canopyComponents':canopy_records,
                   'groundAreaSquareMetres':area.area, 'coverageFile':coverage.name, 'coverageSha256':sha(coverage),
                   'landscapeGeneratorFile':'scripts/exterior_physics_znn_landscape.py', 'landscapeGeneratorSha256':sha(Path(__file__)),
                   'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),
                   'transitionGeneratorSha256':sha(root/'scripts/exterior_physics_ii.py'),
                   'wsiTransitionGeneratorSha256':sha(root/'scripts/exterior_physics_wsi.py'),
                   'canopyGeneratorSha256':sha(root/'scripts/exterior_physics_ii_landscape.py'),
                   'status':'Development geometry and surrounding surveyed ground; native materials, outer joins and visual verification pending'})
    ids = [t['runtimeId'] for t in meta['tiles'] if 'runtimeId' in t]
    assert len(ids)==len(set(ids)), 'Runtime tile ID collision'
    assert area.intersection(prior).area < 1e-6
    assert area.intersection(others).area < 1e-6
    print('ZNN surroundings:',len(ground_tiles),'ground tiles;',len(surface['vegetation']['trees']),'trees;',round(area.area,2),'square metres',flush=True)

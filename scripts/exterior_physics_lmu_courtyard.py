"""Survey-bounded outdoor LMU courtyard terrain and fitted tree crowns."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from exterior_ground_extension import build as extend_ground
from exterior_physics_i import nearby_surveys, polygons
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx):
    root,cache,out,meta,mc=[ctx[k] for k in ('ROOT','CACHE','OUT','metadata','mc')]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/physics-lmu-courtyard.json';spec=json.loads(source.read_text())
    bounds=spec['boundsUTM'];surveys=nearby_surveys(cache,bounds)
    raw=next(s for bid,s in surveys if bid==spec['building'])
    footprint=unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0)
                          for kind,p in raw if kind=='GroundSurface'])
    courtyard=unary_union([Polygon(h) for p in polygons(footprint) for h in p.interiors])
    assert not courtyard.is_empty and courtyard.area>1
    roofs=[]
    for _,surfaces in surveys:
        for kind,rings in surfaces:
            if kind!='RoofSurface':continue
            v=mc(rings[0]);shape=Polygon(v[:,[0,2]],[mc(h)[:,[0,2]] for h in rings[1:]]).buffer(0)
            if shape.area<1e-8:continue
            plane=np.linalg.lstsq(np.column_stack([v[:,0],v[:,2],np.ones(len(v))]),v[:,1],rcond=None)[0]
            roofs.append((shape,plane))
    roof_tree=STRtree([shape for shape,plane in roofs]);removed_cards=0
    def coordinates(shape):
        if shape.is_empty:return []
        if shape.geom_type=='Polygon':return list(shape.exterior.coords)
        if hasattr(shape,'geoms'):return [q for p in shape.geoms for q in coordinates(p)]
        return list(shape.coords)
    def encode_trees(parts):
        nonlocal removed_cards
        # Pixel-to-card jitter can cross a roof edge after crown fitting. Keep
        # complete cards for the renderer, discarding only cards that enter a
        # surveyed building volume; do not raise or move their source crowns.
        vertices,atlas=parts[1];cards=np.asarray(vertices).reshape(-1,6,5);kept=[]
        for card in cards:
            quad=card[[0,1,2,5],:3];shape=Polygon(quad[:,[0,2]]).buffer(0)
            normal=np.cross(quad[1]-quad[0],quad[2]-quad[0]);constant=normal@quad[0];clear=True
            for index in roof_tree.query(shape):
                roof,plane=roofs[int(index)];points=coordinates(shape.intersection(roof))
                if not points:continue
                xy=np.asarray(points);roof_y=np.column_stack([xy,np.ones(len(xy))])@plane
                leaf_y=(constant-normal[0]*xy[:,0]-normal[2]*xy[:,1])/normal[1] if abs(normal[1])>1e-8 else np.full(len(xy),quad[:,1].min())
                if np.min(leaf_y-roof_y)<.4:clear=False;break
            if clear:kept.extend(card.tolist())
            else:removed_cards+=1
        assert kept
        return ctx['encode']([parts[0],(kept,atlas)])
    ground=extend_ground(ctx,courtyard.buffer(-.005),'physics-lmu-courtyard-ground',spec['groundRuntimeId'],spec['groundBlendMetres'])
    assert spec['groundRuntimeId']+len(ground['groundTiles'])<1_000_061_000
    with rasterio.open(cache/'campus-dgm-east.tif') as dem,rasterio.open(cache/'campus-dop-east.tif') as dop:
        elevation=ElevationSampler([dem])
        xy=np.array([(e,n) for n in range(bounds[1],bounds[3]+1,2) for e in range(bounds[0],bounds[2]+1,2)])
        guide={'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,
               'points':mc(np.column_stack([xy,elevation.sample(xy)])).tolist()}
        with tempfile.TemporaryDirectory(prefix='lmu-courtyard-',dir=cache) as temporary:
            folder=Path(temporary)
            pixels=dop.read([1,2,3],window=from_bounds(*bounds,dop.transform)).transpose(1,2,0)
            Image.fromarray(pixels).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':bounds,'terrainGuide':guide,'tiles':[],'replacements':[]}
            previous=[*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[]) for t in s.get('vegetation',{}).get('trees',[])]]
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'encode':encode_trees,'height':elevation,'buildings':surveys,
                              'allowedTreeRegionUTM':courtyard.buffer(-spec['trunkInsetMetres']),
                              'excludedTreeCentresUTM':[t['utm'] for t in previous]})
            trees=[]
            for i,tile in enumerate(sub['tiles']):
                name='lmu-courtyard-'+tile['file'];shutil.copy2(folder/tile['file'],out/name)
                trees.append({**tile,'file':name,'runtimeId':spec['treeRuntimeId']+i})
            meta['tiles'].extend(trees)
            def ring(coords):
                xy=np.asarray(coords);return mc(np.column_stack([xy,elevation.sample(xy)]))[:,[0,2]].tolist()
            courtyard_mc=unary_union([Polygon(ring(p.exterior.coords)) for p in polygons(courtyard)])
            for replacement in sub['replacements']:
                region=Polygon(replacement['ring'],replacement.get('holes',[])).intersection(courtyard_mc)
                for p in polygons(region):
                    meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]})
            # Ground owns only the previously missing core. The surrounding
            # collar is already owned by the LMU envelope; their union retires
            # the courtyard scan without extending into adjacent buildings.
            surface=next(s for s in meta['supplementalSurfaces'] if s['name']=='physics-lmu-courtyard-ground')
            surface['vegetation']=sub['vegetation']
            coverage={'type':'FeatureCollection','coordinateSystem':'EPSG:25832',
                      'courtyard':courtyard.__geo_interface__,'trees':sub['vegetation']['trees'],
                      'qualification':spec['qualification']}
            coverage_file=out/'lmu-courtyard-coverage.json';coverage_file.write_text(json.dumps(coverage,separators=(',',':'))+'\n')
            shutil.copy2(folder/'vegetation-survey.jpg',out/'lmu-courtyard-vegetation-survey.jpg')
    meta['architecture']['physicsLMUCourtyard']={'building':spec['building'],'sourceFile':source.name,'sourceSha256':sha(source),
        'generatorFile':'scripts/exterior_physics_lmu_courtyard.py','generatorSha256':sha(Path(__file__)),
        'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),
        'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),
        'vegetationSourceSha256':sha(root/'minecraft/exterior/vegetation-sources.json'),
        'groundTiles':ground['groundTiles'],'ground':ground,'treeTiles':[t['file'] for t in trees],
        'trees':sub['vegetation']['trees'],'courtyardAreaSquareMetres':courtyard.area,'roofIntersectingLeafCardsRemoved':removed_cards,
        'coverageFile':coverage_file.name,'coverageSha256':sha(coverage_file),'qualification':spec['qualification']}
    print('LMU courtyard:',len(ground['groundTiles']),'ground tiles;',len(sub['vegetation']['trees']),'trees;',courtyard.area,'m²',flush=True)

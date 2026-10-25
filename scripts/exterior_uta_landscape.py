"""Source-fitted UTA south trees and measured terrain with protected neighbours."""
import hashlib,json,shutil,tempfile
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys,polygons
from exterior_ground_extension import build as extend_ground
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx):
    root,cache,out,meta,mc=[ctx[k]for k in ('ROOT','CACHE','OUT','metadata','mc')]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/uta-south-landscape.json';spec=json.loads(source.read_text());bounds=spec['boundsUTM']
    surveys=nearby_surveys(cache,bounds)
    footprints=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for _,s in surveys for k,r in s if k=='GroundSurface'])
    roofs=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for _,s in surveys for k,r in s if k=='RoofSurface'])
    selected=Polygon(spec['landscapeBoundaryUTM']).intersection(box(*bounds))
    ground_domain=selected.difference(footprints.buffer(spec['groundBuildingGuardMetres']))
    outdoor=ground_domain.difference(footprints.union(roofs).buffer(spec['buildingGuardMetres']))
    ground=extend_ground(ctx,ground_domain,'uta-south-landscape-ground',spec['groundRuntimeId'],spec['groundBlendMetres'])
    # Ground alone does not own vegetation above it. The separate complete
    # outdoor region below supplies the explicit canopy retirement bounds.
    meta['supplementalSurfaces'][-1]['outdoorReconstructed']=False
    assert spec['groundRuntimeId']+len(ground['groundTiles'])<1_000_061_300
    with rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'campus-dop-east.tif')as dop:
        elevation=ElevationSampler([dem])
        def rings(region):
            def ring(r):
                xy=np.asarray(r.coords);return mc(np.column_stack([xy,elevation.sample(xy)]))[:,[0,2]].tolist()
            return [{'ring':ring(p.exterior),'holes':[ring(h)for h in p.interiors]}for p in polygons(region)]
        xy=np.array([(e,n)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)])
        guide={'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,'points':mc(np.column_stack([xy,elevation.sample(xy)])).tolist()}
        allowed=Polygon(spec['treeSelectionBoundaryUTM']).intersection(outdoor)
        with tempfile.TemporaryDirectory(prefix='uta-south-landscape-',dir=cache)as temporary:
            folder=Path(temporary);pixels=dop.read([1,2,3],window=from_bounds(*bounds,dop.transform)).transpose(1,2,0);Image.fromarray(pixels).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':bounds,'terrainGuide':guide,'tiles':[],'replacements':[]}
            previous=[*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[])for t in s.get('vegetation',{}).get('trees',[])]]
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':elevation,'buildings':surveys,'allowedTreeRegionUTM':allowed,'excludedTreeCentresUTM':[t['utm']for t in previous]})
            trees=[]
            for i,t in enumerate(sub['tiles']):
                name='uta-south-'+t['file'];shutil.copy2(folder/t['file'],out/name);trees.append({**t,'file':name,'runtimeId':spec['treeRuntimeId']+i})
            meta['tiles'].extend(trees);shutil.copy2(folder/'vegetation-survey.jpg',out/'uta-south-vegetation-survey.jpg')
        outdoor_rings=rings(outdoor)
        meta['supplementalSurfaces'].append({'name':'uta-south-landscape-retirement','rings':outdoor_rings,'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':True,'vegetation':sub['vegetation'],'qualification':spec['qualification']})
    heights=np.asarray(guide['points'])[:,1]
    retirement=[{'rings':outdoor_rings,'y0':float(heights.min())-2,'y1':float(heights.max())+30,'kind':'reconstructed-outdoor-landscape'}]
    for volume in retirement:meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=volume['y0'],y1=volume['y1'])for p in volume['rings'])
    derived=out/'uta-south-landscape-surfaces.json'
    derived.write_text(json.dumps({'ground':ground,'groundDomainUTM':ground_domain.__geo_interface__,'outdoorDomainUTM':outdoor.__geo_interface__,'treeSelectionDomainUTM':allowed.__geo_interface__,'outdoorRings':outdoor_rings,'sourceRetirement':retirement,'trees':sub['vegetation']['trees'],'qualification':spec['qualification']},indent=2)+'\n')
    meta['architecture']['utaLandscape']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_uta_landscape.py','generatorSha256':sha(Path(__file__)),'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),'vegetationSourceSha256':sha(root/'minecraft/exterior/vegetation-sources.json'),'derivedFile':derived.name,'derivedSha256':sha(derived),'groundTiles':ground['groundTiles'],'treeTiles':[t['file']for t in trees],'sourceRetirement':retirement,'qualification':spec['qualification']}
    assert len({t['runtimeId']for t in meta['tiles']})==len(meta['tiles'])
    print('UTA south:',len(ground['groundTiles']),'ground tiles;',len(sub['vegetation']['trees']),'source-fitted trees',flush=True)

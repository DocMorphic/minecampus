"""Measured FRM II approach terrain and bounded height-aware scan retirement."""
import hashlib,json,shutil,tempfile
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys,survey_plan,polygons
from exterior_ground_extension import build as extend_ground
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx):
    root,cache,out,meta,mc=[ctx[k]for k in ('ROOT','CACHE','OUT','metadata','mc')]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/reactor-site.json';spec=json.loads(source.read_text());bid=spec['building'];bounds=spec['boundsUTM']
    surveys=nearby_surveys(cache,bounds);raw=next(s for key,s in surveys if key==bid)
    raw_foot=lambda surfaces:unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for k,r in surfaces if k=='GroundSurface'])
    own=raw_foot(raw);all_feet=unary_union([raw_foot(s)for _,s in surveys])
    others=unary_union([raw_foot(s)for key,s in surveys if key!=bid])
    approach=own.buffer(spec['outdoorMarginMetres']).intersection(box(*bounds))
    ground_domain=approach.difference(all_feet.buffer(spec['groundBuildingGuardMetres']))
    # Roofing projections are protected even when absent from the ground outline.
    roof_guards=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for k,r in s if k=='RoofSurface'])
    outdoor=ground_domain.difference(others.union(roof_guards).buffer(spec['buildingGuardMetres']))
    ground=extend_ground(ctx,ground_domain,'reactor-approach-ground',spec['groundRuntimeId'],spec['groundBlendMetres'])
    assert spec['groundRuntimeId']+len(ground['groundTiles'])<1_000_061_300
    with rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'campus-dop-east.tif')as dop:
        elevation=ElevationSampler([dem])
        def rings(region):
            def ring(r):
                xy=np.asarray(r.coords);return mc(np.column_stack([xy,elevation.sample(xy)]))[:,[0,2]].tolist()
            return [{'ring':ring(p.exterior),'holes':[ring(h)for h in p.interiors]}for p in polygons(region)]
        xy=np.array([(e,n)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)])
        guide={'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,'points':mc(np.column_stack([xy,elevation.sample(xy)])).tolist()}
        with tempfile.TemporaryDirectory(prefix='reactor-approach-',dir=cache)as temporary:
            folder=Path(temporary);pixels=dop.read([1,2,3],window=from_bounds(*bounds,dop.transform)).transpose(1,2,0);Image.fromarray(pixels).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':bounds,'terrainGuide':guide,'tiles':[],'replacements':[]}
            previous=[*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[])for t in s.get('vegetation',{}).get('trees',[])]]
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':elevation,'buildings':surveys,'allowedTreeRegionUTM':outdoor.buffer(-spec['trunkInsetMetres']),'excludedTreeCentresUTM':[t['utm']for t in previous]})
            trees=[]
            for i,t in enumerate(sub['tiles']):
                name='reactor-site-'+t['file'];shutil.copy2(folder/t['file'],out/name);trees.append({**t,'file':name,'runtimeId':spec['treeRuntimeId']+i})
            meta['tiles'].extend(trees)
            shutil.copy2(folder/'vegetation-survey.jpg',out/'reactor-site-vegetation-survey.jpg')
        outdoor_rings=rings(outdoor)
        # The entire bounded outdoor footprint is already covered by old/new
        # ground. Register that union so old protected-pixel bands cannot leave
        # floating fragments over an otherwise measured approach.
        meta['supplementalSurfaces'].append({'name':'reactor-approach-retirement','rings':outdoor_rings,'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':True,'vegetation':sub['vegetation'],'qualification':spec['qualification']})
    foot,walls,roof,points=survey_plan(ctx,raw)
    envelope=foot.buffer(spec['facadeCleanupMarginMetres'])
    neighbours=[]
    for key,s in surveys:
        if key==bid:continue
        shape,_,_,q=survey_plan(ctx,s)
        if shape.buffer(spec['buildingGuardMetres']).intersects(envelope):neighbours.append({'id':key,'shape':shape,'top':float(q[:,1].max())+spec['neighbourRoofGuardMetres']})
    levels=sorted(set([float(points[:,1].min())-2,float(points[:,1].max())+3,*[n['top']for n in neighbours if points[:,1].min()-2<n['top']<points[:,1].max()+3]]))
    serialize=lambda shape:[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(shape)]
    retirement=[]
    for a,b in zip(levels[:-1],levels[1:]):
        protected=unary_union([n['shape'].buffer(spec['buildingGuardMetres'])for n in neighbours if n['top']>a+1e-7])
        region=envelope.difference(protected)
        retirement.append({'rings':serialize(region),'y0':a,'y1':b,'kind':'reconstructed-facade-height-band'})
    # Render clipping handles this complete union even where existing terrain
    # has an older protected-site mask. It only touches provider mesh bytes.
    outdoor_heights=np.asarray(guide['points'])[:,1]
    retirement.append({'rings':outdoor_rings,'y0':float(outdoor_heights.min())-2,'y1':float(outdoor_heights.max())+35,'kind':'reconstructed-outdoor-approach'})
    for region in retirement:meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=region['y0'],y1=region['y1'])for p in region['rings'])
    record={'ground':ground,'outdoorRings':outdoor_rings,'groundDomainUTM':ground_domain.__geo_interface__,'outdoorDomainUTM':outdoor.__geo_interface__,'sourceRetirement':retirement,'neighbourProtection':[{'id':n['id'],'top':n['top'],'rings':serialize(n['shape'])}for n in neighbours],'trees':sub['vegetation']['trees'],'qualification':spec['qualification']}
    derived=out/'reactor-site-surfaces.json';derived.write_text(json.dumps(record,indent=2)+'\n')
    meta['architecture']['reactorSite']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_reactor_site.py','generatorSha256':sha(Path(__file__)),'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),'vegetationSourceSha256':sha(root/'minecraft/exterior/vegetation-sources.json'),'derivedFile':derived.name,'derivedSha256':sha(derived),'groundTiles':ground['groundTiles'],'treeTiles':[t['file']for t in trees],'sourceRetirement':retirement,'qualification':spec['qualification']}
    assert len({t['runtimeId']for t in meta['tiles']})==len(meta['tiles'])
    print('FRM II approach:',len(ground['groundTiles']),'new ground tiles;',len(sub['vegetation']['trees']),'additional trees;',len(retirement),'bounded source retirement volumes',flush=True)

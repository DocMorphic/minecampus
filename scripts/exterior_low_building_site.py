"""Survey-bounded low-building courtyard and DOM-anchored stack reconstruction."""
import hashlib
import json
import shutil
import tempfile
import math
import struct
from rasterio.features import shapes
from shapely.geometry import shape, Point
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
    source=root/'minecraft/exterior/low-building-site.json';spec=json.loads(source.read_text())
    bounds=spec['boundsUTM'];surveys=nearby_surveys(cache,bounds)
    raw=next(s for bid,s in surveys if bid==spec['building'])
    footprint=unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0)
                          for kind,p in raw if kind=='RoofSurface'])
    courtyard=unary_union([Polygon(h) for p in polygons(footprint) for h in p.interiors])
    assert not courtyard.is_empty and courtyard.area>1
    # The source GroundSurface has a diagonal bridge between loops. Use the
    # surveyed roof footprint, including its hole, for foliage exclusion too.
    corrected=[]
    for bid,surfaces in surveys:
        if bid==spec['building']:
            surfaces=[(kind,rings) for kind,rings in surfaces if kind!='GroundSurface']
            for p in polygons(footprint):
                rings=[np.column_stack([np.asarray(r.coords),np.full(len(r.coords),474.0)])
                       for r in [p.exterior,*p.interiors]]
                surfaces.append(('GroundSurface',rings))
        corrected.append((bid,surfaces))
    surveys=corrected
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
    # Existing surveyed ground already covers this courtyard; retain its bytes.
    ground={'groundTiles':[],'areaSquareMetres':0,'retainedExistingGround':True}
    with rasterio.open(cache/'campus-dgm-east.tif') as dem,rasterio.open(cache/'campus-dop-east.tif') as dop:
        elevation=ElevationSampler([dem])
        xy=np.array([(e,n) for n in range(bounds[1],bounds[3]+1,2) for e in range(bounds[0],bounds[2]+1,2)])
        guide={'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,
               'points':mc(np.column_stack([xy,elevation.sample(xy)])).tolist()}
        with tempfile.TemporaryDirectory(prefix='low-building-courtyard-',dir=cache) as temporary:
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
                name='low-building-courtyard-'+tile['file'];shutil.copy2(folder/tile['file'],out/name)
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
            # collar is already owned by the reconstructed envelope; their union retires
            # the courtyard scan without extending into adjacent buildings.
            surface={'name':'low-building-courtyard-ground','rings':[{'ring':list(p.exterior.coords),'holes':[]}for p in polygons(courtyard_mc)],
                     'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':True,'vegetation':sub['vegetation'],
                     'qualification':'Existing surveyed terrain retained; bounded source cleanup and fitted courtyard foliage.'}
            meta['supplementalSurfaces'].append(surface)
            coverage={'type':'FeatureCollection','coordinateSystem':'EPSG:25832',
                      'courtyard':courtyard.__geo_interface__,'trees':sub['vegetation']['trees'],
                      'qualification':spec['qualification']}
            coverage_file=out/'low-building-courtyard-coverage.json';coverage_file.write_text(json.dumps(coverage,separators=(',',':'))+'\n')
            shutil.copy2(folder/'vegetation-survey.jpg',out/'low-building-courtyard-vegetation-survey.jpg')
    meta['architecture']['lowBuildingSite']={'building':spec['building'],'sourceFile':source.name,'sourceSha256':sha(source),
        'generatorFile':'scripts/exterior_low_building_site.py','generatorSha256':sha(Path(__file__)),
        'groundGeneratorSha256':sha(root/'scripts/exterior_ground_extension.py'),
        'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),
        'vegetationSourceSha256':sha(root/'minecraft/exterior/vegetation-sources.json'),
        'groundTiles':ground['groundTiles'],'ground':ground,'treeTiles':[t['file'] for t in trees],
        'trees':sub['vegetation']['trees'],'courtyardAreaSquareMetres':courtyard.area,'roofIntersectingLeafCardsRemoved':removed_cards,
        'coverageFile':coverage_file.name,'coverageSha256':sha(coverage_file),'qualification':spec['qualification']}
    build_stack(ctx,spec,meta['architecture']['lowBuildingSite'])
    build_shrubs(ctx,spec,meta['architecture']['lowBuildingSite'])
    print('Low-building courtyard:',len(ground['groundTiles']),'ground tiles;',len(sub['vegetation']['trees']),'trees;',courtyard.area,'m²',flush=True)


def build_stack(ctx,spec,record):
    root,cache,out,meta,mc=[ctx[k] for k in ('ROOT','CACHE','OUT','metadata','mc')]
    dom_path=cache/'32698_5349_20_DOM.tif'
    with rasterio.open(dom_path) as dom:
        window=from_bounds(*spec['stackSearchBoundsUTM'],dom.transform).round_offsets().round_lengths()
        heights=dom.read(1,window=window);transform=dom.window_transform(window)
        mask=heights>=spec['stackThresholdDHHN2016']
        regions=[shape(g) for g,v in shapes(mask.astype('uint8'),mask=mask,transform=transform) if v]
        assert len(regions)==1 and .2<regions[0].area<5
        footprint=regions[0];centre=np.array(footprint.centroid.coords[0]);top=float(np.quantile(heights[mask],.95))
        sampled={'minimumTopDHHN2016':float(heights[mask].min()),'maximumTopDHHN2016':float(heights[mask].max()),
                 'footprintAreaSquareMetres':footprint.area,'footprintUTM':footprint.__geo_interface__,
                 'selectedPixelCount':int(mask.sum()),'pixelMetres':abs(dom.transform.a)}
    with rasterio.open(cache/'campus-dgm-east.tif') as dem:
        floor=float(ElevationSampler([dem]).sample([centre])[0])
    base,tip=mc(np.array([[*centre,floor-.05],[*centre,top]]))
    sides=spec['stackSides'];radius=spec['stackRadiusMetres'];vertices=[];cap=[]
    def tri(dst,*points):dst.extend([*p,.5,.5] for p in points)
    for i in range(sides):
        a,b=[angle*2*math.pi/sides for angle in [i,i+1]]
        p=base+np.array([radius*math.cos(a),0,radius*math.sin(a)])
        q=base+np.array([radius*math.cos(b),0,radius*math.sin(b)])
        u=p+(tip-base);v=q+(tip-base)
        tri(vertices,p,u,v);tri(vertices,p,v,q)
        tri(cap,tip,v,u)
        tri(vertices,base,q,p)
    name='cyclotron-stack.ect';assert not (out/name).exists()
    (out/name).write_bytes(ctx['encode']([(vertices,Image.new('RGBA',(1,1),tuple(spec['stackColour']))),
                                        (cap,Image.new('RGBA',(1,1),(63,68,72,255)))]))
    xyz=np.asarray([v[:3]for v in vertices+cap]);bounds=[xyz.min(0).tolist(),xyz.max(0).tolist()]
    meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'low-building-stack','runtimeId':spec['stackRuntimeId'],
                          'bounds':bounds,'alwaysVisible':True,'fineCollisionMaterials':[4,4]})
    domain=Point(base[0],base[2]).buffer(spec['stackCleanupRadiusMetres'],quad_segs=16)
    protections=[];nearby_roof=-math.inf
    for building in meta['buildings']:
        foot=unary_union([Polygon([(p[0],p[2])for p in ring]).buffer(0)for ring in building['grounds']])
        if domain.intersects(foot.buffer(.15)):
            protections.append(foot.buffer(.15));nearby_roof=max(nearby_roof,building['bounds'][1][1])
    assert nearby_roof<tip[1]-5
    lower=domain.difference(unary_union(protections));split_y=nearby_roof+.1
    retirement=[]
    for region,y0,y1 in [(lower,base[1]-.2,split_y),(domain,split_y,tip[1]+.5)]:
        for p in polygons(region):retirement.append({'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors],
                                                    'y0':y0,'y1':y1,'kind':'architecture','alwaysVisible':True})
    # Explicit clipping handles tall source triangles crossing the bounded
    # retirement volume; its bottom tier excludes all nearby building footprints.
    meta['replacements'].extend(retirement)
    courtyard_surface=next(s for s in meta['supplementalSurfaces'] if s['name']=='low-building-courtyard-ground')
    courtyard_y=[p[1] for p in courtyard_surface['terrainGuide']['points']]
    courtyard_top=max(b['bounds'][1][1] for b in meta['buildings'] if b['id']==spec['building'])+.1
    courtyard_retirement=[{**ring,'y0':min(courtyard_y)-.2,'y1':courtyard_top}for ring in courtyard_surface['rings']]
    record['sourceRetirement']=[{'rings':[{'ring':zone['ring'],'holes':zone.get('holes',[])}],'y0':zone['y0'],'y1':zone['y1']}for zone in retirement+courtyard_retirement]
    record['courtyardSourceRetirement']=courtyard_retirement
    record['stack']={'meshFile':name,'meshSha256':hashlib.sha256((out/name).read_bytes()).hexdigest(),
                     'runtimeId':spec['stackRuntimeId'],'baseMC':base.tolist(),'topMC':tip.tolist(),'radiusMetres':radius,
                     'centreUTM':centre.tolist(),'floorDHHN2016':floor,'topDHHN2016':top,'sourceMeasurements':sampled,
                     'domSha256':hashlib.sha256(dom_path.read_bytes()).hexdigest(),'splitCleanupY':split_y,
                     'qualification':'DOM footprint and height anchor the stack; circular section, radius and metal finish are inferred.'}
    print('Stack: DOM footprint',round(footprint.area,3),'m²; height',round(tip[1]-base[1],3),'m',flush=True)


def build_shrubs(ctx,spec,record):
    """Low courtyard plants excluded by the campus tree detector's 4 m minimum."""
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    from rasterio.features import rasterize
    from scipy import ndimage
    root,cache,out,meta,mc=[ctx[k]for k in ('ROOT','CACHE','OUT','metadata','mc')]
    bounds=spec['boundsUTM'];resolution=.5
    size=((bounds[3]-bounds[1])*2,(bounds[2]-bounds[0])*2)
    transform=from_origin(bounds[0],bounds[3],resolution,resolution)
    fields=[]
    for name in ['32698_5349_20_DOM.tif','campus-dgm-east.tif']:
        with rasterio.open(cache/name)as source:
            field=np.zeros(size,np.float32)
            reproject(rasterio.band(source,1),field,src_transform=source.transform,src_crs=source.crs,
                      dst_transform=transform,dst_crs=source.crs,resampling=Resampling.bilinear)
            fields.append(field)
    dom,dem=fields;rgb=[]
    with rasterio.open(cache/'campus-dop-east.tif')as source:
        for band in [1,2,3]:
            field=np.zeros(size,np.float32)
            reproject(rasterio.band(source,band),field,src_transform=source.transform,src_crs=source.crs,
                      dst_transform=transform,dst_crs=source.crs,resampling=Resampling.bilinear)
            rgb.append(field)
    coverage=json.loads((out/record['coverageFile']).read_text());courtyard=shape(coverage['courtyard'])
    interior=rasterize([(courtyard.buffer(-.5),1)],out_shape=size,transform=transform)>0
    red,green,blue=rgb;height=dom-dem
    foliage=((green>red*1.025)&(green>blue+2))|((red>green*1.04)&(red<green*1.5)&(green>blue*1.08)&(green<blue*1.7)&(green>35)&(green<175))
    mask=foliage&interior&(height>.65)&(height<4.5)
    labels,count=ndimage.label(mask);counts=np.bincount(labels.ravel());mask&=counts[labels]>=4
    leaf=Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_diff_1k.jpg').convert('RGBA')
    leaf.putalpha(Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_alpha_1k.png').convert('L').resize(leaf.size))
    bark=Image.open(cache/'tree-source/textures/jacaranda_tree_trunk_diff_1k.jpg').resize((512,512)).convert('RGBA')
    wood=[];leaves=[];rng=np.random.default_rng(1015203);controls=[]
    # An overhead canopy return does not establish vegetation down to the
    # paving. Keep the inferred walking envelope clear while retaining crowns.
    paving_source=root/'minecraft/exterior/low-building-paving.json'
    paving_spec=json.loads(paving_source.read_text())
    paving=unary_union([Polygon(p['polygonMC']) for p in paving_spec['regions']])
    clearance=spec['pavingPlantClearanceMetres']
    clearance_region=paving.buffer(spec['pavingPlantClearanceMarginMetres'])
    removed_leaves=0;removed_stems=0

    def blocks_path(points,floor):
        if min(p[1] for p in points)>=floor[1]+clearance:return False
        footprint=Polygon(np.asarray(points)[:,[0,2]]).buffer(.00001)
        return footprint.intersects(clearance_region)

    for row,col in np.argwhere(mask):
        en=np.array([bounds[0]+(col+.5)*resolution,bounds[3]-(row+.5)*resolution])
        floor,top=mc(np.array([[*en,dem[row,col]],[*en,dom[row,col]]]))
        controls.append({'utm':en.tolist(),'baseMC':floor.tolist(),'topMC':top.tolist()})
        # Small vertical stems and branch-sprig cards approximate low woody
        # vegetation. Species, stems and lower canopy depth are not surveyed.
        if row%3==0 and col%3==0:
            tip=floor+(top-floor)*min(.2,.45/(top[1]-floor[1]))
            for axis in [0,2]:
                delta=np.zeros(3);delta[axis]=.022
                points=[floor-delta,floor+delta,tip+delta,tip-delta]
                if blocks_path(points,floor):
                    removed_stems+=1;continue
                for k in [0,1,2,0,2,3]:wood.append([*points[k],*[ (0,1),(1,1),(1,0),(0,0)][k]])
        # Multi-directional sprigs form a low thicket instead of repeated
        # upright sapling silhouettes. Only the source canopy envelope is
        # measured; branch orientation and density remain reconstruction.
        for card in range(16):
            centre=floor.copy();centre[[0,2]]+=rng.uniform(-.23,.23,2)
            centre[1]+=rng.uniform(.15,max(.16,top[1]-floor[1]-.15))
            normal=rng.normal(size=3);normal/=np.linalg.norm(normal)
            right=np.cross(normal,[0.,1.,0.])
            if np.linalg.norm(right)<1e-6:continue
            right/=np.linalg.norm(right);up=np.cross(normal,right)
            roll=rng.uniform(0,2*math.pi)
            axis=right*math.cos(roll)+up*math.sin(roll)
            cross=-right*math.sin(roll)+up*math.cos(roll)
            half_width=rng.uniform(.27,.39);half_height=half_width*.53
            points=[centre-axis*half_width-cross*half_height,centre+axis*half_width-cross*half_height,
                    centre+axis*half_width+cross*half_height,centre-axis*half_width+cross*half_height]
            if max(p[1]for p in points)>top[1]+.15 or min(p[1]for p in points)<floor[1]+.025:continue
            if not all(any(Polygon(s['ring']).covers(Point(p[0],p[2]))for s in record['courtyardSourceRetirement'])for p in points):continue
            if blocks_path(points,floor):
                removed_leaves+=1;continue
            for k in [0,1,2,0,2,3]:leaves.append([*points[k],*[(0,.53),(1,.53),(1,0),(0,0)][k]])
    assert wood and leaves and controls
    name='low-building-courtyard-shrubs.ect'
    (out/name).write_bytes(ctx['encode']([(wood,bark),(leaves,leaf)]))
    xyz=np.array([p[:3]for p in wood+leaves]);rid=spec['treeRuntimeId']+50
    meta['tiles'].append({'file':name,'kind':'vegetation','profile':'low-planting','runtimeId':rid,'bounds':[xyz.min(0).tolist(),xyz.max(0).tolist()],
                          'alwaysVisible':True,'collisionParts':[]})
    record['shrubs']={'meshFile':name,'meshSha256':hashlib.sha256((out/name).read_bytes()).hexdigest(),'runtimeId':rid,
                      'detectedAreaSquareMetres':float(mask.sum())*.25,'sampleResolutionMetres':resolution,'samples':controls,
                      'leafCards':len(leaves)//6,'qualification':'DOP foliage colour and DOM height locate low plants; species, stems and leaf cards are reconstructed. Visual shrubs have no solid leaf collision.'}
    record['shrubs']['pavingClearance']={
        'sourceFile':paving_source.name,'sourceSha256':hashlib.sha256(paving_source.read_bytes()).hexdigest(),
        'heightMetres':clearance,'marginMetres':spec['pavingPlantClearanceMarginMetres'],
        'removedLeafCards':removed_leaves,'removedStemCards':removed_stems,
        'qualification':'Inferred walking-height clearance over the interpreted paved route. DOM locates canopy, not ground-level stems beneath it. Higher canopy and all ordinary Minecraft blocks are retained.'}
    print('Courtyard low plants:',len(controls),'source cells;',len(leaves)//6,'leaf cards',flush=True)

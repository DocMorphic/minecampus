"""Source-informed Physik II and its raised connection; no interior reconstruction."""
import hashlib,json,math,shutil,tempfile
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon,LineString,box,mapping
from shapely.ops import unary_union,triangulate
from exterior_physics_i import nearby_surveys,survey_plan,roof_texture,polygons
from exterior_physics_library import triangles
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def ground_transition(root, spec, prior):
    """Join surveyed ground to sampled retained ground only at exposed edges."""
    source = root/'minecraft/exterior'/spec['groundTransition']['sourceFile']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == spec['groundTransition']['sha256']
    record = json.loads(source.read_text())
    segments, residuals, missing = [], [], []
    for line in record['lines']:
        for i in range(len(line['utm'])-1):
            delta = line.get('joinDelta', line['delta'])[i:i+2]
            if any(v is None for v in delta):
                missing.append(LineString(line['utm'][i:i+2]))
                continue
            segments.append(line['utm'][i:i+2]); residuals.append(delta)
    missing = unary_union(missing)
    segments, residuals = np.asarray(segments), np.asarray(residuals)
    a = segments[:,0]; direction = segments[:,1]-a
    length2 = np.sum(direction**2, axis=1)
    def correction(xy):
        from shapely import points, distance
        xy = np.asarray(xy); result = np.zeros(len(xy))
        for start in range(0, len(xy), 1024):
            q = xy[start:start+1024]
            t = np.clip(np.sum((q[:,None,:]-a)*direction, axis=2)/length2, 0, 1)
            d = np.linalg.norm(q[:,None,:]-a-t[:,:,None]*direction, axis=2)
            nearest = d.argmin(axis=1); row = np.arange(len(q))
            fade = np.clip(1-d[row,nearest]/record['widthMetres'], 0, 1)
            prior_fade = np.clip(distance(points(q), prior)/record['priorFadeMetres'], 0, 1)
            missing_fade = (np.clip(distance(points(q), missing)/record['priorFadeMetres'], 0, 1)
                            if not missing.is_empty else np.ones(len(q)))
            along = t[row,nearest]
            residual = residuals[nearest,0]*(1-along)+residuals[nearest,1]*along
            result[start:start+len(q)] = residual*fade**2*(3-2*fade)*prior_fade**2*(3-2*prior_fade)*missing_fade**2*(3-2*missing_fade)
        return result
    return correction, record

def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ['ROOT','CACHE','OUT','metadata','mc','encode']];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/physics-ii.json';spec=json.loads(source.read_text());assert sha(root/'minecraft/exterior'/spec['reference'])==spec['referenceSha256']
    surveys=nearby_surveys(cache, spec['surveyBoundsUtm']);owned={b['building']for b in spec['bodies']};bodydata=[]
    for b in spec['bodies']:
        surfaces=next(s for bid,s in surveys if bid==b['building']);foot,walls,roof,points=survey_plan(ctx,surfaces);base=float(points[:,1].min());utm=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for k,r in surfaces if k=='GroundSurface'])
        bodydata.append(dict(spec=b,foot=foot,walls=walls,roof=roof,points=points,base=base,utm=utm))
    other=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for bid,s in surveys if bid not in owned for k,r in s if k=='GroundSurface'])
    other_utm=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for bid,s in surveys if bid not in owned for k,r in s if k=='GroundSurface'])
    plans=json.loads((out/'photo-facades.json').read_text());records=[];meshtiles=[]
    for body in bodydata:
        b=body['spec'];bid=b['building'];foot,walls,roof,points,base=[body[k]for k in ['foot','walls','roof','points','base']];parts=[[]for _ in range(4)];textures=[Image.new('RGBA',(1,1),tuple(c))for c in b.get('materialColours',spec['materialColours'])];controls=[];shared=[];joints=[]
        detail={**spec,**b}
        def emit(q,part,normal):
            q=np.asarray(q)
            if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0:q=q[::-1]
            for i in ([0,1,2]if len(q)==3 else [0,1,2,0,2,3]):parts[part].append([*q[i],.5,.5])
        underside=base+b.get('undersideAboveSurveyBaseMetres',-.6)
        for index,wall in enumerate(walls):
            anchor,direction,normal=[np.asarray(wall[k])for k in ['anchor','direction','normal']];shape=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0);left,bottom,right,top=shape.bounds
            if b['name']=='bridge':shape=shape.intersection(box(left,underside,right,top+.01))
            elif bottom<=base+.05:shape=shape.union(box(left,base-.6,right,base+.01))
            def pt(x,y,depth=0):
                p=anchor+direction*x+normal*depth;p[1]=y;return p
            def surface(poly,part,depth=0):
                for tri in triangles(poly):emit([pt(x,y,depth)for x,y in tri],part,normal)
            # Remove only wall intervals facing another owned survey body.
            # Bridge adjacency starts at its underside, leaving the ground route open.
            line=LineString([pt(left,base,.02)[[0,2]],pt(right,base,.02)[[0,2]]])
            for adjacent in bodydata:
                if adjacent is body:continue
                cut=line.intersection(adjacent['foot']);segments=[cut]if cut.geom_type=='LineString'else list(getattr(cut,'geoms',[]))
                for segment in segments:
                    if segment.geom_type!='LineString'or segment.length<.05:continue
                    xs=[float(np.dot(np.array([q[0],base,q[1]])-anchor,direction))for q in segment.coords];low=adjacent['base']+adjacent['spec'].get('undersideAboveSurveyBaseMetres',-.6);high=float(adjacent['points'][:,1].max());removed=shape.intersection(box(min(xs),low,max(xs),high));shape=shape.difference(removed)
                    if removed.area>.001:shared.append({'face':index,'adjacent':adjacent['spec']['building'],'rectangle':[min(xs),low,max(xs),high],'area':removed.area})
            openings=[]
            for rectangle in b['openings'].get(str(index),[]):
                x0,y0,x1,y1=rectangle;y0+=base;y1+=base;opening=shape.intersection(box(x0,y0,x1,y1))
                if opening.is_empty:continue
                openings.append(opening);inner=opening.buffer(-detail['frameWidthMetres'],join_style=2)
                mullions=[box(x-detail['mullionWidthMetres']/2,y0,x+detail['mullionWidthMetres']/2,y1)for x in np.arange(x0+detail['mullionPitchMetres'],x1-.05,detail['mullionPitchMetres'])]
                split=detail.get('windowHorizontalSplitFraction',.4)
                if y1-y0>1 and split is not None:mullions.append(box(x0,y0+(y1-y0)*split-.025,x1,y0+(y1-y0)*split+.025))
                frame=inner.intersection(unary_union(mullions));glass=inner.difference(frame);surface(glass,1,-detail['windowRecessMetres']);surface(opening.difference(inner),2,-.01);surface(frame,2,-.08)
                for p in polygons(opening):
                    for a,c in zip(np.array(p.exterior.coords[:-1]),np.array(p.exterior.coords[1:])):emit([pt(*a),pt(*c),pt(*c,-detail['windowRecessMetres']),pt(*a,-detail['windowRecessMetres'])],2,normal)
                if not glass.is_empty:
                    g=max(polygons(glass),key=lambda p:p.area).representative_point();controls.append({'face':index,'part':1,'position':pt(g.x,g.y,-detail['windowRecessMetres']).tolist(),'normal':normal.tolist(),'rectangle':[x0,y0,x1,y1]})
            solid=shape.difference(unary_union(openings));strips=[box(x-detail['panelJointMetres']/2,base-.6,x+detail['panelJointMetres']/2,top+.01)for x in np.arange(left+detail['panelPitchMetres'],right-.04,detail['panelPitchMetres'])]
            floor_joint=detail.get('floorJointAboveBaseMetres',3.65)
            if b['name']!='bridge':strips.append(box(left,base+floor_joint-.006,right,base+floor_joint+.006))
            grooves=solid.intersection(unary_union(strips));surface(solid.difference(grooves),0);surface(solid,3,-detail['jointDepthMetres'])
            for poly in polygons(grooves):
                if poly.is_empty or poly.area<1e-8:continue
                p=poly.representative_point();joints.append({'face':index,'position':pt(p.x,p.y,-detail['jointDepthMetres']).tolist(),'normal':normal.tolist()})
            wall['reconstructed']=True
        if b['name']=='bridge':
            for xy in triangles(foot):emit(np.column_stack([xy[:,0],np.full(3,underside),xy[:,1]]),0,[0,-1,0])
        rv,rp=roof_texture(cache,roof);parts.append(rv.tolist());textures.append(rp);assert all(parts)
        name=bid+'-physics-ii.ect';(out/name).write_bytes(encode(list(zip(parts,textures))));v=np.concatenate([np.asarray(p)[:,:3]for p in parts]);tile={'file':name,'kind':'reconstruction','runtimeId':b['runtimeId'],'bounds':[v.min(0).tolist(),v.max(0).tolist()]};meshtiles.append(tile)
        roofname=bid+'-photo-roof.ect';(out/roofname).write_bytes(encode([(rv,rp)]));cleanup=foot.buffer(spec['cleanupMarginMetres']).difference(other.buffer(.5));rings=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(cleanup)]
        assert bid not in [p['id']for p in plans['plans']]
        plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roofname,'collisionFile':roofname,'bounds':[points.min(0).tolist(),points.max(0).tolist()],'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':rings,'retirementBoundary':rings})
        meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roofname);meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=base-2,y1=float(points[:,1].max())+4)for p in rings)
        records.append({'building':bid,'name':b['name'],'meshFile':name,'roofFile':roofname,'baseMC':base,'undersideMC':underside if b['name']=='bridge'else None,'openingControls':controls,'jointControls':joints,'sharedWallCuts':shared,'surveyWalls':walls,'roofTriangles':len(roof)//3,'retirement':rings})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')));meta['tiles'].extend(meshtiles)
    # Survey ground closes the old footprint guard and supports the raised bridge.
    # Existing surfaces are subtracted; the courtyard remains open to the sky.
    lat,lon=map(math.radians,meta['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]));east=np.array([-math.sin(lon),math.cos(lon),0]);up=np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)]);south=np.array([math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]);inverse=Transformer.from_crs(4978,25832,always_xy=True)
    def ring_utm(ring):
        q=np.asarray(ring);p=origin+q[:,0,None]*east+q[:,1,None]*south+up;e,n,_=inverse.transform(*p.T);return np.column_stack([e,n])
    prior=unary_union([box(*meta['boundsUtm']),*[Polygon(ring_utm(p['ring']),[ring_utm(h)for h in p.get('holes',[])])for s in meta.get('supplementalSurfaces',[])for p in s['rings']]])
    from exterior_physics_ii_landscape import classify,write_materials,canopy_extension,mapped_extent,close_small_voids
    envelope=unary_union([Polygon(b['utm'].exterior)for b in bodydata])
    primary_envelope=unary_union([Polygon(b['utm'].exterior)for b in bodydata if 'landscapeApronMetres'not in b['spec']])
    base_extent=unary_union([primary_envelope.buffer(spec['apronMetres']),*[Polygon(b['utm'].exterior).buffer(b['spec']['landscapeApronMetres'])for b in bodydata if 'landscapeApronMetres'in b['spec']]])
    base_extent=base_extent.union(mapped_extent(root,spec['landscape']))
    canopy,canopy_records=canopy_extension(cache,spec['landscape'],unary_union([other_utm,*[b['utm']for b in bodydata]]),base_extent)
    landscape_extent=base_extent.union(canopy.buffer(spec['landscape']['canopyExtent']['groundMarginMetres']))
    landscape_extent=close_small_voids(landscape_extent,spec['landscape']['coverage']['maximumEnclosedVoidSquareMetres'])
    area=landscape_extent.difference(other_utm.buffer(.5)).difference(prior.buffer(.002))
    step=spec['groundTileMetres'];lo=(np.floor(np.array(area.bounds[:2])/step)*step).astype(int);hi=(np.ceil(np.array(area.bounds[2:])/step)*step).astype(int);groundtiles=[];treetiles=[]
    layers,features,path_guard=classify(root,cache,spec,area,unary_union([b['utm']for b in bodydata]))
    def ground_triangles(region):
        for cell in triangulate(region):
            yield from triangles(cell.intersection(region))
    with rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'campus-dop-east.tif')as dop:
        sampler=ElevationSampler([dem]);correction,transition=ground_transition(root,spec,prior);xyz=lambda xy:mc(np.column_stack([np.asarray(xy),sampler.sample(np.asarray(xy))+correction(xy)]))
        def rings(shape):return [{'ring':xyz(np.asarray(p.exterior.coords))[:,[0,2]].tolist(),'holes':[xyz(np.asarray(h.coords))[:,[0,2]].tolist()for h in p.interiors]}for p in polygons(shape)]
        for n in range(lo[1],hi[1],step):
            for e in range(lo[0],hi[0],step):
                region=area.intersection(box(e,n,e+step,n+step))
                if region.area<.001:continue
                vertices=[]
                for y in range(n,n+step):
                    for x in range(e,e+step):
                        for xy in ground_triangles(region.intersection(box(x,y,x+1,y+1))):vertices.extend(np.column_stack([xyz(xy),(xy[:,0]-e)/step,(n+step-xy[:,1])/step]).tolist())
                col,row=(~dop.transform)*(e,n+step);rgb=dop.read([1,2,3],window=Window(round(col),round(row),step*5,step*5)).transpose(1,2,0);name=f'physics-ii-ground-{e}-{n}.ect';(out/name).write_bytes(encode([(vertices,Image.fromarray(rgb))]));v=np.asarray(vertices)[:,:3];groundtiles.append({'file':name,'kind':'ground','runtimeId':spec['groundRuntimeStart']+len(groundtiles),'bounds':[v.min(0).tolist(),v.max(0).tolist()]})
        xy=np.array([(e,n)for n in range(lo[1],hi[1]+1,2)for e in range(lo[0],hi[0]+1,2)]);guide={'width':int((hi[0]-lo[0])//2+1),'height':int((hi[1]-lo[1])//2+1),'points':xyz(xy).tolist()};surface={'name':'physics-ii-site','rings':rings(area),'terrainGuide':guide,'protectedFootprints':rings(other_utm.buffer(3)),'outdoorReconstructed':True,'qualification':spec['qualification']}
        with tempfile.TemporaryDirectory(prefix='physics-ii-',dir=cache)as temp:
            folder=Path(temp);col,row=(~dop.transform)*(lo[0],hi[1]);rgb=dop.read([1,2,3],window=Window(round(col),round(row),int((hi[0]-lo[0])*5),int((hi[1]-lo[1])*5))).transpose(1,2,0);Image.fromarray(rgb).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':[*map(int,lo),*map(int,hi)],'terrainGuide':guide,'tiles':[],'replacements':[]};previous=[*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[])for t in s.get('vegetation',{}).get('trees',[])]]
            class JoinedHeight:
                def __call__(self,e,n):
                    xy=np.array([[e,n]]);return float(sampler.sample(xy)[0]+correction(xy)[0])
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':JoinedHeight(),'buildings':surveys,'allowedTreeRegionUTM':area.difference(unary_union([b['utm']for b in bodydata]).buffer(.5)).difference(path_guard),'excludedTreeCentresUTM':[t['utm']for t in previous]})
            for i,t in enumerate(sub['tiles']):
                name='physics-ii-'+t['file'];shutil.copy2(folder/t['file'],out/name);treetiles.append({**t,'file':name,'runtimeId':spec['treeRuntimeStart']+i})
            mc_area=unary_union([Polygon(p['ring'],p['holes'])for p in surface['rings']])
            for replacement in sub['replacements']:
                for p in polygons(Polygon(replacement['ring'],replacement.get('holes',[])).intersection(mc_area)):meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]})
            for key in ['surfaceGuide','vegetationOverhang','vegetation']:surface[key]=sub[key]
            shutil.copy2(folder/'vegetation-survey.jpg',out/'physics-ii-vegetation-survey.jpg')
    from exterior_physics_ii_planting import build as build_planting
    courtyard=Polygon(bodydata[0]['utm'].interiors[0]);shrubtiles,shrubs=build_planting(cache,out,mc,encode,courtyard,spec['treeRuntimeStart']+50)
    surface['vegetation']['shrubs']=shrubs
    meta['tiles'].extend(groundtiles+treetiles+shrubtiles);meta.setdefault('supplementalSurfaces',[]).append(surface);coverage=out/'physics-ii-coverage.geojson';coverage.write_text(json.dumps({'ground':mapping(area),'envelope':mapping(envelope),'landscapeEnvelope':mapping(landscape_extent),'canopySourceArea':mapping(canopy),'priorGround':mapping(prior.intersection(landscape_extent.buffer(4))),'otherBuildings':mapping(other_utm.intersection(landscape_extent.buffer(4))), 'trunkExclusion':mapping(path_guard.intersection(landscape_extent.buffer(4)))},separators=(',',':'))+'\n')
    meta['architecture']['physicsII']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_ii.py','generatorSha256':sha(Path(__file__)),'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),'bodies':records,'groundTiles':[t['file']for t in groundtiles],'treeTiles':[t['file']for t in treetiles],'treeCount':len(surface['vegetation']['trees']),'canopyComponents':canopy_records,'shrubTiles':[t['file']for t in shrubtiles],'shrubControls':shrubs,'plantingGeneratorSha256':sha(root/'scripts/exterior_physics_ii_planting.py'),'groundAreaSquareMetres':area.area,'coverageFile':coverage.name,'coverageSha256':sha(coverage),'qualification':spec['qualification'],'groundTransition':spec['groundTransition']}
    meta['architecture']['physicsII'].update(write_materials(root,out,mc,guide,layers,features))
    shutil.copy2(root/'minecraft/exterior'/spec['groundTransition']['sourceFile'],out/spec['groundTransition']['sourceFile'])
    print('Physik II:',len(records),'bodies;',sum(len(b['openingControls'])for b in records),'opening groups;',len(groundtiles),'ground tiles;',len(surface['vegetation']['trees']),'trees',flush=True)

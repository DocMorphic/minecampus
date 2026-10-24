"""Fill the surveyed west-site coverage gap without changing earlier campus meshes."""
import hashlib,json,math,shutil,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.features import rasterize
from rasterio.transform import from_origin
from pyproj import Transformer
from PIL import Image
from shapely.geometry import Polygon,Point,LineString,box,mapping
from shapely.ops import unary_union
from exterior_physics_i import polygons
from exterior_physics_library import triangles
from exterior_physics_woodland import surveys
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/physics-laboratory-site.json';spec=json.loads(source.read_text());bounds=spec['boundsUTM'];extent=box(*bounds)
    osm_file=root/'minecraft/exterior'/spec['osm']['sourceFile'];assert sha(osm_file)==spec['osm']['sha256']
    osm=ET.parse(osm_file).getroot();to_utm=Transformer.from_crs(4326,25832,always_xy=True).transform
    nodes={n.get('id'):to_utm(float(n.get('lon')),float(n.get('lat')))for n in osm.findall('node')};ways={}
    for w in osm.findall('way'):
        xy=[nodes[n.get('ref')]for n in w.findall('nd')];ways[w.get('id')]=(xy,{t.get('k'):t.get('v')for t in w.findall('tag')})
    buildings=surveys(cache,bounds)
    footprints=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for _,s in buildings for k,r in s if k=='GroundSurface'])
    osm_buildings=unary_union([Polygon(xy).buffer(0)for xy,t in ways.values()if 'building'in t and xy[0]==xy[-1]])
    excluded=footprints.union(osm_buildings).buffer(spec['neighbourGuardMetres'])
    lat,lon=map(math.radians,meta['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]));east=np.array([-math.sin(lon),math.cos(lon),0]);up=np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)]);south=np.array([math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]);to_grid=Transformer.from_crs(4978,25832,always_xy=True)
    def old_ring(ring):
        q=np.asarray(ring);p=origin+q[:,0,None]*east+q[:,1,None]*south+up;e,n,_=to_grid.transform(*p.T);return np.column_stack([e,n])
    prior=unary_union([box(*meta['boundsUtm']),*[Polygon(old_ring(p['ring']),[old_ring(h)for h in p.get('holes',[])])for s in meta.get('supplementalSurfaces',[])for p in s['rings']]])
    area=extent.difference(excluded).difference(prior.buffer(spec['oldSurfaceGuardMetres']))
    layers={'grass':[],'asphalt':[]};features=[];path_guards=[];fences=[]
    for wid,(xy,tags)in ways.items():
        if tags.get('barrier')=='fence'and tags.get('fence_type')=='railing':fences.append((wid,LineString(xy)))
        material=None;shape=None;width=None
        if tags.get('landuse')=='grass'and xy[0]==xy[-1]:material='grass';shape=Polygon(xy).buffer(0)
        if tags.get('highway')=='footway':
            width=float(tags.get('width',spec['defaultPathWidthMetres']));shape=LineString(xy).buffer(width/2,cap_style=2,join_style=2);path_guards.append(shape.buffer(.35))
            material='asphalt'if tags.get('surface')=='asphalt'else None
        if material:
            shape=shape.intersection(area);layers[material].append(shape);features.append({'type':'Feature','properties':{'osmWay':wid,'material':material,'widthMetres':width,'tags':tags},'geometry':mapping(shape)})
    layers={k:unary_union(v)for k,v in layers.items()};layers['grass']=layers['grass'].difference(layers['asphalt'])
    trunk_exclusion=unary_union(path_guards+[line.buffer(.7)for _,line in fences])
    ground_tiles=[];tree_tiles=[];railing_tiles=[];controls=[]
    with rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'campus-dop-east.tif')as photo:
        elevation=ElevationSampler([dem]);xyz=lambda xy:mc(np.column_stack([np.asarray(xy),elevation.sample(np.asarray(xy))]))
        def rings(shape):return [{'ring':xyz(np.asarray(p.exterior.coords))[:,[0,2]].tolist(),'holes':[xyz(np.asarray(h.coords))[:,[0,2]].tolist()for h in p.interiors]}for p in polygons(shape)]
        step=spec['groundTileMetres']
        for n in range(bounds[1],bounds[3],step):
            for e in range(bounds[0],bounds[2],step):
                region=area.intersection(box(e,n,e+step,n+step))
                if region.area<.01:continue
                vertices=[]
                for y in range(n,n+step):
                    for x in range(e,e+step):
                        for xy in triangles(region.intersection(box(x,y,x+1,y+1))):vertices.extend(np.column_stack([xyz(xy),(xy[:,0]-e)/step,(n+step-xy[:,1])/step]).tolist())
                col,row=(~photo.transform)*(e,n+step);rgb=photo.read([1,2,3],window=Window(round(col),round(row),step*5,step*5)).transpose(1,2,0)
                name=f'laboratory-site-ground-{e}-{n}.ect';(out/name).write_bytes(encode([(vertices,Image.fromarray(rgb))]));q=np.asarray(vertices)[:,:3]
                ground_tiles.append({'file':name,'kind':'ground','runtimeId':spec['groundRuntimeStart']+len(ground_tiles),'bounds':[q.min(0).tolist(),q.max(0).tolist()]})
        xy=np.array([(e,n)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)]);guide={'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,'points':xyz(xy).tolist()}
        surface={'name':'physics-laboratory-west-site','rings':rings(area),'terrainGuide':guide,'protectedFootprints':rings(footprints.buffer(3).union(osm_buildings.buffer(1))),'outdoorReconstructed':True,'qualification':spec['qualification']}
        with tempfile.TemporaryDirectory(prefix='laboratory-site-',dir=cache)as temp:
            folder=Path(temp);col,row=(~photo.transform)*(bounds[0],bounds[3]);rgb=photo.read([1,2,3],window=Window(round(col),round(row),(bounds[2]-bounds[0])*5,(bounds[3]-bounds[1])*5)).transpose(1,2,0);Image.fromarray(rgb).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':bounds,'terrainGuide':guide,'tiles':[],'replacements':[]};previous=[*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[])for t in s.get('vegetation',{}).get('trees',[])]]
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':elevation,'buildings':buildings,'allowedTreeRegionUTM':area.difference(trunk_exclusion),'excludedTreeCentresUTM':[t['utm']for t in previous]})
            for i,t in enumerate(sub['tiles']):
                name='laboratory-site-'+t['file'];shutil.copy2(folder/t['file'],out/name);tree_tiles.append({**t,'file':name,'runtimeId':spec['treeRuntimeStart']+i})
            mc_area=unary_union([Polygon(p['ring'],p['holes'])for p in surface['rings']])
            for replacement in sub['replacements']:
                for p in polygons(Polygon(replacement['ring'],replacement.get('holes',[])).intersection(mc_area)):meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]})
            for key in ['surfaceGuide','vegetationOverhang','vegetation']:surface[key]=sub[key]
            shutil.copy2(folder/'vegetation-survey.jpg',out/'laboratory-site-vegetation-survey.jpg')
        # Mapped railings remain present when the old outdoor scan is retired.
        # Exact alignment is sourced; cylindrical members and dimensions are estimates.
        mesh=[];railing=spec['railing']
        def tube(a,b,radius):
            a,b=np.array(a),np.array(b);axis=b-a;axis/=np.linalg.norm(axis);helper=np.array([0.,1,0])if abs(axis[1])<.9 else np.array([1.,0,0]);u=np.cross(axis,helper);u/=np.linalg.norm(u);v=np.cross(axis,u)
            ring=[radius*(u*math.cos(i*math.tau/8)+v*math.sin(i*math.tau/8))for i in range(8)]
            for i in range(8):
                j=(i+1)%8
                for p in [a+ring[i],b+ring[i],b+ring[j],a+ring[i],b+ring[j],a+ring[j],a,a+ring[j],a+ring[i],b,b+ring[i],b+ring[j]]:mesh.append([*p,.5,.5])
        for wid,line in fences:
            assert not line.intersects(footprints)
            # Subdivide rails so their grade follows the measured ground.
            samples=np.linspace(0,line.length,max(2,math.ceil(line.length/.5)+1));xy=np.array([[line.interpolate(s).x,line.interpolate(s).y]for s in samples]);base=xyz(xy)
            for height in [.15,railing['heightMetres']]:
                points=base+[0,height,0]
                for a,b in zip(points[:-1],points[1:]):tube(a,b,railing['railRadiusMetres'])
            for pitch,radius in [(railing['postPitchMetres'],railing['postRadiusMetres']),(railing['picketPitchMetres'],railing['picketRadiusMetres'])]:
                for distance in np.linspace(0,line.length,max(2,math.ceil(line.length/pitch)+1)):
                    p=line.interpolate(distance);a=xyz([[p.x,p.y]])[0];tube(a+[0,.08,0],a+[0,railing['heightMetres'],0],radius)
            controls.append({'osmWay':wid,'lineUTM':list(line.coords),'lengthMetres':line.length,'heightMetres':railing['heightMetres']})
        if mesh:
            name='laboratory-site-railing.ect';(out/name).write_bytes(encode([(mesh,Image.new('RGBA',(1,1),(112,119,120,255)))]));q=np.asarray(mesh)[:,:3];railing_tiles.append({'file':name,'kind':'reconstruction','runtimeId':spec['railingRuntimeId'],'bounds':[q.min(0).tolist(),q.max(0).tolist()]})
    meta['tiles'].extend(ground_tiles+tree_tiles+railing_tiles);meta.setdefault('supplementalSurfaces',[]).append(surface)
    size=1024;span=128;points=np.asarray(guide['points']);ax=math.floor(points[:,0].min()/16)*16;az=math.ceil(points[:,2].max()/16)*16;assert points[:,0].max()<ax+span and points[:,2].min()>az-span
    pixels=np.zeros((size,size,4),dtype=np.uint8);pixels[:,:,3]=255
    for channel,kind in [(0,'grass'),(2,'asphalt')]:
        shapes=[]
        for p in polygons(layers[kind]):
            def q(ring):
                xy=np.asarray(ring.coords);return mc(np.column_stack([xy,np.full(len(xy),475)]))[:,[0,2]]
            shapes.append((Polygon(q(p.exterior),[q(h)for h in p.interiors]),255))
        if shapes:pixels[:,:,channel]=rasterize(shapes,out_shape=(size,size),transform=from_origin(ax,az,span/size,span/size),dtype='uint8')
    target=root/'minecraft/exterior/assets/textures/campus/laboratory_site_ground_surfaces.png';Image.fromarray(pixels).save(target,optimize=True)
    shader=root/'minecraft/exterior/shaders/campus_ground.fsh';text=shader.read_text();start='// BEGIN GENERATED LABORATORY SITE MAPPING\n';end='// END GENERATED LABORATORY SITE MAPPING';mapping_source=f'vec2 laboratorySiteUv(vec2 position) {{ return vec2(position.x-{ax:.1f},{az:.1f}-position.y)/{span:.1f}; }}\n'
    if start not in text:text=text.replace('void main() {',start+end+'\nvoid main() {')
    prefix,rest=text.split(start);_,suffix=rest.split(end);shader.write_text(prefix+start+mapping_source+end+suffix)
    derived=out/'laboratory-site-surfaces.geojson';derived.write_text(json.dumps({'type':'FeatureCollection','coordinateSystem':'EPSG:25832','license':'ODbL1.0','attribution':'© OpenStreetMap contributors','features':features},separators=(',',':'))+'\n')
    coverage=out/'laboratory-site-coverage.geojson';coverage.write_text(json.dumps({'ground':mapping(area),'priorGround':mapping(prior.intersection(extent)),'surveyBuildings':mapping(footprints.intersection(extent)),'osmBuildings':mapping(osm_buildings),'trunkExclusion':mapping(trunk_exclusion)},separators=(',',':'))+'\n')
    meta['architecture']['physicsLaboratorySite']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_laboratory_site.py','generatorSha256':sha(Path(__file__)),'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),'groundTiles':[t['file']for t in ground_tiles],'treeTiles':[t['file']for t in tree_tiles],'railingTiles':[t['file']for t in railing_tiles],'railingControls':controls,'treeCount':len(sub['vegetation']['trees']),'groundAreaSquareMetres':area.area,'coverageFile':coverage.name,'coverageSha256':sha(coverage),'materialDerivedFile':derived.name,'materialDerivedSha256':sha(derived),'materialMaskFile':'assets/textures/campus/'+target.name,'materialMaskSha256':sha(target),'materialMaskBoundsMC':[[ax,az-span],[ax+span,az]],'shaderMappingSha256':hashlib.sha256(mapping_source.encode()).hexdigest(),'qualification':spec['qualification']}
    print('Laboratory west site:',len(ground_tiles),'ground tiles;',len(sub['vegetation']['trees']),'trees;',len(controls),'railings;',round(area.area,2),'m²',flush=True)

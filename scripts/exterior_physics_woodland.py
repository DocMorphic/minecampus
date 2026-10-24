"""Survey terrain/canopy on the campus side of the Garchinger Mühlbach."""
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
from shapely.ops import unary_union,transform
from exterior_physics_i import polygons
from exterior_physics_library import triangles
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def surveys(cache,bounds):
    ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'};result=[];limit=box(*bounds).buffer(30)
    for filename in ['campus-east.gml','campus-west.gml']:
        for b in ET.parse(cache/filename).findall('.//b:Building',ns):
            grounds=[np.array(list(map(float,p.text.split()))).reshape(-1,3)for p in b.findall('.//b:GroundSurface//g:posList',ns)]
            if not grounds:continue
            points=np.concatenate(grounds)
            if not box(*points[:,:2].min(0),*points[:,:2].max(0)).intersects(limit):continue
            surfaces=[]
            for kind in ['GroundSurface','WallSurface','RoofSurface']:
                for poly in b.findall('.//b:'+kind+'//g:Polygon',ns):
                    rings=[]
                    for ring in poly.findall('.//g:LinearRing',ns):
                        p=ring.find('g:posList',ns)
                        if p is None:continue
                        v=np.array(list(map(float,p.text.split()))).reshape(-1,3)
                        if np.linalg.norm(v[0]-v[-1])<.001:v=v[:-1]
                        if len(v)>=3:rings.append(v)
                    if rings:surfaces.append((kind,rings))
            result.append((b.get('{'+ns['g']+'}id'),surfaces))
    return result


def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/physics-woodland.json';spec=json.loads(source.read_text());bounds=spec['boundsUTM'];extent=box(*bounds)
    osm_path=root/'minecraft/exterior'/spec['osm']['sourceFile'];assert sha(osm_path)==spec['osm']['sha256']
    osm=ET.parse(osm_path).getroot();to_utm=Transformer.from_crs(4326,25832,always_xy=True).transform
    nodes={n.get('id'):to_utm(float(n.get('lon')),float(n.get('lat')))for n in osm.findall('node')};ways={}
    for w in osm.findall('way'):
        xy=[nodes.get(n.get('ref'))for n in w.findall('nd')]
        if len(xy)>=2 and all(p is not None for p in xy):ways[w.get('id')]=(xy,{t.get('k'):t.get('v')for t in w.findall('tag')})
    river=Polygon(ways[spec['waterWay']][0]).buffer(0)
    land=next(p for p in polygons(extent.difference(river))if p.covers(Point(*spec['landControlUTM'])))
    buildings=surveys(cache,bounds)
    footprints=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for _,s in buildings for k,r in s if k=='GroundSurface'])
    # Earlier supplemental rings are stored in the tangent frame. A 2mm guard
    # covers sub-millimetre horizontal changes when inverting at a common height.
    to_ecef=Transformer.from_crs(4979,4978,always_xy=True);to_grid=Transformer.from_crs(4978,25832,always_xy=True)
    lat,lon=map(math.radians,meta['origin'][:2]);origin=np.array(to_ecef.transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]));east=np.array([-math.sin(lon),math.cos(lon),0]);up=np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)]);south=np.array([math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)])
    def old_ring(r):
        q=np.asarray(r);ecef=origin+q[:,0,None]*east+q[:,1,None]*south+up
        e,n,_=to_grid.transform(*ecef.T);return np.column_stack([e,n])
    prior=unary_union([box(*meta['boundsUtm']),*[Polygon(old_ring(p['ring']),[old_ring(h)for h in p.get('holes',[])])for s in meta.get('supplementalSurfaces',[])for p in s['rings']]])
    area=land.difference(footprints.buffer(spec['neighbourGuardMetres'])).difference(prior.buffer(spec['oldSurfaceGuardMetres']))
    path_guards=[]
    for xy,tags in ways.values():
        if tags.get('highway')not in ['path','footway','cycleway','service']:continue
        fallback=spec['pathWidthsMetres'].get(tags.get('surface',''),2)
        try:width=float(tags.get('width',fallback))
        except ValueError:width=fallback
        path_guards.append(LineString(xy).buffer(max(.5,min(8,width))/2+.35,cap_style=2,join_style=2))
    trunk_exclusion=unary_union(path_guards).intersection(land)
    ground_tiles=[];records=[]
    with rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'campus-dop-east.tif')as photo:
        elevation=ElevationSampler([dem])
        xyz=lambda xy:mc(np.column_stack([np.asarray(xy),elevation.sample(np.asarray(xy))]))
        def rings(shape):return [{'ring':xyz(np.asarray(p.exterior.coords))[:,[0,2]].tolist(),'holes':[xyz(np.asarray(h.coords))[:,[0,2]].tolist()for h in p.interiors]}for p in polygons(shape)]
        step=spec['groundTileMetres']
        for n in range(bounds[1],bounds[3],step):
            for e in range(bounds[0],bounds[2],step):
                region=area.intersection(box(e,n,min(e+step,bounds[2]),min(n+step,bounds[3])))
                if region.area<.01:continue
                vertices=[]
                for y in range(n,min(n+step,bounds[3])):
                    for x in range(e,min(e+step,bounds[2])):
                        for xy in triangles(region.intersection(box(x,y,x+1,y+1))):
                            vertices.extend(np.column_stack([xyz(xy),(xy[:,0]-e)/step,(n+step-xy[:,1])/step]).tolist())
                col,row=(~photo.transform)*(e,n+step);rgb=photo.read([1,2,3],window=Window(round(col),round(row),step*5,step*5)).transpose(1,2,0)
                name=f'woodland-ground-{e}-{n}.ect';(out/name).write_bytes(encode([(vertices,Image.fromarray(rgb))]));q=np.asarray(vertices)[:,:3]
                tile={'file':name,'kind':'ground','runtimeId':spec['groundRuntimeStart']+len(ground_tiles),'bounds':[q.min(0).tolist(),q.max(0).tolist()]};ground_tiles.append(tile);records.append({'file':name,'originUTM':[e,n]})
        xy=np.array([(e,n)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)]);guide={'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,'points':xyz(xy).tolist()}
        surface={'name':'physics-campus-woodland','rings':rings(area),'terrainGuide':guide,'protectedFootprints':rings(footprints.buffer(3)),'outdoorReconstructed':True,'qualification':spec['qualification']}
        with tempfile.TemporaryDirectory(prefix='woodland-',dir=cache)as temp:
            folder=Path(temp);col,row=(~photo.transform)*(bounds[0],bounds[3]);rgb=photo.read([1,2,3],window=Window(round(col),round(row),(bounds[2]-bounds[0])*5,(bounds[3]-bounds[1])*5)).transpose(1,2,0);Image.fromarray(rgb).save(folder/'campus-orthophoto.jpg',quality=94)
            sub={'boundsUtm':bounds,'terrainGuide':guide,'tiles':[],'replacements':[]}
            previous_trees=[*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[])for t in s.get('vegetation',{}).get('trees',[])]]
            build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':elevation,'buildings':buildings,'allowedTreeRegionUTM':area.difference(trunk_exclusion),'excludedTreeCentresUTM':[t['utm']for t in previous_trees]})
            tree_tiles=[]
            for i,t in enumerate(sub['tiles']):
                name='woodland-'+t['file'];shutil.copy2(folder/t['file'],out/name);tree_tiles.append({**t,'file':name,'runtimeId':spec['treeRuntimeStart']+i})
            mc_area=unary_union([Polygon(p['ring'],p['holes'])for p in surface['rings']])
            for replacement in sub['replacements']:
                clipped=Polygon(replacement['ring'],replacement.get('holes',[])).intersection(mc_area)
                for p in polygons(clipped):meta['replacements'].append({**replacement,'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]})
            for key in ['surfaceGuide','vegetationOverhang','vegetation']:surface[key]=sub[key]
            shutil.copy2(folder/'vegetation-survey.jpg',out/'woodland-vegetation-survey.jpg')
    meta['tiles'].extend(ground_tiles+tree_tiles);meta.setdefault('supplementalSurfaces',[]).append(surface)
    # Independent mapped ground materials avoid printing aerial tree crowns onto
    # the forest floor. Paths override woodland; undocumented widths are estimates.
    layers={k:[]for k in ['grass','paving','asphalt','soil']};features=[]
    for wid,(xy,tags)in ways.items():
        material=None;shape=None;width=None
        if xy[0]==xy[-1]:
            if tags.get('landuse')=='forest'or tags.get('natural')=='wood':material='soil'
            elif tags.get('landuse')in['grass','meadow']or tags.get('natural')=='grassland':material='grass'
            if material:shape=Polygon(xy).buffer(0)
        if tags.get('highway')in['path','footway','cycleway','service']:
            kind=tags.get('surface','');material={'asphalt':'asphalt','chipseal':'asphalt','paving_stones':'paving','grass_paver':'paving','unpaved':'soil','dirt':'soil','grass':'grass','pebblestone':'soil'}.get(kind)
            if material:
                try:width=float(tags.get('width',spec['pathWidthsMetres'].get(kind,2)))
                except ValueError:width=spec['pathWidthsMetres'].get(kind,2)
                width=max(.5,min(8,width));shape=LineString(xy).buffer(width/2,cap_style=2,join_style=2)
        if shape is None:continue
        shape=shape.intersection(area)
        if shape.is_empty:continue
        layers[material].append(shape);features.append({'type':'Feature','properties':{'osmWay':wid,'material':material,'widthMetres':width,'tags':tags},'geometry':mapping(shape)})
    layers={k:unary_union(v)for k,v in layers.items()};layers['paving']=layers['paving'].difference(layers['asphalt']);layers['grass']=layers['grass'].difference(layers['asphalt'].union(layers['paving']));layers['soil']=layers['soil'].difference(unary_union([layers[k]for k in ['grass','paving','asphalt']]))
    size=2048;span=512;all_points=np.asarray(guide['points']);ax=math.floor(all_points[:,0].min()/16)*16;az=math.ceil(all_points[:,2].max()/16)*16;assert all_points[:,0].max()<ax+span and all_points[:,2].min()>az-span
    pixels=np.zeros((size,size,4),dtype=np.uint8);pixels[:,:,3]=255
    for channel,kind in enumerate(['grass','paving','asphalt','soil']):
        shapes=[]
        for p in polygons(layers[kind]):
            def q(ring):
                xy=np.asarray(ring.coords);return mc(np.column_stack([xy,np.full(len(xy),475)]))[:,[0,2]]
            shapes.append((Polygon(q(p.exterior),[q(h)for h in p.interiors]),255))
        if shapes:
            mask=rasterize(shapes,out_shape=(size,size),transform=from_origin(ax,az,span/size,span/size),dtype='uint8');pixels[:,:,channel]=255-mask if kind=='soil'else mask
    target=root/'minecraft/exterior/assets/textures/campus/woodland_ground_surfaces.png';Image.fromarray(pixels).save(target,optimize=True)
    shader=root/'minecraft/exterior/shaders/campus_ground.fsh';text=shader.read_text();start='// BEGIN GENERATED WOODLAND GROUND MAPPING\n';end='// END GENERATED WOODLAND GROUND MAPPING';mapping_source=f'vec2 woodlandGroundUv(vec2 position) {{ return vec2(position.x-{ax:.1f},{az:.1f}-position.y)/{span:.1f}; }}\n'
    if start not in text:text=text.replace('void main() {',start+end+'\nvoid main() {')
    prefix,rest=text.split(start);_,suffix=rest.split(end);shader.write_text(prefix+start+mapping_source+end+suffix)
    derived=out/'woodland-ground-surfaces.geojson';derived.write_text(json.dumps({'type':'FeatureCollection','coordinateSystem':'EPSG:25832','license':'ODbL1.0','attribution':'© OpenStreetMap contributors','features':features},separators=(',',':'))+'\n')
    region_file=out/'woodland-coverage.geojson';region_file.write_text(json.dumps({'land':mapping(land),'ground':mapping(area),'river':mapping(river.intersection(extent)),'priorGround':mapping(prior.intersection(extent)),'buildingFootprints':mapping(footprints.intersection(extent)),'trunkExclusion':mapping(trunk_exclusion)},separators=(',',':'))+'\n')
    meta['architecture']['physicsWoodland']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_woodland.py','generatorSha256':sha(Path(__file__)),'vegetationGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),'boundsUTM':bounds,'groundTiles':[t['file']for t in ground_tiles],'groundTileOrigins':records,'treeTiles':[t['file']for t in tree_tiles],'treeCount':len(sub['vegetation']['trees']),'groundAreaSquareMetres':area.area,'coverageFile':region_file.name,'coverageSha256':sha(region_file),'materialMaskFile':'assets/textures/campus/'+target.name,'materialMaskSha256':sha(target),'materialDerivedFile':derived.name,'materialDerivedSha256':sha(derived),'shaderMappingSha256':hashlib.sha256(mapping_source.encode()).hexdigest(),'materialMaskBoundsMC':[[ax,az-span],[ax+span,az]],'qualification':spec['qualification']}
    print('Woodland:',len(ground_tiles),'ground tiles;',len(sub['vegetation']['trees']),'trees in',len(tree_tiles),'groups;',round(area.area),'m²',flush=True)

"""Bounded clean ground materials around the reactor and UTA; no mesh edits."""
import hashlib
import json
import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import Polygon, LineString, box, shape, mapping
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, polygons


def build(ctx):
    root, cache, out, meta, mc = [ctx[k] for k in ('ROOT', 'CACHE', 'OUT', 'metadata', 'mc')]
    src = root/'minecraft/exterior'
    source = src/'reactor-ground-surfaces.json'
    spec = json.loads(source.read_text())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    research = src/spec['researchFile']
    assert sha(research) == spec['researchSha256']
    records = json.loads(research.read_text())['mappedFeatures']
    bounds = spec['boundsUTM']; limit = box(*bounds)
    buildings = unary_union([Polygon(rings[0][:,:2], [h[:,:2] for h in rings[1:]]).buffer(0)
        for _, surfaces in nearby_surveys(cache, bounds) for kind, rings in surfaces if kind == 'GroundSurface'])
    grass = unary_union([shape(f['geometryUTM']).buffer(0) for f in records
        if f['tags'].get('landuse') == 'grass']).intersection(limit).difference(buildings)
    paths = []; layers = {'grass': grass, 'paving': [], 'asphalt': []}
    exclusion = buildings.union(grass)
    for feature in records:
        tags = feature['tags']; g = shape(feature['geometryUTM'])
        if 'highway' in tags and tags.get('area') != 'yes' and g.geom_type == 'Polygon':
            g = LineString(g.exterior.coords)
        if g.geom_type != 'LineString' or tags.get('highway') not in spec['estimatedWidthsMetres']:
            continue
        if tags.get('surface') in ('grass', 'dirt', 'unpaved', 'fine_gravel'):
            continue
        width = float(tags['width']) if 'width' in tags else spec['estimatedWidthsMetres'][tags['highway']]
        assert .25 <= width <= 20
        area = g.buffer(width/2, cap_style=2, join_style=2).intersection(limit).difference(exclusion)
        material = 'asphalt' if tags.get('surface') in ('asphalt', 'chipseal') else spec['untaggedMaterial']
        layers[material].append(area)
        paths.append({'osmWay': feature['id'], 'widthMetres': width,
            'widthBasis': 'OSM tag' if 'width' in tags else 'estimated', 'material': material,
            'materialBasis': 'OSM tag' if 'surface' in tags else 'aerial appearance estimate'})
    apron = Polygon(spec['parkingApronUTM']).intersection(limit).difference(exclusion)
    layers['paving'].append(apron)
    layers['asphalt'] = unary_union(layers['asphalt'])
    layers['paving'] = unary_union(layers['paving']).difference(layers['asphalt'])
    assert unary_union(list(layers.values())).intersection(buildings).area < 1e-8
    size, span, samples = spec['atlasSize'], spec['atlasSpanMetres'], 4
    corners = mc(np.array([[e,n,475] for e in (bounds[0],bounds[2]) for n in (bounds[1],bounds[3])]))[:,[0,2]]
    left = float(np.floor(corners[:,0].min()/16)*16)
    top = float(np.ceil(corners[:,1].max()/16)*16)
    assert corners[:,0].max() <= left+span and corners[:,1].min() >= top-span
    basis = mc(np.array([[bounds[0],bounds[1],475], [bounds[0]+1,bounds[1],475], [bounds[0],bounds[1]+1,475]]))[:,[0,2]]
    inverse = np.linalg.inv(np.column_stack((basis[1]-basis[0],basis[2]-basis[0])))
    def ring(coords):
        xy = np.asarray(coords)
        return mc(np.column_stack((xy, np.full(len(xy),475))))[:,[0,2]]
    projected = {name: [(Polygon(ring(p.exterior.coords), [ring(h.coords) for h in p.interiors]),255)
        for p in polygons(area)] for name, area in layers.items()}
    pixels = np.zeros((size,size,4),dtype=np.uint8)
    for row in range(0,size,128):
        height = min(128,size-row)
        grid = from_origin(left,top-row*span/size,span/size/samples,span/size/samples)
        for channel,name in enumerate(('grass','paving','asphalt')):
            if projected[name]:
                high = rasterize(projected[name],out_shape=(height*samples,size*samples),transform=grid,dtype='uint8')
                pixels[row:row+height,:,channel] = np.rint(high.reshape(height,samples,size,samples).mean(axis=(1,3))).astype('uint8')
        rr,cc = np.mgrid[row:row+height,:size]
        xy = np.stack([left+(cc+.5)*span/size,top-(rr+.5)*span/size],axis=-1)
        local = (xy-basis[0])@inverse.T
        edge = np.minimum.reduce([local[:,:,0],bounds[2]-bounds[0]-local[:,:,0],local[:,:,1],bounds[3]-bounds[1]-local[:,:,1]])
        t = np.clip(edge/spec['boundaryBlendMetres'],0,1)
        pixels[row:row+height,:,3] = np.rint(t*t*(3-2*t)*255).astype('uint8')
    target = src/'assets/textures/campus/reactor_ground_surfaces.png'
    Image.fromarray(pixels).save(target,optimize=True)
    derived = out/'reactor-ground-surfaces.geojson'
    derived.write_text(json.dumps({'type':'FeatureCollection','coordinateReferenceSystem':'EPSG:25832',
        'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors; aerial interpretation: BVV DOP20',
        'features':[{'type':'Feature','properties':{'material':name},'geometry':mapping(area)} for name,area in layers.items()]},separators=(',',':'))+'\n')
    mapping_source = f'vec2 reactorGroundUv(vec2 position) {{ return vec2(position.x-{left:.1f},{top:.1f}-position.y)/{span:.1f}; }}\n'
    shader = src/'shaders/campus_ground.fsh'; text = shader.read_text()
    start,end = '// BEGIN GENERATED REACTOR GROUND MAPPING\n','// END GENERATED REACTOR GROUND MAPPING'
    assert text.count(start) == text.count(end) == 1
    prefix,rest = text.split(start); _,suffix = rest.split(end)
    shader.write_text(prefix+start+mapping_source+end+suffix)
    meta['architecture']['reactorGroundMaterials'] = {
        'sourceFile':source.name,'sourceSha256':sha(source),
        'researchFile':spec['researchFile'],'researchSha256':sha(research),
        'generatorFile':'scripts/exterior_reactor_ground.py','generatorSha256':sha(root/'scripts/exterior_reactor_ground.py'),
        'maskFile':'assets/textures/campus/'+target.name,'maskSha256':sha(target),
        'derivedFile':derived.name,'derivedSha256':sha(derived),
        'maskBoundsMC':[[left,top-span],[left+span,top]],'maskSize':[size,size],
        'maskChannels':['grass','paving','asphalt','geographic boundary fade'],
        'materialBoundsUTM':bounds,'boundaryBlendMetres':spec['boundaryBlendMetres'],
        'shaderMappingSha256':hashlib.sha256(mapping_source.encode()).hexdigest(),
        'areaSquareMetres':{name:area.area for name,area in layers.items()},'paths':paths,
        'buildingOverlapSquareMetres':unary_union(list(layers.values())).intersection(buildings).area,
        'qualification':spec['qualification']}
    print('Reactor ground materials:',meta['architecture']['reactorGroundMaterials']['areaSquareMetres'],flush=True)

"""Ground classification from pinned OSM and low public-raster vegetation."""
import hashlib,json,math,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import rasterize,shapes
from rasterio.transform import from_origin
from pyproj import Transformer
from PIL import Image
from shapely.geometry import Polygon,LineString,shape,mapping
from shapely.ops import unary_union
from exterior_physics_i import polygons


def canopy_extension(cache, specification, buildings, base_area):
    """Complete selected source canopy groups before choosing a ground edge."""
    from scipy import ndimage
    extent = specification['canopyExtent']
    left, bottom, right, top = extent['boundsUtm']
    resolution = extent['resolutionMetres']
    width, height = int((right-left)/resolution), int((top-bottom)/resolution)
    transform = from_origin(left, top, resolution, resolution)
    xy = np.array([(left+(i+.5)*resolution, top-(j+.5)*resolution)
                   for j in range(height) for i in range(width)])
    with rasterio.open(cache/'campus-dop-east.tif') as dop, \
         rasterio.open(cache/'campus-dgm-east.tif') as dem, \
         rasterio.open(cache/'32698_5349_20_DOM.tif') as dom:
        rgb = np.array(list(dop.sample(xy))).astype(float)
        heights = np.array(list(dom.sample(xy)))[:,0]-np.array(list(dem.sample(xy)))[:,0]
    occupied = rasterize([(buildings.buffer(.5), 1)], out_shape=(height,width),
                         transform=transform, dtype='uint8') > 0
    green = (rgb[:,1]>rgb[:,0]*1.025)&(rgb[:,1]>rgb[:,2]+2)&(heights>3)
    mask = ndimage.binary_closing(green.reshape(height,width)&~occupied,
                                 iterations=2)&~occupied
    labels, _ = ndimage.label(mask)
    selected, records, seen = [], [], set()
    for e, n in extent['componentSeedsUTM']:
        row, col = int((top-n)/resolution), int((e-left)/resolution)
        assert 0 <= row < height and 0 <= col < width
        label = int(labels[row,col])
        assert label > 0 and label not in seen
        seen.add(label)
        pixels = labels == label
        assert not (pixels[0].any() or pixels[-1].any() or pixels[:,0].any() or pixels[:,-1].any()), 'Canopy exceeds source study bounds'
        region = unary_union([shape(g) for g,v in shapes(pixels.astype('uint8'),
                              mask=pixels, transform=transform) if v == 1])
        assert region.area >= 3 and region.intersects(base_area)
        selected.append(region)
        records.append({'seedUTM':[e,n], 'sourceAreaSquareMetres':region.area})
    return unary_union(selected), records


def classify(root,cache,spec,area,owned_footprints):
    nodes,ways={},{}
    project=Transformer.from_crs(4326,25832,always_xy=True).transform
    for source in spec['landscape']['osm']:
        path=root/'minecraft/exterior'/source['sourceFile']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
        osm=ET.parse(path).getroot()
        nodes.update({n.get('id'):project(float(n.get('lon')),float(n.get('lat')))for n in osm.findall('node')})
        for way in osm.findall('way'):
            xy=[nodes[n.get('ref')]for n in way.findall('nd')]
            ways[way.get('id')]=(xy,{t.get('k'):t.get('v')for t in way.findall('tag')})
    layers={'grass':[],'asphalt':[]};features=[];paths=[]
    outdoor=area.difference(owned_footprints)
    for wid,(xy,tags)in ways.items():
        geometry=None;material=None;width=None
        if tags.get('landuse')=='grass'and xy[0]==xy[-1]:
            geometry=Polygon(xy).buffer(0);material='grass'
        if tags.get('highway')=='footway':
            width=float(tags.get('width',spec['landscape']['defaultPathWidthMetres']))
            geometry=LineString(xy).buffer(width/2,cap_style=2,join_style=2)
            paths.append(geometry.buffer(.35))
            if tags.get('surface')=='asphalt':material='asphalt'
        if geometry is None or material is None:continue
        geometry=geometry.intersection(outdoor)
        if geometry.is_empty:continue
        layers[material].append(geometry)
        features.append({'type':'Feature','properties':{'source':'OSM','osmWay':wid,'material':material,'widthMetres':width,'tags':tags},'geometry':mapping(geometry)})
    path_guard=unary_union(paths)
    # Low green ground is an inference; canopy colours never establish lawn.
    lo=np.floor(np.asarray(area.bounds[:2]));hi=np.ceil(np.asarray(area.bounds[2:]));resolution=.5
    width,height=((hi-lo)/resolution).astype(int);transform=from_origin(lo[0],hi[1],resolution,resolution)
    xy=np.array([(lo[0]+(i+.5)*resolution,hi[1]-(j+.5)*resolution)for j in range(height)for i in range(width)])
    with rasterio.open(cache/'campus-dop-east.tif')as dop,rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'32698_5349_20_DOM.tif')as dom:
        rgb=np.asarray(list(dop.sample(xy)));h=np.asarray(list(dom.sample(xy)))[:,0]-np.asarray(list(dem.sample(xy)))[:,0]
        green=(rgb[:,1]>rgb[:,0]*1.025)&(rgb[:,1]>rgb[:,2]+2)&(h>=-.3)&(h<=.7)
    inferred=unary_union([shape(g)for g,v in shapes(green.reshape(height,width).astype('uint8'),mask=green.reshape(height,width),transform=transform)if v==1])
    inferred=inferred.intersection(outdoor).difference(path_guard).difference(unary_union(layers['grass']))
    if not inferred.is_empty:
        layers['grass'].append(inferred)
        features.append({'type':'Feature','properties':{'source':'BVV DOP20/DGM1/DOM20','material':'grass','qualification':'Estimated lawn from green0.5m samples with DOM-DGM between-0.3and0.7m, outside building and path guards.'},'geometry':mapping(inferred)})
    layers={k:unary_union(v)for k,v in layers.items()};layers['grass']=layers['grass'].difference(layers['asphalt'])
    return layers,features,path_guard


def write_materials(root,out,mc,guide,layers,features):
    size=1024;points=np.asarray(guide['points']);ax=math.floor(points[:,0].min()/16)*16;az=math.ceil(points[:,2].max()/16)*16
    span=max(128,math.ceil((max(points[:,0].max()-ax,az-points[:,2].min())+.01)/32)*32)
    assert points[:,0].max()<ax+span and points[:,2].min()>az-span
    pixels=np.zeros((size,size,4),dtype=np.uint8);pixels[:,:,3]=255
    for channel,kind in [(0,'grass'),(2,'asphalt')]:
        regions=[]
        for polygon in polygons(layers[kind]):
            def q(ring):
                xy=np.asarray(ring.coords);return mc(np.column_stack([xy,np.full(len(xy),475)]))[:,[0,2]]
            regions.append((Polygon(q(polygon.exterior),[q(h)for h in polygon.interiors]),255))
        if regions:pixels[:,:,channel]=rasterize(regions,out_shape=(size,size),transform=from_origin(ax,az,span/size,span/size),dtype='uint8')
    target=root/'minecraft/exterior/assets/textures/campus/physics_ii_ground_surfaces.png';Image.fromarray(pixels).save(target,optimize=True)
    shader=root/'minecraft/exterior/shaders/campus_ground.fsh';text=shader.read_text();start='// BEGIN GENERATED PHYSICS II SITE MAPPING\n';end='// END GENERATED PHYSICS II SITE MAPPING';source=f'vec2 physicsIISiteUv(vec2 position) {{ return vec2(position.x-{ax:.1f},{az:.1f}-position.y)/{span:.1f}; }}\n'
    if start not in text:text=text.replace('void main() {',start+end+'\nvoid main() {')
    prefix,rest=text.split(start);_,suffix=rest.split(end);shader.write_text(prefix+start+source+end+suffix)
    derived=out/'physics-ii-surfaces.geojson';derived.write_text(json.dumps({'type':'FeatureCollection','coordinateSystem':'EPSG:25832','attribution':'© OpenStreetMap contributors; ©BVV','qualification':'Mapped land cover plus separately identified low-green inference; untagged path width and material finish are estimates.','features':features},separators=(',',':'))+'\n')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    return {'landscapeGeneratorFile':'scripts/exterior_physics_ii_landscape.py','landscapeGeneratorSha256':sha(Path(__file__)),'materialDerivedFile':derived.name,'materialDerivedSha256':sha(derived),'materialMaskFile':'assets/textures/campus/'+target.name,'materialMaskSha256':sha(target),'materialMaskBoundsMC':[[ax,az-span],[ax+span,az]],'shaderMappingSha256':hashlib.sha256(source.encode()).hexdigest(),'materialAreasSquareMetres':{k:v.area for k,v in layers.items()}}

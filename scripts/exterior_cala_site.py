"""Public-survey CALA street trees and mapped approach materials."""
import hashlib,json,shutil,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import rasterize
from rasterio.transform import from_origin
from pyproj import Transformer
from shapely.geometry import Polygon,LineString,Point,mapping
from shapely.ops import unary_union
from PIL import Image
from exterior_physics_i import polygons
from exterior_terrain import ElevationSampler
from exterior_vegetation import build as build_vegetation


def build(ctx,spec,front,buildings):
    root,cache,out,meta,mc=[ctx[k]for k in ['ROOT','CACHE','OUT','metadata','mc']]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior'/spec['siteOSM']['file'];assert sha(source)==spec['siteOSM']['sha256']
    xml=ET.parse(source).getroot();to_utm=Transformer.from_crs(4326,25832,always_xy=True)
    nodes={n.get('id'):to_utm.transform(float(n.get('lon')),float(n.get('lat')))for n in xml.findall('node')}
    ways={w.get('id'):([nodes[n.get('ref')]for n in w.findall('nd')],{t.get('k'):t.get('v')for t in w.findall('tag')})for w in xml.findall('way')}
    road=LineString(ways['15598996'][0]).buffer(float(ways['15598996'][1]['width'])/2,cap_style=2,join_style=2)
    exclusion=road.buffer(.35)
    bounds=spec['siteBoundsUTM']
    with rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'campus-dop-east.tif')as photo,tempfile.TemporaryDirectory(prefix='cala-site-',dir=cache)as temp:
        folder=Path(temp);elevation=ElevationSampler([dem]);xy=np.array([(e,n)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)])
        guide={'width':(bounds[2]-bounds[0])//2+1,'height':(bounds[3]-bounds[1])//2+1,'points':mc(np.column_stack([xy,elevation.sample(xy)])).tolist()}
        rgb=photo.read([1,2,3],window=from_bounds(*bounds,photo.transform)).transpose(1,2,0);Image.fromarray(rgb).save(folder/'campus-orthophoto.jpg',quality=94)
        sub={'boundsUtm':bounds,'terrainGuide':guide,'tiles':[],'replacements':[]}
        previous=[*meta['vegetation']['trees'],*[t for s in meta.get('supplementalSurfaces',[])for t in s.get('vegetation',{}).get('trees',[])]]
        build_vegetation({**ctx,'OUT':folder,'metadata':sub,'height':elevation,'buildings':buildings,'allowedTreeRegionUTM':front.difference(exclusion),'excludedTreeCentresUTM':[t['utm']for t in previous]})
        from exterior_cala_trees import add as add_small_trees
        add_small_trees(ctx,folder,sub,spec['smallTreeSeedsUTM'],elevation,front.difference(exclusion))
        tiles=[]
        for i,t in enumerate(sub['tiles']):
            filename='cala-'+t['file'];shutil.copy2(folder/t['file'],out/filename);tiles.append({**t,'file':filename,'runtimeId':spec['treeRuntimeId']+i})
        def rings(region):
            def ring(x):
                a=np.asarray(x.coords);return mc(np.column_stack([a,elevation.sample(a)]))[:,[0,2]].tolist()
            return [{'ring':ring(p.exterior),'holes':[ring(h)for h in p.interiors]}for p in polygons(region)]
        meta['tiles'].extend(tiles);meta['replacements'].extend(sub['replacements'])
        # This record supplies canopy metadata only. Existing ground remains
        # authoritative; the extension's own supplemental record supplies it.
        meta['supplementalSurfaces'].append({'name':'cala-street-trees','rings':[],'terrainGuide':guide,'protectedFootprints':[],**{k:sub[k]for k in ['vegetation','vegetationOverhang','surfaceGuide']}})
        shutil.copy2(folder/'vegetation-survey.jpg',out/'cala-vegetation-survey.jpg')
    # Preserve the previous northern material overlay, then classify the
    # explicitly rebuilt apron. Its street is OSM asphalt; verge positions are
    # inferred from public aerial/tree controls, not a parcel survey.
    size=2048;ax,az,span=192.,-432.,128.;yy,xx=np.mgrid[:size,:size];x=ax+(xx+.5)*span/size;z=az-(yy+.5)*span/size
    old=np.asarray(Image.open(root/'minecraft/exterior/assets/textures/campus/north_ground_surfaces.png'))
    col=np.floor((x-256)/192*old.shape[1]).astype(int);row=np.floor((-304-z)/192*old.shape[0]).astype(int);valid=(col>=0)&(row>=0)&(col<old.shape[1])&(row<old.shape[0]);pixels=np.zeros((size,size,4),dtype=np.uint8);pixels[:,:,3]=255;pixels[valid]=old[row[valid],col[valid]]
    def mc_shape(region):
        def ring(r):
            a=np.asarray(r.coords);return mc(np.column_stack([a,np.full(len(a),474)]))[:,[0,2]]
        return unary_union([Polygon(ring(p.exterior),[ring(h)for h in p.interiors])for p in polygons(region)])
    features=[]
    # The repaired street apron uses asphalt seen in the reference photograph.
    layers=[('asphalt',front,[0,0,255,255])]
    for tree in sub['vegetation']['trees']:
        verge=Point(*tree['utm']).buffer(max(.65,min(1.1,tree['radius']*.55)),resolution=12).intersection(front).difference(road)
        if not verge.is_empty:layers.append(('estimated tree verge',verge,[255,0,0,255]))
    for name,region,color in layers:
        region=mc_shape(region);mask=rasterize([(region,1)],out_shape=(size,size),transform=from_origin(ax,az,span/size,span/size),dtype='uint8')>0;pixels[mask]=color;features.append({'type':'Feature','properties':{'material':name,'qualification':'OSM street and official-photo asphalt apron; tree verge extents estimated'},'geometry':mapping(region)})
    atlas=root/'minecraft/exterior/assets/textures/campus/cala_ground_surfaces.png';Image.fromarray(pixels).save(atlas,optimize=True)
    derived=out/'cala-site-materials.geojson';derived.write_text(json.dumps({'type':'FeatureCollection','coordinateSystem':'Minecraft XZ','features':features},separators=(',',':')))
    return {'treeTiles':[t['file']for t in tiles],'treeCount':len(sub['vegetation']['trees']),'trees':sub['vegetation']['trees'],'treeGeneratorSha256':sha(root/'scripts/exterior_vegetation.py'),'siteGeneratorSha256':sha(Path(__file__)),'smallTreeGeneratorSha256':sha(root/'scripts/exterior_cala_trees.py'),'osmFile':spec['siteOSM']['file'],'osmSha256':sha(source),'materialFile':'assets/textures/campus/'+atlas.name,'materialSha256':sha(atlas),'materialBoundsMC':[ax,az-span,ax+span,az],'materialFeaturesFile':derived.name,'materialFeaturesSha256':sha(derived),'qualification':'BVV crown locations/heights with procedural species, branches and leaves. OSM5.9m asphalt road; apron and verge finishes estimated from the official exterior photo and DOP20. No reference-photo pixels.'}

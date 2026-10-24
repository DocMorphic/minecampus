"""Low courtyard planting located and sized from public DOP20/DOM20/DGM1."""
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage
from shapely.geometry import Point,box,mapping
from shapely.ops import unary_union
from PIL import Image


def build(cache,out,mc,encode,courtyard,runtime_id):
    resolution=.5;lo=np.floor(courtyard.bounds[:2]);hi=np.ceil(courtyard.bounds[2:]);w,h=map(int,(hi-lo)/resolution);xy=np.array([(e+.25,n+.25)for n in np.arange(lo[1],hi[1],resolution)for e in np.arange(lo[0],hi[0],resolution)])
    with rasterio.open(cache/'32698_5349_20_DOM.tif')as dom,rasterio.open(cache/'campus-dgm-east.tif')as dem,rasterio.open(cache/'campus-dop-east.tif')as dop:
        top=np.array([p[0]for p in dom.sample(xy)]);floor=np.array([p[0]for p in dem.sample(xy)]);rgb=np.array(list(dop.sample(xy)))
    height=top-floor;green=(rgb[:,1]>rgb[:,0]*1.025)&(rgb[:,1]>rgb[:,2]+2);allowed=np.array([courtyard.buffer(-1.2).contains(Point(*p))for p in xy]);mask=(green&(height>.7)&(height<4.2)&allowed).reshape(h,w);labels,count=ndimage.label(mask);sizes=np.bincount(labels.ravel());selected=[i for i in range(1,count+1)if sizes[i]>=12];wood,leaves=[],[];controls=[];rng=np.random.default_rng(5107)
    leaf=Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_diff_1k.jpg').convert('RGBA');leaf.putalpha(Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_alpha_1k.png').convert('L').resize(leaf.size));bark=Image.open(cache/'tree-source/textures/jacaranda_tree_trunk_diff_1k.jpg').resize((512,512)).convert('RGBA')
    def quad(points):
        for k in [0,1,2,0,2,3]:leaves.append([*points[k],*[[0,0],[1,0],[1,1],[0,1]][k]])
    def stem(a,b):
        for i in range(6):
            t=i*np.pi/3;u=(i+1)*np.pi/3;v=[a+[.025*np.cos(t),0,.025*np.sin(t)],a+[.025*np.cos(u),0,.025*np.sin(u)],b+[.01*np.cos(u),0,.01*np.sin(u)],b+[.01*np.cos(t),0,.01*np.sin(t)]]
            for k in [0,1,2,0,2,3]:wood.append([*v[k],*[[0,1],[1,1],[1,0],[0,0]][k]])
    for label in selected:
        ids=np.flatnonzero(labels.ravel()==label);points=xy[ids];ground=mc(np.column_stack([points,floor[ids]]));tops=mc(np.column_stack([points,top[ids]]));region=unary_union([box(e-.25,n-.25,e+.25,n+.25)for e,n in points]);controls.append({'areaSquareMetres':len(ids)*.25,'sourceHeightRangeMetres':[float(height[ids].min()),float(height[ids].max())],'sourceRegionUTM':mapping(region),'sampleCount':len(ids)})
        # Multi-stem shrubs occupy the measured green cells. Species and branch
        # form remain estimates; no geometry exceeds the measured upper surface.
        for j,(a,b)in enumerate(zip(ground,tops)):
            H=b[1]-a[1]
            if j%3==0:stem(a,a+[0,H*.72,0])
            for _ in range(16):
                y=rng.uniform(.3*H,H-min(.16,H*.11));centre=a+[rng.uniform(-.22,.22),y,rng.uniform(-.22,.22)];angle=rng.uniform(0,np.pi*2);u=np.array([np.cos(angle),0,np.sin(angle)])*.18;v=np.array([0,min(.16,H*.11),0]);quad([centre-u-v,centre+u-v,centre+u+v,centre-u+v])
    if not leaves:return [],controls
    # Flexible shrub stems are visual detail, not metre-wide solid tree trunks.
    name='physics-ii-courtyard-planting.ect';(out/name).write_bytes(encode([(wood,bark),(leaves,leaf)]));v=np.array(wood+leaves)[:,:3];return [{'file':name,'kind':'vegetation','collisionParts':[],'runtimeId':runtime_id,'bounds':[v.min(0).tolist(),v.max(0).tolist()]}],controls

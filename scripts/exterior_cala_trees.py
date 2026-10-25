"""Small street trees missed by the campus detector's large-canopy threshold.
Seeds identify visible DOP20 crowns; fitted pixels determine height and extent.
Species, branches and leaf arrangement remain estimates using the pinned CC0 atlas.
"""
from pathlib import Path
import numpy as np
import rasterio
from shapely.geometry import MultiPoint,Point,Polygon
from PIL import Image


def add(ctx,folder,sub,seeds,elevation,allowed):
    mc,encode,cache=[ctx[k]for k in ['mc','encode','CACHE']];wood=[];leaves=[];rng=np.random.default_rng(57031)
    bark=Image.open(cache/'tree-source/textures/jacaranda_tree_trunk_diff_1k.jpg').resize((512,512)).convert('RGBA')
    leaf=Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_diff_1k.jpg').convert('RGBA');leaf.putalpha(Image.open(cache/'tree-source/textures/jacaranda_tree_leaves_alpha_1k.png').convert('L').resize(leaf.size))
    def tube(a,b,ra,rb):
        axis=b-a;axis/=np.linalg.norm(axis);u=np.cross(axis,[0,1,0]if abs(axis[1])<.9 else[1,0,0]);u/=np.linalg.norm(u);v=np.cross(axis,u)
        for k in range(8):
            ang=np.array([k,k+1])*np.pi/4;d=[u*np.cos(t)+v*np.sin(t)for t in ang];q=[a+ra*d[0],a+ra*d[1],b+rb*d[1],b+rb*d[0]];uv=[[k/8,1],[(k+1)/8,1],[(k+1)/8,0],[k/8,0]]
            wood.extend([*q[i],*uv[i]]for i in [0,1,2,0,2,3])
    with rasterio.open(cache/'campus-dop-east.tif')as dop,rasterio.open(cache/'32698_5349_20_DOM.tif')as dom:
        for seed in seeds:
            e,n=seed;xy=np.array([(e+x,n+y)for y in np.arange(-2,2.01,.2)for x in np.arange(-2,2.01,.2)]);rgb=np.array(list(dop.sample(xy)))[:,:3].astype(float);tops=np.array(list(dom.sample(xy)))[:,0];ground=elevation.sample(xy);height=tops-ground
            mask=(height>2.5)&(height<9)&(rgb[:,1]>rgb[:,0]*.98)&(rgb[:,1]>rgb[:,2]+1)&(rgb[:,1]>30)
            assert np.count_nonzero(mask)>=10,('unresolved street-tree seed',seed,np.count_nonzero(mask))
            crown_xy=xy[mask];centre=np.median(crown_xy,axis=0);assert allowed.covers(Point(*centre))
            base=mc(np.array([[*centre,elevation(*centre)]]))[0];crown=mc(np.column_stack([crown_xy,tops[mask]]));H=float(np.percentile(crown[:,1]-base[1],98));assert 3<H<9
            radius=float(np.percentile(np.linalg.norm(crown_xy-centre,axis=1),90));radius=max(.7,min(2.5,radius));trunk_radius=max(.065,H*.015)
            tube(base,base+[0,H*.72,0],trunk_radius,.025)
            for i in range(9):
                angle=i*np.pi*2/9;start=base+[0,H*(.4+.2*(i%3)/2),0];end=base+[np.cos(angle)*radius*.65,H*(.68+.13*(i%2)),np.sin(angle)*radius*.65];tube(start,end,trunk_radius*.45,.012)
            for i in range(max(180,int(len(crown)*.04*12))):
                p=crown[int(rng.integers(len(crown)))].copy();p[[0,2]]+=rng.uniform(-.1,.1,2);p[1]=rng.uniform(base[1]+H*.4,max(base[1]+H*.41,p[1]))
                normal=rng.normal(size=3);normal/=np.linalg.norm(normal);u=np.cross(normal,[0,1,0]if abs(normal[1])<.9 else[1,0,0]);u/=np.linalg.norm(u);v=np.cross(normal,u);u*=rng.uniform(.35,.6);v*=rng.uniform(.25,.45);q=[p-u-v,p+u-v,p+u+v,p-u+v];uv=[[0,1],[1,1],[1,0],[0,0]];leaves.extend([*q[k],*uv[k]]for k in [0,1,2,0,2,3])
            hull=MultiPoint(crown_xy).convex_hull.buffer(1.0,resolution=12);coords=np.array(hull.exterior.coords);ring=mc(np.column_stack([coords,elevation.sample(coords)]))[:,[0,2]].tolist();sub['replacements'].append({'ring':ring,'holes':[],'y0':float(base[1])-1,'y1':float(base[1])+H+3,'kind':'vegetation'})
            sub['vegetation']['trees'].append({'center':base.tolist(),'utm':centre.tolist(),'height':H,'radius':radius,'crownArea':len(crown)*.04,'crownBounds':[crown.min(0).tolist(),crown.max(0).tolist()],'sourceSeedUTM':seed,'sourcePixels':len(crown),'qualification':'DOP20 small-crown seed; local DOM20 height; estimated branches/species'})
    if wood:
        q=np.array(wood+leaves)[:,:3];file='small-street-trees.ect';(folder/file).write_bytes(encode([(wood,bark),(leaves,leaf)]));sub['tiles'].append({'file':file,'kind':'vegetation','runtimeId':1000010099,'bounds':[q.min(0).tolist(),q.max(0).tolist()]})

"""Replace bounded MLZ courtyard aerial objects with reference-informed materials.

Only existing terrain pixels and the material mask change. Survey vertices, UVs,
collision, building footprints and all pixels outside the surface patches remain.
"""
import hashlib,json,struct
from pathlib import Path
import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import Polygon,LineString,box,mapping
from shapely.ops import transform,unary_union


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def regions(root,meta):
    spec=json.loads((root/'minecraft/exterior/mlz-courtyard-ground.json').read_text())
    bounds=meta['boundsUtm'];middle=np.array([(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2])
    points=np.asarray(meta['terrainGuide']['points'])
    coords=np.array([(e-middle[0],n-middle[1],1)for n in range(bounds[1],bounds[3]+1,2)for e in range(bounds[0],bounds[2]+1,2)])
    fit=np.linalg.lstsq(coords,points[:,[0,2]],rcond=None)[0]
    error=float(np.max(np.abs(coords@fit-points[:,[0,2]])));assert error<.03
    full=fit.copy();full[2]-=middle@fit[:2]
    inverse=np.linalg.inv(np.column_stack((full,[0,0,1])))
    def project(matrix,x,y,z=None):
        p=np.column_stack((np.atleast_1d(x),np.atleast_1d(y),np.ones(np.size(x))))@matrix
        return p[:,0],p[:,1]
    to_world=lambda x,y,z=None:project(full,x,y)
    to_utm=lambda x,y,z=None:project(inverse,x,y)
    footprints=unary_union([transform(to_utm,Polygon(np.asarray(r)[:,[0,2]]).buffer(0))for b in meta['buildings']for r in b['grounds']])
    envelope=Polygon(spec['boundsEPSG25832'])
    domain=envelope.difference(footprints.buffer(spec['buildingExclusionMetres']))
    grass=unary_union([Polygon(p)for p in spec['grassPatchesEPSG25832']]).intersection(domain)
    # The north entrance walk is outside the surveyed facade. Its width is an estimate.
    walk=LineString(spec['northWalkEPSG25832']).buffer(spec['northWalkWidthMetres'],cap_style=2,join_style=2).intersection(domain).difference(grass)
    edges=grass.buffer(spec['edgeWidthMetres'],join_style=2).difference(grass).intersection(domain)
    paving=walk.union(edges)
    asphalt=domain.difference(grass.union(paving))
    patches={'asphalt':asphalt,'paving':paving,'grass':grass}
    assert abs(sum(p.area for p in patches.values())-domain.area)<1e-6
    return spec,patches,to_world,error


def coverages(patches,shape,grid,samples=4):
    # A single categorical raster gives shared edges to one region only.
    # Independent masks can double-count a sample exactly on a shared boundary.
    high=rasterize([(p,i+1)for i,p in enumerate(patches.values())],out_shape=(shape[0]*samples,shape[1]*samples),transform=grid*grid.scale(1/samples,1/samples),dtype='uint8')
    return {kind:(high==i+1).reshape(shape[0],samples,shape[1],samples).mean((1,3))for i,kind in enumerate(patches)}


def build(ctx):
    root,out,meta=[ctx[k]for k in ['ROOT','OUT','metadata']]
    source=root/'minecraft/exterior/mlz-courtyard-ground.json'
    spec,patches,to_world,error=regions(root,meta)
    texture_root=root/'minecraft/exterior/assets/textures/campus'
    # The baked terrain texture is 20 cm/pixel. Filter the source scans to that
    # footprint before sampling; point-sampling 2K grain aliases into white speckle.
    textures={k:np.asarray(Image.open(texture_root/name).convert('RGB').resize((20,20)if k=='asphalt'else (10,10),Image.Resampling.LANCZOS),dtype=float)for k,name in spec['materials'].items()}
    def material(kind,e,n):
        tex=textures[kind];scale=4 if kind=='asphalt'else 2
        u=np.floor((e/scale%1)*tex.shape[1]).astype(int);v=np.floor((n/scale%1)*tex.shape[0]).astype(int)
        c=tex[v,u]
        if kind=='grass':c=np.array([70,89,43])*np.clip(c.mean(-1)[...,None]/89,.6,1.4)
        if kind=='paving':c=np.array([157,156,149])*np.clip(c.mean(-1)[...,None]/126,.8,1.2)
        return c
    changed={}
    for tile in meta['tiles']:
        if tile['kind']!='ground' or not tile['file'].startswith('ground-'):continue
        _,east,north=Path(tile['file']).stem.split('-');east,north=int(east),int(north)
        extent=box(east,north,east+100,north+100)
        if not any(p.intersects(extent)for p in patches.values()):continue
        path=out/tile['file'];data=path.read_bytes();assert data[:4]==b'ECT1' and struct.unpack_from('<i3d',data,4)==(1,0,0,0)
        count,w,h=struct.unpack_from('<3i',data,32);offset=48+count*20
        old=np.frombuffer(data,dtype='uint8',offset=offset).reshape(h,w,4);assert w==h==500
        cols,rows=np.meshgrid(np.arange(w),np.arange(h));e=east+(cols+.5)*100/w;n=north+100-(rows+.5)*100/h
        pixels=old[:,:,:3].astype(float);total=np.zeros((h,w));replacement=np.zeros_like(pixels)
        for kind,cov in coverages(patches,(h,w),from_origin(east,north+100,100/w,100/h)).items():
            total+=cov;replacement+=material(kind,e,n)*cov[:,:,None]
        assert total.max()<=1.00001
        result=old.copy();result[:,:,:3]=np.clip(np.rint(pixels*(1-total[:,:,None])+replacement),0,255).astype('uint8')
        assert np.array_equal(old[total==0],result[total==0])
        path.write_bytes(data[:offset]+result.tobytes())
        changed[tile['file']]={'beforeSha256':hashlib.sha256(data).hexdigest(),'sha256':sha(path),'geometryAndUVSha256':hashlib.sha256(data[:offset]).hexdigest(),'changedPixels':int(np.any(result!=old,axis=2).sum())}
    assert changed,'No courtyard terrain found'
    mask_path=texture_root/'ground_surfaces.png';mask=np.array(Image.open(mask_path).convert('RGBA'));before_mask=sha(mask_path)
    # Write only a bounded atlas crop, preserving every other texel exactly.
    projected={k:transform(to_world,p)for k,p in patches.items()};all_world=unary_union(list(projected.values()));a,b,c,d=all_world.bounds
    size=4096;step=672/size
    c0=max(0,int(np.floor((a+352)/step))-1);c1=min(size,int(np.ceil((c+352)/step))+1)
    r0=max(0,int(np.floor((256-d)/step))-1);r1=min(size,int(np.ceil((256-b)/step))+1)
    grid=from_origin(-352+c0*step,256-r0*step,step,step);old=mask[r0:r1,c0:c1].copy();total=np.zeros(old.shape[:2]);replacement=np.zeros_like(old,dtype=float)
    colors={'asphalt':[0,0,255,255],'paving':[0,255,0,255],'grass':[255,0,0,255]}
    for kind,cov in coverages(projected,old.shape[:2],grid).items():
        total+=cov;replacement+=cov[:,:,None]*np.array(colors[kind])
    assert total.max()<=1.00001
    mask[r0:r1,c0:c1]=np.rint(old*(1-total[:,:,None])+replacement).astype('uint8')
    Image.fromarray(mask).save(mask_path,optimize=True)
    features=[{'type':'Feature','properties':{'material':kind,'inferred':True},'geometry':mapping(poly)}for kind,poly in patches.items()]
    derived=out/'mlz-courtyard-ground-surfaces.json';derived.write_text(json.dumps({'coordinateSystem':'EPSG:25832','features':features},indent=2)+'\n')
    record={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_mlz_courtyard_ground.py','generatorSha256':sha(Path(__file__)),'referenceFile':spec['reference'],'referenceSha256':sha(root/'minecraft/exterior'/spec['reference']),'derivedFile':derived.name,'derivedSha256':sha(derived),'materialHashes':{name:sha(texture_root/name)for name in spec['materials'].values()},'tiles':changed,'areasSquareMetres':{k:p.area for k,p in patches.items()},'maskBeforeSha256':before_mask,'maskSha256':sha(mask_path),'projectionMaximumResidualMetres':error,'terrainAndCollisionUnchanged':True,'qualification':spec['qualification']}
    meta['architecture']['mlzCourtyardGround']=record;meta['groundSurfaces']['maskSha256']=sha(mask_path)
    print('MLZ courtyard ground:',{k:round(v,1)for k,v in record['areasSquareMetres'].items()},';',len(changed),'texture tiles; geometry unchanged',flush=True)

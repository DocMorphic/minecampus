"""Material reconstruction on one measured former-Mensa terrace roof surface."""
from pathlib import Path
import hashlib,json,struct,xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union


def build(ctx):
    root,out,meta,mc,encode=[ctx[k] for k in ['ROOT','OUT','metadata','mc','encode']]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/mensa-terrace.json';spec=json.loads(source.read_text())
    plan=next(p for p in json.loads((out/'photo-facades.json').read_text())['plans']if p['id']==spec['building'])
    assert plan['runtimeId']==spec['runtimeId'] and plan['roofFile']==spec['roofFile'] and not plan['manualRoof']
    ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'}
    inputs={};selected=[]
    for item,name in zip(json.loads((root/'minecraft/exterior/sources.json').read_text())['lod2'],['campus-east.gml','campus-west.gml']):
        p=root/'.cache'/name;assert sha(p)==item['sha256'];inputs[name]=sha(p)
        for building in ET.parse(p).findall('.//b:Building',ns):
            if building.get('{'+ns['g']+'}id')!=spec['building']:continue
            for surf in building.findall('.//b:RoofSurface',ns):
                if surf.get('{'+ns['g']+'}id')!=spec['surfaceId']:continue
                for polygon in surf.findall('.//g:Polygon',ns):
                    rings=[]
                    for pos in polygon.findall('.//g:LinearRing/g:posList',ns):
                        ring=np.array(list(map(float,pos.text.split()))).reshape(-1,3)
                        if np.linalg.norm(ring[0]-ring[-1])<.001:ring=ring[:-1]
                        rings.append(mc(ring))
                    selected.append(rings)
    assert len(selected)==1,'The named terrace must resolve to exactly one survey polygon'
    rings=selected[0];shape=Polygon(rings[0][:,[0,2]],[r[:,[0,2]]for r in rings[1:]])
    assert abs(shape.area-spec['expectedAreaSquareMetres'])<.01
    roof=out/spec['roofFile'];raw=roof.read_bytes();assert raw[:4]==b'ECT1'
    count,*anchor=struct.unpack_from('<i3d',raw,4);assert count==1 and anchor==[0,0,0],'Build from the original one-part survey roof'
    n,w,h=struct.unpack_from('<3i',raw,32);v=np.frombuffer(raw,dtype='<f4',count=n*5,offset=48).reshape(-1,5).copy()
    pixels=Image.frombytes('RGBA',(w,h),raw[48+n*20:]);tri=v.reshape(-1,3,5)
    plane=np.linalg.lstsq(np.column_stack([rings[0][:,0],rings[0][:,2],np.ones(len(rings[0]))]),rings[0][:,1],rcond=None)[0]
    pick=[]
    for t in tri:
        expected=np.column_stack([t[:,0],t[:,2],np.ones(3)])@plane
        pick.append(np.max(np.abs(t[:,1]-expected))<.001 and shape.buffer(.0001).covers(Polygon(t[:,[0,2]])))
    pick=np.array(pick);terrace=tri[pick].reshape(-1,5).copy();rest=tri[~pick].reshape(-1,5)
    coverage=unary_union([Polygon(t[:,[0,2]])for t in tri[pick]])
    assert pick.any() and (~pick).any() and coverage.symmetric_difference(shape).area<.002
    # Texture axes follow the surveyed front edge. The full atlas keeps stable
    # physical unit sizes, without repeating any aerial shadows or vehicles.
    direction=rings[0][1,[0,2]]-rings[0][0,[0,2]];direction/=np.linalg.norm(direction)
    axes=np.array([direction,[-direction[1],direction[0]]]);uv=terrace[:,[0,2]]@axes.T
    lo,hi=uv.min(0),uv.max(0);span=hi-lo;uv=(uv-lo)/span;terrace[:,3]=uv[:,0];terrace[:,4]=1-uv[:,1]
    paving=spec['paving'];size=np.ceil(span*paving['pixelsPerMetre']).astype(int);assert np.all(size<=8192)
    u=(np.arange(size[0])+.5)*span[0]/size[0];v=(size[1]-np.arange(size[1])-.5)*span[1]/size[1]
    xx,yy=np.meshgrid(u,v);uw,vh=paving['unitMetres'];row=np.floor(yy/vh).astype(int);sx=xx+(row%2)*uw*.5
    col=np.floor(sx/uw).astype(int);edge=np.minimum(np.minimum(sx%uw,uw-sx%uw),np.minimum(yy%vh,vh-yy%vh))
    pixel=max(span/size);joint=np.clip((paving['jointMetres']*.5+pixel*.5-edge)/pixel,0,1)
    rng=np.random.default_rng(paving['seed']);tones=rng.uniform(.9,1.08,(row.max()+1,col.max()+1));tone=tones[row,col]
    material=root/'minecraft/exterior/assets/textures/campus/concrete_diff.png'
    material_spec=next(m for m in json.loads((root/'minecraft/exterior/material-sources.json').read_text())['materials']if m['name']=='concrete_diff')
    assert sha(material)==material_spec['resourceSha256']
    texture=np.asarray(Image.open(material).convert('RGB'),dtype=float).mean(2)
    grain=texture[(yy/2*texture.shape[0]).astype(int)%texture.shape[0],(xx/2*texture.shape[1]).astype(int)%texture.shape[1]]/texture.mean()
    rgb=np.array(paving['baseColour'])*tone[:,:,None]*np.clip(grain,.8,1.2)[:,:,None]
    rgb=rgb*(1-joint[:,:,None])+np.array([78,82,73])*joint[:,:,None]
    atlas=Image.fromarray(np.dstack([np.clip(rgb,0,255).astype('uint8'),np.full(row.shape,255,dtype='uint8')]),'RGBA')
    # Geometry and the original roof pixels are retained exactly; only the
    # selected terrace triangles move to a second material part.
    roof.write_bytes(encode([(rest,pixels),(terrace,atlas)]))
    assert np.array_equal(tri[pick,:,:3].reshape(-1,3),terrace[:,:3])
    atlas.save(out/'mensa-terrace-paving.png')
    # Split the same surveyed surface in the collision asset so only this
    # outdoor terrace receives fractional supports. Other roofs and walls
    # retain their existing voxelization and original material pixels.
    collision=out/spec['collisionFile'];data=collision.read_bytes()
    assert data[:4]==b'ECT1' and struct.unpack_from('<i3d',data,4)==(2,0,0,0)
    parts=[];offset=32
    for _ in range(2):
        count,width,height=struct.unpack_from('<3i',data,offset);offset+=16
        vertices=np.frombuffer(data,dtype='<f4',count=count*5,offset=offset).reshape(-1,5).copy();offset+=count*20
        texture=Image.frombytes('RGBA',(width,height),data[offset:offset+width*height*4]);offset+=width*height*4
        parts.append((vertices,texture))
    assert offset==len(data)
    collision_roofs=parts[1][0].reshape(-1,3,5)
    keys={t[:,:3].tobytes()for t in tri[pick]}
    collision_pick=np.array([t[:,:3].tobytes()in keys for t in collision_roofs])
    assert collision_pick.sum()==pick.sum() and len(collision_roofs)==len(tri)
    collision.write_bytes(encode([parts[0],(collision_roofs[~collision_pick].reshape(-1,5),parts[1][1]),(collision_roofs[collision_pick].reshape(-1,5),parts[1][1])]))
    collision_record=next(t for t in meta['photoFacades']['collisionTiles']if t['file']==spec['collisionFile'])
    assert collision_record['kind']=='reconstruction'
    collision_record['collisionHeightfieldParts']=[2]
    meta['architecture']['mensaTerrace']={'sourceFile':'mensa-terrace.json','sourceSha256':sha(source),'generatorFile':'scripts/exterior_mensa_terrace.py','generatorSha256':sha(Path(__file__)),'rawInputs':inputs,'roofFile':spec['roofFile'],'roofSha256':sha(roof),'atlasFile':'mensa-terrace-paving.png','atlasSha256':sha(out/'mensa-terrace-paving.png'),'materialSha256':sha(material),'runtimeId':spec['runtimeId'],'materialPart':'last','areaSquareMetres':shape.area,'triangles':int(pick.sum()),'uvMetres':span.tolist(),'textureSize':size.tolist(),'qualification':spec['qualification']}
    meta['architecture']['mensaTerrace'].update(collisionFile=spec['collisionFile'],collisionSha256=sha(collision),collisionHeightfieldParts=[2])
    print('Former Mensa terrace:',round(shape.area,2),'m²;',pick.sum(),'unchanged survey triangles;',list(size),'paving atlas',flush=True)

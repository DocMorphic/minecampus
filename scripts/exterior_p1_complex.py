"""Survey-bounded P1 garage and service building exterior reconstruction."""
import hashlib,json,math,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
from exterior_physics_i import survey_plan,roof_texture,polygons
from exterior_physics_library import triangles
from exterior_terrain import ElevationSampler


def site_surveys(cache):
    ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'};result=[]
    for filename in ['campus-east.gml','campus-west.gml']:
        for b in ET.parse(cache/filename).findall('.//b:Building',ns):
            grounds=[np.array(list(map(float,p.text.split()))).reshape(-1,3)for p in b.findall('.//b:GroundSurface//g:posList',ns)]
            if not grounds:continue
            p=np.concatenate(grounds);lo,hi=p[:,:2].min(0),p[:,:2].max(0)
            if not box(*lo,*hi).intersects(box(698645,5349455,698748,5349555)):continue
            surfaces=[]
            for kind in ['GroundSurface','WallSurface','RoofSurface']:
                for poly in b.findall('.//b:'+kind+'//g:Polygon',ns):
                    rings=[]
                    for ring in poly.findall('.//g:LinearRing',ns):
                        pos=ring.find('g:posList',ns)
                        if pos is None:continue
                        v=np.array(list(map(float,pos.text.split()))).reshape(-1,3)
                        if np.linalg.norm(v[0]-v[-1])<.001:v=v[:-1]
                        if len(v)>=3:rings.append(v)
                    if rings:surfaces.append((kind,rings))
            result.append((b.get('{'+ns['g']+'}id'),surfaces))
    return result


def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ['ROOT','CACHE','OUT','metadata','mc','encode']]
    source=root/'minecraft/exterior/p1-complex.json';spec=json.loads(source.read_text())
    reference=root/'minecraft/exterior'/spec['reference']
    assert hashlib.sha256(reference.read_bytes()).hexdigest()==spec['referenceSha256']
    evidence=json.loads(reference.read_text())['fixtureEvidence']
    for key in ['surfaceModel','orthophoto']:
        item=evidence[key]
        assert hashlib.sha256((cache/item['cachePath']).read_bytes()).hexdigest()==item['sha256']
    surveys=site_surveys(cache);records=[];ground_tiles=[];used_ground=Polygon()
    for building in spec['buildings']:
        bid=building['building'];surfaces=next(s for key,s in surveys if key==bid)
        footprint,walls,roof,points=survey_plan(ctx,surfaces);base=float(points[:,1].min());garage=building['kind']=='garage'
        parts=[[],[],[],[]];textures=[Image.new('RGBA',(1,1),tuple(c))for c in building['materialColours']];controls=[]
        def emit(q,part,normal):
            q=np.asarray(q)
            if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0:q=q[::-1]
            for i in ([0,1,2]if len(q)==3 else [0,1,2,0,2,3]):parts[part].append([*q[i],.5,.5])
        for index,wall in enumerate(walls):
            anchor,direction,normal=[np.asarray(wall[k])for k in ['anchor','direction','normal']]
            shape=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0);left,bottom,right,top=shape.bounds
            exterior=bottom<base+.1
            if exterior:shape=shape.union(box(left,base-.6,right,base+.01))
            def pt(x,y,depth=0):
                p=anchor+direction*x+normal*depth;p[1]=y;return p
            def surface(poly,part,depth=0):
                for tri in triangles(poly):emit([pt(x,y,depth)for x,y in tri],part,normal)
            openings=[]
            if garage and exterior and index not in building['closedFaces']:
                count=max(1,round((right-left)/building['bayPitchMetres']));pitch=(right-left)/count
                for floor in range(5):
                    y0=base+floor*building['floorPitchMetres']+building['parapetMetres'];y1=base+(floor+1)*building['floorPitchMetres']-building['beamDepthMetres']
                    if min(y1,top-.16)<=y0:continue
                    for bay in range(count):
                        x0=left+bay*pitch+.16;x1=left+(bay+1)*pitch-.16
                        opening=shape.intersection(box(x0,y0,x1,min(y1,top-.16)))
                        if opening.area<.3:continue
                        openings.append(opening);surface(opening,2,-building['recessMetres'])
                        # Exterior reveals terminate a shallow visual recess;
                        # no garage interior or circulation plan is asserted.
                        coords=np.asarray(opening.exterior.coords)
                        for a,b in zip(coords[:-1],coords[1:]):emit([pt(*a),pt(*b),pt(*b,-building['recessMetres']),pt(*a,-building['recessMetres'])],0,normal)
                        for y in np.arange(y0+.08,min(y1,top-.16),.52):surface(opening.intersection(box(x0,y-.018,x1,y+.018)),1,-.045)
                        for x in np.arange(x0+.12,x1,.18):surface(opening.intersection(box(x-.008,y0,x+.008,y1)),1,-.055)
                        # Centre away from the thin grid bars for a depth control.
                        c=opening.representative_point();controls.append({'face':index,'part':2,'position':pt(c.x,c.y,-building['recessMetres']).tolist(),'normal':normal.tolist()})
            elif not garage:
                for rectangle in building['doors'].get(str(index),[]):
                    x0,y0,x1,y1=rectangle;y0+=base;y1+=base;opening=shape.intersection(box(x0,y0,x1,y1));openings.append(opening);surface(opening,3,-.08)
                    surface(opening.difference(opening.buffer(-.06,join_style=2)),1,-.015)
                    surface(opening.intersection(box(x0+.12,y0+.12,x1-.12,y0+.18)),1,-.06)
                    for y in np.arange(y0+.35,y1-.2,.15):surface(opening.intersection(box(x0+.14,y-.012,x1-.14,y+.012)),2,-.065)
                    c=opening.representative_point();controls.append({'face':index,'part':3,'position':pt(c.x,c.y,-.08).tolist(),'normal':normal.tolist()})
            cladding=shape.difference(unary_union(openings));surface(cladding,0)
            surface(cladding.intersection(box(left,top-.09,right,top+.01)),1,.015)
            # Recessed expansion joints in the solid portions, local to each face.
            for x in np.arange(left+4,right-.05,4):surface(cladding.intersection(box(x-.005,bottom,x+.005,top-.1)),3,.004)
            wall['reconstructed']=True
        roof_vertices,roof_photo=roof_texture(cache,roof);parts.append(roof_vertices.tolist());textures.append(roof_photo)
        fixture_shapes=[];fixture_records=[]
        if building.get('fixtures'):
            # Two circular silhouettes and measured cap heights are visible in
            # independent BVV aerial sources. Cylindrical sides/caps are an
            # exterior approximation; equipment function is not asserted.
            parts.append([]);textures.append(Image.new('RGBA',(1,1),(219,221,216,255)))
            with rasterio.open(cache/'campus-dgm-east.tif')as dem:
                sampler=ElevationSampler([dem])
                for fixture in building['fixtures']:
                    e,n=fixture['centreUTM'];radius=fixture['radiusMetres'];cap=fixture['capHeightUTM']
                    angles=np.arange(32)*2*np.pi/32
                    xy=np.column_stack([e+radius*np.cos(angles),n+radius*np.sin(angles)])
                    low=float(sampler.sample(xy).min())-.2
                    bottom=mc(np.column_stack([xy,np.full(32,low)]))
                    shoulder=mc(np.column_stack([xy,np.full(32,cap-.18)]))
                    topxy=np.array([e,n])+(xy-[e,n])*.83
                    top=mc(np.column_stack([topxy,np.full(32,cap)]))
                    centre=mc(np.array([[e,n,cap]]))[0]
                    for i in range(32):
                        j=(i+1)%32;normal=(bottom[i]+bottom[j])/2-centre;normal[1]=0;normal/=np.linalg.norm(normal)
                        emit([bottom[i],bottom[j],shoulder[j],shoulder[i]],5,normal)
                        emit([shoulder[i],shoulder[j],top[j],top[i]],5,normal+np.array([0,1,0]))
                        emit([centre,top[i],top[j]],5,np.array([0,1,0]))
                    ring=Polygon(bottom[:,[0,2]])
                    fixture_shapes.append(ring.buffer(.65))
                    fixture_records.append(dict(fixture,baseHeightUTM=low,capCentreMC=centre.tolist(),baseCentreMC=mc(np.array([[e,n,low]]))[0].tolist(),part=5,segments=32,ring=list(ring.exterior.coords)))
        # ECT permits empty material parts; stable indices distinguish concrete,
        # steel, dark recesses, service doors and the original DOP20 roof.
        name=bid+'-p1-exterior.ect';(out/name).write_bytes(encode(list(zip(parts,textures))))
        vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts if p]);meta['tiles'].append({'file':name,'kind':'reconstruction','profile':'p1-'+building['kind'],'runtimeId':building['runtimeId'],'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]})
        roofname=bid+'-photo-roof.ect';(out/roofname).write_bytes(encode([(roof_vertices,roof_photo)]))
        neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface']).buffer(.35)
        cleanup=footprint.buffer(building['cleanupMarginMetres'],join_style=2).union(unary_union(fixture_shapes)).difference(neighbours)
        rings=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(cleanup)]
        plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id']for p in plans['plans']]
        envelope=np.concatenate([points,vertices])
        plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roofname,'collisionFile':roofname,'bounds':[envelope.min(0).tolist(),envelope.max(0).tolist()],'walls':walls,'roofTriangles':roof[:,3:6].reshape(-1,3,3).tolist(),'retirement':rings,'retirementBoundary':rings})
        (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')));meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roofname);meta['photoFacades']['collisionRetirement'].extend(dict(r,y0=base-2,y1=float(envelope[:,1].max())+4)for r in rings)
        original=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for kind,r in surfaces if kind=='GroundSurface'])
        other=unary_union([Polygon(r[0][:,:2],[h[:,:2]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface'])
        site_box=box(*meta['architecture']['physicsISite']['boundsUTM'])
        # Fill the old footprint guard and the source-retirement apron beyond
        # existing terrain coverage. Previously packaged ground stays untouched.
        ground_area=original.buffer(.5,join_style=1).union(original.buffer(building['cleanupMarginMetres']+.5,join_style=2).difference(site_box)).difference(other.buffer(.5)).difference(used_ground)
        used_ground=used_ground.union(ground_area)
        lo=np.floor(np.array(ground_area.bounds[:2])).astype(int);hi=np.ceil(np.array(ground_area.bounds[2:])).astype(int)
        with rasterio.open(cache/'campus-dgm-east.tif')as dem:
            sampler=ElevationSampler([dem]);ground_vertices=[]
            def xyz(xy):return mc(np.column_stack([xy,sampler.sample(xy)]))
            for n in range(lo[1],hi[1]):
                for e in range(lo[0],hi[0]):
                    for xy in triangles(ground_area.intersection(box(e,n,e+1,n+1))):ground_vertices.extend(np.column_stack([xyz(xy),np.full((3,2),.5)]).tolist())
            guide_xy=np.array([(e,n)for n in range(lo[1],hi[1]+1)for e in range(lo[0],hi[0]+1)])
            guide={'width':int(hi[0]-lo[0]+1),'height':int(hi[1]-lo[1]+1),'points':xyz(guide_xy).tolist()};gr=[{'ring':xyz(np.asarray(p.exterior.coords))[:,[0,2]].tolist(),'holes':[xyz(np.asarray(h.coords))[:,[0,2]].tolist()for h in p.interiors]}for p in polygons(ground_area)]
        floorname='p1-'+building['kind']+'-ground.ect';(out/floorname).write_bytes(encode([(ground_vertices,Image.new('RGBA',(1,1),(138,134,121,255)))]));ground_tiles.append(floorname)
        gv=np.asarray(ground_vertices)[:,:3];meta['tiles'].append({'file':floorname,'kind':'ground','runtimeId':building['groundRuntimeId'],'bounds':[gv.min(0).tolist(),gv.max(0).tolist()]})
        meta.setdefault('supplementalSurfaces',[]).append({'name':'p1-'+building['kind']+'-apron','rings':gr,'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':False,'qualification':'DGM1 footprint/apron continuation; paving appearance estimated, no interior.'})
        records.append({'building':bid,'runtimeId':building['runtimeId'],'groundRuntimeId':building['groundRuntimeId'],'meshFile':name,'groundFile':floorname,'surveyWalls':walls,'openingControls':controls,'fixtures':fixture_records,'retirement':rings,'groundRings':gr,'roofTriangles':len(roof)//3,'surveyBaseMC':base})
        print('P1',building['kind'],len(walls),'survey faces;',len(roof)//3,'roof triangles;',len(controls),'facade controls',flush=True)
    meta['architecture']['p1Complex']={'sourceFile':source.name,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'generatorFile':'scripts/exterior_p1_complex.py','generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'qualification':spec['qualification'],'buildings':records,'groundTiles':ground_tiles}

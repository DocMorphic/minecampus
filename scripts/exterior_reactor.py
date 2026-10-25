"""FRM II exterior: surveyed loft, retained lower roofs and qualified facades."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer
from PIL import Image
from scipy.interpolate import CubicSpline
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles


def barrel_model(surfaces, spec):
    points = np.unique(np.concatenate([surfaces[i][1][0] for i in spec['barrelRoofSurfaceIndices']]), axis=0)
    sample = surfaces[spec['barrelRoofSurfaceIndices'][0]][1][0]
    edges = np.roll(sample,-1,axis=0)-sample
    axis = edges[np.argmax(np.linalg.norm(edges[:,:2],axis=1)),:2].copy()
    axis /= np.linalg.norm(axis)
    if axis[0]<0: axis *= -1
    across = np.array([-axis[1],axis[0]])
    centre = points[:,:2].mean(0)
    coords = (points[:,:2]-centre)@np.array([axis,across]).T
    splines=[]; angles=[]; ends=[]
    for select in [coords[:,0]<0,coords[:,0]>0]:
        p=points[select];v=coords[select,1]
        middle=(v.max()+v.min())*.5;radius=np.ptp(v)*.5
        base=p[:,2].min();rise=np.ptp(p[:,2])
        theta=np.arctan2((p[:,2]-base)/rise,(v-middle)/radius)
        order=np.argsort(theta);theta=theta[order];p=p[order]
        assert np.all(np.diff(theta)>1e-6)
        splines.append(CubicSpline(theta,p,axis=0));angles.extend(theta);ends.append(p)
    def evaluate(theta,along):
        theta,along=np.broadcast_arrays(theta,along)
        return splines[0](theta)*(1-along[...,None])+splines[1](theta)*along[...,None]
    errors=[]
    for end,p in enumerate(ends):
        uv=(p[:,:2]-centre)@np.array([axis,across]).T
        v=uv[:,1];theta=np.arctan2((p[:,2]-p[:,2].min())/np.ptp(p[:,2]),(v-(v.max()+v.min())*.5)/(np.ptp(v)*.5))
        errors.extend(np.linalg.norm(evaluate(theta,end)-p,axis=1))
    assert max(errors)<spec['sourceVertexToleranceMetres']
    return evaluate,np.unique(np.r_[np.linspace(0,np.pi,spec['roofAcrossSegments']+1),angles]),ends,{
        'axisUTM':axis.tolist(),'acrossUTM':across.tolist(),'centreUTM':centre.tolist(),
        'endPointsUTM':[p.tolist()for p in ends],'observedRoofVertices':len(points),
        'maximumObservedVertexErrorMetres':float(max(errors)),
        'method':'Cubic interpolation of each observed end section in elliptical angle, including all measured vertices; linear loft along the barrel. No circular fit or extrapolation.'}


def build(ctx):
    root,cache,out,meta,mc,encode=[ctx[k]for k in ('ROOT','CACHE','OUT','metadata','mc','encode')]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=root/'minecraft/exterior/reactor-exterior.json';spec=json.loads(source.read_text());bid=spec['building']
    reference=root/'minecraft/exterior'/spec['reference']
    sources=json.loads((root/'minecraft/exterior/sources.json').read_text());hashes={}
    for entry,name in zip(sources['lod2'],['campus-east.gml','campus-west.gml']):
        hashes[name]=sha(cache/name);assert hashes[name]==entry['sha256']
    surveys=nearby_surveys(cache,spec['siteBoundsUTM']);surfaces=next(s for key,s in surveys if key==bid)
    foot,walls,roof,points=survey_plan(ctx,surfaces)
    assert len(walls)==55 and len(roof)//3==82
    assert spec['runtimeId']not in [t['runtimeId']for t in meta['tiles']]
    evaluate,angles,ends,model=barrel_model(surfaces,spec)
    parts=[[]for _ in spec['parts']]
    colours=[(131,144,151,255),(195,200,203,255),(187,193,193,255),(59,82,88,255),(33,76,94,255),(160,160,150,255),(174,170,157,255)]
    textures=[Image.new('RGBA',(1,1),c)for c in colours]

    def emit(q,part,normal=None):
        q=np.asarray(q,dtype=float)
        if normal is None:normal=np.cross(q[1]-q[0],q[2]-q[0])
        normal=np.broadcast_to(normal,(3,3)).copy();normal/=np.linalg.norm(normal,axis=1)[:,None]
        if np.cross(q[1]-q[0],q[2]-q[0])@normal.mean(0)<0:q=q[::-1];normal=normal[::-1]
        stored=q.astype(np.float32).astype(float)
        if np.linalg.norm(np.cross(stored[1]-stored[0],stored[2]-stored[0]))<1e-8:return
        octa=normal[:,[0,2]]/np.abs(normal).sum(1)[:,None]
        below=normal[:,1]<0;octa[below]=(1-np.abs(octa[below,::-1]))*np.where(octa[below]>=0,1,-1)
        uv=octa*.5+.5 if part!=3 else np.full((3,2),.5)
        parts[part].extend(np.column_stack([q,uv]).tolist())

    aa,tt=np.meshgrid(angles,np.linspace(0,1,spec['roofAlongSegments']+1))
    grid=mc(evaluate(aa,tt).reshape(-1,3)).reshape(*aa.shape,3)
    eps=1e-5
    du=mc(evaluate(aa+eps,tt).reshape(-1,3))-mc(evaluate(aa-eps,tt).reshape(-1,3))
    dv=mc(evaluate(aa,tt+eps).reshape(-1,3))-mc(evaluate(aa,tt-eps).reshape(-1,3))
    normals=np.cross(du,dv).reshape(*aa.shape,3)
    normals*=np.where(normals[...,1]<0,-1,1)[...,None];normals/=np.linalg.norm(normals,axis=-1)[...,None]
    for j in range(len(grid)-1):
        for i in range(len(angles)-1):
            corners=[(j,i),(j,i+1),(j+1,i+1),(j+1,i)]
            for ids in [(0,1,2),(0,2,3)]:
                indices=[corners[k]for k in ids];emit([grid[k]for k in indices],0,[normals[k]for k in indices])
    # The same loft edge closes the gables; insert its points into their original
    # rings instead of leaving a crack above the survey's straight roof chords.
    end_mc=[mc(p)for p in ends];curves=[grid[0],grid[-1]]
    wall_adjustments=[];facade_controls=[];cfg=spec['facade'];base=float(points[:,1].min())
    for index,wall in enumerate(walls):
        anchor,direction,normal=[np.asarray(wall[k])for k in ('anchor','direction','normal')]
        original=np.asarray(wall['vertices']);ring=np.asarray(wall['rings'][0]);expanded=[];inserted=0
        # Match original 3D boundary points using projected source rings. The
        # datum's few millimetres of plane residual must not drop a match.
        for a,b in zip(ring,np.roll(ring,-1,axis=0)):
            expanded.append(a)
            qa=anchor+direction*a[0];qa[1]=a[1]
            qb=anchor+direction*b[0];qb[1]=b[1]
            for end,source_points in enumerate(end_mc):
                ia=np.argmin(np.linalg.norm(source_points-qa,axis=1));ib=np.argmin(np.linalg.norm(source_points-qb,axis=1))
                if max(np.linalg.norm(source_points[ia]-qa),np.linalg.norm(source_points[ib]-qb))>.025:continue
                ca=np.argmin(np.linalg.norm(curves[end]-source_points[ia],axis=1));cb=np.argmin(np.linalg.norm(curves[end]-source_points[ib],axis=1))
                if abs(cb-ca)<=1:continue
                step=1 if cb>ca else -1
                for k in range(ca+step,cb,step):
                    q=curves[end][k];expanded.append([(q-anchor)@direction,q[1]]);inserted+=1
        region=Polygon(expanded,wall['rings'][1:]).buffer(0)
        assert region.geom_type=='Polygon'
        if inserted:wall_adjustments.append({'wall':index,'insertedBoundaryPoints':inserted})
        left,bottom,right,top=region.bounds
        is_tower=top>90
        concrete=index in cfg['concreteWestArcWalls']
        openings=[]
        if concrete:
            openings.append(box(left,bottom+7.7,right,bottom+8.65))
        elif not is_tower:
            if top-bottom>5:
                openings.extend([box(left+.25,base+1.0,right-.25,base+2.9),box(left+.25,base+4.35,right-.25,base+6.2)])
            elif right-left>15 and bottom>base+5:
                openings.append(box(left+.2,bottom+.55,right-.2,top-.4))
        else:
            for fraction,y,width,height in cfg['towerOpenings'].get(str(index),[]):
                x=left+(right-left)*fraction;openings.append(box(x-width/2,y,x+width/2,y+height))
            if inserted:openings.append(box(left,cfg['towerTopBandHeightMC'],right,top+1))
        windows=region.intersection(unary_union(openings)) if openings else Polygon()
        frame=[]
        for p in polygons(windows):
            frame.append(p.boundary.buffer(cfg['windowFrameMetres']/2).intersection(p))
        # Continuous backing behind raised mullions avoids independent-pane gaps.
        pitch=cfg['windowPitchMetres'];global_offset=anchor@direction
        for u in np.arange(math.floor((left+global_offset)/pitch)*pitch,right+global_offset+pitch,pitch):
            x=u-global_offset;frame.append(windows.intersection(box(x-.025,bottom,x+.025,top)))
        frames=unary_union(frame) if frame else Polygon()
        accents=[]
        if is_tower and right-left>8:
            for fraction in [.25,.5,.75]:
                x=left+(right-left)*fraction;accents.append(box(x-.07,max(bottom,71),x+.07,min(top,91.72)))
        accent=region.intersection(unary_union(accents)).difference(windows) if accents else Polygon()
        def surface(poly,part,depth=0):
            for tri in triangles(poly):
                q=np.asarray([anchor+direction*x-normal*depth for x,y in tri]);q[:,1]=np.asarray(tri)[:,1];emit(q,part,normal)
        surface(region.difference(windows.union(accent)),6 if concrete else 1)
        surface(accent,4,-.012)
        surface(windows,3,cfg['recessMetres'])
        surface(frames,2,cfg['recessMetres']-.025)
        # Reveal geometry closes recessed glass to the measured outer skin.
        for p in polygons(windows):
            for boundary in [p.exterior,*p.interiors]:
                coords=np.asarray(boundary.coords)
                for a,b in zip(coords[:-1],coords[1:]):
                    q=np.array([anchor+direction*a[0],anchor+direction*b[0]]);q[:,1]=[a[1],b[1]]
                    corners=[q[0],q[1],q[1]-normal*cfg['recessMetres'],q[0]-normal*cfg['recessMetres']]
                    for ids in [(0,1,2),(0,2,3)]:emit([corners[k]for k in ids],2)
        wall['reconstructed']=True
        facade_controls.append({'wall':index,'sourceArea':Polygon(ring,wall['rings'][1:]).area,'renderedEnvelopeArea':region.area,'glazingArea':windows.area,'style':'concrete arc'if concrete else 'tower'if is_tower else 'lower wing','observed':index in cfg['observedTowerWalls']+cfg['observedLowerWalls']or concrete})
    # Keep all non-barrel roof triangles, including the measured pyramidal
    # rooflights. Give those skylights glass and narrow raised perimeter bars.
    lower=[s for i,s in enumerate(surfaces)if s[0]=='RoofSurface'and i not in spec['barrelRoofSurfaceIndices']and i not in spec['rooflightSurfaceIndices']]
    _,_,low_roof,_=survey_plan(ctx,lower);p,pixels=roof_texture(cache,low_roof);parts[5]=p.tolist();textures[5]=pixels
    rooflight_triangles=[]
    for i in spec['rooflightSurfaceIndices']:
        _,q,indices=ctx['triangulate'](surfaces[i][1])
        for tri in q[indices]:emit(tri,3);rooflight_triangles.extend(tri.tolist())
        # Preserve the original surveyed silhouette; bars sit only 12 mm above it.
        normal=np.cross(q[indices[0,1]]-q[indices[0,0]],q[indices[0,2]]-q[indices[0,0]]);normal/=np.linalg.norm(normal)
        if normal[1]<0:normal=-normal
        outline=mc(surfaces[i][1][0])
        for a,b in zip(outline,np.roll(outline,-1,axis=0)):
            edge=b-a;side=np.cross(normal,edge);side=side/np.linalg.norm(side)*.035
            corners=[a-side+normal*.012,b-side+normal*.012,b+side+normal*.012,a+side+normal*.012]
            for ids in [(0,1,2),(0,2,3)]:emit([corners[k]for k in ids],2,normal)
    assert all(parts)
    mesh=bid+'-reactor.ect';(out/mesh).write_bytes(encode(list(zip(parts,textures))))
    vertices=np.concatenate([np.asarray(p)[:,:3]for p in parts]);bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','profile':'reactor-exterior','runtimeId':spec['runtimeId'],'fineCollisionMaterials':spec['fineCollisionMaterials'],'bounds':bounds})
    roof_file=bid+'-photo-roof.ect';(out/roof_file).write_bytes(encode([(parts[0],textures[0]),(parts[5],textures[5]),(np.column_stack([rooflight_triangles,np.full((len(rooflight_triangles),2),.5)]).tolist(),textures[3])]))
    neighbours=unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]]for h in r[1:]]).buffer(0)for key,s in surveys if key!=bid for kind,r in s if kind=='GroundSurface'])
    owned=foot.buffer(spec['cleanupMarginMetres']).difference(neighbours.buffer(spec['neighbourGuardMetres']))
    retirement=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(owned)]
    plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id']for p in plans['plans']]
    all_roof=np.concatenate([np.asarray(parts[0])[:,:3],low_roof[:,3:6],rooflight_triangles])
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':bounds,'walls':walls,'roofTriangles':all_roof.reshape(-1,3,3).tolist(),'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roof_file)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=bounds[0][1]-2,y1=bounds[1][1]+3)for p in retirement)
    # Fine collision outside the initial central terrain needs a bounded datum.
    # This measured guide covers only the reconstructed envelope/retirement band;
    # it does not claim to supply the missing outdoor east/south walking ground.
    from exterior_terrain import ElevationSampler
    lat,lon=np.radians(meta['origin'][:2])
    origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
    basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
    inverse=Transformer.from_crs(4978,25832,always_xy=True)
    datum_region=foot.buffer(spec['cleanupMarginMetres']).difference(neighbours)
    datum_rings=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(datum_region)]
    lo=np.floor(np.array(datum_region.bounds[:2])/2)*2;hi=np.ceil(np.array(datum_region.bounds[2:])/2)*2
    flat=np.array([[x,64,z]for z in np.arange(lo[1],hi[1]+1,2)for x in np.arange(lo[0],hi[0]+1,2)])
    en=np.column_stack(inverse.transform(*((flat-[0,64,0])@basis+origin).T))[:,:2]
    with rasterio.open(cache/'campus-dgm-east.tif')as dem:
        sampler=ElevationSampler([dem]);height=mc(np.column_stack([en,sampler.sample(en)]))[:,1]
    flat[:,1]=height
    guide={'width':int((hi[0]-lo[0])/2+1),'height':int((hi[1]-lo[1])/2+1),'points':flat.tolist()}
    meta['supplementalSurfaces'].append({'name':'reactor-envelope-datum','rings':datum_rings,'terrainGuide':guide,'protectedFootprints':[],'outdoorReconstructed':False,'qualification':'BVV DGM1 datum confined to the reconstructed building envelope and bounded retirement band. Enables exterior wall/roof collision outside the old terrain footprint; no new outdoor route or interior is represented.'})
    record={**model,'surveyHashes':hashes,'datumRings':datum_rings,'datumSourceSha256':sha(cache/'campus-dgm-east.tif'),'partTriangles':[len(p)//3 for p in parts],'lowerRoofTriangles':len(low_roof)//3,'rooflightTriangles':len(rooflight_triangles)//3,'wallAdjustments':wall_adjustments,'facades':facade_controls,'retirement':retirement,'protectedNeighbourOverlapSquareMetres':owned.intersection(neighbours).area,'qualification':spec['qualification']}
    derived=out/'reactor-surfaces.json';derived.write_text(json.dumps(record,indent=2)+'\n')
    meta['architecture']['reactorExterior']={'building':bid,'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_reactor.py','generatorSha256':sha(Path(__file__)),'referenceFile':spec['reference'],'referenceSha256':sha(reference),'derivedFile':derived.name,'derivedSha256':sha(derived),'meshFile':mesh,'meshSha256':sha(out/mesh),'roofFile':roof_file,'roofSha256':sha(out/roof_file),'qualification':spec['qualification']}
    print('FRM II exterior:',len(walls),'walls;',len(parts[0])//3,'barrel triangles;',len(low_roof)//3,'retained lower roof triangles;',len(wall_adjustments),'closed curved gables',flush=True)

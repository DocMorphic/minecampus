"""Open glazed Atom-Ei canopies registered to the public survey roof geometry."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, survey_plan, polygons
from exterior_physics_library import triangles


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ('ROOT','CACHE','OUT','metadata','mc','encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/atom-ei-canopies.json'
    spec = json.loads(source.read_text()); selected = set(spec['buildings'])
    surveys = dict(nearby_surveys(cache, spec['siteBoundsUTM']))
    existing = json.loads((out/'photo-facades.json').read_text())
    plan_by_id = {p['id']:p for p in existing['plans']}
    dome = json.loads((out/'atom-ei-surfaces.json').read_text())
    centre = np.asarray(dome['baseCentreMC'])[[0,2]]
    footprints = {bid:unary_union([Polygon(mc(r[0])[:,[0,2]],[mc(h)[:,[0,2]] for h in r[1:]]).buffer(0)
                    for kind,r in surfaces if kind == 'GroundSurface']) for bid,surfaces in surveys.items()}
    protect = unary_union([p for bid,p in footprints.items() if bid not in selected|{spec['mainBuilding']}])
    terrain = meta['terrainGuide']; grid = np.asarray(terrain['points']).reshape(terrain['height'],terrain['width'],3)
    origin = grid[0,0,[0,2]]
    inverse = np.linalg.inv(np.column_stack([grid[0,1,[0,2]]-origin,grid[1,0,[0,2]]-origin]))
    def ground(xz):
        u,v = inverse@(np.asarray(xz)-origin); i,j = math.floor(u),math.floor(v); fu,fv = u-i,v-j
        assert 0<=i<terrain['width']-1 and 0<=j<terrain['height']-1
        return float((grid[j,i,1]*(1-fu)+grid[j,i+1,1]*fu)*(1-fv)+(grid[j+1,i,1]*(1-fu)+grid[j+1,i+1,1]*fu)*fv)
    records = []; retired_collision = []
    for bid,config in spec['buildings'].items():
        assert config['runtimeId'] not in [t['runtimeId'] for t in meta['tiles']]
        surfaces = surveys[bid]; foot,walls,roof,points = survey_plan(ctx,surfaces)
        assert len(roof)//3 == config['roofTriangles']
        panes = np.column_stack([roof[:,3:6],np.full((len(roof),2),.5)]).tolist()
        frame = []; roof_regions = []; supports = []; control_candidates = []
        def triangle(p, normal):
            q=np.asarray(p,dtype=np.float32).astype(float)
            if np.linalg.norm(np.cross(q[1]-q[0],q[2]-q[0]))<1e-9:return
            # Flat face normals avoid derivative noise on narrow frame faces.
            # Solid-colour textures leave UVs available for octahedral encoding.
            normal=np.asarray(normal,dtype=float)
            normal/=np.linalg.norm(normal)
            octa=normal[[0,2]]/np.abs(normal).sum()
            if normal[1]<0:octa=(1-np.abs(octa[::-1]))*np.where(octa>=0,1,-1)
            uv=octa*.5+.5
            frame.extend([*v,*uv]for v in p)
        def extrude(region, plane, lower, upper):
            def lift(xz,dy):return np.array([xz[0],float(np.dot([*xz,1],plane))+dy,xz[1]])
            for tri in triangles(region):
                top=np.array([lift(p,upper)for p in tri])
                if np.cross(top[1]-top[0],top[2]-top[0])[1]<0:top=top[::-1]
                n=np.array([-plane[0],1,-plane[1]])
                triangle(top,n);triangle(np.array([lift(p,lower)for p in tri])[::-1],-n)
            for poly in polygons(region):
                for ring in [poly.exterior,*poly.interiors]:
                    coords=np.asarray(ring.coords)
                    for a,b in zip(coords[:-1],coords[1:]):
                        q=[lift(a,lower),lift(b,lower),lift(b,upper),lift(a,upper)]
                        n=np.array([a[1]-b[1],0,b[0]-a[0]])
                        triangle([q[k]for k in [0,1,2]],n);triangle([q[k]for k in [0,2,3]],n)
        for roof_index,(kind,rings) in enumerate((k,r)for k,r in surfaces if k=='RoofSurface'):
            q=mc(rings[0]); region=Polygon(q[:,[0,2]],[mc(h)[:,[0,2]]for h in rings[1:]]).buffer(0)
            plane=np.linalg.lstsq(np.column_stack([q[:,[0,2]],np.ones(len(q))]),q[:,1],rcond=None)[0]
            assert np.max(np.abs(np.column_stack([q[:,[0,2]],np.ones(len(q))])@plane-q[:,1]))<.0001
            width=spec['frameWidthMetres']; strips=[region.boundary.buffer(width/2)]
            for angle in np.linspace(0,2*np.pi,spec['paneDivisionsAroundCircle'],endpoint=False):
                direction=np.array([math.cos(angle),math.sin(angle)])
                strips.append(LineString([centre,centre+direction*40]).buffer(width/2,cap_style=2))
            bars=region.intersection(unary_union(strips)); extrude(bars,plane,-spec['frameDepthMetres']/2,spec['frameDepthMetres']/2)
            current_supports=[]
            for angle in np.linspace(0,2*np.pi,spec['postDivisionsAroundCircle'],endpoint=False):
                direction=np.array([math.cos(angle),math.sin(angle)])
                cut=region.intersection(LineString([centre,centre+direction*40]))
                if cut.is_empty:continue
                lines=[cut]if cut.geom_type=='LineString'else [g for g in getattr(cut,'geoms',[])if g.geom_type=='LineString']
                for line in lines:
                    endpoints=np.asarray(line.coords); distances=(endpoints-centre)@direction
                    if distances.max()-distances.min()<.7:continue
                    xz=centre+direction*(distances.max()-spec['postEdgeInsetMetres'])
                    if not region.buffer(-.04).contains(Point(xz)):continue
                    half=spec['postWidthMetres']/2
                    post=Polygon([xz+[-half,-half],xz+[half,-half],xz+[half,half],xz+[-half,half]])
                    floor=ground(xz)-.08; height=float(np.dot([*xz,1],plane))-spec['frameDepthMetres']/2
                    # A horizontal top differs from the tiny datum tilt by less than0.01mm.
                    extrude(post,np.array([0,0,0]),floor,height)
                    entry={'positionMC':[xz[0],floor,xz[1]],'topMC':height,'widthMetres':spec['postWidthMetres'],'roofIndex':roof_index}
                    supports.append(entry);current_supports.append(xz)
                    mid=centre+direction*(distances.min()+distances.max())/2
                    # Midspan controls are between posts, not at their radial lines.
                    tangent=np.array([-direction[1],direction[0]])
                    control=mid+tangent*.65
                    if region.buffer(.0).contains(Point(control)):
                        control_candidates.append({'positionMC':[control[0],ground(control),control[1]],'roofY':float(np.dot([*control,1],plane)),'roofIndex':roof_index})
            roof_regions.append({'roofIndex':roof_index,'ring':list(region.exterior.coords),'holes':[list(h.coords)for h in region.interiors],
                                 'plane':plane.tolist(),'frameAreaSquareMetres':bars.area,'postCount':len(current_supports)})
        assert len(roof_regions)==config['roofSurfaces'] and supports
        mesh=bid+'-atom-canopy.ect';(out/mesh).write_bytes(encode([(panes,Image.new('RGBA',(1,1),(165,187,185,255))),(frame,Image.new('RGBA',(1,1),(208,213,207,255)))]))
        vertices=np.concatenate([np.asarray(panes)[:,:3],np.asarray(frame)[:,:3]])
        bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()]
        meta['tiles'].append({'file':mesh,'kind':'reconstruction','profile':'atom-ei-canopy','runtimeId':config['runtimeId'],
            'fineCollisionMaterials':spec['fineCollisionMaterials'],'bounds':bounds})
        owned=foot.buffer(spec['cleanupMarginMetres']).difference(protect.buffer(spec['neighbourGuardMetres']))
        retirement=[{'ring':list(p.exterior.coords),'holes':[list(h.coords)for h in p.interiors]}for p in polygons(owned)]
        plan=plan_by_id[bid];retired_collision.append(plan['collisionFile'])
        plan.update(manualRoof=True,completeEnvelope=True,retirement=retirement,retirementBoundary=retirement)
        for wall in plan['walls']:
            wall['reconstructed']=True
            wall['reconstructionRole']='Survey volume boundary retired: exterior canopy sides are open; the supported roof and posts own collision.'
        meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=plan['bounds'][0][1]-2,y1=plan['bounds'][1][1]+3)for p in retirement)
        records.append({'building':bid,'runtimeId':config['runtimeId'],'meshFile':mesh,'meshSha256':sha(out/mesh),
            'glassTriangles':len(panes)//3,'frameTriangles':len(frame)//3,'roofRegions':roof_regions,'supports':supports,
            'walkingCandidates':control_candidates,'retirement':retirement,'protectedNeighbourOverlapSquareMetres':owned.intersection(protect).area,
            'retiredPhotoRuntimeId':plan['runtimeId'],'retiredCollisionFile':plan['collisionFile'],'retiredVolumeWalls':len(plan['walls'])})
    meta['photoFacades']['collisionTiles']=[t for t in meta['photoFacades']['collisionTiles']if t['file']not in retired_collision]
    (out/'photo-facades.json').write_text(json.dumps(existing,separators=(',',':')))
    derived=out/'atom-ei-canopy-surfaces.json';derived.write_text(json.dumps({'buildings':records,'qualification':spec['qualification']},indent=2)+'\n')
    meta['architecture']['atomEiCanopies']={'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_atom_ei_canopies.py',
        'generatorSha256':sha(Path(__file__)),'referenceFile':spec['reference'],'referenceSha256':sha(root/'minecraft/exterior'/spec['reference']),
        'derivedFile':derived.name,'derivedSha256':sha(derived),'meshFiles':[p['meshFile']for p in records],
        'retiredCollisionFiles':retired_collision,'qualification':spec['qualification']}
    print('Atom-Ei canopies:',sum(p['glassTriangles']for p in records),'survey roof triangles;',sum(len(p['supports'])for p in records),'posts;',sum(p['retiredVolumeWalls']for p in records),'false enclosure faces retired',flush=True)

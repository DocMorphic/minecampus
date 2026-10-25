"""Surveyed west-ZNN service body and two separately inferred tank silhouettes."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Polygon, Point, box, mapping
from shapely.ops import unary_union
from exterior_physics_i import nearby_surveys, survey_plan, roof_texture, polygons
from exterior_physics_library import triangles


def build(ctx):
    root, cache, out, meta, mc, encode = [ctx[k] for k in ('ROOT','CACHE','OUT','metadata','mc','encode')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior/physics-znn-west.json'
    spec = json.loads(source.read_text()); bid = spec['building']
    assert spec['runtimeId'] not in [t.get('runtimeId') for t in meta['tiles']]
    osm_file = root/'minecraft/exterior'/spec['osm']['sourceFile']; assert sha(osm_file)==spec['osm']['sha256']
    osm = ET.parse(osm_file).getroot(); project = Transformer.from_crs(4326,25832,always_xy=True).transform
    nodes = {n.get('id'): project(float(n.get('lon')),float(n.get('lat'))) for n in osm.findall('node')}
    way = next(w for w in osm.findall('way') if w.get('id')==spec['osm']['way'])
    compound = Polygon([nodes[n.get('ref')] for n in way.findall('nd')])
    surveys = nearby_surveys(cache,spec['siteBoundsUTM'])
    surfaces = next(s for key,s in surveys if key==bid)
    footprint,walls,roof,points = survey_plan(ctx,surfaces)
    raw_foot = unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for kind,p in surfaces if kind=='GroundSurface'])
    assert len(walls)==4 and len(roof)==9
    parts = [[],[],[],[]]; textures = [Image.new('RGBA',(1,1),tuple(c)) for c in spec['materialColours']]
    base = float(points[:,1].min()); controls=[]
    def emit(q,part,normal):
        q=np.asarray(q,dtype=float)
        if np.dot(np.cross(q[1]-q[0],q[2]-q[0]),normal)<0:q=q[::-1]
        for i in ([0,1,2] if len(q)==3 else [0,1,2,0,2,3]):parts[part].append([*q[i],.5,.5])
    for index,wall in enumerate(walls):
        anchor,direction,normal=[np.asarray(wall[k]) for k in ('anchor','direction','normal')]
        region=Polygon(wall['rings'][0],wall['rings'][1:]).buffer(0);left,bottom,right,top=region.bounds
        region=region.union(box(left,base-spec['wallBaseExtensionMetres'],right,base+.01))
        def pt(x,y,depth=0):
            p=anchor+direction*x+normal*depth;p[1]=y;return p
        def surface(region,part,depth=0):
            for tri in triangles(region):emit([pt(x,y,depth) for x,y in tri],part,normal)
        surface(region,0)
        surface(region.intersection(box(left,base-.8,right,base+.22)),3,.003)
        surface(region.intersection(box(left,top-spec['roofFasciaHeightMetres'],right,top+.01)),1,.008)
        for x in np.arange(left+spec['panelPitchMetres'],right,spec['panelPitchMetres']):
            width=spec['panelJointWidthMetres']/2
            surface(region.intersection(box(x-width,base+.22,x+width,top-spec['roofFasciaHeightMetres'])),1,.004)
        wall['reconstructed']=True
        controls.append({'kind':'survey-wall','face':index,'part':0,'position':pt(left+(right-left)*.37,base+1.4).tolist(),'normal':normal.tolist()})
    # Tank centres, top heights and radii come from public source controls.
    # Rounded caps and narrow base pads are explicitly estimated geometry.
    equipment=[]; tank_footprints=[]; tank_roof_triangles=[]
    for index,tank in enumerate(spec['equipment']):
        e,n=tank['centreUTM'];radius=tank['radiusMetres'];ground=tank['centreGroundElevation'];top=ground+tank['topAboveLocalGroundMetres'];rise=spec['tankCapRiseMetres'];bottom=ground+spec['tankPlinthHeightMetres'];segments=spec['tankSegments']
        assert .4<radius<2 and top-bottom>3 and compound.covers(Point(e,n).buffer(radius))
        angles=np.arange(segments)*math.tau/segments
        def ring(r,z):return mc(np.column_stack([e+r*np.cos(angles),n+r*np.sin(angles),np.full(segments,z)]))
        lower,upper=ring(radius,bottom),ring(radius,top-rise)
        centre=mc(np.array([[e,n,bottom]]))[0]
        for i in range(segments):
            j=(i+1)%segments;normal=(lower[i]+lower[j])/2-centre;normal[1]=0
            emit([lower[i],lower[j],upper[j],upper[i]],2,normal)
        last=upper
        for phi in np.linspace(0,math.pi/2,6)[1:]:
            current=ring(radius*math.cos(phi),top-rise+rise*math.sin(phi))
            for i in range(segments):
                j=(i+1)%segments
                if phi==math.pi/2:
                    q=np.array([last[i],last[j],current[i]])
                    emit(q,2,[0,1,0]);tank_roof_triangles.append(q)
                else:
                    q=np.array([last[i],last[j],current[j],current[i]])
                    emit(q,2,[0,1,0]);tank_roof_triangles.extend([q[[0,1,2]],q[[0,2,3]]])
            last=current
        pad_radius=radius+.18;pad_bottom,pad_top=ring(pad_radius,ground-.1),ring(pad_radius,bottom)
        pad_centre=mc(np.array([[e,n,bottom]]))[0]
        for i in range(segments):
            j=(i+1)%segments;normal=(pad_bottom[i]+pad_bottom[j])/2-centre;normal[1]=0
            emit([pad_bottom[i],pad_bottom[j],pad_top[j],pad_top[i]],3,normal)
            emit([pad_top[i],pad_top[j],pad_centre],3,[0,1,0])
        tank_footprints.append(Point(e,n).buffer(pad_radius,resolution=32))
        target=(lower[0]+lower[1]+upper[0]+upper[1])*.25;normal=target-centre;normal[1]=0;normal/=np.linalg.norm(normal)
        controls.append({'kind':'inferred-tank','equipment':index,'part':2,'position':target.tolist(),'normal':normal.tolist()})
        equipment.append({**tank,'baseMC':centre.tolist(),'topMC':mc(np.array([[e,n,top]]))[0].tolist(),'segments':segments})
    rv,rp=roof_texture(cache,roof);parts.append(rv.tolist());textures.append(rp)
    assert all(parts)
    mesh=bid+'-znn-west.ect';(out/mesh).write_bytes(encode(list(zip(parts,textures))))
    all_points=np.concatenate([np.asarray(p)[:,:3] for p in parts]);bounds=[all_points.min(0).tolist(),all_points.max(0).tolist()]
    meta['tiles'].append({'file':mesh,'kind':'reconstruction','runtimeId':spec['runtimeId'],'bounds':bounds})
    roof_file=bid+'-photo-roof.ect'
    cap_vertices=np.column_stack([np.asarray(tank_roof_triangles).reshape(-1,3),np.full((len(tank_roof_triangles)*3,2),.5)]).tolist()
    (out/roof_file).write_bytes(encode([(rv,rp),(cap_vertices,textures[2])]))
    # Retire only the modeled building/tanks and their small outer margin.
    # Keep the remainder of the mapped equipment compound, whose low fittings
    # cannot be resolved confidently from the available public sources.
    modeled=raw_foot.union(unary_union(tank_footprints))
    unmodeled=compound.difference(modeled)
    others=unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for key,s in surveys if key!=bid for kind,p in s if kind=='GroundSurface'])
    cleanup=modeled.buffer(spec['cleanupMarginMetres']).difference(unmodeled).difference(others.buffer(.5))
    def rings(region):
        def convert(ring):
            xy=np.asarray(ring.coords);return mc(np.column_stack([xy,np.full(len(xy),474.5)]))[:,[0,2]].tolist()
        return [{'ring':convert(p.exterior),'holes':[convert(h) for h in p.interiors]} for p in polygons(region)]
    retirement=rings(cleanup)
    plans=json.loads((out/'photo-facades.json').read_text());assert bid not in [p['id'] for p in plans['plans']]
    roof_triangles=roof[:,3:6].reshape(-1,3,3).tolist()+np.asarray(tank_roof_triangles).tolist()
    plans['plans'].append({'id':bid,'runtimeId':1_000_050_000+len(plans['plans']),'manualRoof':True,'completeEnvelope':True,'roofFile':roof_file,'collisionFile':roof_file,'bounds':bounds,'walls':walls,'roofTriangles':roof_triangles,'retirement':retirement,'retirementBoundary':retirement})
    (out/'photo-facades.json').write_text(json.dumps(plans,separators=(',',':')))
    meta['photoFacades']['buildings'].append(bid);meta['photoFacades']['roofFiles'].append(roof_file)
    meta['photoFacades']['collisionRetirement'].extend(dict(p,y0=bounds[0][1]-2,y1=bounds[1][1]+3) for p in retirement)
    coverage=out/'physics-znn-west-coverage.geojson';coverage.write_text(json.dumps({'building':mapping(raw_foot),'equipment':mapping(unary_union(tank_footprints)),'mappedCompound':mapping(compound),'unmodeledProtected':mapping(unmodeled),'retirement':mapping(cleanup)},separators=(',',':'))+'\n')
    from exterior_foundation_collar import build as build_collar
    collar=build_collar(ctx,footprint,spec['groundRuntimeId'],'physics-znn-west-ground.ect')
    meta['architecture']['physicsZNNWest']={'building':bid,'sourceFile':source.name,'sourceSha256':sha(source),'generatorFile':'scripts/exterior_physics_znn_west.py','generatorSha256':sha(Path(__file__)),'meshFile':mesh,'roofFile':roof_file,'coverageFile':coverage.name,'coverageSha256':sha(coverage),'foundationCollar':collar,'groundTiles':[collar['file']],'collarGeneratorSha256':sha(root/'scripts/exterior_foundation_collar.py'),'surveyRoofTriangles':3,'surveyWalls':walls,'equipment':equipment,'controls':controls,'retirement':retirement,'qualification':spec['qualification']}
    print('ZNN west service body:',len(walls),'survey walls;',len(equipment),'source-estimated tanks; unknown equipment area protected',flush=True)

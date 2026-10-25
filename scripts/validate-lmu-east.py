#!/usr/bin/env python3
"""Independently check the LMU east service building and adjoining mapped ground against raw public survey inputs."""
from pathlib import Path
import argparse,hashlib,json,math,struct,xml.etree.ElementTree as ET
import numpy as np
import rasterio
from PIL import Image
from rasterio.windows import from_bounds
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union,nearest_points
from shapely.strtree import STRtree

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior');parser.add_argument('--ground-directory',type=Path);args=parser.parse_args();out=args.directory;prior=args.ground_directory or out
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(out/'manifest.json');rec=m['architecture']['physicsLMUEast'];source=root/'minecraft/exterior'/rec['sourceFile'];spec=read(source)
assert sha(source)==rec['sourceSha256']
for path,key in [(rec['generatorFile'],'generatorSha256'),('scripts/exterior_ground_extension.py','groundGeneratorSha256'),('scripts/exterior_vegetation.py','vegetationGeneratorSha256'),('minecraft/exterior/vegetation-sources.json','vegetationSourceSha256')]:assert sha(root/path)==rec[key]
assert sha(out/rec['coverageFile'])==rec['coverageSha256']
inputs={}
for item in read(root/'minecraft/exterior/vegetation-sources.json')['inputs']:
    assert sha(root/'.cache'/item['cachePath'])==item['sha256'];inputs[item['cachePath']]=item['sha256']
sources=read(root/'minecraft/exterior/sources.json')
for item,name in zip(sources['lod2'],['campus-east.gml','campus-west.gml']):
    assert sha(root/'.cache'/name)==item['sha256'];inputs[name]=item['sha256']
for kind,name in [('dgm1','campus-dgm-east.tif'),('dop20','campus-dop-east.tif')]:
    digest=sorted(sources[kind],key=lambda item:item['name'])[1]['sha256']
    assert sha(root/'.cache'/name)==digest;inputs[name]=digest
assert sha(root/'.cache/de_bkg_gcg2016.tif')==sources['geoid']['sha256']
inputs['de_bkg_gcg2016.tif']=sources['geoid']['sha256']
ns={'g':'http://www.opengis.net/gml','b':'http://www.opengis.net/citygml/building/1.0'};surfaces={}
for name in ['campus-east.gml','campus-west.gml']:
    for b in ET.parse(root/'.cache'/name).findall('.//b:Building',ns):
        items=[]
        for kind in ['GroundSurface','RoofSurface','WallSurface']:
            for p in b.findall('.//b:'+kind+'//g:Polygon',ns):
                rings=[np.array(list(map(float,x.text.split()))).reshape(-1,3) for x in p.findall('.//g:LinearRing/g:posList',ns)]
                if rings:items.append((kind,rings))
        surfaces[b.get('{'+ns['g']+'}id')]=items
raw=surfaces[spec['building']];foot=unary_union([Polygon(p[0][:,:2],[h[:,:2] for h in p[1:]]).buffer(0) for k,p in raw if k=='GroundSurface'])
polys=lambda p:[p] if p.geom_type=='Polygon' else [x for x in p.geoms if x.geom_type=='Polygon']
lat,lon=np.radians(m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-np.sin(lon),np.cos(lon),0],[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],[np.sin(lat)*np.cos(lon),np.sin(lat)*np.sin(lon),-np.cos(lat)]])
ecef=Transformer.from_crs(25832,4978,always_xy=True);geo=Transformer.from_crs(25832,4258,always_xy=True);inverse=Transformer.from_crs(4978,25832,always_xy=True)
with rasterio.open(root/'.cache/de_bkg_gcg2016.tif') as raster:geoid=raster.read(1).astype(float);geoid_transform=raster.transform

def world(p):
    lon,lat=geo.transform(p[:,0],p[:,1]);c,r=(~geoid_transform)*(lon,lat);h=p[:,2]+map_coordinates(geoid,[r-.5,c-.5],order=1,prefilter=False)
    return (np.column_stack(ecef.transform(p[:,0],p[:,1],h))-origin)@basis.T+[0,64,0]
def utm(p):return np.column_stack(inverse.transform(*((p-[0,64,0])@basis+origin).T))
def decode(path):
    data=path.read_bytes();assert data[:4]==b'ECT1';count,*anchor=struct.unpack_from('<i3d',data,4);offset=32;parts=[]
    for _ in range(count):
        n,w,h=struct.unpack_from('<3i',data,offset);offset+=16;assert n%3==0
        v=np.frombuffer(data,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).astype(float);v[:,:3]+=anchor;offset+=n*20
        pixels=np.frombuffer(data,dtype='uint8',count=w*h*4,offset=offset).reshape(h,w,4);offset+=w*h*4;assert np.isfinite(v).all();parts.append((v,pixels))
    assert offset==len(data);return parts

# Read the pinned map geometry directly; never use emitted coverage to define
# the expected building/lawn/path envelope.
osm_path=source.parent/spec['osm']['sourceFile'];assert sha(osm_path)==spec['osm']['sha256']
inputs[spec['osm']['sourceFile']]=spec['osm']['sha256']
osm=ET.parse(osm_path).getroot();project=Transformer.from_crs(4326,25832,always_xy=True).transform
nodes={n.get('id'):project(float(n.get('lon')),float(n.get('lat'))) for n in osm.findall('node')}
ways={w.get('id'):[nodes[n.get('ref')] for n in w.findall('nd')] for w in osm.findall('way')}
from shapely.geometry import LineString
lawn=Polygon(ways[spec['osm']['lawnWay']])
nearby=[]
for bid,items in surfaces.items():
    if bid==spec['building']:continue
    for kind,rings in items:
        if kind=='GroundSurface':
            p=Polygon(rings[0][:,:2],[h[:,:2] for h in rings[1:]]).buffer(0)
            if p.intersects(box(*spec['boundsUTM']).buffer(30)):nearby.append(p)
neighbours=unary_union(nearby)
collar=foot.buffer(spec['cleanupMarginMetres']).difference(neighbours.buffer(.25))
expected=collar.union(lawn)
for way,width in [('drivewayWay','drivewayHalfWidthMetres'),('footwayWay','footwayHalfWidthMetres')]:
    expected=expected.union(LineString(ways[spec['osm'][way]]).buffer(spec[width]))
expected=expected.convex_hull.buffer(spec['groundContinuityMarginMetres'])
expected=expected.intersection(box(*spec['boundsUTM'])).difference(neighbours.buffer(.25))
with rasterio.open(root/'.cache/campus-dgm-east.tif') as dem:
    dgm=dem.read(1).astype(float);transform=dem.transform
    def elevation(xy):
        c,r=(~transform)*(xy[:,0],xy[:,1]);return map_coordinates(dgm,[r-.5,c-.5],order=1,prefilter=False)
def horizontal(shape):
    def ring(r):
        xy=np.asarray(r.coords);return world(np.column_stack([xy,elevation(xy)]))[:,[0,2]]
    return unary_union([Polygon(ring(p.exterior),[ring(h) for h in p.interiors]) for p in polys(shape)])
expected_mc=horizontal(expected)
parts=decode(out/rec['meshFile']);roof_parts=decode(out/rec['roofFile'])
assert len(parts)==4 and len(roof_parts)==1
assert np.array_equal(parts[3][0],roof_parts[0][0]) and np.array_equal(parts[3][1],roof_parts[0][1])
for (v,pixels),colour in zip(parts[:3],spec['materialColours']):
    assert np.array_equal(pixels,np.array([[colour]],dtype=np.uint8))
    assert np.all(v[:,3:]==.5)
raw_roofs=[rings for kind,rings in raw if kind=='RoofSurface']
roof_points=np.concatenate([world(ring) for rings in raw_roofs for ring in rings])
rv=parts[3][0];assert len(rv)==spec['roofTriangles']*3
roof_error=float(cKDTree(roof_points).query(rv[:,:3])[0].max());assert roof_error<1e-4
roof_expected=unary_union([Polygon(world(r[0])[:,[0,2]],[world(h)[:,[0,2]] for h in r[1:]]) for r in raw_roofs])
roof_actual=unary_union([Polygon(t[:,[0,2]]) for t in rv[:,:3].reshape(-1,3,3)])
assert roof_actual.symmetric_difference(roof_expected).area<roof_expected.length*1e-4
# Project each encoded face onto each independent survey plane. Require the
# source silhouette, outward winding and disjoint material bands.
raw_walls=[r for kind,r in raw if kind=='WallSurface'];assert len(raw_walls)==spec['wallCount']
all_raw=np.concatenate([world(r) for kind,rings in raw for r in rings]);base=all_raw[:,1].min()
wall_checks=[]
for wall_index,rings in enumerate(raw_walls):
    v=world(rings[0]);a=v[0].copy();edges=np.roll(v,-1,axis=0)-v
    u=edges[np.argmax(np.linalg.norm(edges[:,[0,2]],axis=1))].copy();u[1]=0;u/=np.linalg.norm(u)
    n=np.array([-u[2],0,u[0]])
    centre=v.mean(0);inside=horizontal(foot)
    if inside.covers(Point(*(centre+n*.1)[[0,2]])):n=-n
    poly=Polygon(np.column_stack([(v-a)@u,v[:,1]]),[np.column_stack([(world(h)-a)@u,world(h)[:,1]]) for h in rings[1:]]).buffer(0)
    left,bottom,right,top=poly.bounds
    expected_wall=poly.union(box(left,base-spec['wallBaseExtensionMetres'],right,base+.01))
    projected=[]
    for vertices,pixels in parts[:3]:
        triangles=vertices[:,:3].reshape(-1,3,3);depth=(triangles-a)@n
        # UTM verticals tilt slightly in the ENU frame; the generator uses
        # vertical wall planes. This 1 mm selection envelope includes that
        # measured sub-millimetre projection drift and float32 storage error.
        normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        lengths=np.linalg.norm(normals,axis=1);assert np.all(lengths>1e-9)
        parallel=abs(normals@n)/lengths>.999
        selected=triangles[(np.max(abs(depth),axis=1)<.001)&parallel]
        polygons=[]
        for t in selected:
            normal=np.cross(t[1]-t[0],t[2]-t[0]);assert normal@n>0,(wall_index,normal.tolist(),n.tolist(),t.tolist())
            polygons.append(Polygon(np.column_stack([(t-a)@u,t[:,1]])))
        projected.append(unary_union(polygons))
    actual=unary_union(projected)
    missing=expected_wall.difference(actual.buffer(.0001)).area
    excess=actual.difference(expected_wall.buffer(.0001)).area
    overlap=sum(projected[i].intersection(projected[j]).area for i in range(3) for j in range(i))
    assert missing<.001 and excess<.001 and overlap<.001,(wall_index,missing,excess,overlap,[(float(np.min(abs((v[:,:3]-a)@n))),float(np.max(abs((v[:,:3]-a)@n)))) for v,p in parts[:3]])
    wall_checks.append({'missingSquareMetres':missing,'excessSquareMetres':excess,'finishOverlapSquareMetres':overlap})
plan=next(p for p in read(out/'photo-facades.json')['plans'] if p['id']==spec['building'])
assert plan['completeEnvelope'] and len(plan['walls'])==spec['wallCount']
retired=unary_union([Polygon(p['ring'],p['holes']) for p in plan['retirement']])
assert retired.symmetric_difference(horizontal(collar)).area<.002
ids=[t['runtimeId'] for t in m['tiles']];assert len(ids)==len(set(ids))
new_files=rec['groundTiles'];new_parts=[decode(out/name)[0] for name in new_files];tri=np.concatenate([v[:,:3].reshape(-1,3,3) for v,pixels in new_parts]);region=unary_union([Polygon(t[:,[0,2]]) for t in tri]);assert abs(region.area-rec['ground']['areaSquareMetres'])<.005
assert region.difference(expected_mc.buffer(.0001)).area<.001
old=[];start=min(i for i,t in enumerate(m['tiles']) if t['file'] in new_files)
for tile in m['tiles'][:start]:
    if tile['kind']!='ground':continue
    lo,hi=tile['bounds']
    if not expected_mc.buffer(spec['groundBlendMetres']+1).intersects(box(lo[0],lo[2],hi[0],hi[2])):continue
    for v,_ in decode(prior/tile['file']):
        for t in v[:,:3].reshape(-1,3,3):
            p=Polygon(t[:,[0,2]])
            if p.area>1e-8:old.append((p,t))
existing=unary_union([p for p,t in old]);assert region.intersection(existing).area<.005
missing=expected_mc.buffer(-.01).difference(region.union(existing)).area;assert missing<.02,('mapped ground gap',missing)
# Regression controls are fixed pixels from the failed native62 views, not
# points selected from the new region. All ten previously missed the ground.
fixture=root/'minecraft/exterior/checks/lmu-east-ground-rays.json'
inputs[str(fixture.relative_to(root))]=sha(fixture)
gap_controls=read(fixture)['controls'];gap_hits=[]
e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0]
for c in gap_controls:
    eye=np.array(c['eye']);forward=np.array(c['forward'])
    right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    scale=math.tan(math.radians(c['fov'])/2)
    direction=forward+right*(2*c['u']-1)*scale*c['aspect']+up*(1-2*c['v'])*scale
    direction/=np.linalg.norm(direction)
    cross=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,cross);safe=np.where(abs(det)>1e-10,det,1)
    delta=eye-tri[:,0];u=np.einsum('ij,ij->i',delta,cross)/safe
    cross2=np.cross(delta,e1);v=cross2@direction/safe;distance=np.einsum('ij,ij->i',e2,cross2)/safe
    hits=distance[(abs(det)>1e-10)&(u>=0)&(v>=0)&(u+v<=1)&(distance>0)]
    assert len(hits) and abs(float(hits.min())-c['expectedDistance'])<c['distanceTolerance'],('native gap pixel remains uncovered',c)
    gap_hits.append({'cameraLabel':c['cameraLabel'],'u':c['u'],'v':c['v'],'distance':float(hits.min())})
vertices=np.unique(tri.reshape(-1,3),axis=0);en=utm(vertices)[:,:2]
with rasterio.open(root/'.cache/campus-dgm-east.tif') as dem:
    dgm=dem.read(1).astype(float);transform=dem.transform
    def elevation(xy):
        c,r=(~transform)*(xy[:,0],xy[:,1]);return map_coordinates(dgm,[r-.5,c-.5],order=1,prefilter=False)
    source_world=world(np.column_stack([en,elevation(en)]))
old_tree=STRtree([p for p,t in old]);errors=[];seams=[]
for q,raw_height in zip(vertices,source_world[:,1]):
    p=Point(q[0],q[2]);poly,t=old[int(old_tree.nearest(p))];near=nearest_points(poly,p)[0];distance=p.distance(poly);weights=np.linalg.solve(np.vstack([t[:,0],t[:,2],np.ones(3)]),[near.x,near.y,1]);height=float(weights@t[:,1]);w=min(1,distance/spec['groundBlendMetres']);w=w*w*(3-2*w);errors.append(abs(q[1]-(height*(1-w)+raw_height*w)))
    if distance<.001:seams.append(abs(q[1]-height))
assert max(errors)<.002 and seams and max(seams)<.002
for v,pixels in new_parts+[parts[3]]:
    e,n,_=utm(v[:,:3]).T
    with rasterio.open(root/'.cache/campus-dop-east.tif') as dop:
        c,r=(~dop.transform)*(e,n);h,w=pixels.shape[:2];left=float(np.median(c-v[:,3]*w));top=float(np.median(r-v[:,4]*h));assert abs(left-round(left))<.002 and abs(top-round(top))<.002
        expected_pixels=dop.read([1,2,3],window=rasterio.windows.Window(round(left),round(top),w,h)).transpose(1,2,0);assert np.array_equal(expected_pixels,pixels[:,:,:3]);assert np.max(abs(np.column_stack([(c-round(left))/w,(r-round(top))/h])-v[:,3:]))<1e-4
bark=np.array(Image.open(root/'.cache/tree-source/textures/jacaranda_tree_trunk_diff_1k.jpg').resize((512,512)).convert('RGBA'));leaf=Image.open(root/'.cache/tree-source/textures/jacaranda_tree_leaves_diff_1k.jpg').convert('RGBA');leaf.putalpha(Image.open(root/'.cache/tree-source/textures/jacaranda_tree_leaves_alpha_1k.png').convert('L').resize(leaf.size));leaf=np.array(leaf)
wood=[];cards=[];leaf_vertices=[]
for name in rec['treeTiles']:
    parts=decode(out/name);assert len(parts)==2;assert np.array_equal(parts[0][1],bark) and np.array_equal(parts[1][1],leaf);wood.extend(parts[0][0][:,:3]);v=parts[1][0];assert len(v)%6==0;cards.extend((v.reshape(-1,6,5)[:,0,:3]+v.reshape(-1,6,5)[:,2,:3])/2);leaf_vertices.extend(v[:,:3])
wood=np.array(wood);cards=np.array(cards);assert len(cards)>0
for tree in rec['trees']:
    assert lawn.buffer(-spec['trunkInsetMetres']).covers(Point(*tree['utm']))
    assert 3<tree['height']<26
    centre=np.array(tree['center']);raw_base=world(np.array([[*tree['utm'],elevation(np.array([tree['utm']]))[0]]]))[0]
    assert np.linalg.norm(centre-raw_base)<.002
    roots=wood[(np.linalg.norm(wood[:,[0,2]]-centre[[0,2]],axis=1)<.5)&(abs(wood[:,1]-centre[1])<.02)];assert len(roots)>=6,('missing physical tree base',tree)
# Actual leaf-card centres must stay above source terrain. Shape/species remain estimates.
card_en=utm(cards)[:,:2];floor=world(np.column_stack([card_en,elevation(card_en)]))[:,1];clearance=float((cards[:,1]-floor).min());assert clearance>1
# Canopy may overhang the low workshop roof, but must not occupy it. Check
# emitted geometry against independent survey roof planes, not fitted bounds.
roofs=[]
for surfaces_one in surfaces.values():
    for kind,rings in surfaces_one:
        if kind!='RoofSurface':continue
        raw_poly=Polygon(rings[0][:,:2],[h[:,:2] for h in rings[1:]]).buffer(0)
        if not raw_poly.intersects(expected.buffer(20)):continue
        v=world(rings[0]);poly=Polygon(v[:,[0,2]],[world(h)[:,[0,2]] for h in rings[1:]]).buffer(0)
        if poly.area<1e-8:continue
        plane=np.linalg.lstsq(np.column_stack([v[:,0],v[:,2],np.ones(len(v))]),v[:,1],rcond=None)[0]
        assert np.max(abs(np.column_stack([v[:,0],v[:,2],np.ones(len(v))])@plane-v[:,1]))<.01
        roofs.append((poly,plane))
roof_tree=STRtree([p for p,plane in roofs]);roof_clearances={}
for label,points,minimum in [('leaf centres',cards,.3),('leaf vertices',np.array(leaf_vertices),.3),('wood vertices',wood,-.02)]:
    values=[]
    for q in points:
        p=Point(q[0],q[2])
        for i in roof_tree.query(p):
            poly,plane=roofs[int(i)]
            if poly.covers(p):values.append(float(q[1]-np.array([q[0],q[2],1])@plane))
    assert not values or min(values)>minimum,('east tree intersects survey roof',label,min(values))
    roof_clearances[label]={'samples':len(values),'minimumMetres':min(values) if values else None}
for key,surfaces_one in surfaces.items():
    for kind,rings in surfaces_one:
        if kind!='GroundSurface' or key==spec['building']:continue
        p=Polygon(world(rings[0])[:,[0,2]],[world(h)[:,[0,2]] for h in rings[1:]]).buffer(0)
        if p.intersects(region):assert p.intersection(region).area<.001,('ground crossed building',key)

prior_trees=[*m['vegetation']['trees'],*[t for s in m.get('supplementalSurfaces',[]) if s['name']!='physics-lmu-east-ground' for t in s.get('vegetation',{}).get('trees',[])]]
for tree in rec['trees']:
    assert all(np.linalg.norm(np.array(tree['utm'])-p['utm'])>1 for p in prior_trees)
    # Independently sample the raw DOM at the fitted crown bounds. These are
    # survey-informed crowns, not measured botanical branch reconstructions.
    bounds=np.array(tree['crownBounds']);corners=np.array([[x,y,z] for x in bounds[:,0] for y in bounds[:,1] for z in bounds[:,2]])
    en=utm(corners)[:,:2];low=en.min(0);high=en.max(0)
    with rasterio.open(root/'.cache/32698_5349_20_DOM.tif') as dom:
        window=from_bounds(*low,*high,dom.transform).round_offsets().round_lengths()
        heights=dom.read(1,window=window);valid=heights[(heights>400)&(heights<550)]
        assert len(valid)>0
        source_top=float(np.percentile(valid,98)-elevation(np.array([tree['utm']]))[0])
        assert abs(source_top-tree['height'])<2,('DOM crown height mismatch',source_top,tree['height'])
files=rec['groundTiles']+rec['treeTiles']+[rec['meshFile'],rec['roofFile'],rec['coverageFile']]
report={'status':'PASS: source envelope, disjoint facade finishes, DOP pixels, mapped ground joins and fitted tree geometry',
 'manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'validatorSha256':sha(Path(__file__)),
 'rawInputs':inputs,'tileSha256':{f:sha(out/f) for f in files},'walls':wall_checks,'roofVertexErrorMetres':roof_error,
 'newGroundAreaSquareMetres':region.area,'uncoveredMappedAreaSquareMetres':missing,'groundVertices':len(vertices),
 'nativeGapPixelControls':gap_hits,
 'groundHeightErrorMetres':max(errors),'seamHeightErrorMetres':max(seams),'trees':len(rec['trees']),'leafCards':len(cards),
 'minimumLeafCentreTerrainClearanceMetres':clearance,'roofClearance':roof_clearances,
 'qualification':spec['qualification']}
(out/'lmu-east-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['rawInputs','tileSha256']},indent=2))

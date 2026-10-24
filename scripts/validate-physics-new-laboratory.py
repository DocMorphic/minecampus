#!/usr/bin/env python3
"""Check laboratory survey preservation, recessed panes, fins and terrain overlap."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct

import numpy as np
import rasterio
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from shapely import polygons, union_all
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=root/'dist-minecraft/exterior')
folder = parser.parse_args().directory
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((folder/'manifest.json').read_text())
record = manifest['architecture']['physicsNewLaboratory']
source = root/'minecraft/exterior'/record['sourceFile']
spec = json.loads(source.read_text())
assert sha(source) == record['sourceSha256']
assert sha(root/record['generatorFile']) == record['generatorSha256']
assert sha(root/'minecraft/exterior'/spec['reference']) == spec['referenceSha256']
plans = json.loads((folder/'photo-facades.json').read_text())['plans']
plan = next(p for p in plans if p['id'] == spec['building'])


def decode(path):
    data = path.read_bytes()
    count, *anchor = struct.unpack_from('<i3d', data, 4)
    offset, parts = 32, []
    for _ in range(count):
        n, w, h = struct.unpack_from('<3i', data, offset)
        offset += 16
        v = np.frombuffer(data, dtype='<f4', count=n*5, offset=offset).reshape(-1,5).astype(float)
        v[:, :3] += anchor
        offset += n*20
        texture = data[offset:offset+w*h*4]
        offset += w*h*4
        assert np.isfinite(v).all()
        parts.append((v, texture))
    assert offset == len(data)
    return parts


def ray_hits(triangles, origin, direction):
    a, b, c = triangles[:,0], triangles[:,1], triangles[:,2]
    e1, e2 = b-a, c-a
    h = np.cross(np.broadcast_to(direction,e2.shape),e2)
    det = np.einsum('ij,ij->i',e1,h)
    valid = np.abs(det)>1e-8
    inv = np.divide(1,det,out=np.zeros_like(det),where=valid)
    s = origin-a
    u = inv*np.einsum('ij,ij->i',s,h)
    q = np.cross(s,e1)
    v = inv*(q@direction)
    distance = inv*np.einsum('ij,ij->i',e2,q)
    mask = valid & (u>=-1e-7) & (v>=-1e-7) & (u+v<=1+1e-7) & (distance>=0)
    return distance[mask], (np.cross(e1,e2)@(-direction))[mask]


parts = decode(folder/record['meshFile'])
roof = decode(folder/record['roofFile'])
assert len(parts) == 6 and len(roof) == 1
assert np.array_equal(parts[4][0],roof[0][0]) and parts[4][1] == roof[0][1]
roof_error = float(np.max(np.abs(parts[4][0][:,:3]-np.array(plan['roofTriangles']).reshape(-1,3))))
assert roof_error < .0001 and len(parts[4][0]) == 32*3
assert len(plan['walls']) == 20 and all(w['reconstructed'] for w in plan['walls'])
assert sorted(spec['outerFaces']+spec['courtyardFaces']+spec['roofPlantFaces']) == list(range(20))
assert len(parts[5][0]) > 0 and len(record['fins']) > 500
for control in record['openingControls']:
    target, normal = np.array(control['position']), np.array(control['normal'])
    distances, winding = ray_hits(parts[1][0][:,:3].reshape(-1,3,3),target+normal*.6,-normal)
    assert np.any((np.abs(distances-.6)<.0001) & (winding>0)), control
    for part in [0,5]:
        distances, _ = ray_hits(parts[part][0][:,:3].reshape(-1,3,3),target+normal*1.6,-normal)
        assert not np.any(distances<1.5999), ('cladding covers pane',control)
assert record['jointControls'], 'Missing physical panel joints'
for control in record['jointControls']:
    target, normal = np.array(control['position']), np.array(control['normal'])
    distances, winding = ray_hits(parts[3][0][:,:3].reshape(-1,3,3),target+normal*.6,-normal)
    assert np.any((np.abs(distances-.6)<.0001) & (winding>0)), ('missing joint backing',control)
    for part in [0,5]:
        distances, _ = ray_hits(parts[part][0][:,:3].reshape(-1,3,3),target+normal*.6,-normal)
        assert not np.any(distances<.5999), ('metal overlaps joint',control)
# A narrow strip behind a gap disappears at grazing angles. Check the
# opaque backing through each outer wall's mid-panel vertical joint, both ways.
joint_grazing_checks = 0
for face in spec['outerFaces']:
    wall = record['surveyWalls'][face]
    anchor, tangent, normal = [np.array(wall[k]) for k in ['anchor','direction','normal']]
    width = wall['bounds'][1][0]
    phase = float(anchor@tangent)
    x = math.ceil((width/2+phase)/spec['panelWidthMetres'])*spec['panelWidthMetres']-phase
    if x < .5 or x > width-.5:
        continue
    target = anchor+tangent*x
    target[1] = record['mainRoofMC']-2
    for sign in [-1,1]:
        direction = -normal*.2+tangent*.98*sign
        direction /= np.linalg.norm(direction)
        hits = [(i,float(d)) for i,(v,_) in enumerate(parts) for d in ray_hits(v[:,:3].reshape(-1,3,3),target-direction*.6,direction)[0] if .59<d<1]
        assert hits and min(hits,key=lambda h:h[1])[0] == 3, ('open grazing joint',face,sign)
        joint_grazing_checks += 1
assert joint_grazing_checks == 16
for fin in record['fins']:
    target, normal = np.array(fin['centre']), np.array(fin['normal'])
    distances, winding = ray_hits(parts[2][0][:,:3].reshape(-1,3,3),target+normal*.6,-normal)
    assert np.any((np.abs(distances-.6)<.0001) & (winding>0)), fin
    distances, winding = ray_hits(parts[2][0][:,:3].reshape(-1,3,3),target-normal*(fin['depth']+.6),normal)
    assert np.any((np.abs(distances-.6)<.0001) & (winding>0)), fin
cleanup = unary_union([Polygon(p['ring'],p['holes']) for p in record['retirement']])
for other in plans:
    if other['id'] == spec['building']:
        continue
    footprints = [Polygon(np.asarray(t)[:,[0,2]]) for t in other.get('roofTriangles',[])]
    if footprints:
        assert cleanup.intersection(unary_union(footprints)).area < .001, other['id']

# Reconstruct projected source coordinates from the emitted tangent-space points.
lat,lon = map(math.radians, manifest['origin'][:2])
origin = np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(manifest['origin'][1],manifest['origin'][0],manifest['origin'][2]))
basis = np.array([[-math.sin(lon),math.cos(lon),0],[math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)],[math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
to_grid = Transformer.from_crs(4978,25832,always_xy=True)
to_geo = Transformer.from_crs(4978,4258,always_xy=True)
ground = decode(folder/record['groundTiles'][0])[0][0]
ecef = (ground[:,:3]-[0,64,0])@basis+origin
e,n,h = to_grid.transform(*ecef.T)
longitude,latitude,_ = to_geo.transform(*ecef.T)
with rasterio.open(root/'.cache/campus-dgm-east.tif') as dem, rasterio.open(root/'.cache/de_bkg_gcg2016.tif') as geoid:
    x,y = (~dem.transform)*(e,n)
    surface = map_coordinates(dem.read(1).astype(float),[y-.5,x-.5],order=1,prefilter=False)
    x,y = (~geoid.transform)*(longitude,latitude)
    separation = map_coordinates(geoid.read(1).astype(float),[y-.5,x-.5],order=1,prefilter=False)
    ground_error = float(np.max(np.abs(h-surface-separation)))
    assert ground_error < .001, ground_error
area = union_all(polygons(ground[:,:3].reshape(-1,3,3)[:,:,[0,2]]))
overlap = 0
for tile in manifest['tiles']:
    if tile['kind'] != 'ground' or tile['file'] in record['groundTiles']:
        continue
    lo,hi = tile['bounds']
    if not area.intersects(box(lo[0],lo[2],hi[0],hi[2])):
        continue
    for vertices,_ in decode(folder/tile['file']):
        overlap += area.intersection(union_all(polygons(vertices[:,:3].reshape(-1,3,3)[:,:,[0,2]]))).area
assert overlap < .005, overlap
result = {
    'status':'PASS: survey roof/pixels, outward recessed glazing, physical fins, bounded retirement, DGM1 ground and old-ground separation',
    'manifestSha256':sha(folder/'manifest.json'),
    'sourceSha256':sha(source),
    'validatorSha256':sha(Path(__file__)),
    'roofMaximumCoordinateErrorMetres':roof_error,
    'groundMaximumHeightErrorMetres':ground_error,
    'oldGroundOverlapSquareMetres':overlap,
    'paneControls':len(record['openingControls']),
    'physicalFins':len(record['fins']),
    'tileSha256':{name:sha(folder/name) for name in [record['meshFile'],record['roofFile'],*record['groundTiles']]},
    'qualification':'Geometric representation checks, not finished-grade, architectural accuracy or native visual acceptance. Fin/panel dimensions and hidden details remain estimated.'
}
(folder/'physics-new-laboratory-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

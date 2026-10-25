#!/usr/bin/env python3
"""Check the restored courtyard against raw DGM1 and actual rendered coverage."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct
import numpy as np
import rasterio
from scipy.ndimage import map_coordinates
from pyproj import Transformer
from shapely.geometry import shape, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from validate_ground_restoration import restoration_weights

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=root/'dist-minecraft/exterior')
parser.add_argument('--before', type=Path)
args = parser.parse_args()
out = args.directory
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
meta = read(out/'manifest.json')
policy = read(out/meta['groundRestoration']['sourceFile'])
area = shape(policy['geometry'])
core = area.buffer(-policy['fadeMetres'])
def in_core(q):
    point = Point(q)
    return area.covers(point) and point.distance(area.boundary) >= policy['fadeMetres']
coverage = unary_union([shape(read(out/item['file'])['ground']) for item in policy['sourceCoverage']])
uncovered = area.difference(coverage.buffer(policy['coverageToleranceMetres'])).area
assert uncovered < .01, ('Restoration extends outside rebuilt ground', uncovered)
sources = read(root/'minecraft/exterior/sources.json')
dem_path = root/'.cache/campus-dgm-east.tif'
geoid_path = root/'.cache/de_bkg_gcg2016.tif'
assert sha(dem_path) == sorted(sources['dgm1'], key=lambda v: v['name'])[1]['sha256']
assert sha(geoid_path) == sources['geoid']['sha256']
lat, lon = map(math.radians, meta['origin'][:2])
origin = np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(meta['origin'][1],meta['origin'][0],meta['origin'][2]))
basis = np.array([[-math.sin(lon),math.cos(lon),0], [math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)], [math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
geographic = Transformer.from_crs(25832,4258,always_xy=True)
ecef = Transformer.from_crs(25832,4978,always_xy=True)

def sample(ds, xy):
    x, y = (~ds.transform)*xy.T
    return map_coordinates(ds.read(1).astype(float), [y-.5,x-.5], order=1, prefilter=False)

with rasterio.open(dem_path) as dem, rasterio.open(geoid_path) as geoid:
    def raw_world(xy):
        lng, lat = geographic.transform(*xy.T)
        h = sample(dem, xy)+sample(geoid, np.column_stack([lng,lat]))
        xyz = np.column_stack(ecef.transform(xy[:,0],xy[:,1],h))
        return (xyz-origin)@basis.T+[0,64,0]

    def terrain(folder):
        manifest = read(folder/'manifest.json')
        triangles, xy_triangles, vertices_checked, maximum_error = [], [], 0, 0
        unchanged = 0
        for tile in manifest['tiles']:
            if tile['kind'] != 'ground' or not tile['file'].startswith(('physics-ii-ground-','physics-wsi-ground-','physics-znn-ground-','riverbank-ground-')):
                continue
            data = (folder/tile['file']).read_bytes()
            count, *anchor = struct.unpack_from('<i3d',data,4)
            offset = 32
            e,n = map(int,Path(tile['file']).stem.split('-')[-2:])
            # These four generators use the same fixed 20m terrain tile size.
            step = 20
            for _ in range(count):
                size,w,h = struct.unpack_from('<3i',data,offset); offset += 16
                v = np.frombuffer(data,dtype='<f4',count=size*5,offset=offset).reshape(-1,5).astype(float)
                v[:,:3] += anchor; offset += size*20+w*h*4
                xy = np.column_stack([e+v[:,3]*step,n+step-v[:,4]*step])
                inside = np.array([in_core(q) for q in xy])
                if folder == out and inside.any():
                    error = np.max(np.abs(v[inside,:3]-raw_world(xy[inside])))
                    maximum_error = max(maximum_error,float(error)); vertices_checked += int(inside.sum())
                for a,b in zip(v[:,:3].reshape(-1,3,3),xy.reshape(-1,3,2)):
                    poly = Polygon(b)
                    if poly.area > 1e-10 and poly.intersects(area):
                        triangles.append(a); xy_triangles.append(poly)
            assert offset == len(data)
            if folder == out and args.before and not any(Point(q).within(area) for q in [[e,n],[e+20,n],[e,n+20],[e+20,n+20]]):
                from shapely.geometry import box
                if not box(e,n,e+step,n+step).intersects(area):
                    assert data == (args.before/tile['file']).read_bytes(), ('Unrelated terrain changed',tile['file'])
                    unchanged += 1
        return triangles,xy_triangles,vertices_checked,maximum_error,unchanged

    current,polys,count,error,unchanged = terrain(out)
    assert count > 100 and error < .001, (count,error)
    x0,y0,x1,y1 = core.bounds
    xy = np.array([(e,n) for n in np.arange(math.ceil(y0),y1,.5) for e in np.arange(math.ceil(x0),x1,.5) if in_core((e,n))])
    expected = raw_world(xy)
    assert np.all(restoration_weights(root,out,meta,xy) < 1e-10)
    # The strict vertex check above verifies the data; interior interpolation
    # residuals quantify the difference between bilinear DGM and planar faces.
    def residuals(tris, polygons):
        index = STRtree(polygons); result = []
        for utm,q in zip(xy,expected):
            point = Point(utm); hits = []
            for i in index.query(point):
                if not polygons[i].buffer(1e-7).covers(point): continue
                t = tris[i]
                coeff = np.linalg.solve(np.column_stack([t[:,0],t[:,2],np.ones(3)]),t[:,1])
                hits.append(float(q[[0,2]]@coeff[:2]+coeff[2]-q[1]))
            if hits: result.append(max(hits))
        return np.asarray(result)
    residual = residuals(current,polys)
    assert len(residual) >= len(xy)*.99, ('Missing interior ground',len(residual),len(xy))
    result = {'status':'PASS: survey-derived core vertices and continuous coverage; native appearance unverified', 'manifestSha256':sha(out/'manifest.json'), 'validatorSha256':sha(Path(__file__)), 'independentPolicyValidatorSha256':sha(root/'scripts/validate_ground_restoration.py'), 'policySha256':sha(out/meta['groundRestoration']['sourceFile']), 'coreVertices':count, 'maximumRawSurveyVertexErrorMetres':error, 'interiorSamples':len(residual), 'interpolatedResidualRangeMetres':[float(residual.min()),float(residual.max())], 'uncoveredRestorationAreaSquareMetres':uncovered, 'unchangedOutsideGroundTiles':unchanged}
    if args.before:
        old,old_polys,*_ = terrain(args.before)
        baseline = residuals(old,old_polys)
        result['beforeResidualRangeMetres'] = [float(baseline.min()),float(baseline.max())]
        assert residual.min() > baseline.min()+.5, 'The observed artificial depression must actually improve'
    (out/'courtyard-ground-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

"""Pin public river polygons for water generation when live OSM is unavailable."""
import hashlib
import json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from exterior_physics_ii_landscape import osm_ways


def build(ctx):
    root, meta, mc = [ctx[k] for k in ['ROOT','metadata','mc']]
    source = root/'minecraft/exterior/physics-wsi.json'
    spec = json.loads(source.read_text())['northLandscapeBoundary']
    ways = osm_ways(root,spec)
    xy,tags = ways[spec['riverWay']]
    assert tags.get('natural') == 'water' and tags.get('water') == 'river'
    assert xy[0] == xy[-1] and Polygon(xy).is_valid
    # Matching the upstream waterFor projection, the feature carries horizontal
    # boundaries only. It does not invent a surveyed water height or river bed.
    q = np.asarray(xy)
    points = mc(np.column_stack([q,np.full(len(q),475.0)]))[:,[0,2]]
    segments = np.column_stack([points[:-1],points[1:]]).reshape(-1).tolist()
    meta['pinnedWater'] = {
        'origin':meta['origin'][:2],
        'sourceFile':'physics-wsi.json',
        'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'osm':spec['osm'],
        'generatorFile':'scripts/exterior_pinned_water.py',
        'generatorSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'features':[{'id':'way/'+spec['riverWay'],'segs':segments,'minx':float(points[:,0].min()),'maxx':float(points[:,0].max()),'minz':float(points[:,1].min()),'maxz':float(points[:,1].max())}],
        'qualification':'Pinned OSM river polygon, ODbL. Supplements the upstream water lookup when enabled; does not classify the river as reconstructed land. Existing upstream water-level and river-bed estimation remain unverified until native inspection.'
    }
    print('Pinned water: one public river polygon;',len(points)-1,'boundary segments',flush=True)

"""Infer surface strips from explicitly tagged OSM widths; preserve mapped areas.

Centre-lines/widths do not survey curbs. Buildings and existing surface polygons
take precedence over these inferred strips, including lawns and water/courts.
"""
import hashlib
import json
import math
import numpy as np
from shapely.geometry import Polygon, shape, mapping, box
from shapely.ops import transform, unary_union
from pyproj import Transformer


def derive(ctx, mapped):
    root, out, meta, buildings = [ctx[k] for k in ['ROOT', 'OUT', 'metadata', 'buildings']]
    source = root / 'minecraft/exterior/path-widths.json'
    data = json.loads(source.read_text())
    to_utm = Transformer.from_crs(4326, 25832, always_xy=True).transform
    to_geo = Transformer.from_crs(25832, 4326, always_xy=True).transform
    limit = box(*meta['boundsUtm'])
    footprints = [Polygon(np.asarray(rings[0])[:, :2], [np.asarray(h)[:, :2] for h in rings[1:]]).buffer(0)
                  for _, surfaces in buildings for kind, rings in surfaces if kind == 'GroundSurface']
    mapped_areas = [transform(to_utm, shape(f['geometry'])).buffer(0) for f in mapped['features']]
    exclude = unary_union(footprints + mapped_areas)
    features, raw = [], []
    for way in data['ways']:
        tags, width = way['tags'], way['widthMetres']
        assert math.isfinite(width) and .25 <= width <= 20 and float(tags['width']) == width
        assert tags['surface'] in ['asphalt', 'paving_stones']
        assert tags.get('indoor') != 'yes' and not tags.get('tunnel') and not tags.get('bridge')
        assert tags.get('level', '0') == '0' and tags.get('layer', '0') == '0'
        line = transform(to_utm, shape(way['geometry']))
        assert line.geom_type == 'LineString'
        strip = line.buffer(width / 2, cap_style=2, join_style=2).intersection(limit)
        raw.append(strip)
        clipped = strip.difference(exclude)
        if clipped.is_empty:
            continue
        features.append({'type': 'Feature', 'properties': {
            'osmWay': way['osmWay'], 'version': way['version'], 'timestamp': way['timestamp'],
            'material': 'asphalt' if tags['surface'] == 'asphalt' else 'paving',
            'tags': tags, 'derivedFromWidth': True, 'widthMetres': width,
        }, 'geometry': mapping(transform(to_geo, clipped))})
    result = {'type': 'FeatureCollection', 'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
              'derivation': data['derivation'], 'features': features}
    target = out / 'path-surfaces.geojson'
    target.write_text(json.dumps(result, separators=(',', ':')))
    covered = unary_union([transform(to_utm, shape(f['geometry'])) for f in features])
    assert covered.intersection(exclude).area < .001
    stats = {'sourceFile': 'path-widths.json', 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'derivedFile': target.name, 'derivedSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
             'ways': len(features), 'rawAreaSquareMetres': round(unary_union(raw).area, 2),
             'includedAreaSquareMetres': round(covered.area, 2),
             'exclusions': 'BVV building ground footprints and all existing mapped surface polygons',
             'boundaryQualification': 'Half-width buffers of mapped lines, not surveyed curbs or inferred sidewalks.'}
    return features, stats

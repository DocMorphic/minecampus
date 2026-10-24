"""Orthophoto-sized asphalt corridors on mapped promenade paths.

Widths and centre offsets are estimates, separate from the original OSM tags.
Existing materials take precedence; facades receive a documented texture margin.
"""
import hashlib
import json
import math
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box, mapping, shape
from shapely.ops import transform, unary_union, substring


def build(ctx, existing, source_name="promenade-paths.json", derived_name="promenade-surfaces.geojson"):
    root, out, meta = [ctx[k] for k in ['ROOT', 'OUT', 'metadata']]
    source = root / 'minecraft/exterior' / source_name
    spec = json.loads(source.read_text())
    assert hashlib.sha256((out / 'campus-orthophoto.jpg').read_bytes()).hexdigest() == spec['orthophotoSha256']
    to_utm = Transformer.from_crs(4326, 25832, always_xy=True).transform
    to_geo = Transformer.from_crs(25832, 4326, always_xy=True).transform
    occupied = unary_union([transform(to_utm, shape(f['geometry'])).buffer(0) for f in existing])
    footprints = unary_union([
        Polygon(np.asarray(rings[0])[:, :2], [np.asarray(h)[:, :2] for h in rings[1:]]).buffer(0)
        for _, surfaces in ctx['buildings'] for kind, rings in surfaces if kind == 'GroundSurface'
    ])
    # The terrain texture is sampled across texel boundaries. A narrow margin
    # under the facade prevents unassigned photographic pixels bleeding out.
    # This changes no geometry or collision and is not an interior surface.
    padding = spec['texturePaddingInsideFootprintsMetres']
    assert 0 <= padding <= .25
    excluded = occupied.union(footprints.buffer(-padding))
    limit = box(*meta['boundsUtm'])
    features, areas = [], {}
    for way in spec['ways']:
        assert way['tags']['surface'] == 'asphalt' and 'width' not in way['tags']
        assert way['tags']['highway'] in ['footway', 'path']
        assert not way['tags'].get('bridge') and not way['tags'].get('tunnel')
        coords = [to_utm(*p) for p in way['coordinates']]
        corridors = []
        for segment in way['segments']:
            width, offset = segment['widthMetres'], segment['leftOffsetMetres']
            assert math.isfinite(width) and 1 <= width <= 12 and math.isfinite(offset) and abs(offset) <= 6
            if 'fromDistanceMetres' in segment:
                start, end = segment['fromDistanceMetres'], segment['toDistanceMetres']
                full = LineString(coords)
                assert math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= full.length + .01
                # Overlap station joins by 1 mm to avoid a zero-area seam after
                # geographic round-tripping of adjacent, differently offset strips.
                line = substring(full, max(0, start - .001), min(end + .001, full.length))
            else:
                start, end = segment['fromVertex'], segment['toVertex']
                assert 0 <= start < end < len(coords)
                line = LineString(coords[start:end + 1])
            line = line.offset_curve(offset, join_style=2)
            corridors.append(line.buffer(width / 2, cap_style=2, join_style=2))
        surface = unary_union(corridors).intersection(limit).difference(excluded)
        assert not surface.is_empty and surface.intersection(excluded).area < 1e-6
        features.append({'type': 'Feature', 'properties': {
            'osmWay': way['osmWay'], 'version': way['version'], 'timestamp': way['timestamp'],
            'tags': way['tags'], 'material': 'asphalt', 'widthInferredFromOrthophoto': True,
            'segments': way['segments'], 'qualification': way['widthEvidence'],
        }, 'geometry': mapping(transform(to_geo, surface))})
        areas[str(way['osmWay'])] = round(surface.area, 2)
        excluded = excluded.union(surface)
    target = out / derived_name
    target.write_text(json.dumps({'type': 'FeatureCollection', 'features': features,
        'attribution': '© OpenStreetMap contributors; © Bayerische Vermessungsverwaltung',
        'license': 'OSM-derived path geometry: ODbL-1.0; orthophoto-derived width estimates: CC-BY-4.0',
        'qualification': spec['derivation']}, separators=(',', ':')))
    stats = {'sourceFile': source.name, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'derivedFile': target.name, 'derivedSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'areasSquareMetres': areas, 'orthophotoSha256': spec['orthophotoSha256'],
        'texturePaddingInsideFootprintsMetres': padding, 'note': spec['derivation']}
    print(source_name, 'asphalt:', sum(areas.values()), 'm²; previous materials preserved, facade texture margin', padding, 'm', flush=True)
    return features, stats

"""Source-informed Galileo panels, clipped to the BVV wall polygons.

Module positions are estimates, not a surveyed window schedule. No contractor
photographs are baked into the materials. Roof meshes are built by the caller.
"""
import math
import numpy as np
import mapbox_earcut
from shapely.geometry import Polygon, Point, box


def shapes(value):
    if value.geom_type == 'Polygon':
        if value.area > 1e-8:
            yield value
    else:
        for part in getattr(value, 'geoms', []):
            yield from shapes(part)


def wall(q, footprint, levels, parts, records):
    """Append pale sheet metal, recessed glass and dark frames/louvres."""
    delta = max((v - q[0] for v in q), key=lambda v: np.linalg.norm(v[[0, 2]]))
    direction = np.array([delta[0], 0., delta[2]])
    length = np.linalg.norm(direction)
    if length < .01:
        return
    direction /= length
    # A canonical direction and world-projected station keep coplanar pieces
    # on the same grid, independently of ring start vertex or winding.
    if direction[np.argmax(np.abs(direction))] < 0:
        direction = -direction
    anchor = q[0] - direction * np.dot(q[0], direction)
    station = q @ direction
    poly = Polygon(np.column_stack((station, q[:, 1])))
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        return
    normal = np.array([-direction[2], 0., direction[0]])
    middle = q.mean(axis=0)
    if footprint.contains(Point((middle + normal * .3)[[0, 2]])):
        normal = -normal
    left, bottom, right, top = poly.bounds

    def position(x, y, depth):
        p = anchor + direction * x - normal * depth
        p[1] = y
        return [*p, 0., 0.]

    def face(shape, part, depth):
        for p in shapes(shape):
            rings = [np.asarray(r.coords[:-1]) for r in [p.exterior, *p.interiors]]
            xy = np.concatenate(rings)
            indices = mapbox_earcut.triangulate_float64(xy, np.cumsum([len(r) for r in rings]).astype('uint32'))
            parts[part].extend(position(*xy[i], depth) for i in indices)

    def reveal(shape, front, back):
        for p in shapes(shape):
            for ring in [p.exterior, *p.interiors]:
                xy = list(ring.coords)
                for a, b in zip(xy, xy[1:]):
                    v = [position(*a, front), position(*b, front), position(*b, back), position(*a, back)]
                    parts[2].extend(v[i] for i in [0, 1, 2, 0, 2, 3])

    # Dark joint backing closes every centimetre of the original survey wall.
    # Panels and glazing in front create depth without opening an interior.
    face(poly, 2, .145)
    rows = [*levels, max(top, levels[-1]) + 1.]
    if bottom < rows[0]:
        rows.insert(0, bottom)
    module = 1.4
    pattern = 'MGGMGMGGMGGMMGMGG'
    metal_area = glass_area = vent_area = covered = 0.
    cells = 0
    for y0, y1 in zip(rows, rows[1:]):
        if y1 <= bottom or y0 >= top:
            continue
        row = max(0, int(np.searchsorted(levels, y0 + .001, side='right')) - 1)
        for column in range(math.floor(left / module), math.ceil(right / module)):
            x0, x1 = column * module, (column + 1) * module
            cell = poly.intersection(box(x0, y0, x1, y1))
            if cell.is_empty or cell.area < 1e-8:
                continue
            covered += cell.area
            cells += 1
            inner = cell.intersection(box(x0 + .016, y0 + .022, x1 - .016, y1 - .022))
            parapet = top - bottom < 3.0 or y0 >= levels[-1] - .01
            ground = False  # Continuous ground-floor glazing is not established by the north photo.
            opaque = parapet or (not ground and pattern[(column + row * 5) % len(pattern)] == 'M')
            if opaque:
                face(inner, 0, 0.)
                reveal(inner, 0., .145)
                metal_area += inner.area
                continue
            # Windows have the slim dark ventilation panel visible in
            # the contractor's close-up; its exact width is an inference.
            vent_width = 0. if ground else .18
            window = inner.intersection(box(x0 + .025, y0 + .035, x1 - .025 - vent_width, y1 - .035))
            vent = inner.intersection(box(x1 - vent_width, y0 + .035, x1 - .025, y1 - .035)) if vent_width else Polygon()
            frame = inner.difference(window.union(vent))
            face(frame, 2, .015)
            face(window, 1, .105)
            reveal(window, .015, .105)
            glass_area += window.area
            if not vent.is_empty:
                face(vent, 2, .085)
                # Real relief, not aliased lines in a photograph. Slim fins
                # tilt from their recessed lower edge to their upper lip.
                for y in np.arange(y0 + .09, y1 - .045, .09):
                    strip = vent.intersection(box(x1 - vent_width, y, x1, y + .028))
                    for p in shapes(strip):
                        xy = np.asarray(p.exterior.coords[:-1])
                        ids = mapbox_earcut.triangulate_float64(xy, np.array([len(xy)], dtype='uint32'))
                        parts[2].extend(position(xy[i, 0], xy[i, 1], .072 - (xy[i, 1] - y) / .028 * .045) for i in ids)
                vent_area += vent.area
    if abs(covered - poly.area) > 1e-5:
        raise ValueError('Galileo panel partition missed surveyed wall area')
    records.append({'points': q.tolist(), 'areaSquareMetres': poly.area,
                    'partitionAreaSquareMetres': covered, 'panelCells': cells,
                    'metalAreaSquareMetres': metal_area, 'glassAreaSquareMetres': glass_area,
                    'ventAreaSquareMetres': vent_area})

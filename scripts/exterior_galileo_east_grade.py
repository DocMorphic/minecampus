"""Bounded inferred finished grade beside Galileo's eastern access ramps."""
import hashlib
import json
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from exterior_terrain import BoundedGradeElevation


def configure(ctx):
    root = ctx['ROOT']
    source = root / 'minecraft/exterior/galileo-east-grade.json'
    spec = json.loads(source.read_text())
    reference = root / 'minecraft/exterior' / spec['reference']
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest(reference) == spec['referenceSha256']
    # Keep material boundaries in their established horizontal frame. Fitting
    # them again to the edited height guide moves unrelated atlas edge texels.
    bounds = ctx['metadata']['boundsUtm']
    xy = np.array([(e, n) for n in range(bounds[1], bounds[3] + 1, 2)
                   for e in range(bounds[0], bounds[2] + 1, 2)])
    middle = np.array([(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2])
    horizontal = ctx['mc'](np.column_stack((xy, ctx['elevation'].sample(xy))))[:, [0, 2]]
    design = np.column_stack((xy - middle, np.ones(len(xy))))
    fit = np.linalg.lstsq(design, horizontal, rcond=None)[0]
    residual = float(np.max(np.abs(design @ fit - horizontal)))
    assert residual < .03
    ctx['metadata']['groundMaterialFrame'] = {
        'originUtm': middle.tolist(), 'fit': fit.tolist(),
        'maximumResidualMetres': residual,
        'basis': 'Terrain coordinate frame before Galileo east frontage grading',
    }
    neighbours = unary_union([
        Polygon(rings[0][:, :2], [hole[:, :2] for hole in rings[1:]]).buffer(0)
        for bid, surfaces in ctx['buildings'] if bid not in spec['ownBuildings']
        for kind, rings in surfaces if kind == 'GroundSurface'
    ]).buffer(spec['neighbourExclusionMetres'])
    elevation = BoundedGradeElevation(ctx['elevation'], spec['patches'], neighbours)
    ctx['metadata']['galileoEastGrading'] = {
        'sourceFile': source.name, 'sourceSha256': digest(source),
        'generatorFile': 'scripts/exterior_galileo_east_grade.py',
        'generatorSha256': digest(root / 'scripts/exterior_galileo_east_grade.py'),
        'rampGeneratorFile': 'scripts/exterior_galileo_ramps.py',
        'rampGeneratorSha256': digest(root / 'scripts/exterior_galileo_ramps.py'),
        'referenceFile': spec['reference'], 'referenceSha256': digest(reference),
        'patches': spec['patches'], 'ownBuildings': spec['ownBuildings'],
        'neighbourExclusionMetres': spec['neighbourExclusionMetres'],
        'qualification': spec['qualification'],
    }
    return elevation

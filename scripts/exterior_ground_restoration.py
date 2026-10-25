"""Retire old mesh joins only inside a declared, rebuilt survey-ground region."""
import hashlib
import json
import shutil
import numpy as np
from shapely import points, covers, distance
from shapely.geometry import shape

POLICY = 'courtyard-ground-restoration.json'


def restored_transition(root, correction):
    record = json.loads((root/'minecraft/exterior'/POLICY).read_text())
    area = shape(record['geometry'])
    fade = record['fadeMetres']
    assert area.is_valid and not area.is_empty and fade > 0

    def calculate(xy):
        pts = points(np.asarray(xy))
        inward = np.where(covers(area, pts), distance(pts, area.boundary), 0)
        amount = np.clip(inward/fade, 0, 1)
        weight = 1-amount*amount*(3-2*amount)
        return correction(xy)*weight
    return calculate


def record_policy(root, out, metadata):
    source = root/'minecraft/exterior'/POLICY
    shutil.copy2(source, out/POLICY)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    metadata['groundRestoration'] = {
        'sourceFile': POLICY, 'sourceSha256': sha(source),
        'generatorFile': 'scripts/exterior_ground_restoration.py',
        'generatorSha256': sha(root/'scripts/exterior_ground_restoration.py'),
    }

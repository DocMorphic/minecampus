"""Independent scalar evaluation and provenance checks for ground-join retirement."""
import hashlib
import json
import numpy as np
from shapely.geometry import shape, Point


def restoration_weights(root, out, metadata, xy):
    rec = metadata['groundRestoration']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = root/'minecraft/exterior'/rec['sourceFile']
    assert sha(source) == rec['sourceSha256'] == sha(out/source.name)
    assert sha(root/rec['generatorFile']) == rec['generatorSha256']
    policy = json.loads(source.read_text())
    area = shape(policy['geometry'])
    result = []
    for q in xy:
        point = Point(q)
        t = min(1, point.distance(area.boundary)/policy['fadeMetres']) if area.covers(point) else 0
        result.append(1-3*t*t+2*t*t*t)
    return np.asarray(result)

"""A real stepped survey wall must retain its recessed window openings."""
import json
from pathlib import Path
import unittest

from shapely.geometry import shape, Polygon
from shapely.ops import unary_union

from exterior_physics_library import triangles
from exterior_physics_lmu import surface_triangles


class LMUFacadeTriangulationTest(unittest.TestCase):
    def test_near_coincident_corner_does_not_fill_windows(self):
        source=Path(__file__).parent/'fixtures/lmu-facade-triangulation.json'
        wall=shape(json.loads(source.read_text())['geometry'])
        old=unary_union([Polygon(t) for t in triangles(wall)])
        self.assertGreater(old.difference(wall).area,29)
        actual=unary_union([Polygon(t) for t in surface_triangles(wall)])
        self.assertLess(actual.symmetric_difference(wall).area,1e-5)
        self.assertLess(actual.difference(wall.buffer(1e-6)).area,1e-9)
        self.assertLess(wall.difference(actual.buffer(1e-6)).area,1e-9)


if __name__=='__main__':unittest.main()

"""Regression: a narrow join must retain a prior terrain height breakpoint."""
import unittest
import numpy as np
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from shapely.ops import unary_union
from exterior_physics_library import triangles
from exterior_ground_extension import split_narrow_joins

class NarrowJoinTest(unittest.TestCase):
    def test_height_kink_is_carried_across_two_millimetre_gap(self):
        kink=.652
        patch=Polygon([(0,0),(.002,0),(.002,1),(0,1),(0,kink)])
        prior=[]
        for points in [[(-1,0),(0,0),(0,kink)],[(-1,1),(0,kink),(0,1)]]:
            q=np.array([[x,0,z]for x,z in points]);prior.append((Polygon(points),q))
        def maximum_slope(shapes):
            maximum=0
            for p in shapes:
                for xy in triangles(p):
                    height=np.where(xy[:,1]<kink,xy[:,1]*.5,kink*.5+(xy[:,1]-kink)*.9)
                    plane=np.linalg.solve(np.column_stack([xy,np.ones(3)]),height)
                    maximum=max(maximum,float(np.hypot(*plane[:2])))
            return maximum
        self.assertGreater(maximum_slope([patch]),10)
        pieces=split_narrow_joins(patch,prior,STRtree([p for p,t in prior]))
        self.assertLess(unary_union(pieces).symmetric_difference(patch).area,1e-12)
        self.assertLessEqual(maximum_slope(pieces),.900001)

if __name__=='__main__':unittest.main()

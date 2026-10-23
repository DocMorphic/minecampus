"""Survey sampling regressions: raster centres, neighbouring tiles and nodata."""
import unittest
import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from exterior_terrain import ElevationSampler,SiteGradedElevation,PlanarApronElevation,terrain_axis

class TerrainSamplingTest(unittest.TestCase):
 def make(self,left,values):
  memory=MemoryFile();self.addCleanup(memory.close)
  raster=memory.open(driver='GTiff',width=values.shape[1],height=values.shape[0],count=1,dtype='float32',crs='EPSG:25832',transform=from_origin(left,2,1,1),nodata=-9999)
  raster.write(values.astype('float32'),1);self.addCleanup(raster.close);return raster
 def test_pixel_centres_and_tile_seam_preserve_a_plane(self):
  tiles=[]
  for left in [0,2]:
   x,y=np.meshgrid(np.arange(left+.5,left+2,1),[1.5,.5]);tiles.append(self.make(left,2*x+3*y))
  sampler=ElevationSampler(tiles)
  points=np.array([[.5,.5],[1.5,1.5],[2,1],[2.1,.8],[3.5,.5]])
  np.testing.assert_allclose(sampler.sample(points),2*points[:,0]+3*points[:,1],atol=1e-6)
  self.assertEqual(sampler(0,1),sampler(.5,1))
  with self.assertRaisesRegex(ValueError,'Outside DEM'):sampler(4,1)
 def test_missing_data_is_not_blended_into_terrain(self):
  sampler=ElevationSampler([self.make(0,np.array([[10,-9999],[10,10]]))])
  self.assertEqual(sampler(.5,1.5),10)
  with self.assertRaisesRegex(ValueError,'missing survey'):sampler(1,1.5)
 def test_tile_edges_match_and_interior_uses_source_centres(self):
  a,b=terrain_axis(100),terrain_axis(200)
  self.assertEqual(a[-1],b[0]);np.testing.assert_array_equal(a[1:-1],np.arange(100.5,200,1))
 def test_finished_site_grading_is_local_and_preserves_neighbours(self):
  from shapely.geometry import box
  class Source:
   def sample(self,xy):return np.full(len(xy),10.)
  grade=SiteGradedElevation(Source(),box(0,0,10,10),4,[box(12,3,14,7)])
  xy=np.array([[5,5],[5,-4],[5,-6],[5,-8],[5,-9],[13,5],[11.5,5]])
  np.testing.assert_allclose(grade.sample(xy),[4,4,7,10,10,10,10])
  self.assertEqual(grade(5,-4),4)

class ApronGradingTest(unittest.TestCase):
 def test_smooth_plane_blends_to_ground_and_excludes_neighbours(self):
  from shapely.geometry import box
  class Source:
   def sample(self,xy):return np.full(len(xy),5.)
  grade=PlanarApronElevation(Source(),box(0,0,10,10),[0,0],[0,1],2,.1/2,[box(4,4,6,6)],2)
  xy=np.array([[2,5],[5,5],[5,11],[5,12],[5,-1]])
  np.testing.assert_allclose(grade.sample(xy),[2.25,5,3.775,5,3.5])
  self.assertAlmostEqual(grade(2,5),2.25)

if __name__=='__main__':unittest.main()

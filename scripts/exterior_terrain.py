"""Pixel-centred sampling of the pinned BVV DGM1 GeoTIFFs."""
import numpy as np
from rasterio.merge import merge

class ElevationSampler:
 def __init__(self,rasters):
  values,self.transform=merge(rasters);self.values=values[0];self.nodata=rasters[0].nodata
  t=self.transform
  if t.b!=0 or t.d!=0 or t.a<=0 or t.e>=0:raise ValueError('Expected north-up elevation rasters')
  self.left,self.top=t.c,t.f;self.dx,self.dy=t.a,-t.e
  self.right=self.left+self.values.shape[1]*self.dx;self.bottom=self.top-self.values.shape[0]*self.dy
 def sample(self,points):
  p=np.asarray(points,dtype=float)
  if p.ndim!=2 or p.shape[1]!=2:raise ValueError('Expected projected easting/northing pairs')
  if np.any((p[:,0]<self.left)|(p[:,0]>=self.right)|(p[:,1]<self.bottom)|(p[:,1]>=self.top)):raise ValueError('Outside DEM')
  # GeoTIFF's affine transform addresses pixel corners. Values live half a
  # pixel inward. Interpolate across the merged tile seam, not per-file edges.
  c=(p[:,0]-self.left)/self.dx-.5;r=(self.top-p[:,1])/self.dy-.5
  i=np.floor(c).astype(int);j=np.floor(r).astype(int);fx=c-i;fy=r-j
  result=np.zeros(len(p),dtype=float)
  for di,dj,weight in [(0,0,(1-fx)*(1-fy)),(1,0,fx*(1-fy)),(0,1,(1-fx)*fy),(1,1,fx*fy)]:
   values=self.values[np.clip(j+dj,0,self.values.shape[0]-1),np.clip(i+di,0,self.values.shape[1]-1)]
   invalid=~np.isfinite(values)
   if self.nodata is not None:invalid|=values==self.nodata
   if np.any(invalid&(weight>1e-12)):raise ValueError('Elevation sample crosses missing survey data')
   result+=np.where(invalid,0,values)*weight
  return result
 def __call__(self,e,n):return float(self.sample([[e,n]])[0])

def terrain_axis(start,length=100):
 # Interior vertices coincide with DGM1 sample centres. Shared integer tile
 # boundaries use interpolated heights, giving identical edges on both sides.
 return np.r_[float(start),np.arange(start+.5,start+length,1),float(start+length)]

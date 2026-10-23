#!/usr/bin/env python3
"""Verify encoded terrain against DGM1 sample centres and neighbouring tile seams.
Optional --before-manifest reports the previous 2m mesh's representation error.
These are errors relative to the source raster, not real-world survey accuracy.
"""
from pathlib import Path
import argparse,json,math,struct
import numpy as np
import rasterio
from rasterio.merge import merge
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import contains_xy,points,distance,intersects
root=Path(__file__).resolve().parents[1];out=root/'dist-minecraft/exterior'
parser=argparse.ArgumentParser();parser.add_argument('--before-manifest',type=Path);args=parser.parse_args()
m=json.loads((out/'manifest.json').read_text());origin=m['origin'];bounds=m['boundsUtm']
rasters=[rasterio.open(root/'.cache'/('campus-dgm-'+s+'.tif'))for s in ['west','east']];dgm,tr=merge(rasters);dgm=dgm[0]
geoid=rasterio.open(root/'.cache/de_bkg_gcg2016.tif');gv=geoid.read(1)
toGeo=Transformer.from_crs(25832,4258,always_xy=True);toEcef=Transformer.from_crs(25832,4978,always_xy=True);geoEcef=Transformer.from_crs(4979,4978,always_xy=True)
lat,lon=map(math.radians,origin[:2]);zero=np.array(geoEcef.transform(origin[1],origin[0],origin[2]));east=np.array([-math.sin(lon),math.cos(lon),0]);up=np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)]);south=np.array([math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)])
def expected(x,y,z):
 lon,lat=toGeo.transform(x,y);col,row=(~geoid.transform)*(lon,lat);col-=.5;row-=.5;i=np.floor(col).astype(int);j=np.floor(row).astype(int);fx=col-i;fy=row-j
 offset=(gv[j,i]*(1-fx)+gv[j,i+1]*fx)*(1-fy)+(gv[j+1,i]*(1-fx)+gv[j+1,i+1]*fx)*fy
 xx,yy,zz=toEcef.transform(x,y,z+offset);p=np.column_stack((xx,yy,zz))-zero
 return np.column_stack((p@east,p@up+64,p@south))
seams={};maxSeam=0;errors=[];expectedPoints=[];sampleXY=[];bankHeights=[];cosHeights=[];plantingHeights=[];apronHeights=[];gradedCount=0;apronCount=0
grade=m.get('siteGrading')
if grade:
 footprint=Polygon(grade['footprintUtm']);neighbours=unary_union([Polygon(p)for p in grade['excludedNeighbourFootprintsUtm']]).buffer(grade['neighbourBufferMetres'])
for spec in m['tiles']:
 if spec['kind']!='ground':continue
 data=(out/spec['file']).read_bytes();parts,*anchor=struct.unpack_from('<i3d',data,4);assert parts==1
 count=struct.unpack_from('<i',data,32)[0];v=np.frombuffer(data,dtype='<f4',count=count*5,offset=48).reshape(-1,5)
 # Independently recover the visible surface underneath the native gravity probe.
 lo,hi=spec['bounds']
 for px,pz,heights in [(14.5,-228.5,bankHeights),(186.5,-288.5,cosHeights),(154.04,-278.63,plantingHeights),(163.5,-276.5,apronHeights)]:
  if lo[0]<=px<=hi[0] and lo[2]<=pz<=hi[2]:
   triangles=(v[:,:3].astype(float)+anchor).reshape(-1,3,3)
   a=triangles[:,0];u=triangles[:,1]-a;w=triangles[:,2]-a;det=u[:,0]*w[:,2]-u[:,2]*w[:,0]
   f=((px-a[:,0])*w[:,2]-(pz-a[:,2])*w[:,0])/det;g=(u[:,0]*(pz-a[:,2])-u[:,2]*(px-a[:,0]))/det
   hit=(f>=0)&(g>=0)&(f+g<=1);heights.extend((a[:,1]+f*u[:,1]+g*w[:,1])[hit].tolist())
 _,ids=np.unique(v[:,3:5],axis=0,return_index=True);v=v[ids];assert len(v)==102*102
 e,n=map(int,Path(spec['file']).stem.split('-')[1:]);x=np.round(e+v[:,3].astype(float)*100,3);y=np.round(n+100-v[:,4].astype(float)*100,3);actual=v[:,:3].astype(float)+anchor
 interior=(v[:,3]>0)&(v[:,3]<1)&(v[:,4]>0)&(v[:,4]<1)
 for xx,yy,point in zip(x[~interior],y[~interior],actual[~interior]):
  key=(xx,yy)
  if key in seams:maxSeam=max(maxSeam,float(np.max(np.abs(point-seams[key]))))
  else:seams[key]=point
 x=x[interior];y=y[interior];actual=actual[interior]
 np.testing.assert_allclose(np.mod(x,1),.5,atol=1e-6);np.testing.assert_allclose(np.mod(y,1),.5,atol=1e-6)
 col,row=(~tr)*(x,y);height=dgm[row.astype(int),col.astype(int)].astype(float)
 if grade:
  locations=points(x,y);d=distance(locations,footprint)
  t=np.clip((d-grade['innerMetres'])/(grade['outerMetres']-grade['innerMetres']),0,1);weight=1-t*t*(3-2*t)
  weight[intersects(locations,neighbours)]=0;graded=weight>0
  height+=weight*(grade['heightDHHN2016']-height)
  if grade.get('apron'):
   apron=grade['apron'];a=distance(locations,Polygon(apron['footprintUtm']));t=np.clip(a/apron['blendMetres'],0,1);w=1-t*t*(3-2*t);w[intersects(locations,neighbours)]=0
   target=apron['baseHeightDHHN2016']+apron['slope']*np.maximum(0,(np.column_stack((x,y))-apron['originUtm'])@np.array(apron['outwardUtm']))
   height+=w*(target-height);apronCount+=int(np.count_nonzero(w));graded|=w>0
  gradedCount+=int(np.count_nonzero(graded))
 want=expected(x,y,height)
 errors.extend(np.linalg.norm(actual-want,axis=1));expectedPoints.append(want);sampleXY.append(np.column_stack((x,y)))
assert len(errors)==360000 and max(errors)<.001 and maxSeam<.00001,(len(errors),max(errors),maxSeam)
result={'status':'PASS: encoded terrain matches DGM1 plus explicit site grading, with adjoining tile seams preserved','sourceSampleCount':len(errors),'unalteredDgmSamples':len(errors)-gradedCount,'inferredSiteGradingSamples':gradedCount,'apronGradingSamples':apronCount,'maximumPositionErrorMetres':max(errors),'maximumTileSeamErrorMetres':maxSeam,'note':'Source representation accuracy only; not a claim of millimetre real-world survey accuracy. Explicit site grading is approximate finished terrain, not measured DGM.'}
assert len(bankHeights)==1 and abs(bankHeights[0]-62.378458)<.00001,bankHeights
result['nativeBankProbe']={'positionMC':[14.5,-228.5],'meshHeight':bankHeights[0],'expectedProxyTop':round(bankHeights[0]),'toleranceMetres':.51}
if grade:
 assert len(cosHeights)==1 and abs(cosHeights[0]-63.15315985)<.00001,cosHeights
 result['nativeCosGroundProbe']={'positionMC':[186.5,-288.5],'meshHeight':cosHeights[0],'expectedProxyTop':round(cosHeights[0]),'toleranceMetres':.51}
if grade and grade.get('apron'):
 assert len(plantingHeights)==1
 assert len(apronHeights)==1 and abs(apronHeights[0]-63.46270589)<.00001
 result['nativeApronProbe']={'positionMC':[163.5,-276.5],'meshHeight':apronHeights[0],'expectedProxyTop':63,'previousMeshHeight':63.56278362,'previousProxyTop':64}
 result['nativePlantingProbe']={'positionMC':[154.04,-278.63],'meshHeight':plantingHeights[0],'note':'Rendered soil probe uses the same smooth apron plane.'}
if args.before_manifest:
 old=json.loads(args.before_manifest.read_text());grid=np.array(old['terrainGuide']['points']).reshape(301,301,3);xy=np.concatenate(sampleXY);want=np.concatenate(expectedPoints)
 s=(xy[:,0]-bounds[0])/2;t=(xy[:,1]-bounds[1])/2;i=s.astype(int);j=t.astype(int);fx=s-i;fy=t-j
 a=grid[j,i,1];b=grid[j,i+1,1];c=grid[j+1,i,1];d=grid[j+1,i+1,1]
 previous=np.where(fx+fy<=1,a+(b-a)*fx+(c-a)*fy,d+(c-d)*(1-fx)+(b-d)*(1-fy));error=np.abs(previous-want[:,1])
 protected=unary_union([Polygon(r)for r in old['protectedFootprints']]);outside=~contains_xy(protected,want[:,0],want[:,2])
 terrace=(xy[:,0]>698180)&(xy[:,0]<698260)&(xy[:,1]>5349400)&(xy[:,1]<5349460)
 def stats(mask):
  e=error[mask];return {'sampleCount':len(e),'absoluteHeightErrorP50P95P99MaxMetres':np.percentile(e,[50,95,99,100]).tolist(),'over25cm':int(np.count_nonzero(e>.25))}
 result['previousTwoMetreMesh']={'wholeCampus':stats(np.ones(len(error),bool)),'outsideProtectedFootprints':stats(outside),'terraceWindow':stats(terrace),'terraceOutsideProtectedFootprints':stats(terrace&outside)}
(out/'terrain-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

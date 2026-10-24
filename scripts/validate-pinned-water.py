#!/usr/bin/env python3
"""Independently verify packaged river segments against pinned public OSM nodes."""
from pathlib import Path
import argparse,hashlib,json,math,xml.etree.ElementTree as ET
import numpy as np
import rasterio
from scipy.ndimage import map_coordinates
from pyproj import Transformer
from shapely.geometry import Polygon
r=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=r/'dist-minecraft/exterior');out=p.parse_args().directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=read(out/'manifest.json');rec=m['pinnedWater'];spec=read(r/'minecraft/exterior'/rec['sourceFile'])
assert sha(r/'minecraft/exterior'/rec['sourceFile'])==rec['sourceSha256'];assert sha(r/rec['generatorFile'])==rec['generatorSha256'];assert rec['origin']==m['origin'][:2];assert rec['osm']==spec['northLandscapeBoundary']['osm']
project=Transformer.from_crs(4326,25832,always_xy=True).transform;nodes={};ways={}
for item in rec['osm']:
 path=r/'minecraft/exterior'/item['sourceFile'];assert sha(path)==item['sha256'];assert sha(out/path.name)==item['sha256'];xml=ET.parse(path).getroot()
 nodes.update({n.get('id'):project(float(n.get('lon')),float(n.get('lat')))for n in xml.findall('node')})
 ways.update({w.get('id'):w for w in xml.findall('way')})
assert len(rec['features'])==1
f=rec['features'][0];assert f['id']=='way/'+spec['northLandscapeBoundary']['riverWay'];way=ways[f['id'].split('/')[1]];tags={t.get('k'):t.get('v')for t in way.findall('tag')};assert tags['natural']=='water'and tags['water']=='river';xy=np.array([nodes[n.get('ref')]for n in way.findall('nd')]);assert np.array_equal(xy[0],xy[-1])and Polygon(xy).is_valid
lat,lon=map(math.radians,m['origin'][:2]);origin=np.array(Transformer.from_crs(4979,4978,always_xy=True).transform(m['origin'][1],m['origin'][0],m['origin'][2]));basis=np.array([[-math.sin(lon),math.cos(lon),0],[math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)],[math.sin(lat)*math.cos(lon),math.sin(lat)*math.sin(lon),-math.cos(lat)]])
geoid=r/'.cache/de_bkg_gcg2016.tif';assert sha(geoid)==read(r/'minecraft/exterior/sources.json')['geoid']['sha256']
with rasterio.open(geoid)as d:
 lon,lat=Transformer.from_crs(25832,4258,always_xy=True).transform(*xy.T);col,row=(~d.transform)*(lon,lat);h=475+map_coordinates(d.read(1).astype(float),[row-.5,col-.5],order=1,prefilter=False)
xyz=np.column_stack(Transformer.from_crs(25832,4978,always_xy=True).transform(xy[:,0],xy[:,1],h));expected=((xyz-origin)@basis.T+[0,64,0])[:,[0,2]];segments=np.array(f['segs']).reshape(-1,4);target=np.column_stack([expected[:-1],expected[1:]])
error=float(np.max(np.abs(segments-target)));assert error<.0001;assert len(segments)==len(xy)-1
for key,value in [('minx',expected[:,0].min()),('maxx',expected[:,0].max()),('minz',expected[:,1].min()),('maxz',expected[:,1].max())]:assert abs(f[key]-value)<.0001
assert np.array_equal(segments[:-1,2:],segments[1:,:2])and np.array_equal(segments[-1,2:],segments[0,:2])
result={'status':'PASS: pinned public river boundary, projection, closure and bounds','manifestSha256':sha(out/'manifest.json'),'sourceSha256':rec['sourceSha256'],'generatorSha256':rec['generatorSha256'],'validatorSha256':sha(Path(__file__)),'segments':len(segments),'maximumCoordinateErrorMetres':error,'qualification':'Boundary-only validation; upstream water level, bed and visible banks still require native verification.'};(out/'pinned-water-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

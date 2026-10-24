#!/usr/bin/env python3
"""Verify Physics I's additive scope against a frozen previous exterior build."""
from pathlib import Path
import argparse,base64,hashlib,json,struct
import numpy as np
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from exterior_physics_i import BID, polygons

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior')
a=p.parse_args();old=a.baseline/'exterior';out=a.directory
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before,current=read(old/'manifest.json'),read(out/'manifest.json')
for field in before:
    if field not in ['tiles','architecture','photoFacades','replacements']:
        assert current[field]==before[field],field
assert current['tiles'][:len(before['tiles'])]==before['tiles']
assert current['replacements'][:len(before['replacements'])]==before['replacements']
for tile in before['tiles']:
    assert sha(old/tile['file'])==sha(out/tile['file']),tile['file']
for key in before['architecture']:
    assert before['architecture'][key]==current['architecture'][key],key
prior,plans=read(old/'photo-facades.json'),read(out/'photo-facades.json')
assert plans['plans'][:-1]==prior['plans']
assert plans['plans'][-1]['id']==BID
for plan in prior['plans']:
    for key in ['roofFile','collisionFile']:
        assert sha(old/plan[key])==sha(out/plan[key])
new=plans['plans'][-1]
assert len(new['walls'])==80 and len(new['roofTriangles'])==150
record=current['architecture']['physicsIExterior'];spec=read(root/'minecraft/exterior'/record['sourceFile'])
assert record['sourceSha256']==sha(root/'minecraft/exterior'/record['sourceFile'])
shape=lambda rings:unary_union([Polygon(p['ring'],p.get('holes',[])) for p in rings])
foot=shape(record['surveyFootprint'])
assert sum(len(p.interiors)for p in polygons(foot))==3
assert 8468<foot.area<8470
cleanup=shape(record['retirement'])
assert spec['sourceCleanupMarginMetres']==3
owned=foot.buffer(spec['sourceCleanupMarginMetres'],join_style=2)
neighbours=shape(record['neighbourExclusions'])
fringe=shape(record['rasterRetirementFringe'])
grid=current['protectionGrid'];guide=current['terrainGuide'];points=np.asarray(guide['points'])[:,[0,2]]
origin=points[0];u=points[1]-origin;v=points[guide['width']]-origin
u*=grid['metresPerPixel']/np.linalg.norm(u);v*=grid['metresPerPixel']/np.linalg.norm(v)
pixels=np.frombuffer(base64.b64decode(grid['data']),dtype=np.uint8).reshape(grid['height'],grid['width']);cells=[]
for i,j in record['rasterProtectionCells']:
    assert 0<=i<grid['width'] and 0<=j<grid['height'] and pixels[j,i]
    corner=origin+u*i+v*(grid['height']-1-j);cell=Polygon([corner,corner+u,corner+u+v,corner+v])
    assert cell.intersection(owned).area>1e-8 and not owned.covers(cell)
    cells.append(cell)
assert fringe.symmetric_difference(unary_union(cells).difference(owned).difference(neighbours)).area<.001
assert cleanup.symmetric_difference(owned.union(fringe).difference(neighbours)).area<.001
assert cleanup.intersection(neighbours).area<.001
assert all(w['reconstructed']for w in new['walls'])
for wall in new['walls']:
    ring=np.asarray(wall['vertices']);source_normal=np.sum(np.cross(ring,np.roll(ring,-1,axis=0)),axis=0);source_normal/=np.linalg.norm(source_normal)
    assert source_normal@np.asarray(wall['normal'])>.999,'Wall normal disagrees with original survey polygon orientation'
assert new['completeEnvelope'] and new['manualRoof'] and new['retirementBoundary']==record['retirement']

def decode(path):
    data=path.read_bytes();count=struct.unpack_from('<i',data,4)[0];offset=32;parts=[]
    for _ in range(count):
        n,w,h=struct.unpack_from('<iii',data,offset);offset+=16
        vertices=np.frombuffer(data,dtype='<f4',count=n*5,offset=offset).reshape(-1,5).copy();offset+=n*20
        pixels=data[offset:offset+w*h*4];offset+=w*h*4;parts.append((vertices,pixels))
    assert offset==len(data)
    return parts
body=decode(out/(BID+'-physics-i-exterior.ect'));roof=decode(out/new['roofFile'])
assert len(body)==5 and len(roof)==1
assert np.array_equal(body[-1][0],roof[0][0])and body[-1][1]==roof[0][1]
assert np.allclose(roof[0][0][:,:3],np.asarray(new['roofTriangles']).reshape(-1,3),atol=2e-5,rtol=0)
glazing=body[1][0][:,:3].reshape(-1,3,3)
for triangle in glazing:
    center=triangle.mean(0);normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0]);normal/=np.linalg.norm(normal)
    matches=[]
    for wall in new['walls']:
        anchor,direction,outward=[np.asarray(wall[k])for k in ['anchor','direction','normal']]
        uv=[(center-anchor)@direction,center[1]]
        if abs((center-anchor+outward*spec['recessMetres'])@outward)<.002 and Polygon(wall['rings'][0],wall['rings'][1:]).buffer(.001).contains(Point(uv)):
            matches.append(normal@outward)
    assert matches and all(dot>.999 for dot in matches),'Glazing winding must face the surveyed exterior/courtyard'
assert len(current['supplementalSurfaces'])==1
site=current['architecture']['physicsISite'];tile_origins=spec['site']['tileOriginsUTM']
assert len(tile_origins)==len(set(map(tuple,tile_origins)))
assert tile_origins[:12]==[[e,n]for e in range(698500,698660,40)for n in range(5349400,5349520,40)]
extent=box(*spec['site']['boundsUTM'])
tile_coverage=unary_union([box(e,n,e+40,n+40)for e,n in tile_origins])
assert extent.difference(tile_coverage).area<1e-7,'Supplemental tile grid leaves a gap'
assert len(site['groundTiles'])==len(tile_origins)
for index,(e,n)in enumerate(tile_origins):
    name=f'physics-ground-{e}-{n}.ect';assert name in site['groundTiles']
    tile=next(t for t in current['tiles']if t['file']==name)
    assert tile['runtimeId']==1_000_060_000+index
assert len({t['runtimeId']for t in current['tiles']})==len(current['tiles'])
assert current['boundsUtm']==before['boundsUtm']
assert current['terrainGuide']==before['terrainGuide']
result={'status':'PASS: additive Physics I candidate; native visual acceptance remains pending','priorRenderMeshesUnchanged':len(before['tiles']),'priorPhotoPlansUnchanged':len(prior['plans']),'priorRoofsAndCollisionFilesUnchanged':len(prior['plans']),'newBuildingWallFaces':80,'newRoofTriangles':150,'courtyardHoles':3,'newGroundTiles':len(site['groundTiles']),'rasterProtectionBoundaryCells':len(cells),'rasterRetirementFringeSquareMetres':fringe.area,'neighbourRetirementOverlapSquareMetres':cleanup.intersection(neighbours).area,'newTrees':site['vegetation']['trees'],'newVegetationGroups':site['vegetation']['groups'],'oldTerrainBoundsAndGuideUnchanged':True,'sourceSha256':record['sourceSha256'],'qualification':spec['qualification']}
(out/'physics-i-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

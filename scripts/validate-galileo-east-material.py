#!/usr/bin/env python3
"""Validate bounded paving provenance, geometry-independent scope and shared passes."""
import hashlib,json,math,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];source=root/'minecraft/exterior';out=root/'dist-minecraft/exterior'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec=json.loads((source/'galileo-east-material.json').read_text());m=json.loads((out/'manifest.json').read_text())
assert sha(source/spec['reference'])==spec['referenceSha256']
assert sha(source/spec['material'])==spec['materialSha256']
frame=m['groundMaterialFrame'];assert hashlib.sha256(json.dumps(frame,sort_keys=True).encode()).hexdigest()==spec['groundFrameSha256']
for utm,world in zip(spec['polygonEPSG25832'],spec['polygonMC']):
 d=[utm[i]-frame['originUtm'][i] for i in range(2)]+[1]
 projected=[sum(d[j]*frame['fit'][j][i] for j in range(3)) for i in range(2)]
 assert max(abs(a-b) for a,b in zip(projected,world))<1e-8
poly=spec['polygonMC'];area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1]))/2
assert 1300<abs(area)<1400
# The outer side follows the pinned mapped verge, including only the declared
# short southern continuation. Check perpendicular distance independently.
boundary=spec['boundarySource'];assert sha(source/boundary['file'])==boundary['sha256']
feature=next(f for f in json.loads((source/boundary['file']).read_text())['features']if f['properties'].get('osmWay')==boundary['osmWay'])
assert feature['geometry']['coordinates'][0][3:5]==boundary['westEdgeWGS84']
a,b=boundary['westEdgeEPSG25832'];v=[b[i]-a[i]for i in range(2)];length=math.hypot(*v)
for point in spec['polygonEPSG25832'][2:]:
 q=[point[i]-a[i]for i in range(2)]
 assert abs(v[0]*q[1]-v[1]*q[0])/length<1e-7
 station=sum(q[i]*v[i]for i in range(2))/length
 assert 0<=station<=length+boundary['maximumInferredEndContinuationMetres']
# Independent convex-domain checks include inner frontage, both ramp centres,
# the established eastern grass verge, adjacent courtyard and roof exclusion.
def inside(x,y,z):
 if not spec['heightRangeMC'][0]<=y<=spec['heightRangeMC'][1]:return False
 cross=[(b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(x-a[0]) for a,b in zip(poly,poly[1:]+poly[:1])]
 return min(cross)>=0 or max(cross)<=0
controls=[('north frontage',(135.8,64,-131),True),('central frontage',(131.5,64,-115),True),('south frontage',(126.8,64,-88),True),('north ramp',(140.69,61.92,-125.83),True),('south ramp',(134.43,62.43,-92.52),True),('east planted verge',(155,64,-120),False),('courtyard',(161.63,64,-110.93),False),('west promenade',(72,64,-125),False),('building roof',(131.5,89,-115),False)]
for name,point,expected in controls:assert inside(*point)==expected,name
subprocess.run([sys.executable,str(root/'scripts/build-galileo-east-material.py'),'--check'],check=True)
main=(source/'shaders/campus_ground.fsh').read_text();reflection=(source/'shaders/campus_reflection.fsh').read_text();client=(source/'client/CampusReflections.java').read_text()
assert 'if(abs(MaterialDetail-1.0)<.1||physicsGround)'in main and 'galileoEastAlbedo(worldPosition)'in main
patch=(source/'patches/realworldmc-exterior.patch').read_text()
assert 'boolean physicsGround=campus&&surveyed;'in patch
assert 'bool physicsGround=abs(MaterialDetail-19.0)<.1' in main
assert 'if(SurveyedGround>.5)'in reflection and 'galileoEastAlbedo(worldPosition)'in reflection
assert 'tile.data.id==1_000_030_022&&(p==1||p==3)'in client
paths=['galileo-east-material.json',spec['reference'],'shaders/campus_ground.fsh','shaders/campus_reflection.fsh','client/CampusReflections.java',spec['material']]
record={'status':'PASS: source-supported bounded asphalt, both render passes, exclusions and coordinate controls','sourceFiles':{p:sha(source/p) for p in paths},'generatorSha256':sha(root/'scripts/build-galileo-east-material.py'),'validatorSha256':sha(Path(__file__)),'areaSquareMetres':abs(area),'controls':[{'label':n,'positionMC':p,'inside':v}for n,p,v in controls],'geometryChanged':False,'nativeVisualAcceptance':False}
(out/'galileo-east-material-validation.json').write_text(json.dumps(record,indent=2)+'\n');print(record['status'],round(abs(area),2),'m²')

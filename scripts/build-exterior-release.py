#!/usr/bin/env python3
"""Build the licensed Minecampus variant from pinned RealWorldMC source and public data.
Requires JDK 21 and a completed scripts/build-exterior.py + validation run.
Never reads provider configuration or saved worlds.
"""
import argparse,hashlib,io,json,os,shutil,subprocess,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'minecraft/exterior';CACHE=ROOT/'.cache/exterior-build';OUT=ROOT/'dist-minecraft';DATA=OUT/'exterior'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--java-home',default=os.environ.get('JAVA_HOME'));args=parser.parse_args()
if not args.java_home:raise SystemExit('Supply --java-home with a JDK 21 installation.')
subprocess.run(['python3',str(ROOT/'scripts/validate-exterior.py')],check=True)
for item in json.loads((SOURCE/'material-sources.json').read_text())['materials']:
 p=SOURCE/'assets/textures/campus'/(item['name']+'.png')
 if hashlib.sha256(p.read_bytes()).hexdigest()!=item['resourceSha256']:raise SystemExit('Material resource checksum mismatch: '+item['name'])
upstream=json.loads((SOURCE/'upstream.json').read_text());spec=upstream['release'];CACHE.mkdir(parents=True,exist_ok=True)
release=CACHE/'upstream.jar'
if not release.exists() or hashlib.sha256(release.read_bytes()).hexdigest()!=spec['sha256']:
 req=urllib.request.Request(spec['url'],headers={'User-Agent':'Minecampus/0.3 (https://github.com/DocMorphic/minecampus)'})
 release.write_bytes(urllib.request.urlopen(req,timeout=120).read())
if release.stat().st_size!=spec['size'] or hashlib.sha256(release.read_bytes()).hexdigest()!=spec['sha256']:raise SystemExit('Upstream release integrity check failed.')
inputs=[SOURCE/'patches/realworldmc-exterior.patch',*sorted((SOURCE/'native').glob('*.java')),*sorted((SOURCE/'shaders').glob('*')),*sorted((SOURCE/'client').glob('*.java')),*sorted((SOURCE/'assets').rglob('*.png'))]
fingerprint=hashlib.sha256(upstream['commit'].encode()+b''.join(p.read_bytes() for p in inputs)).hexdigest()[:16]
work=CACHE/fingerprint
if not work.exists():
 work.mkdir();subprocess.run(['git','init',str(work)],check=True)
 subprocess.run(['git','-C',str(work),'remote','add','origin',upstream['repository']],check=True)
 subprocess.run(['git','-C',str(work),'fetch','--depth','1','origin',upstream['commit']],check=True)
 subprocess.run(['git','-C',str(work),'checkout','--detach','FETCH_HEAD'],check=True)
 subprocess.run(['git','-C',str(work),'apply',str(inputs[0])],check=True)
 (work/'.minecampus-build').write_text(fingerprint)
if not (work/'.minecampus-build').exists() or (work/'.minecampus-build').read_text()!=fingerprint:raise SystemExit('Build directory is not owned by this build; use a fresh cache path.')
if subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()!=upstream['commit']:raise SystemExit('Build source commit mismatch.')
subprocess.run(['git','-C',str(work),'apply','--reverse','--check',str(inputs[0])],check=True)
for p in (SOURCE/'native').glob('*.java'):shutil.copy2(p,work/'mod/src/main/java/dev/realworldmc'/p.name)
for p in (SOURCE/'client').glob('*.java'):shutil.copy2(p,work/'mod/src/client/java/dev/realworldmc/client'/p.name)
for p in (SOURCE/'assets').rglob('*.png'):
 target=work/'mod/src/main/resources/assets/realworldmc'/p.relative_to(SOURCE/'assets');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
shader=work/'mod/src/main/resources/assets/realworldmc/shaders/core';shader.mkdir(parents=True,exist_ok=True)
for p in (SOURCE/'shaders').glob('*'):shutil.copy2(p,shader/p.name)
env=dict(os.environ,JAVA_HOME=str(Path(args.java_home).resolve()))
subprocess.run(['bash',str(work/'mod/gradlew'),'-p',str(work/'mod'),'remapJar','--console=plain'],env=env,check=True)
compiled=work/'mod/build/libs/realworldmc-1.0.3.jar'
if not compiled.is_file():raise SystemExit('Expected remapped release JAR missing.')
manifest=json.loads((DATA/'manifest.json').read_text())
notices='''Minecampus exterior modifications and provenance

RealWorldMC 1.0.3 by Teddy563 and contributors: Apache-2.0.
Pinned source: https://github.com/Teddy563/realworldmc/tree/6f18d1f3ba5a02dadee4b14bcb96578bf3941d13
Minecampus modifications: https://github.com/DocMorphic/minecampus

Terrain DGM1, DOP20 orthophotos, and LoD2 building geometry:
© Bayerische Vermessungsverwaltung, https://geodaten.bayern.de/ (CC BY 4.0).
Cropped to the Garching campus, reprojected, meshed and combined with photographs.
Height transformation grid GCG2016: © GeoBasis-DE / BKG 2023 (CC BY 4.0).
Grid distribution: https://cdn.proj.org/de_bkg_gcg2016.tif
License: https://creativecommons.org/licenses/by/4.0/

Galileo facade photograph by MaxEmanuel, 18 August 2021 (CC0 1.0).
https://commons.wikimedia.org/wiki/File:Galileo_Garching_Nordende.jpg
Rectified photograph strip; approximate repetition and recessed window reconstruction.
https://creativecommons.org/publicdomain/zero/1.0/

MW concrete photographic material: Renardo la vulpo (CC BY-SA 4.0).
https://commons.wikimedia.org/wiki/File:Garching,_Eberhard-von-Kuenheim-Bau,_2.jpeg
https://creativecommons.org/licenses/by-sa/4.0/
Cropped concrete surface; window and louvre layout reconstructed on BVV survey envelopes.
The combined MW mesh/material adaptation is supplied under CC BY-SA 4.0.

Vegetation positions/heights: BVV DOM20/DGM1/DOP20 (CC BY 4.0).
Ground/concrete micro-material colour/normal maps: Poly Haven concrete_wall_007 and grass_ground (CC0 1.0).
https://polyhaven.com/a/concrete_wall_007
https://polyhaven.com/a/grass_ground
Leaf and bark atlases: Poly Haven jacaranda_tree (CC0 1.0).
https://polyhaven.com/a/jacaranda_tree
Reconstructed branch placement and artistic foliage, not surveyed tree species.

IAS facade material: High Contrast (CC BY 3.0 DE).
https://commons.wikimedia.org/wiki/File:TU_M%C3%BCnchen_Garching_-_Institute_for_Advanced_Study.jpg
https://creativecommons.org/licenses/by/3.0/de/
Cropped metal/glass material; surveyed envelope with reconstructed atrium,
folding screens and terrace based on the architect's project reference.

Google scenery is streamed by the user's own configured service. No Google tile
content, Minecraft assets, credentials or saved worlds are included in this build.
'''
def write(z,name,payload):
 info=zipfile.ZipInfo(name,(2026,10,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,payload)
with zipfile.ZipFile(release) as original:
 payload=original.read('realworldmc-service.zip');expected=original.read('realworldmc-service.sha256').decode().strip()
 if hashlib.sha256(payload).hexdigest()!=expected:raise SystemExit('Embedded upstream service checksum mismatch.')
 patched=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(payload)) as service,zipfile.ZipFile(patched,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as target:
  for entry in service.infolist():
   data=service.read(entry.filename)
   if entry.filename=='src/server.mjs':
    s=data.decode()
    defaults='render: { maxSse: 12, falloff: 600, viewportHeight: 1080, fovDeg: 70, far: 8000, fineRadius: 160, maxTiles: 900 }'
    assert s.count(defaults)==1
    s=s.replace(defaults,'render: { maxSse: 2, falloff: 600, viewportHeight: 1440, fovDeg: 70, far: 1000, fineRadius: 250, maxTiles: 1200 }')
    needle='  const service = new EarthService(cfg);'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'''
  const exteriorDir=path.join(here,'minecampus-exterior');
  if(fs.existsSync(path.join(exteriorDir,'manifest.json'))){
    const {attachSurveySurface}=await import('./minecampus-survey.mjs');
    attachSurveySurface(service,exteriorDir,{voxelizeArea});
  }''')
    needle="        case '/render/tile': {";assert s.count(needle)==1
    s=s.replace(needle,'''        case '/campus/collision': {
          if(!service.campusCollision)return json(res,{error:'Survey collision data unavailable'},404);
          const frame=service.frame(num(q,'lat'),num(q,'lon'),num(q,'h'));
          const bytes=service.campusCollision(frame,num(q,'cx'),num(q,'cz'),num(q,'minY'),num(q,'height'));
          res.writeHead(200,{'content-type':'application/octet-stream','content-length':bytes.length});return res.end(bytes);
        }
'''+needle);data=s.encode()
   write(target,entry.filename,data)
  write(target,'src/minecampus-survey.mjs',(SOURCE/'service/survey-surface.mjs').read_bytes())
  write(target,'src/minecampus-exterior/manifest.json',(DATA/'manifest.json').read_bytes())
  write(target,'src/minecampus-exterior/NOTICE.txt',notices.encode())
  write(target,'src/minecampus-exterior/sources.json',(SOURCE/'sources.json').read_bytes())
  write(target,'src/minecampus-exterior/vegetation-sources.json',(SOURCE/'vegetation-sources.json').read_bytes())
  for asset in manifest['tiles']:
   name=asset['file'];assert Path(name).name==name and name.endswith('.ect')
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
 bundle=patched.getvalue()
 target=OUT/'RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar'
 with zipfile.ZipFile(compiled) as code,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for entry in code.infolist():
   if entry.filename in ['realworldmc-service.zip','realworldmc-service.sha256']:continue
   data=code.read(entry.filename)
   if entry.filename=='fabric.mod.json':
    d=json.loads(data);d['version']='1.0.3+minecampus.exterior.3-dev';d['name']='RealWorldMC — Minecampus Exterior';data=json.dumps(d,indent=2).encode()
   write(z,entry.filename,data)
  write(z,'realworldmc-service.zip',bundle);write(z,'realworldmc-service.sha256',hashlib.sha256(bundle).hexdigest().encode())
  write(z,'LICENSES/Minecampus-exterior-notices.txt',notices.encode())
report={'file':target.name,'size':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'sourceCommit':upstream['commit'],'sourcePatchSha256':hashlib.sha256(inputs[0].read_bytes()).hexdigest(),'bundleSha256':hashlib.sha256(bundle).hexdigest(),'tiles':len(manifest['tiles'])}
(OUT/'exterior-release.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

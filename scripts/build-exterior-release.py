#!/usr/bin/env python3
"""Build the licensed Minecampus variant from pinned RealWorldMC source and public data.
Requires JDK 21 and a completed scripts/build-exterior.py + validation run.
Never reads provider configuration or saved worlds.
"""
import argparse,hashlib,io,json,os,re,shutil,subprocess,urllib.request,zipfile
from pathlib import Path
from exterior_ground_provenance import ground_generator_matches
from exterior_voxel_patch import patch_voxel
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'minecraft/exterior';CACHE=ROOT/'.cache/exterior-build';OUT=ROOT/'dist-minecraft';DATA=OUT/'exterior'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--java-home',default=os.environ.get('JAVA_HOME'));args=parser.parse_args()
if not args.java_home:raise SystemExit('Supply --java-home with a JDK 21 installation.')
subprocess.run(['python3',str(ROOT/'scripts/validate-exterior.py')],check=True)
site_record=DATA/'physics-site-validation.json'
if not site_record.exists():raise SystemExit('Run scripts/validate-physics-site.py with the geodata Python environment before packaging.')
site_check=json.loads(site_record.read_text());site=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsISite']
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert site_check['status'].startswith('PASS:')
assert site_check['manifestSha256']==digest(DATA/'manifest.json')
assert site_check['sourceSha256']==digest(SOURCE/site['sourceFile'])
assert site_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-site.py')
assert set(site_check['tileSha256'])==set(site['groundTiles'])
assert all(digest(DATA/name)==value for name,value in site_check['tileSha256'].items())
surface=json.loads((DATA/'manifest.json').read_text())['groundSurfaces']
physics_surface=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsGroundMaterials']
for path,key in [(SOURCE/physics_surface['sourceFile'],'sourceSha256'),
                 (SOURCE/physics_surface['maskFile'],'maskSha256'),
                 (DATA/physics_surface['derivedFile'],'derivedSha256'),
                 (ROOT/'scripts/exterior_physics_ground.py','generatorSha256')]:
 if digest(path)!=physics_surface[key]:raise SystemExit('Physics ground material provenance mismatch: '+path.name)
mapping_source=(SOURCE/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED PHYSICS GROUND MAPPING\n')[1].split('// END GENERATED PHYSICS GROUND MAPPING')[0]
if hashlib.sha256(mapping_source.encode()).hexdigest()!=physics_surface['shaderMappingSha256']:
 raise SystemExit('Physics ground mapping does not match generated atlas')
for path,key in [(SOURCE/'ground-surfaces.geojson','sourceSha256'),(SOURCE/'assets/textures/campus/ground_surfaces.png','maskSha256')]:
 if hashlib.sha256(path.read_bytes()).hexdigest()!=surface[key]:raise SystemExit('Ground material provenance mismatch: '+path.name)
for item in json.loads((SOURCE/'material-sources.json').read_text())['materials']:
 p=SOURCE/'assets/textures/campus'/(item['name']+'.png')
 if hashlib.sha256(p.read_bytes()).hexdigest()!=item['resourceSha256']:raise SystemExit('Material resource checksum mismatch: '+item['name'])
for path,key in [(SOURCE/'path-widths.json','sourceSha256'),(DATA/'path-surfaces.geojson','derivedSha256')]:
 if hashlib.sha256(path.read_bytes()).hexdigest()!=surface['paths'][key]:raise SystemExit('Path material provenance mismatch: '+path.name)
for path,key in [(SOURCE/'cos-site.json','sourceSha256'),(DATA/'cos-site-surfaces.geojson','derivedSha256')]:
 if hashlib.sha256(path.read_bytes()).hexdigest()!=surface['cosSite'][key]:raise SystemExit('COS site provenance mismatch: '+path.name)
for path,key in [(SOURCE/'promenade-paths.json','sourceSha256'),(DATA/'promenade-surfaces.geojson','derivedSha256')]:
 if hashlib.sha256(path.read_bytes()).hexdigest()!=surface['promenade'][key]:raise SystemExit('Promenade provenance mismatch: '+path.name)
for path,key in [(SOURCE/'crosspaths.json','sourceSha256'),(DATA/'crosspath-surfaces.geojson','derivedSha256')]:
 if hashlib.sha256(path.read_bytes()).hexdigest()!=surface['crosspaths'][key]:raise SystemExit('Cross-path provenance mismatch: '+path.name)
mlz_ground=json.loads((DATA/'manifest.json').read_text())['architecture']['mlzCourtyardGround']
for path,key in [(SOURCE/mlz_ground['sourceFile'],'sourceSha256'),(ROOT/mlz_ground['generatorFile'],'generatorSha256'),(SOURCE/mlz_ground['referenceFile'],'referenceSha256'),(DATA/mlz_ground['derivedFile'],'derivedSha256')]:assert digest(path)==mlz_ground[key]
mlz_ground_check=json.loads((DATA/'mlz-courtyard-ground-validation.json').read_text())
assert mlz_ground_check['status'].startswith('PASS:')
assert mlz_ground_check['manifestSha256']==digest(DATA/'manifest.json')
assert mlz_ground_check['validatorSha256']==digest(ROOT/'scripts/validate-mlz-courtyard-ground.py')
assert mlz_ground_check['maskSha256']==surface['maskSha256']==mlz_ground['maskSha256']
assert mlz_ground_check['sourceSha256']==mlz_ground['sourceSha256'] and mlz_ground_check['generatorSha256']==mlz_ground['generatorSha256']
for name,info in mlz_ground['tiles'].items():assert digest(DATA/name)==info['sha256']==mlz_ground_check['tileSha256'][name]
for name,value in mlz_ground['materialHashes'].items():assert digest(SOURCE/'assets/textures/campus'/name)==value
atom=json.loads((DATA/'manifest.json').read_text())['architecture']['atomEi']
for path,key in [(SOURCE/atom['sourceFile'],'sourceSha256'),(ROOT/atom['generatorFile'],'generatorSha256'),(SOURCE/atom['referenceFile'],'referenceSha256'),(DATA/atom['derivedFile'],'derivedSha256'),(DATA/atom['meshFile'],'meshSha256'),(DATA/atom['roofFile'],'roofSha256')]:assert digest(path)==atom[key]
atom_check=json.loads((DATA/'atom-ei-validation.json').read_text())
assert atom_check['status'].startswith('PASS:')
assert atom_check['manifestSha256']==digest(DATA/'manifest.json')
assert atom_check['validatorSha256']==digest(ROOT/'scripts/validate-atom-ei.py')
assert atom_check['meshSha256']==atom['meshSha256'] and atom_check['roofSha256']==atom['roofSha256']
canopies=json.loads((DATA/'manifest.json').read_text())['architecture']['atomEiCanopies']
for path,key in [(SOURCE/canopies['sourceFile'],'sourceSha256'),(ROOT/canopies['generatorFile'],'generatorSha256'),(SOURCE/canopies['referenceFile'],'referenceSha256'),(DATA/canopies['derivedFile'],'derivedSha256')]:assert digest(path)==canopies[key]
canopy_check=json.loads((DATA/'atom-ei-canopies-validation.json').read_text())
assert canopy_check['status'].startswith('PASS:') and canopy_check['manifestSha256']==digest(DATA/'manifest.json')
assert canopy_check['validatorSha256']==digest(ROOT/'scripts/validate-atom-ei-canopies.py')
for building in json.loads((DATA/canopies['derivedFile']).read_text())['buildings']:assert digest(DATA/building['meshFile'])==building['meshSha256']
west=json.loads((DATA/'manifest.json').read_text())['architecture']['atomEiWestEntrance']
for path,key in [(SOURCE/west['sourceFile'],'sourceSha256'),(ROOT/west['generatorFile'],'generatorSha256'),(SOURCE/west['referenceFile'],'referenceSha256'),(DATA/west['derivedFile'],'derivedSha256'),(DATA/west['meshFile'],'meshSha256')]:assert digest(path)==west[key]
west_check=json.loads((DATA/'atom-ei-west-entrance-validation.json').read_text())
assert west_check['status'].startswith('PASS:') and west_check['manifestSha256']==digest(DATA/'manifest.json')
assert west_check['validatorSha256']==digest(ROOT/'scripts/validate-atom-ei-west-entrance.py')
assert west_check['meshSha256']==west['meshSha256']

reactor=json.loads((DATA/'manifest.json').read_text())['architecture']['reactorExterior']
for path,key in [(SOURCE/reactor['sourceFile'],'sourceSha256'),(ROOT/reactor['generatorFile'],'generatorSha256'),(SOURCE/reactor['referenceFile'],'referenceSha256'),(DATA/reactor['derivedFile'],'derivedSha256'),(DATA/reactor['meshFile'],'meshSha256'),(DATA/reactor['roofFile'],'roofSha256')]:assert digest(path)==reactor[key]
reactor_check=json.loads((DATA/'reactor-exterior-validation.json').read_text())
assert reactor_check['status'].startswith('PASS:') and reactor_check['manifestSha256']==digest(DATA/'manifest.json')
assert reactor_check['validatorSha256']==digest(ROOT/'scripts/validate-reactor-exterior.py')
assert reactor_check['meshSha256']==reactor['meshSha256'] and reactor_check['roofSha256']==reactor['roofSha256']

reactor_site=json.loads((DATA/'manifest.json').read_text())['architecture']['reactorSite']
for path,key in [(SOURCE/reactor_site['sourceFile'],'sourceSha256'),(ROOT/reactor_site['generatorFile'],'generatorSha256'),(DATA/reactor_site['derivedFile'],'derivedSha256'),(ROOT/'scripts/exterior_ground_extension.py','groundGeneratorSha256'),(ROOT/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(SOURCE/'vegetation-sources.json','vegetationSourceSha256')]:assert digest(path)==reactor_site[key] or (key=='groundGeneratorSha256' and ground_generator_matches(path,reactor_site[key]))
reactor_site_check=json.loads((DATA/'reactor-site-validation.json').read_text())
assert reactor_site_check['status'].startswith('PASS:') and reactor_site_check['manifestSha256']==digest(DATA/'manifest.json')
assert reactor_site_check['validatorSha256']==digest(ROOT/'scripts/validate-reactor-site.py')
for name,value in reactor_site_check['tileSha256'].items():assert digest(DATA/name)==value

landscape=json.loads((DATA/'manifest.json').read_text())['architecture']['utaLandscape']
for path,key in [(SOURCE/landscape['sourceFile'],'sourceSha256'),(ROOT/landscape['generatorFile'],'generatorSha256'),(DATA/landscape['derivedFile'],'derivedSha256'),(ROOT/'scripts/exterior_ground_extension.py','groundGeneratorSha256'),(ROOT/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(SOURCE/'vegetation-sources.json','vegetationSourceSha256')]:assert digest(path)==landscape[key]
landscape_check=json.loads((DATA/'uta-south-landscape-validation.json').read_text())
assert landscape_check['status'].startswith('PASS:') and landscape_check['manifestSha256']==digest(DATA/'manifest.json')
assert landscape_check['validatorSha256']==digest(ROOT/'scripts/validate-uta-landscape.py')
assert set(landscape_check['tileSha256'])==set(landscape['groundTiles']+landscape['treeTiles'])
for name,value in landscape_check['tileSha256'].items():assert digest(DATA/name)==value

reactor_east=json.loads((DATA/'manifest.json').read_text())['architecture']['reactorEast']
for path,key in [(SOURCE/reactor_east['sourceFile'],'sourceSha256'),(ROOT/reactor_east['generatorFile'],'generatorSha256'),(SOURCE/reactor_east['referenceFile'],'referenceSha256'),(DATA/reactor_east['derivedFile'],'derivedSha256'),(DATA/reactor_east['meshFile'],'meshSha256'),(DATA/reactor_east['roofFile'],'roofSha256')]:assert digest(path)==reactor_east[key]
reactor_east_check=json.loads((DATA/'reactor-east-validation.json').read_text())
assert reactor_east_check['status'].startswith('PASS:') and reactor_east_check['manifestSha256']==digest(DATA/'manifest.json')
assert reactor_east_check['validatorSha256']==digest(ROOT/'scripts/validate-reactor-east.py')
assert reactor_east_check['meshSha256']==reactor_east['meshSha256'] and reactor_east_check['roofSha256']==reactor_east['roofSha256']

uta=json.loads((DATA/'manifest.json').read_text())['architecture']['utaExterior']
for path,key in [(SOURCE/uta['sourceFile'],'sourceSha256'),(ROOT/uta['generatorFile'],'generatorSha256'),(SOURCE/uta['referenceFile'],'referenceSha256'),(DATA/uta['roofFile'],'roofSha256'),(DATA/uta['collisionFile'],'collisionSha256')]:assert digest(path)==uta[key]
uta_check=json.loads((DATA/'uta-exterior-validation.json').read_text())
assert uta_check['status'].startswith('PASS:') and uta_check['manifestSha256']==digest(DATA/'manifest.json')
assert uta_check['validatorSha256']==digest(ROOT/'scripts/validate-uta-exterior.py')
assert uta_check['roofSha256']==uta['roofSha256'] and uta_check['collisionSha256']==uta['collisionSha256']
uta_site=json.loads((DATA/'manifest.json').read_text())['architecture']['utaSite']
assert digest(DATA/uta_site['derivedFile'])==uta_site['derivedSha256']
assert digest(ROOT/'scripts/exterior_ground_extension.py')==uta_site['groundGeneratorSha256']
assert set(uta_check['groundTileSha256'])==set(uta_site['groundTiles'])
for name,value in uta_check['groundTileSha256'].items():assert digest(DATA/name)==value

court=json.loads((DATA/'manifest.json').read_text())['architecture']['galileoCourt']
assert hashlib.sha256((SOURCE/court['sourceFile']).read_bytes()).hexdigest()==court['sourceSha256']
facade=json.loads((DATA/'manifest.json').read_text())['architecture']['galileoFacade']
assert hashlib.sha256((SOURCE/facade['sourceFile']).read_bytes()).hexdigest()==facade['sourceSha256']
frontage=json.loads((DATA/'manifest.json').read_text())['frontageGrading']
assert hashlib.sha256((SOURCE/frontage['sourceFile']).read_bytes()).hexdigest()==frontage['sourceSha256']
ramps=json.loads((DATA/'manifest.json').read_text())['architecture']['galileoRamps']
assert hashlib.sha256((SOURCE/ramps['sourceFile']).read_bytes()).hexdigest()==ramps['sourceSha256']
mlz=json.loads((DATA/'manifest.json').read_text())['architecture']['mlzExteriors']
assert hashlib.sha256((SOURCE/mlz['sourceFile']).read_bytes()).hexdigest()==mlz['sourceSha256']
mlz_spec=json.loads((SOURCE/mlz['sourceFile']).read_text())
assert mlz_spec['fineCollisionMaterials']==[6,4,4,4,4]
mlz_tiles=[t for t in json.loads((DATA/'manifest.json').read_text())['tiles']if t.get('profile')=='mlz-exterior']
assert len(mlz_tiles)==3
for tile in mlz_tiles:assert tile['fineCollisionMaterials']==mlz_spec['fineCollisionMaterials']

siemensbau=json.loads((DATA/'manifest.json').read_text())['architecture']['siemensbauExterior']
assert hashlib.sha256((SOURCE/siemensbau['sourceFile']).read_bytes()).hexdigest()==siemensbau['sourceSha256']
rcm=json.loads((DATA/'manifest.json').read_text())['architecture']['rcmExterior']
assert hashlib.sha256((SOURCE/rcm['sourceFile']).read_bytes()).hexdigest()==rcm['sourceSha256']
physics=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsIExterior']
assert hashlib.sha256((SOURCE/physics['sourceFile']).read_bytes()).hexdigest()==physics['sourceSha256']
library=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsLibrary']
assert digest(SOURCE/library['sourceFile'])==library['sourceSha256']
assert digest(ROOT/library['generatorFile'])==library['generatorSha256']
library_spec=json.loads((SOURCE/library['sourceFile']).read_text())
assert digest(SOURCE/library_spec['reference'])==library_spec['referenceSha256']
library_check=json.loads((DATA/'physics-library-validation.json').read_text())
assert library_check['status'].startswith('PASS:')
assert library_check['manifestSha256']==digest(DATA/'manifest.json')
assert library_check['sourceSha256']==digest(SOURCE/library['sourceFile'])
assert library_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-library.py')
assert all(digest(DATA/name)==value for name,value in library_check['tileSha256'].items())
container=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsContainer']
assert digest(SOURCE/container['sourceFile'])==container['sourceSha256']
assert digest(ROOT/container['generatorFile'])==container['generatorSha256']
container_spec=json.loads((SOURCE/container['sourceFile']).read_text())
assert digest(SOURCE/container_spec['reference'])==container_spec['referenceSha256']
container_check=json.loads((DATA/'physics-container-validation.json').read_text())
assert container_check['status'].startswith('PASS:')
assert container_check['manifestSha256']==digest(DATA/'manifest.json')
assert container_check['sourceSha256']==digest(SOURCE/container['sourceFile'])
assert container_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-container.py')
assert all(digest(DATA/name)==value for name,value in container_check['tileSha256'].items())
p1=json.loads((DATA/'manifest.json').read_text())['architecture']['p1Complex']
assert digest(SOURCE/p1['sourceFile'])==p1['sourceSha256']
assert digest(ROOT/p1['generatorFile'])==p1['generatorSha256']
p1_spec=json.loads((SOURCE/p1['sourceFile']).read_text())
assert digest(SOURCE/p1_spec['reference'])==p1_spec['referenceSha256']
p1_check=json.loads((DATA/'p1-complex-validation.json').read_text())
assert p1_check['status'].startswith('PASS:')
assert p1_check['manifestSha256']==digest(DATA/'manifest.json')
assert p1_check['sourceSha256']==digest(SOURCE/p1['sourceFile'])
assert p1_check['validatorSha256']==digest(ROOT/'scripts/validate-p1-complex.py')
assert all(digest(DATA/name)==value for name,value in p1_check['tileSha256'].items())
woodland=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsWoodland']
assert digest(SOURCE/woodland['sourceFile'])==woodland['sourceSha256']
assert digest(ROOT/woodland['generatorFile'])==woodland['generatorSha256']
woodland_source=json.loads((SOURCE/woodland['sourceFile']).read_text())
assert digest(SOURCE/woodland_source['osm']['sourceFile'])==woodland_source['osm']['sha256']
assert digest(ROOT/'scripts/exterior_vegetation.py')==woodland['vegetationGeneratorSha256']
for key,path in [('coverageSha256',DATA/woodland['coverageFile']),('materialMaskSha256',SOURCE/woodland['materialMaskFile']),('materialDerivedSha256',DATA/woodland['materialDerivedFile'])]:assert digest(path)==woodland[key]
woodland_mapping=(SOURCE/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED WOODLAND GROUND MAPPING\n')[1].split('// END GENERATED WOODLAND GROUND MAPPING')[0]
assert hashlib.sha256(woodland_mapping.encode()).hexdigest()==woodland['shaderMappingSha256']
woodland_check=json.loads((DATA/'physics-woodland-validation.json').read_text())
assert woodland_check['status'].startswith('PASS:')
assert woodland_check['manifestSha256']==digest(DATA/'manifest.json')
assert woodland_check['sourceSha256']==woodland['sourceSha256']
assert woodland_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-woodland.py')
assert all(digest(DATA/name)==value for name,value in woodland_check['tileSha256'].items())
laboratory=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsNewLaboratory']
assert digest(SOURCE/laboratory['sourceFile'])==laboratory['sourceSha256']
assert digest(ROOT/laboratory['generatorFile'])==laboratory['generatorSha256']
laboratory_spec=json.loads((SOURCE/laboratory['sourceFile']).read_text())
assert digest(SOURCE/laboratory_spec['reference'])==laboratory_spec['referenceSha256']
laboratory_check=json.loads((DATA/'physics-new-laboratory-validation.json').read_text())
assert laboratory_check['status'].startswith('PASS:')
assert laboratory_check['manifestSha256']==digest(DATA/'manifest.json')
assert laboratory_check['sourceSha256']==laboratory['sourceSha256']
assert laboratory_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-new-laboratory.py')
assert set(laboratory_check['tileSha256'])=={laboratory['meshFile'],laboratory['roofFile'],*laboratory['groundTiles']}
assert all(digest(DATA/name)==value for name,value in laboratory_check['tileSha256'].items())
site=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsLaboratorySite']
assert digest(SOURCE/site['sourceFile'])==site['sourceSha256']
assert digest(ROOT/site['generatorFile'])==site['generatorSha256']
site_source=json.loads((SOURCE/site['sourceFile']).read_text())
assert digest(SOURCE/site_source['osm']['sourceFile'])==site_source['osm']['sha256']
assert digest(ROOT/'scripts/exterior_vegetation.py')==site['vegetationGeneratorSha256']
for key,path in [('coverageSha256',DATA/site['coverageFile']),('materialMaskSha256',SOURCE/site['materialMaskFile']),('materialDerivedSha256',DATA/site['materialDerivedFile'])]:assert digest(path)==site[key]
site_mapping=(SOURCE/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED LABORATORY SITE MAPPING\n')[1].split('// END GENERATED LABORATORY SITE MAPPING')[0]
assert hashlib.sha256(site_mapping.encode()).hexdigest()==site['shaderMappingSha256']
site_check=json.loads((DATA/'physics-laboratory-site-validation.json').read_text())
assert site_check['status'].startswith('PASS:')
assert site_check['manifestSha256']==digest(DATA/'manifest.json')
assert site_check['sourceSha256']==site['sourceSha256']
assert site_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-laboratory-site.py')
assert set(site_check['tileSha256'])==set(site['groundTiles']+site['treeTiles']+site['railingTiles'])
assert all(digest(DATA/name)==value for name,value in site_check['tileSha256'].items())
physics_ii=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsII']
assert digest(SOURCE/physics_ii['sourceFile'])==physics_ii['sourceSha256']
assert digest(ROOT/physics_ii['generatorFile'])==physics_ii['generatorSha256']
assert digest(ROOT/'scripts/exterior_vegetation.py')==physics_ii['vegetationGeneratorSha256']
assert digest(ROOT/'scripts/exterior_physics_ii_planting.py')==physics_ii['plantingGeneratorSha256']
physics_ii_spec=json.loads((SOURCE/physics_ii['sourceFile']).read_text())
assert digest(SOURCE/physics_ii_spec['reference'])==physics_ii_spec['referenceSha256']
assert digest(DATA/physics_ii['coverageFile'])==physics_ii['coverageSha256']
assert digest(SOURCE/physics_ii_spec['groundTransition']['sourceFile'])==physics_ii_spec['groundTransition']['sha256']
assert digest(DATA/physics_ii_spec['groundTransition']['sourceFile'])==physics_ii_spec['groundTransition']['sha256']
assert digest(ROOT/physics_ii['landscapeGeneratorFile'])==physics_ii['landscapeGeneratorSha256']
for key,path in [('materialMaskSha256',SOURCE/physics_ii['materialMaskFile']),('materialDerivedSha256',DATA/physics_ii['materialDerivedFile'])]:assert digest(path)==physics_ii[key]
physics_ii_mapping=(SOURCE/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED PHYSICS II SITE MAPPING\n')[1].split('// END GENERATED PHYSICS II SITE MAPPING')[0]
assert hashlib.sha256(physics_ii_mapping.encode()).hexdigest()==physics_ii['shaderMappingSha256']
for source in physics_ii_spec['landscape']['osm']:assert digest(SOURCE/source['sourceFile'])==source['sha256']
for body in physics_ii_spec['bodies']:
 if 'osmReference'in body:assert digest(SOURCE/body['osmReference']['sourceFile'])==body['osmReference']['sha256']
physics_ii_check=json.loads((DATA/'physics-ii-validation.json').read_text())
assert physics_ii_check['status'].startswith('PASS:')
assert physics_ii_check['manifestSha256']==digest(DATA/'manifest.json')
assert physics_ii_check['sourceSha256']==physics_ii['sourceSha256']
assert physics_ii_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-ii.py')
assert set(physics_ii_check['tileSha256'])==set(physics_ii['groundTiles']+physics_ii['treeTiles']+physics_ii['shrubTiles']+[b[key]for b in physics_ii['bodies']for key in ['meshFile','roofFile']])
assert all(digest(DATA/name)==value for name,value in physics_ii_check['tileSha256'].items())
wsi=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsWSI']
wsi_spec=json.loads((SOURCE/wsi['sourceFile']).read_text())
assert digest(SOURCE/wsi['sourceFile'])==wsi['sourceSha256']
assert digest(SOURCE/wsi_spec['reference'])==wsi_spec['referenceSha256']
for path,key in [(ROOT/wsi['generatorFile'],'generatorSha256'),(ROOT/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(ROOT/'scripts/exterior_physics_ii.py','transitionGeneratorSha256'),(ROOT/'scripts/exterior_physics_ii_landscape.py','canopyGeneratorSha256')]:assert digest(path)==wsi[key]
assert digest(DATA/wsi['coverageFile'])==wsi['coverageSha256']
assert wsi['groundTransition']==wsi_spec['groundTransition']
assert digest(SOURCE/wsi_spec['groundTransition']['sourceFile'])==wsi_spec['groundTransition']['sha256']
assert digest(DATA/wsi_spec['groundTransition']['sourceFile'])==wsi_spec['groundTransition']['sha256']
assert wsi['northLandscapeBoundary']==wsi_spec['northLandscapeBoundary']
for item in wsi_spec['northLandscapeBoundary']['osm']:
 assert digest(SOURCE/item['sourceFile'])==item['sha256']
 assert digest(DATA/item['sourceFile'])==item['sha256']
pinned_water=json.loads((DATA/'manifest.json').read_text())['pinnedWater']
assert pinned_water['sourceSha256']==digest(SOURCE/pinned_water['sourceFile'])
assert pinned_water['generatorSha256']==digest(ROOT/pinned_water['generatorFile'])
assert pinned_water['osm']==wsi_spec['northLandscapeBoundary']['osm']
assert len(pinned_water['features'])==1 and pinned_water['features'][0]['id']=='way/'+wsi_spec['northLandscapeBoundary']['riverWay']
water_check=json.loads((DATA/'pinned-water-validation.json').read_text())
assert water_check['status'].startswith('PASS:')
assert water_check['manifestSha256']==digest(DATA/'manifest.json')
assert water_check['sourceSha256']==pinned_water['sourceSha256']
assert water_check['generatorSha256']==pinned_water['generatorSha256']
assert water_check['validatorSha256']==digest(ROOT/'scripts/validate-pinned-water.py')
wsi_check=json.loads((DATA/'physics-wsi-validation.json').read_text())
assert wsi_check['status'].startswith('PASS:')
assert wsi_check['manifestSha256']==digest(DATA/'manifest.json')
assert wsi_check['sourceSha256']==wsi['sourceSha256']
assert wsi_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-wsi.py')
assert set(wsi_check['tileSha256'])==set(wsi['groundTiles']+wsi['treeTiles']+[wsi['meshFile'],wsi['roofFile']])
assert all(digest(DATA/name)==value for name,value in wsi_check['tileSha256'].items())
znn=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsZNN']
znn_spec=json.loads((SOURCE/znn['sourceFile']).read_text())
assert digest(SOURCE/znn['sourceFile'])==znn['sourceSha256']
assert digest(SOURCE/znn_spec['reference'])==znn_spec['referenceSha256']
for path,key in [(ROOT/znn['generatorFile'],'generatorSha256'),(ROOT/znn['landscapeGeneratorFile'],'landscapeGeneratorSha256'),(ROOT/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(ROOT/'scripts/exterior_physics_ii.py','transitionGeneratorSha256'),(ROOT/'scripts/exterior_physics_wsi.py','wsiTransitionGeneratorSha256'),(ROOT/'scripts/exterior_physics_ii_landscape.py','canopyGeneratorSha256')]:assert digest(path)==znn[key]
assert digest(DATA/znn['coverageFile'])==znn['coverageSha256']
znn_check=json.loads((DATA/'physics-znn-validation.json').read_text())
assert znn_check['status'].startswith('PASS:')
assert znn_check['manifestSha256']==digest(DATA/'manifest.json')
assert znn_check['sourceSha256']==znn['sourceSha256']
assert znn_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-znn.py')
assert set(znn_check['tileSha256'])==set(znn['groundTiles']+znn['treeTiles']+[znn['meshFile'],znn['roofFile']])
assert all(digest(DATA/name)==value for name,value in znn_check['tileSha256'].items())
znn_west=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsZNNWest']
znn_west_spec=json.loads((SOURCE/znn_west['sourceFile']).read_text())
assert digest(SOURCE/znn_west['sourceFile'])==znn_west['sourceSha256']
assert digest(ROOT/znn_west['generatorFile'])==znn_west['generatorSha256']
assert digest(ROOT/'scripts/exterior_foundation_collar.py')==znn_west['collarGeneratorSha256']
assert digest(SOURCE/znn_west_spec['osm']['sourceFile'])==znn_west_spec['osm']['sha256']
assert digest(DATA/znn_west['coverageFile'])==znn_west['coverageSha256']
znn_west_check=json.loads((DATA/'physics-znn-west-validation.json').read_text())
assert znn_west_check['status'].startswith('PASS:')
assert znn_west_check['manifestSha256']==digest(DATA/'manifest.json')
assert znn_west_check['sourceSha256']==znn_west['sourceSha256']
assert znn_west_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-znn-west.py')
assert set(znn_west_check['tileSha256'])==set(znn_west['groundTiles']+[znn_west['meshFile'],znn_west['roofFile']])
assert all(digest(DATA/name)==value for name,value in znn_west_check['tileSha256'].items())
cala=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsCALA']
assert digest(SOURCE/cala['sourceFile'])==cala['sourceSha256']
assert digest(ROOT/cala['generatorFile'])==cala['generatorSha256']
assert ground_generator_matches(ROOT/'scripts/exterior_ground_extension.py',cala['groundGeneratorSha256'])
cala_check=json.loads((DATA/'physics-cala-validation.json').read_text())
assert cala_check['status'].startswith('PASS:')
assert cala_check['manifestSha256']==digest(DATA/'manifest.json')
assert cala_check['sourceSha256']==cala['sourceSha256']
assert cala_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-cala.py')
assert set(cala_check['tileSha256'])==set(cala['groundTiles']+cala['site']['treeTiles']+[cala['meshFile'],cala['roofFile']])
assert all(digest(DATA/name)==value for name,value in cala_check['tileSha256'].items())
assert digest(ROOT/'scripts/exterior_cala_site.py')==cala['site']['siteGeneratorSha256']
assert digest(ROOT/'scripts/exterior_cala_trees.py')==cala['site']['smallTreeGeneratorSha256']
assert digest(SOURCE/cala['site']['osmFile'])==cala['site']['osmSha256']
assert digest(SOURCE/cala['site']['materialFile'])==cala['site']['materialSha256']
assert digest(DATA/cala['site']['materialFeaturesFile'])==cala['site']['materialFeaturesSha256']
lmu=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsLMU']
assert digest(SOURCE/lmu['sourceFile'])==lmu['sourceSha256']
assert digest(ROOT/lmu['generatorFile'])==lmu['generatorSha256']
assert ground_generator_matches(ROOT/'scripts/exterior_ground_extension.py',lmu['groundGeneratorSha256'])
lmu_check=json.loads((DATA/'physics-lmu-validation.json').read_text())
assert lmu_check['status'].startswith('PASS:')
assert lmu_check['manifestSha256']==digest(DATA/'manifest.json')
assert lmu_check['sourceSha256']==lmu['sourceSha256']
assert lmu_check['validatorSha256']==digest(ROOT/'scripts/validate-physics-lmu.py')
assert set(lmu_check['tileSha256'])==set(lmu['groundTiles']+[lmu['meshFile'],lmu['roofFile']])
assert all(digest(DATA/name)==value for name,value in lmu_check['tileSha256'].items())
lmu_courtyard=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsLMUCourtyard']
assert digest(SOURCE/lmu_courtyard['sourceFile'])==lmu_courtyard['sourceSha256']
for path,key in [(ROOT/lmu_courtyard['generatorFile'],'generatorSha256'),(ROOT/'scripts/exterior_ground_extension.py','groundGeneratorSha256'),(ROOT/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(SOURCE/'vegetation-sources.json','vegetationSourceSha256')]:assert digest(path)==lmu_courtyard[key] or (key=='groundGeneratorSha256' and ground_generator_matches(path,lmu_courtyard[key]))
assert digest(DATA/lmu_courtyard['coverageFile'])==lmu_courtyard['coverageSha256']
lc_check=json.loads((DATA/'lmu-courtyard-validation.json').read_text())
assert lc_check['status'].startswith('PASS:') and lc_check['manifestSha256']==digest(DATA/'manifest.json')
assert lc_check['sourceSha256']==lmu_courtyard['sourceSha256'] and lc_check['validatorSha256']==digest(ROOT/'scripts/validate-lmu-courtyard.py')
assert set(lc_check['tileSha256'])==set(lmu_courtyard['groundTiles']+lmu_courtyard['treeTiles']+[lmu_courtyard['coverageFile']])
assert all(digest(DATA/name)==value for name,value in lc_check['tileSha256'].items())
lmu_east=json.loads((DATA/'manifest.json').read_text())['architecture']['physicsLMUEast']
lmu_east_spec=json.loads((SOURCE/lmu_east['sourceFile']).read_text())
assert digest(SOURCE/lmu_east['sourceFile'])==lmu_east['sourceSha256']
assert digest(SOURCE/lmu_east_spec['osm']['sourceFile'])==lmu_east_spec['osm']['sha256']
for path,key in [(ROOT/lmu_east['generatorFile'],'generatorSha256'),(ROOT/'scripts/exterior_ground_extension.py','groundGeneratorSha256'),(ROOT/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(SOURCE/'vegetation-sources.json','vegetationSourceSha256')]:assert digest(path)==lmu_east[key] or (key=='groundGeneratorSha256' and ground_generator_matches(path,lmu_east[key]))
assert digest(DATA/lmu_east['coverageFile'])==lmu_east['coverageSha256']
le_check=json.loads((DATA/'lmu-east-validation.json').read_text())
assert le_check['status'].startswith('PASS:') and le_check['manifestSha256']==digest(DATA/'manifest.json')
assert le_check['sourceSha256']==lmu_east['sourceSha256'] and le_check['validatorSha256']==digest(ROOT/'scripts/validate-lmu-east.py')
assert le_check['rawInputs']['minecraft/exterior/checks/lmu-east-ground-rays.json']==digest(SOURCE/'checks/lmu-east-ground-rays.json')
assert set(le_check['tileSha256'])==set(lmu_east['groundTiles']+lmu_east['treeTiles']+[lmu_east['meshFile'],lmu_east['roofFile'],lmu_east['coverageFile']])
assert all(digest(DATA/name)==value for name,value in le_check['tileSha256'].items())
riverbank=json.loads((DATA/'manifest.json').read_text())['architecture']['riverbank']
riverbank_spec=json.loads((SOURCE/riverbank['sourceFile']).read_text())
assert digest(SOURCE/riverbank['sourceFile'])==riverbank['sourceSha256']
for path,key in [(ROOT/riverbank['generatorFile'],'generatorSha256'),(ROOT/'scripts/exterior_vegetation.py','vegetationGeneratorSha256'),(ROOT/'scripts/exterior_physics_ii.py','transitionGeneratorSha256'),(ROOT/'scripts/exterior_physics_wsi.py','wsiTransitionGeneratorSha256'),(ROOT/'scripts/exterior_physics_ii_landscape.py','canopyGeneratorSha256')]:assert digest(path)==riverbank[key]
assert digest(DATA/riverbank['coverageFile'])==riverbank['coverageSha256']
for source in riverbank_spec['osm']:
 assert digest(SOURCE/source['sourceFile'])==source['sha256']
 assert digest(DATA/source['sourceFile'])==source['sha256']
assert pinned_water['features'][0]['surveyGround']==riverbank['waterGround']
assert riverbank['sourceRetirement'][-1]['kind']=='water-channel'
assert riverbank['sourceRetirement'][-1]['rings']==riverbank['waterGround']['rings']
riverbank_check=json.loads((DATA/'riverbank-validation.json').read_text())
assert riverbank_check['status'].startswith('PASS:')
assert riverbank_check['manifestSha256']==digest(DATA/'manifest.json')
assert riverbank_check['sourceSha256']==riverbank['sourceSha256']
assert riverbank_check['validatorSha256']==digest(ROOT/'scripts/validate-riverbank.py')
assert set(riverbank_check['tileSha256'])==set(riverbank['groundTiles']+riverbank['treeTiles'])
assert all(digest(DATA/name)==value for name,value in riverbank_check['tileSha256'].items())
restoration=json.loads((DATA/'manifest.json').read_text())['groundRestoration']
assert digest(SOURCE/restoration['sourceFile'])==restoration['sourceSha256']==digest(DATA/restoration['sourceFile'])
assert digest(ROOT/restoration['generatorFile'])==restoration['generatorSha256']
restoration_check=json.loads((DATA/'courtyard-ground-validation.json').read_text())
assert restoration_check['status'].startswith('PASS:')
assert restoration_check['manifestSha256']==digest(DATA/'manifest.json')
assert restoration_check['policySha256']==restoration['sourceSha256']
assert restoration_check['validatorSha256']==digest(ROOT/'scripts/validate-courtyard-ground.py')
assert restoration_check['independentPolicyValidatorSha256']==digest(ROOT/'scripts/validate_ground_restoration.py')
north=json.loads((DATA/'manifest.json').read_text())['northGroundMaterials']
for key,folder in [('generator',ROOT),('classificationGenerator',ROOT),('source',SOURCE),('previousDerived',DATA),('derived',DATA),('mask',SOURCE)]:
 assert digest(folder/north[key+'File'])==north[key+'Sha256']
for name,value in north['coverageFiles'].items():assert digest(DATA/name)==value
north_mapping=(SOURCE/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED NORTH GROUND MAPPING\n')[1].split('// END GENERATED NORTH GROUND MAPPING')[0]
assert hashlib.sha256(north_mapping.encode()).hexdigest()==north['shaderMappingSha256']
north_check=json.loads((DATA/'north-ground-validation.json').read_text())
assert north_check['status'].startswith('PASS:')
assert north_check['manifestSha256']==digest(DATA/'manifest.json')
assert north_check['validatorSha256']==digest(ROOT/'scripts/validate-north-ground.py')
assert north_check['maskSha256']==north['maskSha256']
reactor_ground=json.loads((DATA/'manifest.json').read_text())['architecture']['reactorGroundMaterials']
for key,folder in [('source',SOURCE),('research',SOURCE),('generator',ROOT),('mask',SOURCE),('derived',DATA),('sharedMaterial',SOURCE),('courtyardSource',SOURCE)]:
 assert digest(folder/reactor_ground[key+'File'])==reactor_ground[key+'Sha256']
assert digest(ROOT/'.cache'/reactor_ground['courtyardAerialCacheFile'])==reactor_ground['courtyardAerialSha256']
reactor_ground_mapping=(SOURCE/'shaders/campus_ground.fsh').read_text().split('// BEGIN GENERATED REACTOR GROUND MAPPING\n')[1].split('// END GENERATED REACTOR GROUND MAPPING')[0]
assert hashlib.sha256(reactor_ground_mapping.encode()).hexdigest()==reactor_ground['shaderMappingSha256']
for name in ('campus_ground.fsh','campus_reflection.fsh'):
 text=(SOURCE/'shaders'/name).read_text()
 assert text.split('// BEGIN GENERATED REACTOR GROUND MAPPING\n')[1].split('// END GENERATED REACTOR GROUND MAPPING')[0]==reactor_ground_mapping
 assert text.split('// BEGIN SHARED REACTOR MATERIAL\n')[1].split('// END SHARED REACTOR MATERIAL')[0]==(SOURCE/reactor_ground['sharedMaterialFile']).read_text()

reactor_ground_check=json.loads((DATA/'reactor-ground-validation.json').read_text())
assert reactor_ground_check['status'].startswith('PASS:')
assert reactor_ground_check['manifestSha256']==digest(DATA/'manifest.json')
assert reactor_ground_check['validatorSha256']==digest(ROOT/'scripts/validate-reactor-ground.py')
assert reactor_ground_check['maskSha256']==reactor_ground['maskSha256']
terrace=json.loads((DATA/'manifest.json').read_text())['architecture']['mensaTerrace']
terrace_check=json.loads((DATA/'mensa-terrace-validation.json').read_text())
assert terrace_check['status'].startswith('PASS:')
assert terrace_check['manifestSha256']==digest(DATA/'manifest.json')
assert terrace_check['validatorSha256']==digest(ROOT/'scripts/validate-mensa-terrace.py')
assert terrace['sourceSha256']==terrace_check['sourceSha256']==digest(SOURCE/terrace['sourceFile'])
assert terrace['generatorSha256']==terrace_check['generatorSha256']==digest(ROOT/terrace['generatorFile'])
assert terrace['roofSha256']==terrace_check['roofSha256']==digest(DATA/terrace['roofFile'])
assert terrace['atlasSha256']==terrace_check['atlasSha256']==digest(DATA/terrace['atlasFile'])
assert terrace['collisionSha256']==terrace_check['collisionSha256']==digest(DATA/terrace['collisionFile'])
assert terrace['collisionHeightfieldParts']==terrace_check['collisionHeightfieldParts']==[2]
for name,value in terrace_check['rawInputs'].items():assert digest(ROOT/'.cache'/name)==value
subprocess.run(['python3',str(ROOT/'scripts/validate-foliage-rendering.py'),'--directory',str(DATA)],env={**os.environ,'JAVA_HOME':args.java_home},check=True)
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
# The fine wood proxy retains the original wood model, drops and tool category.
resources=work/'mod/src/main/resources'
for folder in ['assets/earthcraft/blockstates','data/earthcraft/loot_table/blocks']:
 shutil.copy2(resources/folder/'map_wood.json',resources/folder/'campus_wood.json')
axe=resources/'data/minecraft/tags/block/mineable/axe.json';axe_data=json.loads(axe.read_text())
if 'earthcraft:campus_wood' not in axe_data['values']:axe_data['values'].append('earthcraft:campus_wood')
axe.write_text(json.dumps(axe_data)+'\n')
# Fine surveyed solids retain their original drops, pickaxe tag and cut material.
for material in ['stone','plaster']:
 for folder in ['assets/earthcraft/blockstates','data/earthcraft/loot_table/blocks']:
  shutil.copy2(resources/folder/('map_'+material+'.json'),resources/folder/('campus_'+material+'.json'))
pickaxe=resources/'data/minecraft/tags/block/mineable/pickaxe.json';pickaxe_data=json.loads(pickaxe.read_text())
for material in ['stone','plaster']:
 if 'earthcraft:campus_'+material not in pickaxe_data['values']:pickaxe_data['values'].append('earthcraft:campus_'+material)
pickaxe.write_text(json.dumps(pickaxe_data)+'\n')

shader=work/'mod/src/main/resources/assets/realworldmc/shaders/core';shader.mkdir(parents=True,exist_ok=True)
for p in (SOURCE/'shaders').glob('*'):shutil.copy2(p,shader/p.name)
env=dict(os.environ,JAVA_HOME=str(Path(args.java_home).resolve()))
subprocess.run(['bash',str(work/'mod/gradlew'),'-p',str(work/'mod'),'remapJar','--console=plain'],env=env,check=True)
compiled=work/'mod/build/libs/realworldmc-1.0.3.jar'
if not compiled.is_file():raise SystemExit('Expected remapped release JAR missing.')
manifest=json.loads((DATA/'manifest.json').read_text())
notices='''Minecampus exterior modifications and provenance

LMU physics/workshop complex: BVV LoD2 envelope and DOP20 roof. Concrete
frames and recessed facade subdivisions are estimated from the NavigaTUM
Alexander Pach photograph and the MGK CALA project street view. No reference
photograph pixels are redistributed. Sources and qualifications: physics-lmu.json.

LMU outdoor courtyard: BVV LoD2 courtyard ring, DGM1/DOP20 ground and
DOM20/DOP20 fitted tree crowns. Branches and species appearance are estimates;
leaf/bark atlases are the pinned Poly Haven CC0 assets. Physics-lmu-courtyard.json
records scope; the building interiors are not reconstructed.

LMU east service building and mapped access ground: BVV LoD2/DGM1/DOP20
and OpenStreetMap contributors (ODbL 1.0). Roof and ground pixels are BVV;
facade finishes and path widths are estimates. DOM20 fits the nearby crown;
branches/species are estimated with pinned Poly Haven CC0 atlases. Scope and
source references: physics-lmu-east.json. No interior is reconstructed.

CALA main volume: BVV LoD2 walls, DOP20 green roof and DGM1 north/east
slope. Openings, canopies, finishes and geometric markings are approximate
interpretations of the official exterior photograph linked in physics-cala.json.
Reference-photo pixels are not bundled. Adjacent survey volumes are preserved.
West ZNN service building: BVV LoD2 envelope and DOP20 roof; two tank
silhouettes estimated from DOM20/DGM1, with approximate finishes and caps.
OSM service compound by OpenStreetMap contributors, ODbL1.0; see
physics-znn-west.json and physics-znn-west-osm.xml. Unresolved equipment retained.
WSI riverbanks: BVV DGM1/DOP20/DOM20 bank terrain and estimated crowns;
pinned OSM river and wooden footbridge geometry. Native water uses a
DGM-guided elevation estimate, not surveyed bathymetry. Corridor extent,
bridge guards, tree species and crown shape are estimates. Channel cleanup
retains bridge geometry and native fluid. See riverbank.json and riverbank-osm.xml.

ZNN / TUM5115: BVV surveyed envelope, stepped roof, DOP20 roof pixels and
DGM1 approach terrain. Recessed window bands, projecting shading rails, pale
cladding and the ochre south panel are qualified estimates from exterior
references. Tree placement follows public DOP20/DOM20/DGM1; crowns and species
are estimates. No interiors or reference-photo pixels. See physics-znn.json
and physics-znn-reference.json.

Physik II / TUM5107: BVV surveyed main, stair and bridge envelopes and original
DOP20 roof pixels. Recessed windows, silver panels, bridge clearance and facade
details are source-informed estimates. Courtyard shrubs use DOP20 colour and
DOM20/DGM1 height bounds; species and foliage form are estimated with CC0
Poly Haven textures. No interiors or provider pixels. See physics-ii.json
and physics-ii-reference.json.

The WSI exterior preserves BVV wall planes, including the thin roof-edge strip,
and original roof geometry with public DOP20 roof imagery. Window tiers and
projecting frames are estimates informed by TUM exterior photographs and private
source review; no reference pixels are bundled. Surrounding terrain and tree
positions/heights use BVV DGM1/DOM20/DOP20. Tree forms and species are inferred.
An estimated 2.5 m outer terrain shoulder joins sampled retained source heights,
with prior terrain and unresolved samples protected by a bounded fade.
See physics-wsi.json and physics-wsi-reference.json. No interiors.

The expanded Physik II landscape follows OSM parking, grass and footway
boundaries (ODbL 1.0, © OpenStreetMap contributors) and BVV DGM1 heights.
Verge widths are inferred; enclosed ground continuity follows the separately
documented BVV aerial-source controls. Gravel finish
on the new parking ground is inferred from a nearby pebblestone aisle and
aerial appearance; generic gravel_ground_01 scan by Rob Tuytel / Poly Haven,
CC0 1.0, https://polyhaven.com/a/gravel_ground_01, at three-metre scale.
Mapped and low-raster vegetation retain priority over the inferred aggregate.

Laboratory west site: BVV DGM1 ground and DOP20 imagery, preserving prior
terrain and building/bridge footprints. OSM paths, grass and railing alignment
are ODbL 1.0, © OpenStreetMap contributors. Untagged widths, railing dimensions
and tree forms are estimates. See physics-laboratory-site.json.

Campus-side woodland: BVV DGM1 ground, DOP20 imagery and DOM20 canopy.
The mapped Garchinger Mühlbach bank bounds this extension; river water and
neighbour footprints remain excluded. OSM land cover and paths are ODbL 1.0,
© OpenStreetMap contributors. Tree forms, species appearance, path widths
without tags and woodland floor materials are estimates. See physics-woodland.json.

P1 garage / TUM 5142 and adjoining service building: surveyed envelopes and
DOP20 roofs retained. Concrete decks, metal grid and recessed exterior bays
are source-informed estimates; no interiors or provider/contractor pixels.
The footprint guard and bounded aprons use DGM1 with estimated paving.
See p1-complex.json and p1-complex-reference.json.
TUM5117 uses the BVV surveyed envelope and roof, with estimated galvanized panels,
recessed glazing and physical fins informed by Cukrowicz Nachbaur project photographs.
Photograph pixels are not included. Finished grade and hidden details are unverified.
See physics-new-laboratory.json and physics-new-laboratory-reference.json.

Physics container / TUM 5140: BVV eight-face envelope and six original roof
triangles with DOP20 imagery. Pale modular cladding and paired windows are
source-informed estimates; hidden details remain unresolved. No interiors or
provider pixels. See physics-container.json and physics-container-reference.json.

Physics library annex: BVV upper envelope and DOP20 roof; open undercroft,
glazed facade, concrete piers, tapered edge and louvres informed by historical
TUM architectural reference. Dimensions, materials and hidden elevations are
estimated; no interiors or reference pixels. See physics-library.json and
physics-library-reference.json. External staircase detail remains unresolved.

Physics I / TUM 5101: survey envelope, three courtyards and roof geometry;
DGM1/DOP20 ground and DOM20-supported canopy extend beyond the old boundary.
Facade bays, fins, recesses and branch/species appearance are estimates.
No interiors or provider source imagery. See physics-i-5101.json.
Laboratory galvanized material: Sisters.seamless, CC0 1.0.
https://commons.wikimedia.org/wiki/File:Light_grey_galvanized_slightly_scuffed_dirty_seamless_metal_steel_texture.jpg
JPEG decoded to RGB PNG unchanged. Generic photographed material, not a campus
sample. Source size is unknown; 1 m repeat and facade colour are estimates.

Physics I concrete micro-material: Poly Haven granular_concrete, CC0 1.0;
Michael Jenkins (photography), Dario Barresi (processing).
https://polyhaven.com/a/granular_concrete — sampled at its 2.4 m scan scale.
Diffuse grain is normalized to an estimated facade colour. It is not a
photograph or measured material sample of the Physics I building.

RCM-Technikum / TUM 5104: surveyed five-face envelope and stepped roof retained.
Individual dark source features guide estimated windows/vents; obscured details,
materials, divisions and recess dimensions remain unresolved or inferred.
No interiors or provider source imagery. See rcm-technikum-5104.json.

Siemensbau / TUM 5103: surveyed envelope and orthophoto roof retained.
North opening groups follow locally observed provider photography; obscured
north/south openings, end divisions, materials and recesses remain estimates.
The public package includes no provider image or source tile for this study.
No interiors. See siemensbau-5103.json for qualifications and observations.

MLZ UYW/UYL exteriors: BVV survey envelopes and roof geometry retained.
Per-face openings, panel joints and recesses inferred from official state
building office photographs and FRM II / TUM video. References are research
only and are not redistributed as textures. Exact dimensions and unobserved
faces remain estimates. No interiors. See mlz-exteriors.json.

Galileo east ramps: exterior runs follow OSM driveways and pinned BVV DGM1
profiles. Width, retaining walls, caps and shallow portal recesses are inferred
from DOP20 and the SLAM site plan; no underground interior is reconstructed.
See galileo-east-ramps.json and galileo-east-ramp-reference.json.

Galileo western frontage: three small source-terrain depressions replaced by
two bounded paving grades inferred from surrounding BVV DGM1 controls.
BVV DOP20 and SLAM landscape references support continuous paving; fitted
levels are a reconstruction, not a new survey. See galileo-frontage-grade.json.

Galileo north sunken courtyard: OSM ways 579584070, 983606071 and 983606072
(ODbL 1.0), BVV DGM1 floor/landing heights (CC BY 4.0). Wall thickness,
parapets, five-flight arrangement, handrails, lower glazing and pavement
are inferred exterior geometry. Landscape references: SLAM Schaar
Landschaftsarchitekten; completed photo credited to Realotel Garching
Hotelbetriebs GmbH. Reference photographs are not redistributed or used
as game textures. See galileo-north-court-reference.json for provenance.

RealWorldMC 1.0.3 by Teddy563 and contributors: Apache-2.0.
Pinned source: https://github.com/Teddy563/realworldmc/tree/6f18d1f3ba5a02dadee4b14bcb96578bf3941d13
Minecampus modifications: https://github.com/DocMorphic/minecampus

Terrain DGM1, DOP20 orthophotos, and LoD2 building geometry:
© Bayerische Vermessungsverwaltung, https://geodaten.bayern.de/ (CC BY 4.0).
Cropped to the Garching campus, reprojected, meshed and combined with photographs.
Height transformation grid GCG2016: © GeoBasis-DE / BKG 2023 (CC BY 4.0).
Grid distribution: https://cdn.proj.org/de_bkg_gcg2016.tif
License: https://creativecommons.org/licenses/by/4.0/

Galileo facade: BVV surveyed wall/roof geometry (CC BY 4.0), with inferred
1.4m panel modules, recessed glazing, smooth powder-coated metal and slim
ventilation fins. Contractor Dobler Metallbau project sheet HGG_dt_web.pdf
(issue 2022-02-28, photographs Sergej Chernoisikow); architect Nickl & Partner;
completed-site landscape photo from SLAM / Realotel Garching Hotelbetriebs GmbH.
These are research references only; no copyrighted reference pixels are
redistributed or used as textures. Floor heights and panel/window sequences
are estimates, not an as-built window schedule. Roof imagery is unchanged.
See galileo-facade-reference.json. The earlier MaxEmanuel CC0 repeated strip
has been retired from the two Galileo tiles.

MW concrete photographic material: Renardo la vulpo (CC BY-SA 4.0).
https://commons.wikimedia.org/wiki/File:Garching,_Eberhard-von-Kuenheim-Bau,_2.jpeg
https://creativecommons.org/licenses/by-sa/4.0/
Cropped concrete surface; window and louvre layout reconstructed on BVV survey envelopes.
The combined MW mesh/material adaptation is supplied under CC BY-SA 4.0.

Vegetation positions/heights: BVV DOM20/DGM1/DOP20 (CC BY 4.0).
Ground/concrete micro-material colour/normal maps: Poly Haven concrete_wall_007 and grass_ground (CC0 1.0).
https://polyhaven.com/a/concrete_wall_007
https://polyhaven.com/a/grass_ground
Ground surface boundaries: © OpenStreetMap contributors (ODbL 1.0).
https://www.openstreetmap.org/copyright
Selected mapped polygons and their tags are included as ground-surfaces.geojson.
The reactor/UTA material overlay uses pinned OSM paths and lawns with explicit
width and paving estimates from BVV DOP20 inspection. Its source, derived
polygons and validation are included as reactor-ground-*.json/geojson. It
replaces photographic cars/shadows only on classified surveyed ground.

Physics I's supplemental ground map is included as physics-ground-source.geojson
and physics-ground-surfaces.geojson. OSM lawn polygons and ground-level paths
are clipped away from surveyed building footprints. Untagged path widths are
explicit estimates, not surveyed curbs. The material map does not change terrain.
It overlaps the old terrain seam by 20 metres and blends over the outer 8 metres
of its study boundary, retaining the original ground material outside coverage.
Mapped woodland uses a generic leaf-litter/soil material as an appearance
estimate: the OSM canopy tag does not establish the actual forest-floor cover.
Mapped paths and lawns take precedence wherever they overlap the canopy.
Explicit-width road/path source lines and derived strips are included as
path-widths.json and path-surfaces.geojson (ODbL 1.0), with building and mapped-area exclusions.
Promenade paths without width tags use explicitly estimated widths/offsets from
BVV DOP20 orthophotos (CC BY 4.0), with the mapped OSM asphalt classification.
Source: promenade-paths.json; derived corridors: promenade-surfaces.geojson.
Existing mapped areas take priority. A documented 20 cm texture margin beneath
surveyed facades prevents bright sampling seams; geometry and collision remain unchanged.
Material boundaries use 4x area coverage to reduce visible raster steps.
Eight asphalt cross-path/entrance corridors use separately inferred BVV widths
and offsets with OSM alignment/classification. Existing materials and complete
building footprints take priority. Source: crosspaths.json; derived polygons:
crosspath-surfaces.geojson. Dimensions are estimates, not a path-width survey.
COS completed-site map lines and furniture positions: © OpenStreetMap contributors.
Source and derived surfaces: cos-site.json and cos-site-surfaces.geojson (ODbL 1.0).
Path widths, apron infill, bench dimensions/supports and rack arrangement are
approximate reconstructions; the mapped bicycle capacity implies ten stands.
Bench timber reuses the credited Alexander Pach COS photograph (CC BY 4.0).
Thin rack tubes are decorative; benches retain collision.
Asphalt detail: Poly Haven asphalt_04 by Jenelle van Heerden and Sergej Majboroda (CC0).
https://polyhaven.com/a/asphalt_04
The material is approximate; it is not a scan of the campus roads.
The derived surface database/mask is available under ODbL 1.0; material grain
and paving joints are approximate reconstructions, not measured paving units.
Planting-bed soil: Poly Haven brown_mud_leaves_01 by Rob Tuytel (CC0 1.0).
https://polyhaven.com/a/brown_mud_leaves_01
Approximate leaf/soil material; not a scan of the campus planting bed.
COS landscape infill follows 2021 design context and current mapped anchors;
its boundaries are inferred, not an as-built survey. Source qualifications
are included in cos-site.json.
Warehouse masonry: Poly Haven brick_wall_001 by Dimitrios Savva and Rob Tuytel (CC0 1.0).
https://polyhaven.com/a/brick_wall_001
Colour and repeat scale adapted; an approximate material, not the actual building surface.

Leaf and bark atlases: Poly Haven jacaranda_tree (CC0 1.0).
https://polyhaven.com/a/jacaranda_tree
Reconstructed branch placement and artistic foliage, not surveyed tree species.

IAS facade material: High Contrast (CC BY 3.0 DE).
https://commons.wikimedia.org/wiki/File:TU_M%C3%BCnchen_Garching_-_Institute_for_Advanced_Study.jpg
https://creativecommons.org/licenses/by/3.0/de/
Cropped metal/glass material; surveyed envelope with reconstructed atrium,
folding screens and terrace based on the architect's project reference.

COS timber photograph: Alexander Pach / NavigaTUM (CC BY 4.0).
https://nav.tum.de/building/cos
https://nav.tum.de/cdn/lg/5132_0.webp
https://creativecommons.org/licenses/by/4.0/
An unobstructed patch is rectified, resized and repeated at an estimated scale.
The BVV envelope and roof are retained; window dimensions, rear elevations and
finished-site grading are approximate reconstructions, not measured as-built data.
Source provenance is supplied as cos-reference.json.

GRS north-wing exterior: BVV survey envelope with estimated curtain-wall
frames and fascia extrapolated from historical Detlef Schreiber context
photographs. Unsupported braces are omitted. Reference photographs/drawings
are not included in this package.
https://claudia-schreiber-architektur.de/projekte/neubau-buero-und-laborgebaeude-ii-garching
Colours, frame dimensions and less-visible elevations are inferred.
Source qualifications are supplied as grs-reference.json.

GRS stair tower and connectors: BVV survey envelopes and orthophoto roofs,
with glazing, pale walls, louvres and a courtyard door informed by the same
historical architect reference. Dimensions, colours, door placement and bridge
glazing are inferred. No interiors or reference photographs are included.
Source qualifications are supplied as grs-connectors-reference.json.

GRS II rectangular wing: complete BVV envelope with recessed glazing, pale
fascia and upper braces informed by the matching architect plan and photographs.
Frame dimensions, colours and hidden elevations remain estimated. The exact
surveyed orthophoto roof is retained; the missing west exterior is repaired.
Source qualifications are supplied as grs-main-reference.json.

GRS III exterior: survey geometry and orthophoto roof, with facade character
referenced from Claudia Schreiber Architektur
https://claudia-schreiber-architektur.de/projekte/neubau-buero-und-laborgebaeude-iii-garching
Historical reference photographs and drawings are not redistributed.
Source qualifications are supplied as grs-iii-reference.json.
The small GRS II/III connector and inferred courtyard approach use the same
architectural context; additional qualifications are in grs-courtyard-reference.json.

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
    s=s.replace("import { TileClient } from './tiles.mjs';","import { TileClient, sampleColor } from './tiles.mjs';")
    s=s.replace(needle,needle+'''
  const exteriorDir=path.join(here,'minecampus-exterior');
  if(fs.existsSync(path.join(exteriorDir,'manifest.json'))){
    const {attachSurveySurface}=await import('./minecampus-survey.mjs');
    attachSurveySurface(service,exteriorDir,{voxelizeArea,collectRegionTiles,mcPositions,sampleColor});
  }''')
    needle="        case '/render/tile': {";assert s.count(needle)==1
    s=s.replace(needle,'''        case '/campus/collision': {
          if(!service.campusCollision)return json(res,{error:'Survey collision data unavailable'},404);
          const frame=service.frame(num(q,'lat'),num(q,'lon'),num(q,'h'));
          const collision=q.get('wood')==='1'?service.campusCollisionPacket:service.campusCollision;
          const bytes=collision(frame,num(q,'cx'),num(q,'cz'),num(q,'minY'),num(q,'height'));
          res.writeHead(200,{'content-type':'application/octet-stream','content-length':bytes.length});return res.end(bytes);
        }
'''+needle);data=s.encode()
   if entry.filename=='src/voxel.mjs':data=patch_voxel(data.decode()).encode()
   write(target,entry.filename,data)
  write(target,'src/terrain-column.mjs',(SOURCE/'service/terrain-column.mjs').read_bytes())
  write(target,'src/water-survey.mjs',(SOURCE/'service/water-survey.mjs').read_bytes())
  write(target,'src/source-retirement.mjs',(SOURCE/'service/source-retirement.mjs').read_bytes())
  write(target,'src/solid-shapes.mjs',(SOURCE/'service/solid-shapes.mjs').read_bytes())
  write(target,'src/wood-shapes.mjs',(SOURCE/'service/wood-shapes.mjs').read_bytes())
  write(target,'src/collision-packet.mjs',(SOURCE/'service/collision-packet.mjs').read_bytes())
  write(target,'src/minecampus-survey.mjs',(SOURCE/'service/survey-surface.mjs').read_bytes())
  write(target,'src/photo-facades.mjs',(SOURCE/'service/photo-facades.mjs').read_bytes())
  write(target,'src/supplemental-surfaces.mjs',(SOURCE/'service/supplemental-surfaces.mjs').read_bytes())
  write(target,'src/minecampus-exterior/'+terrace['sourceFile'],(SOURCE/terrace['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/mensa-terrace-validation.json',(DATA/'mensa-terrace-validation.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-i-5101.json',(SOURCE/'physics-i-5101.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-i-reference.json',(SOURCE/'photos/physics-i-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-ii.json',(SOURCE/'physics-ii.json').read_bytes())
  write(target,'src/minecampus-exterior/'+physics_ii_spec['groundTransition']['sourceFile'],(SOURCE/physics_ii_spec['groundTransition']['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/physics-ii-reference.json',(SOURCE/'photos/physics-ii-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-ii-parking-osm.xml',(SOURCE/'physics-ii-parking-osm.xml').read_bytes())
  for body in physics_ii_spec['bodies']:
   if 'osmReference'in body:write(target,'src/minecampus-exterior/'+body['osmReference']['sourceFile'],(SOURCE/body['osmReference']['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+physics_ii['coverageFile'],(DATA/physics_ii['coverageFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+physics_ii['materialDerivedFile'],(DATA/physics_ii['materialDerivedFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+north['derivedFile'],(DATA/north['derivedFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+riverbank['sourceFile'],(SOURCE/riverbank['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+riverbank['coverageFile'],(DATA/riverbank['coverageFile']).read_bytes())
  for source in riverbank_spec['osm']:write(target,'src/minecampus-exterior/'+source['sourceFile'],(SOURCE/source['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+lmu['sourceFile'],(SOURCE/lmu['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+lmu_east['sourceFile'],(SOURCE/lmu_east['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+lmu_east['coverageFile'],(DATA/lmu_east['coverageFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+lmu_east_spec['osm']['sourceFile'],(SOURCE/lmu_east_spec['osm']['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+lmu_courtyard['sourceFile'],(SOURCE/lmu_courtyard['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+lmu_courtyard['coverageFile'],(DATA/lmu_courtyard['coverageFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+cala['sourceFile'],(SOURCE/cala['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+cala['site']['osmFile'],(SOURCE/cala['site']['osmFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+cala['site']['materialFeaturesFile'],(DATA/cala['site']['materialFeaturesFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+znn_west['sourceFile'],(SOURCE/znn_west['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+znn_west['coverageFile'],(DATA/znn_west['coverageFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+znn_west_spec['osm']['sourceFile'],(SOURCE/znn_west_spec['osm']['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/physics-znn.json',(SOURCE/znn['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/physics-znn-reference.json',(SOURCE/znn_spec['reference']).read_bytes())
  write(target,'src/minecampus-exterior/'+znn['coverageFile'],(DATA/znn['coverageFile']).read_bytes())
  write(target,'src/minecampus-exterior/physics-wsi.json',(SOURCE/wsi['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/'+wsi_spec['groundTransition']['sourceFile'],(SOURCE/wsi_spec['groundTransition']['sourceFile']).read_bytes())
  for item in wsi_spec['northLandscapeBoundary']['osm']:write(target,'src/minecampus-exterior/'+item['sourceFile'],(SOURCE/item['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/physics-wsi-reference.json',(SOURCE/wsi_spec['reference']).read_bytes())
  write(target,'src/minecampus-exterior/'+wsi['coverageFile'],(DATA/wsi['coverageFile']).read_bytes())
  write(target,'src/minecampus-exterior/physics-new-laboratory.json',(SOURCE/'physics-new-laboratory.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-new-laboratory-reference.json',(SOURCE/'photos/physics-new-laboratory-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-laboratory-site.json',(SOURCE/'physics-laboratory-site.json').read_bytes())
  write(target,'src/minecampus-exterior/'+site_source['osm']['sourceFile'],(SOURCE/site_source['osm']['sourceFile']).read_bytes())
  for key in ['coverageFile','materialDerivedFile']:write(target,'src/minecampus-exterior/'+site[key],(DATA/site[key]).read_bytes())
  write(target,'src/minecampus-exterior/physics-woodland.json',(SOURCE/'physics-woodland.json').read_bytes())
  write(target,'src/minecampus-exterior/'+woodland_source['osm']['sourceFile'],(SOURCE/woodland_source['osm']['sourceFile']).read_bytes())
  for key in ['coverageFile','materialDerivedFile']:write(target,'src/minecampus-exterior/'+woodland[key],(DATA/woodland[key]).read_bytes())
  write(target,'src/minecampus-exterior/p1-complex.json',(SOURCE/'p1-complex.json').read_bytes())
  write(target,'src/minecampus-exterior/p1-complex-reference.json',(SOURCE/'photos/p1-complex-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-container.json',(SOURCE/'physics-container.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-container-reference.json',(SOURCE/'photos/physics-container-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-library.json',(SOURCE/'physics-library.json').read_bytes())
  write(target,'src/minecampus-exterior/physics-library-reference.json',(SOURCE/'photos/physics-library-reference.json').read_bytes())
  if manifest.get('photoFacades'):
   for name in [manifest['photoFacades']['file'],*manifest['photoFacades']['roofFiles'],*[t['file']for t in manifest['photoFacades']['collisionTiles']]]:
    assert Path(name).name==name
    write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/manifest.json',(DATA/'manifest.json').read_bytes())
  write(target,'src/minecampus-exterior/'+restoration['sourceFile'],(DATA/restoration['sourceFile']).read_bytes())
  write(target,'src/minecampus-exterior/foliage-rendering.json',(SOURCE/'foliage-rendering.json').read_bytes())
  write(target,'src/minecampus-exterior/NOTICE.txt',notices.encode())
  write(target,'src/minecampus-exterior/cos-reference.json',(SOURCE/'photos/cos-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/grs-reference.json',(SOURCE/'photos/grs-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/grs-connectors-reference.json',(SOURCE/'photos/grs-connectors-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/grs-main-reference.json',(SOURCE/'photos/grs-main-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/grs-iii-reference.json',(SOURCE/'photos/grs-iii-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/grs-courtyard-reference.json',(SOURCE/'photos/grs-courtyard-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/galileo-north-court-reference.json',(SOURCE/'photos/galileo-north-court-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/galileo-facade-reference.json',(SOURCE/'photos/galileo-facade-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/galileo-frontage-grade.json',(SOURCE/'galileo-frontage-grade.json').read_bytes())
  write(target,'src/minecampus-exterior/mlz-exteriors.json',(SOURCE/'mlz-exteriors.json').read_bytes())
  write(target,'src/minecampus-exterior/mlz-courtyard-ground.json',(SOURCE/'mlz-courtyard-ground.json').read_bytes())
  for name in ['mlz-courtyard-ground-surfaces.json','mlz-courtyard-ground-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/atom-ei-canopies.json',(SOURCE/'atom-ei-canopies.json').read_bytes())
  write(target,'src/minecampus-exterior/atom-ei-canopies-reference.json',(SOURCE/'photos/atom-ei-canopies-reference.json').read_bytes())
  for name in ['atom-ei-canopy-surfaces.json','atom-ei-canopies-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/atom-ei-west-entrance.json',(SOURCE/'atom-ei-west-entrance.json').read_bytes())
  write(target,'src/minecampus-exterior/atom-ei-entrances-reference.json',(SOURCE/'photos/atom-ei-entrances-reference.json').read_bytes())
  for name in ['atom-ei-west-entrance-surfaces.json','atom-ei-west-entrance-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/reactor-east.json',(SOURCE/'reactor-east.json').read_bytes())
  write(target,'src/minecampus-exterior/uta-exterior.json',(SOURCE/'uta-exterior.json').read_bytes())
  write(target,'src/minecampus-exterior/reactor-south-exterior-research.json',(SOURCE/'photos/reactor-south-exterior-research.json').read_bytes())
  write(target,'src/minecampus-exterior/uta-exterior-validation.json',(DATA/'uta-exterior-validation.json').read_bytes())
  write(target,'src/minecampus-exterior/uta-site-surfaces.json',(DATA/'uta-site-surfaces.json').read_bytes())
  for name in ['reactor-ground-surfaces.geojson','reactor-ground-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/reactor-ground-surfaces.json',(SOURCE/'reactor-ground-surfaces.json').read_bytes())
  write(target,'src/minecampus-exterior/reactor-courtyard-materials.geojson',(SOURCE/'reactor-courtyard-materials.geojson').read_bytes())
  write(target,'src/minecampus-exterior/reactor-approach-ground-research.json',(SOURCE/'photos/reactor-approach-ground-research.json').read_bytes())
  write(target,'src/minecampus-exterior/reactor-east-exterior-research.json',(SOURCE/'photos/reactor-east-exterior-research.json').read_bytes())
  for name in ['reactor-east-surfaces.json','reactor-east-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/uta-south-landscape.json',(SOURCE/'uta-south-landscape.json').read_bytes())
  for name in ['uta-south-landscape-surfaces.json','uta-south-landscape-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/reactor-site.json',(SOURCE/'reactor-site.json').read_bytes())
  for name in ['reactor-site-surfaces.json','reactor-site-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/reactor-exterior.json',(SOURCE/'reactor-exterior.json').read_bytes())
  write(target,'src/minecampus-exterior/reactor-exterior-research.json',(SOURCE/'photos/reactor-exterior-research.json').read_bytes())
  for name in ['reactor-surfaces.json','reactor-exterior-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/atom-ei.json',(SOURCE/'atom-ei.json').read_bytes())
  write(target,'src/minecampus-exterior/atom-ei-exterior-research.json',(SOURCE/'photos/atom-ei-exterior-research.json').read_bytes())
  for name in ['atom-ei-surfaces.json','atom-ei-validation.json']:
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
  write(target,'src/minecampus-exterior/siemensbau-5103.json',(SOURCE/'siemensbau-5103.json').read_bytes())
  write(target,'src/minecampus-exterior/rcm-technikum-5104.json',(SOURCE/'rcm-technikum-5104.json').read_bytes())
  write(target,'src/minecampus-exterior/rcm-technikum-reference.json',(SOURCE/'photos/rcm-technikum-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/galileo-east-neighbours-reference.json',(SOURCE/'photos/galileo-east-neighbours-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/galileo-east-ramps.json',(SOURCE/'galileo-east-ramps.json').read_bytes())
  write(target,'src/minecampus-exterior/galileo-east-ramp-reference.json',(SOURCE/'photos/galileo-east-ramp-reference.json').read_bytes())
  write(target,'src/minecampus-exterior/cos-site.json',(SOURCE/'cos-site.json').read_bytes())
  write(target,'src/minecampus-exterior/cos-site-surfaces.geojson',(DATA/'cos-site-surfaces.geojson').read_bytes())
  write(target,'src/minecampus-exterior/grs-courtyard-surfaces.geojson',(DATA/'grs-courtyard-surfaces.geojson').read_bytes())
  write(target,'src/minecampus-exterior/sources.json',(SOURCE/'sources.json').read_bytes())
  write(target,'src/minecampus-exterior/vegetation-sources.json',(SOURCE/'vegetation-sources.json').read_bytes())
  write(target,'src/minecampus-exterior/ground-surfaces.geojson',(SOURCE/'ground-surfaces.geojson').read_bytes())
  write(target,'src/minecampus-exterior/physics-ground-source.geojson',(SOURCE/'physics-ground-surfaces.geojson').read_bytes())
  write(target,'src/minecampus-exterior/physics-ground-surfaces.geojson',(DATA/'physics-ground-surfaces.geojson').read_bytes())
  write(target,'src/minecampus-exterior/path-widths.json',(SOURCE/'path-widths.json').read_bytes())
  write(target,'src/minecampus-exterior/crosspaths.json',(SOURCE/'crosspaths.json').read_bytes())
  write(target,'src/minecampus-exterior/crosspath-surfaces.geojson',(DATA/'crosspath-surfaces.geojson').read_bytes())
  write(target,'src/minecampus-exterior/promenade-paths.json',(SOURCE/'promenade-paths.json').read_bytes())
  write(target,'src/minecampus-exterior/promenade-surfaces.geojson',(DATA/'promenade-surfaces.geojson').read_bytes())
  write(target,'src/minecampus-exterior/path-surfaces.geojson',(DATA/'path-surfaces.geojson').read_bytes())
  for asset in manifest['tiles']:
   name=asset['file'];assert Path(name).name==name and name.endswith('.ect')
   write(target,'src/minecampus-exterior/'+name,(DATA/name).read_bytes())
 bundle=patched.getvalue()
 # Check the exact unpacker source compiled above; a valid ZIP can still exceed
 # its runtime extraction guard and fail before a fresh world loads.
 unpacker=(work/'mod/src/main/java/dev/realworldmc/BundledService.java').read_text()
 limit_match=re.search(r'MAX_UNPACKED_BYTES = (\d+)L \* 1024 \* 1024;',unpacker)
 if not limit_match:raise SystemExit('Cannot establish bundled service extraction limit.')
 bundle_limit=int(limit_match.group(1))*1024*1024
 with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
  unpacked_bytes=sum(entry.file_size for entry in archive.infolist())
  if unpacked_bytes>bundle_limit:raise SystemExit(f'Service needs {unpacked_bytes} unpacked bytes; runtime limit is {bundle_limit}.')
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
report={'file':target.name,'size':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'sourceCommit':upstream['commit'],'sourcePatchSha256':hashlib.sha256(inputs[0].read_bytes()).hexdigest(),'rendererSourceFingerprint':fingerprint,'bundleSha256':hashlib.sha256(bundle).hexdigest(),'tiles':len(manifest['tiles'])}
report['bundleUnpackedBytes']=unpacked_bytes;report['bundleUnpackedLimit']=bundle_limit
(OUT/'exterior-release.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

from pathlib import Path
import json,shutil,subprocess
root=Path.cwd();base=root/'.cache/exterior-release-check';qa=root/'.cache/exterior-reflection-check';exp=root/'minecraft/exterior/experiments/reflections';run=qa/'run-campus-check'
qa.mkdir(exist_ok=True);run.mkdir(exist_ok=True)
for name in ['settings.gradle','gradle.properties']:shutil.copy2(base/name,qa/name)
for name in ['config','saves']:
 if not (run/name).exists():subprocess.run(['cp','-cR',str(base/'run-campus-check'/name),str(run/name)],check=True)
if (base/'run-campus-check/options.txt').exists() and not (run/'options.txt').exists():shutil.copy2(base/'run-campus-check/options.txt',run/'options.txt')
service=run/'realworldmc-service';service.mkdir(exist_ok=True)
if not (service/'config.json').exists():shutil.copy2(base/'run-campus-check/realworldmc-service/config.json',service/'config.json')
# Keep private settings local. Rewrite only a copied service-directory path if explicit.
p=run/'config/realworldmc.json';config=json.loads(p.read_text())
for key,value in config.items():
 if isinstance(value,str) and str(base) in value:config[key]=value.replace(str(base),str(qa))
p.write_text(json.dumps(config,indent=2)+'\n')
meta=json.loads((root/'dist-minecraft/exterior-release.json').read_text());bundle=meta['bundleSha256'];dest=service/'.bundles'/bundle;dest.parent.mkdir(exist_ok=True)
if not dest.exists():subprocess.run(['cp','-cR',str(base/'run-campus-check/realworldmc-service/.bundles'/bundle),str(dest)],check=True)
src=qa/'src/main/java/dev/realworldmc/client';src.mkdir(parents=True,exist_ok=True)
for p in (root/'minecraft/exterior/checks').glob('*.java'):shutil.copy2(p,src/p.name)
p=src/'CampusExteriorCheck.java';p.write_text(p.read_text().replace('CampusMaterialBenchmark.tick(mc)','CampusReflectionBenchmark.tick(mc)'))
for p in exp.glob('*.java'):shutil.copy2(p,src/p.name)
res=qa/'src/main/resources';res.mkdir(parents=True,exist_ok=True)
mod={'schemaVersion':1,'id':'minecampus-reflection-check','version':'1.0.0','environment':'client','entrypoints':{'client':['dev.realworldmc.client.CampusExteriorCheck','dev.realworldmc.client.CampusReflectionTrial']},'depends':{'realworldmc':'>=1.0.3'}}
(res/'fabric.mod.json').write_text(json.dumps(mod,indent=2)+'\n')
shaders=res/'assets/realworldmc/shaders/core';shaders.mkdir(parents=True,exist_ok=True)
base_shader=json.loads((root/'minecraft/exterior/shaders/campus_ground.json').read_text())
spec={'vertex':'realworldmc:campus_reflection','fragment':'realworldmc:campus_reflection','samplers':[{'name':'Sampler0'}],'attributes':['Position','UV0'],'uniforms':[u for u in base_shader['uniforms']if u['name']in ['ModelViewMat','ProjMat','TileAnchor']]+[{'name':name,'type':'float','count':len(values),'values':values}for name,values in [('ClipPlane',[0,0,0,0]),('AlphaCutoff',[.1]),('WorldLight',[1.]),('SunDirection',[0,1,0]),('ReflectedEye',[0,0,0])]]}
(exp/'campus_reflection.json').write_text(json.dumps(spec,indent=2)+'\n')
for p in exp.glob('campus_reflection.*'):shutil.copy2(p,shaders/p.name)
pack=run/'resourcepacks/campus-planar-reflection';out=pack/'assets/realworldmc/shaders/core';out.mkdir(parents=True,exist_ok=True)
(pack/'pack.mcmeta').write_text(json.dumps({'pack':{'pack_format':34,'description':'Isolated planar campus reflection experiment'}}))
base_shader['uniforms'].append({'name':'PlanarTexture','type':'int','count':1,'values':[12]})
base_shader['uniforms'] += [{'name':'PlanarMatrix','type':'matrix4x4','count':16,'values':[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]},{'name':'PlanarPlane','type':'float','count':4,'values':[0,0,0,0]},{'name':'PlanarStrength','type':'float','count':1,'values':[0]}]
(out/'campus_ground.json').write_text(json.dumps(base_shader,indent=2)+'\n')
shader=(root/'minecraft/exterior/shaders/campus_ground.fsh').read_text();shader=shader.replace('void main() {','uniform sampler2D PlanarTexture;\nuniform mat4 PlanarMatrix;\nuniform vec4 PlanarPlane;\nuniform float PlanarStrength;\n\nvoid main() {')
needle='            glazing=mix(glazing,color.rgb*(.82+.18*diffuse),.45*(1.0-.45*fresnel));';assert shader.count(needle)==1
shader=shader.replace(needle,needle+'\n'+(exp/'reflection_receive.glsl').read_text())
shader=shader.replace('void main() {','void main() {\n    vec3 planarRadiance=vec3(0); float planarWeight=0.;')
# Reflected radiance has its own sky/world illumination; do not shadow the
# reflected sky with the pane's surface shadow or dim the night sky twice.
shader=shader.replace('    color*=ColorModulator;','    color*=ColorModulator;\n    color.rgb=mix(color.rgb,planarRadiance,planarWeight);')
(out/'campus_ground.fsh').write_text(shader)
(root/'.cache/reflection-candidate-shader.fsh').write_text(shader)
build=(base/'build.gradle').read_text().split('loom { runs')[0]
build+='''
loom { runs { client { client(); runDir 'run-campus-check'; vmArg '-Xmx6G'; vmArg '-Dminecampus.checkWorld=campus-check-margin'; vmArg '-Dminecampus.inspectOnly=true'; vmArg '-Dminecampus.inspectStage=42'; vmArg '-Dminecampus.materialBenchmark=true'; programArg '--width'; programArg '1280'; programArg '--height'; programArg '720'; } } }
tasks.named('runClient') {
 doFirst { delete file('run-campus-check/campus-reflection-benchmark.json') }
 doLast { assert file('run-campus-check/campus-reflection-benchmark.json').text.contains('PASS:') }
}
'''
(qa/'build.gradle').write_text(build)
print('Isolated reflection project prepared; user installations and production inputs unchanged.')

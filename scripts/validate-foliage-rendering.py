#!/usr/bin/env python3
"""Exercise the production Java leaf mapper against every generated vegetation tile."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory',type=Path,default=root/'dist-minecraft/exterior')
out = parser.parse_args().directory.resolve()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = read(out/'manifest.json')
policy = root/'minecraft/exterior/foliage-rendering.json'
helper = root/'minecraft/exterior/client/CampusFoliage.java'
upload = root/'minecraft/exterior/client/CampusFoliageTextures.java'
check = root/'minecraft/exterior/tests/FoliageCheck.java'
scale = re.search(r'ATLAS_METRES = ([0-9.]+)',helper.read_text())
assert scale and float(scale[1]) == read(policy)['atlasMetres']
files = [out/t['file'] for t in manifest['tiles'] if t['kind']=='vegetation']
assert files
home = os.environ.get('JAVA_HOME')
java = str(Path(home)/'bin/java') if home else shutil.which('java')
javac = str(Path(home)/'bin/javac') if home else shutil.which('javac')
assert java and javac, 'A JDK is required for native foliage validation'
with tempfile.TemporaryDirectory(prefix='foliage-check-',dir=root/'.cache') as temp:
    folder = Path(temp)
    (folder/'files.txt').write_text('\n'.join(t['kind']+'|'+str(t['runtimeId'])+'|'+str(out/t['file']) for t in manifest['tiles'])+'\n')
    subprocess.run([javac,'-d',str(folder),str(helper),str(check)],check=True)
    result = subprocess.run([java,'-cp',str(folder),'FoliageCheck',str(folder/'files.txt')],text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    assert result.stdout.splitlines()[-1].startswith('PASS groups=')
record = {'status':'PASS: physical UV scale, contained planar patches, unchanged input, cutout mip coverage and colour filtering; native appearance unverified',
          'manifestSha256':sha(out/'manifest.json'),'policySha256':sha(policy),
          'helperSha256':sha(helper),'uploadSha256':sha(upload),'checkSha256':sha(check),
          'validatorSha256':sha(Path(__file__)),'renderGroups':len(files),
          'tileSha256':{p.name:sha(p) for p in files},'measurements':result.stdout.splitlines()}
(out/'foliage-rendering-validation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='tileSha256'},indent=2))

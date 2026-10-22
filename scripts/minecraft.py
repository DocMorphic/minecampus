#!/usr/bin/env python3
"""Build/import an actual Minecraft Java pack; never packages game assets or credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / 'minecraft/dependencies.json').read_text())
OUTPUT = ROOT / 'dist-minecraft'
CACHE = ROOT / '.cache/native-downloads'
INSTANCE = ROOT / '.minecampus/java'
PACK_VERSION = SPEC.get('pack-version', '0.3.0')
PROFILE_ID = f"fabric-loader-{SPEC['fabric-loader']}-{SPEC['minecraft']}"


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Minecampus/0.3.0 (DocMorphic/minecampus)'})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def get_json(url):
    return json.loads(fetch(url))


def dependency(spec):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / Path(spec['path']).name
    algorithm = 'sha256' if 'sha256' in spec else 'sha512'
    expected = spec[algorithm]
    def valid():
        return path.is_file() and path.stat().st_size == spec['size'] and hashlib.new(algorithm, path.read_bytes()).hexdigest() == expected
    if not valid():
        print(f"Downloading {path.name}", flush=True)
        payload = fetch(spec['url'])
        if len(payload) != spec['size'] or hashlib.new(algorithm, payload).hexdigest() != expected:
            raise RuntimeError(f"Integrity check failed: {path.name}")
        path.write_bytes(payload)
    return path


def zip_bytes(archive, name, payload):
    entry = zipfile.ZipInfo(name, date_time=(2026, 10, 20, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(entry, payload)


def addon():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f'minecampus-{PACK_VERSION}.jar'
    source = ROOT / 'minecraft/campus'
    with zipfile.ZipFile(target, 'w') as archive:
        for file in sorted(source.rglob('*')):
            if file.is_file():
                zip_bytes(archive, file.relative_to(source).as_posix(), file.read_bytes())
        zip_bytes(archive, 'LICENSE', (ROOT / 'minecraft/LICENSE').read_bytes())
    return target


def build():
    campus = addon()
    # Fetch and check every dependency now, so an emitted pack has verified hashes.
    index_files = []
    for spec in SPEC['files']:
        payload = dependency(spec).read_bytes()
        index_files.append({
            'path': spec['path'], 'fileSize': len(payload),
            'hashes': {alg: hashlib.new(alg, payload).hexdigest() for alg in ('sha1', 'sha512')},
            'downloads': [spec['url']], 'env': {'client': 'required', 'server': 'required'},
        })
    index = {
        'formatVersion': 1, 'game': 'minecraft', 'versionId': PACK_VERSION,
        'name': 'Minecampus — actual Minecraft at TUM Garching',
        'summary': 'Minecraft Java 1.21.1 + Fabric + RealWorldMC. Own game account and map access required.',
        'dependencies': {key: SPEC[key] for key in ('minecraft', 'fabric-loader')},
        'files': index_files,
    }
    target = OUTPUT / f'Minecampus-{PACK_VERSION}-mc1.21.1.mrpack'
    with zipfile.ZipFile(target, 'w') as archive:
        zip_bytes(archive, 'modrinth.index.json', json.dumps(index, indent=2).encode())
        zip_bytes(archive, 'overrides/mods/' + campus.name, campus.read_bytes())
        zip_bytes(archive, 'overrides/config/realworldmc.json', (ROOT / 'minecraft/config/realworldmc.json').read_bytes())
        zip_bytes(archive, 'overrides/options.txt', b'renderClouds:"false"\n')
        zip_bytes(archive, 'overrides/MINECAMPUS-README.md', (ROOT / 'minecraft/README.md').read_bytes())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.mrpack.sha256').write_text(f'{digest}  {target.name}\n')
    print(f'Built {target}')
    return campus


def launcher_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/minecraft'
    if sys.platform == 'win32':
        return Path(os.environ['APPDATA']) / '.minecraft'
    return Path.home() / '.minecraft'


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as output:
        json.dump(value, output, indent=2)
        temporary = Path(output.name)
    temporary.replace(path)


def quality():
    """Prioritize local scan detail without touching credentials or saved collision chunks."""
    path = INSTANCE / 'realworldmc-service/config.json'
    config = json.loads(path.read_text()) if path.exists() else {}
    if path.exists():
        backup = path.with_name('config.before-campus-quality.json')
        if not backup.exists():
            shutil.copy2(path, backup)
            backup.chmod(0o600)
    config['render'] = {
        **config.get('render', {}),
        **json.loads((ROOT / 'minecraft/config/terrain-quality.json').read_text()),
    }
    atomic_json(path, config)
    options=INSTANCE/'options.txt'
    lines=options.read_text().splitlines() if options.exists() else []
    lines=[line for line in lines if not line.startswith('renderClouds:')]
    lines.append('renderClouds:"false"')
    options.write_text('\n'.join(lines)+'\n')
    print('Applied local-detail terrain settings: 2px error target, 1 km radius, 1,200 tile budget; clear campus sky.')
    print('Saved collision geometry and provider credentials are preserved. No provider requests made.')
    print('Fully quit Minecraft and relaunch the Minecampus installation to apply. Keep your existing world.')


def install(launcher):
    campus = build()
    INSTANCE.mkdir(parents=True, exist_ok=True)
    mods=INSTANCE/'mods';mods.mkdir(parents=True,exist_ok=True)
    prepared=[(dependency(spec),INSTANCE/spec['path']) for spec in SPEC['files']]+[(campus,mods/campus.name)]
    expected={target for _,target in prepared}
    def retire(file):
        import uuid
        backup=INSTANCE/'retired-mods';backup.mkdir(exist_ok=True)
        name=hashlib.sha256(file.read_bytes()).hexdigest()[:12]+'-'+file.name
        target=backup/name
        if target.exists():target=backup/(uuid.uuid4().hex[:8]+'-'+name)
        file.replace(target)
    # Prepare all new files before retiring either of the two owned mod ids.
    staged=[]
    for source,target in prepared:
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest():continue
        temporary=target.with_suffix('.jar.pending');shutil.copy2(source,temporary);staged.append((temporary,target))
    for file in mods.glob('*.jar'):
        if file in expected:continue
        try:
            with zipfile.ZipFile(file) as archive:mod=json.loads(archive.read('fabric.mod.json')).get('id')
        except (OSError,zipfile.BadZipFile,KeyError,ValueError):continue
        if mod in {'realworldmc','minecampus'}:retire(file)
    for temporary,target in staged:
        if target.exists():retire(target)
        temporary.replace(target)
    if not (INSTANCE/'options.txt').exists():(INSTANCE/'options.txt').write_text('renderClouds:"false"\n')
    config_path = INSTANCE / 'config/realworldmc.json'
    if not config_path.exists():
        config = json.loads((ROOT / 'minecraft/config/realworldmc.json').read_text())
        # Finder-launched apps often have no Homebrew PATH. Store this machine's executable.
        node = shutil.which('node')
        if not node:
            raise RuntimeError('Install Node.js 22+ before installing the native profile.')
        major = int(subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')[0])
        if major < 22:
            raise RuntimeError('Node.js 22+ is required by the map service.')
        config['nodeExecutable'] = node
        atomic_json(config_path, config)

    # Official version metadata only. The official launcher downloads/authenticates the game.
    version_dir = launcher / 'versions' / PROFILE_ID
    version_dir.mkdir(parents=True, exist_ok=True)
    loader = get_json(f"https://meta.fabricmc.net/v2/versions/loader/{SPEC['minecraft']}/{SPEC['fabric-loader']}/profile/json")
    if loader.get('id') != PROFILE_ID or loader.get('inheritsFrom') != SPEC['minecraft']:
        raise RuntimeError('Unexpected Fabric profile metadata')
    atomic_json(version_dir / f'{PROFILE_ID}.json', loader)
    manifest = get_json('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json')
    base = next(v for v in manifest['versions'] if v['id'] == SPEC['minecraft'])
    payload = fetch(base['url'])
    if hashlib.sha1(payload).hexdigest() != base['sha1']:
        raise RuntimeError('Minecraft version metadata integrity check failed')
    base_dir = launcher / 'versions' / SPEC['minecraft']
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / f"{SPEC['minecraft']}.json").write_bytes(payload)

    profile_path = launcher / 'launcher_profiles.json'
    profiles = json.loads(profile_path.read_text()) if profile_path.exists() else {'profiles': {}, 'settings': {}}
    if profile_path.exists():
        # Preserve the original and any existing installation settings. No account data is printed.
        backup = launcher / 'launcher_profiles.before-minecampus.json'
        if not backup.exists():
            shutil.copy2(profile_path, backup)
    profiles.setdefault('profiles', {})['minecampus-java'] = {
        **profiles.get('profiles', {}).get('minecampus-java', {}),
        'name': 'Minecampus — TUM Garching', 'type': 'custom',
        'lastVersionId': PROFILE_ID, 'gameDir': str(INSTANCE),
        'javaArgs': '-Xmx6G -Xms1G -XX:+UseG1GC', 'icon': 'TNT',
    }
    atomic_json(profile_path, profiles)
    print(f'Installed isolated game directory: {INSTANCE}')
    print('Restart the official Minecraft Launcher → Installations → Minecampus — TUM Garching → Play.')
    print('Choose Steve in Skins. Complete the masked map setup before creating the campus world.')


def doctor(launcher):
    checks = {
        'official launcher profiles': (launcher / 'launcher_profiles.json').exists(),
        'Fabric version metadata': (launcher / 'versions' / PROFILE_ID / f'{PROFILE_ID}.json').exists(),
        'campus add-on installed': (INSTANCE / f'mods/minecampus-{PACK_VERSION}.jar').exists(),
        'Node.js available': bool(shutil.which('node')),
        'exterior renderer installed': (INSTANCE/SPEC['files'][0]['path']).exists() and hashlib.sha256((INSTANCE/SPEC['files'][0]['path']).read_bytes()).hexdigest()==SPEC['files'][0]['sha256'],
    }
    path = INSTANCE / 'realworldmc-service/config.json'
    config = json.loads(path.read_text()) if path.exists() else {}
    checks['map credential configured (value hidden)'] = bool(config.get('apiKey') or config.get('cesiumToken'))
    for name, ready in checks.items():
        print(f"{'OK' if ready else 'MISSING'}  {name}")
    print('A configured credential is not a live coverage test. Use Test connection inside Minecraft.')
    return all(checks.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'install', 'doctor', 'quality'])
    parser.add_argument('--launcher-dir', type=Path, default=launcher_directory())
    args = parser.parse_args()
    try:
        if args.action == 'build':
            build()
        elif args.action == 'install':
            install(args.launcher_dir.expanduser().resolve())
        elif args.action == 'quality':
            quality()
        else:
            sys.exit(0 if doctor(args.launcher_dir.expanduser().resolve()) else 1)
    except (OSError, ValueError, RuntimeError, StopIteration) as error:
        # Network exception URLs can contain credentials in other programs. This script only
        # fetches public URLs only; locally inspected provider credentials are never printed or sent.
        print(f'Minecampus setup failed: {error}', file=sys.stderr)
        sys.exit(1)

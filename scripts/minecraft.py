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
PROFILE_ID = f"fabric-loader-{SPEC['fabric-loader']}-{SPEC['minecraft']}"


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Minecampus/0.2.0 (DocMorphic/minecampus)'})
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
    target = OUTPUT / 'minecampus-0.2.0.jar'
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
        'formatVersion': 1, 'game': 'minecraft', 'versionId': '0.2.0',
        'name': 'Minecampus — actual Minecraft at TUM Garching',
        'summary': 'Minecraft Java 1.21.1 + Fabric + RealWorldMC. Own game account and map access required.',
        'dependencies': {key: SPEC[key] for key in ('minecraft', 'fabric-loader')},
        'files': index_files,
    }
    target = OUTPUT / 'Minecampus-0.2.0-mc1.21.1.mrpack'
    with zipfile.ZipFile(target, 'w') as archive:
        zip_bytes(archive, 'modrinth.index.json', json.dumps(index, indent=2).encode())
        zip_bytes(archive, 'overrides/mods/' + campus.name, campus.read_bytes())
        zip_bytes(archive, 'overrides/config/realworldmc.json', (ROOT / 'minecraft/config/realworldmc.json').read_bytes())
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


def install(launcher):
    campus = build()
    INSTANCE.mkdir(parents=True, exist_ok=True)
    for spec in SPEC['files']:
        target = INSTANCE / spec['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dependency(spec), target)
    shutil.copy2(campus, INSTANCE / 'mods' / campus.name)
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
        'campus add-on installed': (INSTANCE / 'mods/minecampus-0.2.0.jar').exists(),
        'Node.js available': bool(shutil.which('node')),
    }
    path = INSTANCE / 'realworldmc-service/config.json'
    config = json.loads(path.read_text()) if path.exists() else {}
    checks['map credential configured (value hidden)'] = bool(config.get('apiKey') or config.get('cesiumToken'))
    for name, ready in checks.items():
        print(f"{'OK' if ready else 'MISSING'}  {name}")
    print('A configured credential is not a live coverage test. Use Test connection inside Minecraft.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'install', 'doctor'])
    parser.add_argument('--launcher-dir', type=Path, default=launcher_directory())
    args = parser.parse_args()
    try:
        if args.action == 'build':
            build()
        elif args.action == 'install':
            install(args.launcher_dir.expanduser().resolve())
        else:
            doctor(args.launcher_dir.expanduser().resolve())
    except (OSError, ValueError, RuntimeError, StopIteration) as error:
        # Network exception URLs can contain credentials in other programs. This script only
        # fetches the public URLs above and deliberately never reads provider credentials here.
        print(f'Minecampus setup failed: {error}', file=sys.stderr)
        sys.exit(1)

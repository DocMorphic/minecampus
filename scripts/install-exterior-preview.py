#!/usr/bin/env python3
"""Install the native-verified exterior preview alongside an existing Minecampus.

Copies saves and local setup into a new private instance; never upgrades the source.
Requires an existing official-launcher Minecampus installation. No network requests.
"""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from minecraft import ROOT, INSTANCE, PROFILE_ID, atomic_json, launcher_directory


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def snapshot(folder):
    return {str(p.relative_to(folder)): digest(p) for p in folder.rglob('*') if p.is_file()}


def install(source, destination, launcher, jar):
    evidence = json.loads((ROOT / 'minecraft/exterior/uya-development-validation.json').read_text())
    expected = evidence['artifact']
    if jar.stat().st_size != expected['size'] or digest(jar) != expected['sha256']:
        raise RuntimeError('Preview JAR does not match the native-verified artifact.')
    if destination.exists():
        raise RuntimeError('Preview directory already exists; keeping its saves and settings untouched.')
    if source == destination or source in destination.parents or destination in source.parents:
        raise RuntimeError('Source and preview directories must be separate.')
    profile_path = launcher / 'launcher_profiles.json'
    profile_bytes = profile_path.read_bytes()
    profiles = json.loads(profile_bytes)
    if not (launcher / 'versions' / PROFILE_ID / (PROFILE_ID + '.json')).is_file():
        raise RuntimeError('Install the normal Minecampus launcher profile first.')
    if 'minecampus-exterior-preview' in profiles.get('profiles', {}):
        raise RuntimeError('Preview launcher profile already exists; keeping it untouched.')
    if not (source / 'saves').is_dir() or not (source / 'realworldmc-service/config.json').is_file():
        raise RuntimeError('Existing Minecampus saves and map setup are required.')
    # Do not follow user-created links out of the instance while copying.
    copied = ['saves', 'mods', 'config', 'resourcepacks', 'options.txt', 'usercache.json']
    for name in copied:
        path = source / name
        if path.is_symlink() or any(p.is_symlink() for p in path.rglob('*')):
            raise RuntimeError('Copy source contains a symbolic link: ' + name)
    import fcntl  # macOS/Linux: Minecraft uses a POSIX lock for each open world.
    with contextlib.ExitStack() as locks:
        for lock_path in (source / 'saves').glob('*/session.lock'):
            stream = locks.enter_context(lock_path.open('rb'))
            try:
                fcntl.lockf(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Quit Minecraft before copying an open world.') from None
        before = snapshot(source / 'saves')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.preview-stage-', dir=destination.parent) as temp:
            staging = Path(temp) / 'instance'
            staging.mkdir(mode=0o700)
            for name in copied:
                path = source / name
                if path.is_dir():
                    shutil.copytree(path, staging / name)
                elif path.is_file():
                    shutil.copy2(path, staging / name)
            mods = staging / 'mods'
            for old in mods.glob('*.jar'):
                with zipfile.ZipFile(old) as archive:
                    metadata = json.loads(archive.read('fabric.mod.json'))
                if metadata.get('id') == 'realworldmc':
                    old.unlink()  # Only the newly staged copy is changed.
            shutil.copy2(jar, mods / jar.name)
            service = staging / 'realworldmc-service'
            service.mkdir(mode=0o700)
            for name in ['config.json', 'streetview.config.json']:
                private = source / 'realworldmc-service' / name
                if private.is_file():
                    shutil.copy2(private, service / name)
                    (service / name).chmod(0o600)
            config_path = staging / 'config/realworldmc.json'
            config = json.loads(config_path.read_text())
            config['serviceDir'] = 'realworldmc-service'
            atomic_json(config_path, config)
            if snapshot(staging / 'saves') != before or snapshot(source / 'saves') != before:
                raise RuntimeError('Save copy changed during installation; no launcher profile installed.')
            if profile_path.read_bytes() != profile_bytes:
                raise RuntimeError('Launcher settings changed during copying; retry after closing the launcher.')
            report = {'artifactSha256': digest(jar), 'sourceSaveFiles': len(before),
                      'sourceSavesUnchanged': True, 'copiedSavesIdentical': True,
                      'sourceInstance': str(source), 'previewInstance': str(destination)}
            atomic_json(staging / 'preview-installation.json', report)
            staging.rename(destination)
        profiles.setdefault('profiles', {})['minecampus-exterior-preview'] = {
            'name': 'Minecampus — Exterior Preview 0.5', 'type': 'custom',
            'lastVersionId': PROFILE_ID, 'gameDir': str(destination),
            'javaArgs': '-Xmx6G -Xms1G -XX:+UseG1GC', 'icon': 'GRASS',
        }
        backup = launcher / 'launcher_profiles.before-exterior-preview.json'
        if not backup.exists():
            backup.write_bytes(profile_bytes)
            backup.chmod(0o600)
        atomic_json(profile_path, profiles)
    print('Installed Minecampus — Exterior Preview 0.5')
    print(f'Copied and verified {len(before)} save files; original installation unchanged.')
    print('Restart Minecraft Launcher → Installations → Minecampus — Exterior Preview 0.5 → Play.')
    print('Open Minecampus Garching. Progress here belongs to the preview copy.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=INSTANCE)
    parser.add_argument('--destination', type=Path, default=ROOT / '.minecampus/exterior-preview-0.5')
    parser.add_argument('--launcher-dir', type=Path, default=launcher_directory())
    parser.add_argument('--jar', type=Path, default=ROOT / 'dist-minecraft/RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar')
    args = parser.parse_args()
    try:
        install(*(p.expanduser().resolve() for p in (args.source, args.destination, args.launcher_dir, args.jar)))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from None

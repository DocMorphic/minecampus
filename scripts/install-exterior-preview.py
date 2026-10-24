#!/usr/bin/env python3
"""Install the native-verified exterior preview alongside an existing Minecampus.

Copies saves and local setup into a new private instance; never upgrades the source.
--update replaces only the recorded preview mod, preserving its saves/settings.
Requires an existing official-launcher Minecampus installation. No network requests.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
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


def verify_artifact(jar):
    evidence = json.loads((ROOT / 'minecraft/exterior/crosspath-development-validation.json').read_text())
    expected = evidence['artifact']
    if jar.stat().st_size != expected['size'] or digest(jar) != expected['sha256']:
        raise RuntimeError('Preview JAR does not match the native-verified artifact.')
    return expected


def update(destination, jar):
    """Replace only the recorded preview mod; preserve saves and private setup."""
    expected = verify_artifact(jar)
    report_path = destination / 'preview-installation.json'
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    if destination != Path(report['previewInstance']).resolve():
        raise RuntimeError('Preview installation record does not match this directory.')
    # A menu-only client has no world lock; check its instance argument too.
    processes = subprocess.check_output(['ps', '-axo', 'comm=,args='], text=True)
    if any('java' in line.lower().split()[0] and str(destination) in line
           for line in processes.splitlines() if line.split()):
        raise RuntimeError('Quit the Exterior Preview Minecraft client before updating.')
    for name in ['mods', 'saves', 'config', 'realworldmc-service', 'artifact-backups']:
        path = destination / name
        if path.is_symlink() or any(p.is_symlink() for p in path.rglob('*')):
            raise RuntimeError('Preview contains a symbolic link: ' + name)
    owned = []
    for path in (destination / 'mods').glob('*.jar'):
        with zipfile.ZipFile(path) as archive:
            if 'fabric.mod.json' in archive.namelist() and json.loads(archive.read('fabric.mod.json')).get('id') == 'realworldmc':
                owned.append(path)
    if len(owned) != 1 or digest(owned[0]) != report['artifactSha256']:
        raise RuntimeError('Preview mod differs from its installation record; no files changed.')
    old = owned[0]
    if report['artifactSha256'] == expected['sha256']:
        print('Exterior Preview already has this verified snapshot.')
        return
    import fcntl
    with contextlib.ExitStack() as locks:
        for path in (destination / 'saves').glob('*/session.lock'):
            stream = locks.enter_context(path.open('rb'))
            try:
                fcntl.lockf(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Quit Minecraft before updating an open world.') from None
        before = snapshot(destination / 'saves')
        private = [destination / 'config/realworldmc.json', destination / 'realworldmc-service/config.json',
                   destination / 'realworldmc-service/streetview.config.json', destination / 'options.txt']
        settings = {p: digest(p) for p in private if p.is_file()}
        backup = destination / 'artifact-backups' / report['artifactSha256']
        backup.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(old, backup / old.name)
        (backup / 'preview-installation.json').write_bytes(report_bytes)
        with tempfile.NamedTemporaryFile(prefix='.preview-mod-', suffix='.pending', dir=old.parent) as temp:
            shutil.copyfile(jar, temp.name)
            if digest(Path(temp.name)) != expected['sha256']:
                raise RuntimeError('Staged preview artifact checksum mismatch.')
            if snapshot(destination / 'saves') != before or any(digest(p) != value for p, value in settings.items()):
                raise RuntimeError('Preview saves/settings changed during preparation; no mod replaced.')
            # Copy to a sibling then replace atomically; the open temp file can
            # be removed normally by its context manager after the replacement.
            staged = old.with_suffix('.jar.pending')
            if staged.exists():
                raise RuntimeError('A pending mod update already exists; no mod replaced.')
            shutil.copy2(temp.name, staged)
            os.replace(staged, old)
        report['previousArtifactSha256'] = report['artifactSha256']
        report['artifactSha256'] = expected['sha256']
        report['updateSaveFilesVerified'] = len(before)
        report['updateSavesAndSettingsUnchanged'] = (snapshot(destination / 'saves') == before
                                                    and all(digest(p) == value for p, value in settings.items()))
        if not report['updateSavesAndSettingsUnchanged']:
            shutil.copy2(backup / old.name, old)
            raise RuntimeError('Preview changed during update; previous mod restored.')
        try:
            atomic_json(report_path, report)
        except OSError:
            shutil.copy2(backup / old.name, old)
            raise
    print(f'Updated Exterior Preview; verified {len(before)} unchanged save files and preserved local settings.')
    print('Launch Minecampus — Exterior Preview 0.5. The previous mod is retained in artifact-backups.')


def install(source, destination, launcher, jar):
    verify_artifact(jar)
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
    parser.add_argument('--update', action='store_true', help='Update only the mod in an existing recorded preview; keep its saves/settings.')
    args = parser.parse_args()
    try:
        if args.update:
            update(args.destination.expanduser().resolve(), args.jar.expanduser().resolve())
        else:
            install(*(p.expanduser().resolve() for p in (args.source, args.destination, args.launcher_dir, args.jar)))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from None

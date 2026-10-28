#!/usr/bin/env python3
"""Build isolated friend launchers from pinned public inputs only.

Does not inspect installed launchers, accounts, saves, or .minecampus. Keeps the
reviewed renderer unchanged. Minecraft/Java are downloaded by official Prism
at first launch, after the friend supplies their own Microsoft account.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tempfile
import tarfile
import urllib.request
import zipfile

import minecraft

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'minecraft/friends-launcher.json').read_text())


def stream_checksum(stream):
    result = hashlib.sha256()
    while block := stream.read(1024 * 1024):
        result.update(block)
    return result.hexdigest()


def checksum(path):
    with path.open('rb') as stream:
        return stream_checksum(stream)


def fetch(spec, folder):
    path = folder / spec['path']
    if path.exists() and path.stat().st_size == spec['size'] and checksum(path) == spec['sha256']:
        return path
    folder.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(spec['url'], headers={'User-Agent': 'Minecampus-Friends-Builder'})
    with tempfile.NamedTemporaryFile(dir=folder) as temporary:
        with urllib.request.urlopen(request, timeout=120) as response:
            while block := response.read(1024 * 1024):
                temporary.write(block)
        temporary.flush()
        staged = Path(temporary.name)
        if staged.stat().st_size != spec['size'] or checksum(staged) != spec['sha256']:
            raise RuntimeError('Download checksum mismatch: ' + spec['path'])
        path.write_bytes(staged.read_bytes())
    return path


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise RuntimeError('Unsafe archive path: ' + name)
    return name


def build(platform='Windows'):
    output = ROOT / 'dist-minecraft'
    cache = ROOT / '.cache/native-downloads'
    pack = fetch(LOCK['pack'], output)
    platform_spec = LOCK if platform == 'Windows' else LOCK['platforms'][platform]
    prism = fetch(platform_spec['prism'], cache)
    prism_source = fetch(LOCK['prismSource'], cache)
    hashes = {}
    version = LOCK['version']
    prefix = f'Minecampus-Friends-{platform}/'
    target = output / f"Minecampus-Friends-{platform}-{version}.zip"
    pending = target.with_suffix('.pending')
    with zipfile.ZipFile(pending, 'w', allowZip64=True) as archive:
        def put(name, data, mode=0o100644, mac_metadata=False):
            name = ('__MACOSX/' if mac_metadata else '') + prefix + safe_name(name)
            if name in hashes:
                raise RuntimeError('Duplicate archive member: ' + name)
            member = zipfile.ZipInfo(name, date_time=(2026, 10, 28, 0, 0, 0))
            member.create_system = 3
            member.external_attr = mode << 16
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, data)
            hashes[name] = hashlib.sha256(data).hexdigest()

        # Preserve the entire upstream portable distribution, byte-for-byte.
        if platform.startswith('Linux'):
            put('launcher/PrismLauncher.AppImage', prism.read_bytes(), 0o100755)
        else:
            with zipfile.ZipFile(prism) as original:
                for member in original.infolist():
                    if not member.is_dir():
                        # App framework links and executable bits must survive repacking.
                        mode = member.external_attr >> 16 if member.create_system == 3 else 0o100644
                        # AppleDouble entries carry signatures for non-Mach-O files.
                        # They must stay under the ZIP-root __MACOSX tree, mirroring
                        # the new location, so Archive Utility/ditto restore them.
                        metadata = platform == 'Mac' and member.filename.startswith('__MACOSX/')
                        name = member.filename.removeprefix('__MACOSX/') if metadata else member.filename
                        put('launcher/' + safe_name(name), original.read(member), mode or 0o100644, metadata)
        for runtime, spec in platform_spec.get('node', {}).items():
            node_archive = fetch(spec, cache)
            node_root = spec['path'].removesuffix('.tar.gz')
            with tarfile.open(node_archive) as original:
                for name in ['bin/node', 'LICENSE']:
                    member = original.getmember(node_root + '/' + name)
                    assert member.isfile(), member.name
                    put('runtime/' + runtime + '/' + name, original.extractfile(member).read(),
                        0o100755 if name == 'bin/node' else 0o100644)
        put('licenses/PrismLauncher-11.1.1-source.tar.gz', prism_source.read_bytes())
        put('licenses/Minecampus-LICENSE.txt', (ROOT / 'minecraft/LICENSE').read_bytes())
        put('licenses/THIRD_PARTY.md', (ROOT / 'THIRD_PARTY.md').read_bytes())
        put('licenses/Prism-NOTICE.txt', (
            'Official unmodified Prism Launcher 11.1.1, GPL-3.0-only.\n'
            'Full upstream source and its licenses are included alongside this notice.\n'
            'https://github.com/PrismLauncher/PrismLauncher/releases/tag/11.1.1\n'
            'Bundled libraries retain their upstream licenses.\n'
            'This Minecampus bundle is not endorsed by Prism Launcher.\n').encode())

        game = 'data/instances/minecampus/.minecraft/'
        with zipfile.ZipFile(pack) as source:
            index = json.loads(source.read('modrinth.index.json'))
            # Explicitly copy only public mods and blank setup from the pinned pack.
            expected = {
                'overrides/mods/RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar',
                'overrides/mods/minecampus-0.4.0.jar',
                'overrides/config/realworldmc.json',
            }
            for name in sorted(expected):
                put(game + name.removeprefix('overrides/'), source.read(name))
            for entry in index['files']:
                spec = next(item for item in minecraft.SPEC['files'] if item['path'] == entry['path'])
                data = minecraft.dependency(spec).read_bytes()
                if hashlib.sha512(data).hexdigest() != entry['hashes']['sha512']:
                    raise RuntimeError('Pack dependency mismatch: ' + entry['path'])
                put(game + safe_name(entry['path']), data)

        put(game + 'options.txt', b'renderClouds:"false"\n')
        put('data/instances/minecampus/instance.cfg', (
            '[General]\nInstanceType=OneSix\nname=Minecampus - Join a friend\n'
            'iconKey=grass\nOverrideMemory=true\nMinMemAlloc=512\nMaxMemAlloc=4096\n').encode())
        put('data/instances/minecampus/mmc-pack.json', json.dumps({
            'formatVersion': 1,
            'components': [
                {'uid': 'org.lwjgl3', 'version': '3.3.3', 'dependencyOnly': True},
                {'uid': 'net.minecraft', 'version': index['dependencies']['minecraft'], 'important': True},
                {'uid': 'net.fabricmc.intermediary', 'version': index['dependencies']['minecraft'], 'dependencyOnly': True},
                {'uid': 'net.fabricmc.fabric-loader', 'version': index['dependencies']['fabric-loader'], 'important': True},
            ],
        }, indent=2).encode())
        put('data/prismlauncher.cfg', (
            '[General]\nLanguage=en_US\nAutomaticJavaSwitch=true\nAutomaticJavaDownload=true\n'
            'UserAskedAboutAutomaticJavaDownload=true\nApplicationTheme=system\nIconTheme=pe_colored\n'
            'MinMemAlloc=512\nMaxMemAlloc=4096\n').encode())
        if platform == 'Windows':
            for name in ['Play Minecampus.cmd', 'READ ME FIRST.txt']:
                data = (ROOT / 'minecraft/friends' / name).read_text().replace('\n', '\r\n').encode()
                put(name, data)
        else:
            script = 'Play Minecampus.command' if platform == 'Mac' else 'Play Minecampus.sh'
            put(script, (ROOT / 'minecraft/friends' / script).read_bytes(), 0o100755)
            put('configure-runtime.cjs', (ROOT / 'minecraft/friends/configure-runtime.cjs').read_bytes())
            instructions = (ROOT / 'minecraft/friends/READ-ME-UNIX.txt').read_text()
            instructions = instructions.replace('@PLATFORM@', platform).replace('@SCRIPT@', script)
            put('READ ME FIRST.txt', instructions.encode())

    # Validate every archived input, not just the final ZIP's CRC table.
    with zipfile.ZipFile(pending) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(hashes):
            raise RuntimeError('Portable archive is incomplete')
        for name, expected_hash in hashes.items():
            with archive.open(name) as stream:
                if stream_checksum(stream) != expected_hash:
                    raise RuntimeError('Archive content mismatch: ' + name)
        if platform == 'Windows':
            assert archive.read(prefix + 'launcher/prismlauncher.exe')[:2] == b'MZ'
            assert archive.read(prefix + 'launcher/portable.txt') is not None
        elif platform.startswith('Linux'):
            assert archive.read(prefix + 'launcher/PrismLauncher.AppImage')[:4] == b'\x7fELF'
        else:
            assert archive.getinfo(prefix + 'launcher/Prism Launcher.app/Contents/MacOS/prismlauncher').external_attr >> 16 & 0o111
        if platform != 'Windows':
            assert archive.getinfo(prefix + script).external_attr >> 16 & 0o111
            for runtime in platform_spec['node']:
                assert archive.getinfo(prefix + 'runtime/' + runtime + '/bin/node').external_attr >> 16 & 0o111
        config = json.loads(archive.read(prefix + game + 'config/realworldmc.json'))
        assert config['setupComplete'] is False and config['nodeExecutable'] == 'node'
        renderer = archive.read(prefix + game + 'mods/RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar')
        review = json.loads((ROOT / 'minecraft/exterior/preview-upgrade-development-validation.json').read_text())
        assert hashlib.sha256(renderer).hexdigest() == review['artifact']['sha256']
        # The renderer's bundled service must include Node for Windows x64.
        with zipfile.ZipFile(io.BytesIO(renderer)) as jar:
            bundles = [n for n in jar.namelist() if n.endswith('.zip') and 'service' in n]
            assert len(bundles) == 1, bundles
            with zipfile.ZipFile(io.BytesIO(jar.read(bundles[0]))) as service:
                assert service.read('runtime/win-x64/node.exe')[:2] == b'MZ'
    pending.replace(target)
    final_hash = checksum(target)
    target.with_suffix('.zip.sha256').write_text(f'{final_hash}  {target.name}\n')
    report = {
        'file': target.name, 'platform': platform, 'size': target.stat().st_size, 'sha256': final_hash,
        'archiveIntegrityVerified': True, 'allPublicInputHashesVerified': True,
        'rendererSha256': review['artifact']['sha256'],
        'upstreamPrismVersion': '11.1.1', 'windowsNodeBundled': True,
        'automaticJavaDownloadEnabled': True, 'privateInstanceRead': False,
        'fullGameLaunchTestPassed': False, 'twoPlayerRemoteTestPassed': False,
        'additionalBundledNodeRuntimes': list(platform_spec.get('node', {})),
        'entryCount': len(hashes),
    }
    (output / f'friends-launcher-{platform}-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=['Windows', *LOCK.get('platforms', {})], default='Windows')
    build(parser.parse_args().platform)

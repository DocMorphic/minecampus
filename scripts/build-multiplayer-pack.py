#!/usr/bin/env python3
"""Package the reviewed campus client from an explicit public-file allowlist."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

import minecraft

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.5.0-multiplayer-preview'


def digest(data, algorithm='sha256'):
    return hashlib.new(algorithm, data).hexdigest()


def build():
    output = ROOT / 'dist-minecraft'
    review = json.loads((ROOT / 'minecraft/exterior/preview-upgrade-development-validation.json').read_text())
    assert review['playablePreviewReady']
    artifact = review['artifact']
    renderer = (output / artifact['file']).read_bytes()
    assert len(renderer) == artifact['size'] and digest(renderer) == artifact['sha256']
    # Build the resource-only add-on from tracked source, never from a private instance.
    previous = minecraft.OUTPUT
    try:
        with tempfile.TemporaryDirectory() as directory:
            minecraft.OUTPUT = Path(directory)
            addon = minecraft.addon()
            addon_name, addon_bytes = addon.name, addon.read_bytes()
    finally:
        minecraft.OUTPUT = previous
    api = next(f for f in minecraft.SPEC['files'] if 'fabric-api-' in f['path'])
    api_bytes = minecraft.dependency(api).read_bytes()
    index = {
        'formatVersion': 1, 'game': 'minecraft', 'versionId': VERSION,
        'name': 'Minecampus — Friends Preview 0.5',
        'summary': 'Matching campus client. Own Java account and map access required. Remote play awaiting two-player verification.',
        'dependencies': {'minecraft': '1.21.1', 'fabric-loader': minecraft.SPEC['fabric-loader']},
        'files': [{'path': api['path'], 'fileSize': len(api_bytes),
                   'hashes': {a: digest(api_bytes, a) for a in ('sha1', 'sha512')},
                   'downloads': [api['url']], 'env': {'client': 'required', 'server': 'required'}}],
    }
    files = {
        'modrinth.index.json': json.dumps(index, indent=2).encode(),
        'overrides/mods/' + artifact['file']: renderer,
        'overrides/mods/' + addon_name: addon_bytes,
        'overrides/config/realworldmc.json': (ROOT / 'minecraft/config/realworldmc.json').read_bytes(),
        'overrides/MINECAMPUS-MULTIPLAYER.md': (ROOT / 'minecraft/MULTIPLAYER.md').read_bytes(),
        'overrides/configure-node.py': (ROOT / 'scripts/configure-minecraft-node.py').read_bytes(),
    }
    target = output / f'Minecampus-{VERSION}.mrpack'
    with zipfile.ZipFile(target, 'w') as archive:
        for name, data in files.items():
            minecraft.zip_bytes(archive, name, data)
    # Read back every member, check CRCs, and prove there are no extra/private entries.
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(files)
        for name, data in files.items():
            assert digest(archive.read(name)) == digest(data), name
    checksum = digest(target.read_bytes())
    target.with_suffix('.mrpack.sha256').write_text(f'{checksum}  {target.name}\n')
    report = {'file': target.name, 'sha256': checksum, 'size': target.stat().st_size,
              'rendererSha256': artifact['sha256'], 'addonSha256': digest(addon_bytes),
              'fabricApiSha256': digest(api_bytes), 'allowlistedEntries': list(files),
              'archiveIntegrityVerified': True, 'privateInstanceRead': False,
              'twoPlayerRemoteTestPassed': False}
    (output / 'multiplayer-pack.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    build()

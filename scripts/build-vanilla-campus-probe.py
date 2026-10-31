#!/usr/bin/env python3
"""Convert one existing, licensed campus building into an experimental vanilla pack.

Run with .cache/geodata-venv/bin/python. This is a conversion probe, not a
replacement server or a claim of runtime/performance/gameplay verification.
Reads generated public ECT assets only. Never reads the user's instance/world.
"""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '940ed38dd0ca87739aa7fadd7ff5924aaf4227de'
CACHE = ROOT / '.cache/vanilla-campus-probe'
UPSTREAM = CACHE / 'objmc'
DATA = ROOT / 'dist-minecraft/exterior'
OUT = ROOT / 'dist-minecraft/vanilla-probe'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source():
    # Fixed commit is from before the 1.21.2+ shader format changes.
    url = 'https://api.github.com/repos/Godlander/objmc/zipball/' + COMMIT
    archive = CACHE / (COMMIT + '.zip')
    CACHE.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            archive.write_bytes(response.read())
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            name = member.filename.split('/', 1)[-1]
            if member.is_dir() or not name:
                continue
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('Unsafe upstream archive')
            target = UPSTREAM / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zipped.read(member))
    original = (UPSTREAM / 'objmc.py').read_text()
    # Suppress Windows console cosmetics and restore the converter's intended
    # automatic UV compression choice (the old CLI accidentally defaults to 1).
    script = CACHE / 'objmc-cli.py'
    patched = '\n'.join(line for line in original.splitlines() if not line.startswith('os.system(')) + '\n'
    patched = patched.replace('help="Compression mode: true/false",\n    default=autorotate,',
                              'help="Compression mode: true/false",\n    default=None,')
    script.write_text(patched)
    return script, sha(original.encode())


def parts(path):
    data = path.read_bytes()
    assert data[:4] == b'ECT1'
    count, ax, ay, az = struct.unpack_from('<i3d', data, 4)
    offset = 32
    for _ in range(count):
        n, width, height = struct.unpack_from('<3i', data, offset)
        tint = data[offset + 12:offset + 16]
        assert tint == b'\xff\xff\xff\xff' and n % 3 == 0
        offset += 16
        vertices = list(struct.iter_unpack('<5f', data[offset:offset + n * 20]))
        offset += n * 20
        texture = Image.frombytes('RGBA', (width, height), data[offset:offset + width * height * 4])
        offset += width * height * 4
        yield [(x + ax, y + ay, z + az, u, v) for x, y, z, u, v in vertices], texture
    assert offset == len(data)


def build():
    tool, source_hash = source()
    resource = CACHE / 'resourcepack'
    datapack = CACHE / 'datapack'
    for directory in [resource, datapack]:
        if directory.exists():
            shutil.rmtree(directory)  # Only this builder's generated staging trees.
        directory.mkdir()
    shutil.copytree(UPSTREAM / 'objmc/assets/minecraft/shaders', resource / 'assets/minecraft/shaders')
    (resource / 'pack.mcmeta').write_text(json.dumps({'pack': {'pack_format': 34,
        'description': 'Minecampus mesh probe — experimental, Java 1.21.1'}}))
    (datapack / 'pack.mcmeta').write_text(json.dumps({'pack': {'pack_format': 48,
        'description': 'Place/remove the experimental Minecampus warehouse mesh'}}))
    (resource / 'OBJMC-LICENSE.txt').write_bytes((UPSTREAM / 'LICENSE').read_bytes())
    (resource / 'ATTRIBUTION.md').write_bytes((ROOT / 'THIRD_PARTY.md').read_bytes())
    files = ['DEBY_LOD2_52738492-warehouse.ect', 'DEBY_LOD2_52738492-photo-roof.ect']
    geometry = [(name, verts, texture) for name in files for verts, texture in parts(DATA / name)]
    points = [v[:3] for _, vertices, _ in geometry for v in vertices]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    origin = [(low[0] + high[0]) / 2, low[1], (low[2] + high[2]) / 2]
    report = {'sourceCommit': COMMIT, 'converterSha256': source_hash,
              'patchedConverterSha256': sha(tool.read_bytes()),
              'targetMinecraftVersion': '1.21.1', 'sourceBounds': [low, high], 'origin': origin,
              'inputSha256': {name: sha((DATA / name).read_bytes()) for name in files}, 'parts': []}
    overrides, commands = [], ['kill @e[type=minecraft:item_display,tag=minecampus_probe]']
    for index, (filename, vertices, texture) in enumerate(geometry):
        model_id = 'minecampus_probe:warehouse_' + str(index)
        obj = CACHE / f'part-{index}.obj'
        lines = []
        for x, y, z, u, v in vertices:
            xyz = [x - origin[0], y - origin[1], z - origin[2]]
            assert max(abs(value) for value in xyz) < 127
            lines.append('v ' + ' '.join(f'{value:.8f}' for value in xyz))
            lines.append(f'vt {u:.8f} {1-v:.8f}')
        for i in range(0, len(vertices), 3):
            lines.append('f ' + ' '.join(f'{j}/{j}' for j in range(i + 1, i + 4)))
        obj.write_text('\n'.join(lines) + '\n')
        tex = CACHE / f'part-{index}.png'
        if min(texture.size) < 8:
            texture = texture.resize((128, 128), Image.Resampling.NEAREST)
        # Non-power-of-two sprites disable mipmaps for the entire block atlas.
        size = tuple(1 << (side - 1).bit_length() for side in texture.size)
        if texture.size != size:
            texture = texture.resize(size, Image.Resampling.BILINEAR)
        texture.save(tex)
        model_path = resource / f'assets/minecampus_probe/models/warehouse_{index}.json'
        texture_path = resource / f'assets/minecampus_probe/textures/item/warehouse_{index}.png'
        model_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        with (CACHE / f'conversion-{index}.log').open('w') as log:
            subprocess.run([sys.executable, str(tool), '--objs', str(obj), '--texs', str(tex),
                            '--out', str(model_path), str(texture_path), '--autorotate', '0',
                            '--colorbehavior', 'time', 'time', 'time'], cwd=CACHE,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        # This upstream version saves PNGs by basename in its working folder.
        (CACHE / texture_path.name).replace(texture_path)
        model = json.loads(model_path.read_text())
        model['textures'] = {'0': 'minecampus_probe:item/warehouse_' + str(index)}
        model['display'] = {'fixed': {'translation': [0, 0, 0], 'rotation': [0, 0, 0], 'scale': [1, 1, 1]}}
        model_path.write_text(json.dumps(model, separators=(',', ':')))
        assert len(model['elements']) == len(vertices) // 3
        with Image.open(texture_path) as encoded:
            assert encoded.getpixel((0, 0)) in [(12, 34, 56, 78), (12, 34, 56, 79)]
            dimensions = list(encoded.size)
        cmd = 7000 + index
        overrides.append({'predicate': {'custom_model_data': cmd}, 'model': model_id})
        commands.append('summon minecraft:item_display ~ ~ ~ {Tags:["minecampus_probe"],'
                        'billboard:"fixed",view_range:4f,width:32f,height:16f,shadow_radius:0f,'
                        'item_display:"fixed",item:{id:"minecraft:paper",count:1,components:{'
                        f'"minecraft:custom_model_data":{cmd}' + '}}}')
        report['parts'].append({'source': filename, 'triangles': len(vertices) // 3,
                                'textureSize': dimensions, 'model': model_id})
    paper = resource / 'assets/minecraft/models/item/paper.json'
    paper.parent.mkdir(parents=True, exist_ok=True)
    paper.write_text(json.dumps({'parent': 'minecraft:item/generated', 'textures': {'layer0': 'minecraft:item/paper'},
                                'overrides': overrides}))
    functions = datapack / 'data/minecampus_probe/function'
    functions.mkdir(parents=True)
    (functions / 'place.mcfunction').write_text('\n'.join(commands) + '\n')
    (functions / 'clear.mcfunction').write_text(commands[0] + '\n')
    OUT.mkdir(parents=True, exist_ok=True)
    for name, directory in [('resourcepack', resource), ('datapack', datapack)]:
        target = OUT / f'Minecampus-vanilla-probe-{name}.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for file in sorted(directory.rglob('*')):
                if file.is_file():
                    zipped.write(file, file.relative_to(directory).as_posix())
        with zipfile.ZipFile(target) as zipped:
            assert zipped.testzip() is None
            assert not any(n.endswith('.jar') for n in zipped.namelist())
        report[name] = {'file': target.name, 'size': target.stat().st_size,
                        'sha256': sha(target.read_bytes()), 'sha1': hashlib.sha1(target.read_bytes()).hexdigest()}
    report.update({'exportPassed': True, 'fullCampusConverted': False,
                   'vanillaClientRenderingVerified': False, 'serverPackDownloadVerified': False,
                   'collisionAndDestructionImplemented': False, 'remoteMultiplayerVerified': False})
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    build()

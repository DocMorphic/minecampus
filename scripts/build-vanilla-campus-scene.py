#!/usr/bin/env python3
"""Export an outdoor Garching sector for vanilla Java 1.21.1 clients.

Keeps the existing survey coordinates, meshes and licensed textures. This first
sector covers Atom-Ei, MLZ and the surrounding outdoor paths, not an interior.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mesh_probe', ROOT / 'scripts/build-vanilla-campus-probe.py')
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
DATA = ROOT / 'dist-minecraft/exterior'
CACHE = ROOT / '.cache/vanilla-campus-scene'
OUT = ROOT / 'dist-minecraft/vanilla-campus'
BOUNDS = (145, 420, -165, 10)  # min x, max x, min z, max z, existing campus coordinates


def intersects(bounds):
    low, high = bounds
    return high[0] >= BOUNDS[0] and low[0] <= BOUNDS[1] and high[2] >= BOUNDS[2] and low[2] <= BOUNDS[3]


def clip(vertices):
    """Clip boundary triangles, preserving linearly interpolated UVs."""
    output = []
    for triangle in np.asarray(vertices).reshape(-1, 3, 5):
        if triangle[:, 0].max() < BOUNDS[0] or triangle[:, 0].min() > BOUNDS[1] or triangle[:, 2].max() < BOUNDS[2] or triangle[:, 2].min() > BOUNDS[3]:
            continue
        polygon = list(triangle)
        for axis, bound, sign in [(0, BOUNDS[0], 1), (0, BOUNDS[1], -1), (2, BOUNDS[2], 1), (2, BOUNDS[3], -1)]:
            if not polygon:
                break
            result = []
            previous = polygon[-1]
            for current in polygon:
                a = sign * (previous[axis] - bound) >= 0
                b = sign * (current[axis] - bound) >= 0
                if a != b:
                    result.append(previous + (current - previous) * ((bound - previous[axis]) / (current[axis] - previous[axis])))
                if b:
                    result.append(current)
                previous = current
            polygon = result
        for index in range(1, len(polygon) - 1):
            output.extend([polygon[0], polygon[index], polygon[index + 1]])
    return np.asarray(output).reshape(-1, 5)


def rasterize_floor(vertices, heights):
    """A one-block collision grid under the visual terrain; never claims mesh collision."""
    for triangle in vertices[:, :3].reshape(-1, 3, 3):
        a, b, c = triangle
        denominator = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
        if abs(denominator) < 1e-8:
            continue
        lo = np.floor(triangle[:, [0, 2]].min(axis=0)).astype(int)
        hi = np.ceil(triangle[:, [0, 2]].max(axis=0)).astype(int)
        x, z = np.meshgrid(np.arange(lo[0], hi[0]) + .5, np.arange(lo[1], hi[1]) + .5)
        if not x.size:
            continue
        u = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / denominator
        v = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / denominator
        mask = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1.000001)
        y = u * a[1] + v * b[1] + (1 - u - v) * c[1]
        for px, pz, py in zip(x[mask], z[mask], y[mask]):
            key = (int(math.floor(px)), int(math.floor(pz)))
            heights[key] = max(heights.get(key, -1000), int(math.floor(py + .5)))


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    tool, upstream_hash = PROBE.source()
    resource, datapack = CACHE / 'resourcepack', CACHE / 'datapack'
    for directory in [resource, datapack]:
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir()
    shutil.copytree(PROBE.UPSTREAM / 'objmc/assets/minecraft/shaders', resource / 'assets/minecraft/shaders')
    (resource / 'pack.mcmeta').write_text(json.dumps({'pack': {'pack_format': 34, 'description': 'Minecampus: Garching outdoor sector — Java 1.21.1'}}))
    (datapack / 'pack.mcmeta').write_text(json.dumps({'pack': {'pack_format': 48, 'description': 'Garching outdoor sector placement and approximate terrain collision'}}))
    (resource / 'OBJMC-LICENSE.txt').write_bytes((PROBE.UPSTREAM / 'LICENSE').read_bytes())
    (resource / 'ATTRIBUTION.md').write_bytes((ROOT / 'THIRD_PARTY.md').read_bytes())
    manifest = json.loads((DATA / 'manifest.json').read_text())
    records = [t for t in manifest['tiles'] if t['kind'] != 'vegetation' and intersects(t['bounds'])]
    plans = json.loads((DATA / 'photo-facades.json').read_text())['plans']
    for plan in plans:
        if intersects(plan['bounds']) and plan.get('roofFile'):
            records.append({'file': plan['roofFile'], 'kind': 'roof', 'bounds': plan['bounds']})
    # Deduplicate source paths, preserving the source manifest's order.
    records = list({record['file']: record for record in records}.values())
    report = {'scene': 'Garching outdoor Atom-Ei / MLZ sector', 'version': '1.21.1',
              'boundsMC': list(BOUNDS), 'sourceCommit': PROBE.COMMIT,
              'upstreamConverterSha256': upstream_hash, 'inputSha256': {}, 'parts': [],
              'interiorsIncluded': False, 'fullCampusConverted': False,
              'vegetationIncluded': False, 'buildingCollisionImplemented': False,
              'destructionImplemented': False}
    placements = ['kill @e[type=minecraft:item_display,tag=minecampus_probe]',
                  'kill @e[type=minecraft:item_display,tag=minecampus_scene]']
    overrides, heights = [], {}
    index = 0
    for record in records:
        filename = record['file']
        path = DATA / filename
        report['inputSha256'][filename] = PROBE.sha(path.read_bytes())
        print('Converting', filename, flush=True)
        for vertices, original_texture in PROBE.parts(path):
            vertices = clip(vertices)
            if not len(vertices):
                continue
            if record['kind'] == 'ground':
                rasterize_floor(vertices, heights)
            # Bounded pieces prevent enormous shader data textures.
            for start in range(0, len(vertices), 4096 * 3):
                part = vertices[start:start + 4096 * 3]
                lo, hi = part[:, :3].min(axis=0), part[:, :3].max(axis=0)
                origin = np.array([(lo[0] + hi[0]) / 2, 64., (lo[2] + hi[2]) / 2])
                if np.max(np.abs(part[:, :3] - origin)) >= 127:
                    raise ValueError('Source part requires spatial splitting: ' + filename)
                obj = CACHE / 'part.obj'
                lines = []
                for vertex in part:
                    lines.append('v ' + ' '.join(f'{p:.7f}' for p in vertex[:3] - origin))
                    lines.append(f'vt {vertex[3]:.7f} {1 - vertex[4]:.7f}')
                for offset in range(0, len(part), 3):
                    lines.append('f ' + ' '.join(f'{j}/{j}' for j in range(offset + 1, offset + 4)))
                obj.write_text('\n'.join(lines) + '\n')
                texture = original_texture.copy()
                if texture.size == (1, 1):
                    texture = texture.resize((128, 128), Image.Resampling.NEAREST)
                else:
                    texture.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    size = tuple(max(8, 1 << (side - 1).bit_length()) for side in texture.size)
                    texture = texture.resize(size, Image.Resampling.BILINEAR)
                tex = CACHE / 'part.png'
                texture.save(tex)
                name = f'part_{index}'
                model_path = resource / f'assets/minecampus_scene/models/{name}.json'
                texture_path = resource / f'assets/minecampus_scene/textures/item/{name}.png'
                model_path.parent.mkdir(parents=True, exist_ok=True)
                texture_path.parent.mkdir(parents=True, exist_ok=True)
                with (CACHE / 'converter.log').open('w') as log:
                    subprocess.run([sys.executable, str(tool), '--objs', str(obj), '--texs', str(tex),
                                    '--out', str(model_path), str(texture_path), '--autorotate', '0',
                                    '--colorbehavior', 'time', 'time', 'time'], cwd=CACHE,
                                   stdout=log, stderr=subprocess.STDOUT, check=True)
                (CACHE / texture_path.name).replace(texture_path)
                model = json.loads(model_path.read_text())
                model['textures'] = {'0': 'minecampus_scene:item/' + name}
                model['display'] = {'fixed': {'translation': [0, 0, 0], 'rotation': [0, 0, 0], 'scale': [1, 1, 1]}}
                model_path.write_text(json.dumps(model, separators=(',', ':')))
                assert len(model['elements']) == len(part) // 3
                with Image.open(texture_path) as encoded:
                    dimensions = list(encoded.size)
                    assert max(dimensions) <= 8192
                    assert encoded.getpixel((0, 0)) in [(12, 34, 56, 78), (12, 34, 56, 79)]
                cmd = 10000 + index
                overrides.append({'predicate': {'custom_model_data': cmd}, 'model': 'minecampus_scene:' + name})
                xyz = ' '.join(f'{p:.6f}' for p in origin)
                width = max(hi[0] - lo[0], hi[2] - lo[2]) + 4
                height = max(8, hi[1] - 64 + 4)
                placements.append(f'summon minecraft:item_display {xyz} ' + '{Tags:["minecampus_scene"],'
                    f'billboard:"fixed",view_range:3f,width:{width:.2f}f,height:{height:.2f}f,shadow_radius:0f,'
                    'item_display:"fixed",item:{id:"minecraft:paper",count:1,components:{'
                    f'"minecraft:custom_model_data":{cmd}' + '}}}')
                report['parts'].append({'source': filename, 'triangles': len(part) // 3,
                                        'textureSize': dimensions, 'origin': origin.tolist(), 'model': name})
                index += 1
    paper = resource / 'assets/minecraft/models/item/paper.json'
    paper.parent.mkdir(parents=True, exist_ok=True)
    paper.write_text(json.dumps({'parent': 'minecraft:item/generated', 'textures': {'layer0': 'minecraft:item/paper'}, 'overrides': overrides}))
    functions = datapack / 'data/minecampus_scene/function'
    functions.mkdir(parents=True)
    (functions / 'place.mcfunction').write_text('\n'.join(placements) + '\n')
    (functions / 'clear.mcfunction').write_text('kill @e[type=minecraft:item_display,tag=minecampus_scene]\n')
    # Group adjacent columns into strips. Terrain collision is quantized to 1 m.
    commands = []
    for z in range(BOUNDS[2], BOUNDS[3]):
        x = BOUNDS[0]
        while x < BOUNDS[1]:
            y = heights.get((x, z))
            end = x
            while end + 1 < BOUNDS[1] and heights.get((end + 1, z)) == y:
                end += 1
            if y is not None and y > 60:
                commands.append(f'fill {x} 60 {z} {end} {y - 1} {z} minecraft:barrier')
            x = end + 1
    # Placement needs loaded chunks, including the distant ends of the sector.
    (functions / 'terrain.mcfunction').write_text('\n'.join(commands) + '\n')
    (functions / 'setup.mcfunction').write_text(
        f'forceload add {BOUNDS[0]} {BOUNDS[2]} {BOUNDS[1] - 1} {BOUNDS[3] - 1}\n'
        'schedule function minecampus_scene:populate 2s replace\n')
    (functions / 'populate.mcfunction').write_text('function minecampus_scene:terrain\nfunction minecampus_scene:place\n')
    report['triangles'] = sum(p['triangles'] for p in report['parts'])
    report['displayEntities'] = index
    report['terrainCollisionColumns'] = len(heights)
    report['terrainCollisionStrips'] = len(commands)
    report['encodedTexturePixels'] = sum(math.prod(p['textureSize']) for p in report['parts'])
    OUT.mkdir(parents=True, exist_ok=True)
    for kind, directory in [('resourcepack', resource), ('datapack', datapack)]:
        target = OUT / f'Minecampus-outdoor-{kind}.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for file in sorted(directory.rglob('*')):
                if file.is_file():
                    zipped.write(file, file.relative_to(directory).as_posix())
        with zipfile.ZipFile(target) as zipped:
            assert zipped.testzip() is None
        content = target.read_bytes()
        report[kind] = {'file': target.name, 'size': len(content), 'sha256': PROBE.sha(content), 'sha1': hashlib.sha1(content).hexdigest()}
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['parts', 'inputSha256']}, indent=2))


if __name__ == '__main__':
    main()

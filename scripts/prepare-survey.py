#!/usr/bin/env python3
"""Extract Garching's CC-BY aerial survey from a remote SLPK using HTTP Range.

Setup: python3 -m venv .cache/geodata-venv
       .cache/geodata-venv/bin/pip install -r scripts/geodata-requirements.txt
Run:   .cache/geodata-venv/bin/python scripts/prepare-survey.py

The regional source is ~53 GiB. Only its ZIP index, node pages, and the selected
campus tiles are downloaded (~140 MB). Never downloads the full regional file.
"""
import concurrent.futures
import datetime
import gzip
import io
import json
import math
import os
from pathlib import Path
import struct
import time
import urllib.request
import zlib

import numpy as np
from PIL import Image
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'realworld'
OUT = ROOT / 'public' / 'realworld'
SOURCE = 'https://download1.bayernwolke.de/p/dom-mesh-slpk/124023_0/DSM_Mesh.slpk'
CACHE.mkdir(parents=True, exist_ok=True)
(OUT / 'tiles').mkdir(parents=True, exist_ok=True)


def fetch_range(start, length):
    for attempt in range(4):
        try:
            request = urllib.request.Request(SOURCE, headers={'Range': f'bytes={start}-{start+length-1}'})
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206:
                    raise RuntimeError('Server ignored Range; refusing a full regional download')
                result = response.read(length + 1)
                if len(result) != length:
                    raise RuntimeError('Incomplete byte range')
                return result
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def archive_index():
    path = CACHE / 'index.json'
    if path.exists():
        return json.loads(path.read_text())
    with urllib.request.urlopen(urllib.request.Request(SOURCE, method='HEAD'), timeout=30) as response:
        size = int(response.headers['Content-Length'])
    tail = fetch_range(size-65536, 65536)
    locator = tail.rfind(b'PK\x06\x07')
    if locator < 0:
        raise RuntimeError('Expected an official ZIP64 SLPK')
    zip64 = struct.unpack_from('<4sLQL', tail, locator)[2]
    info = struct.unpack('<4sQ2H2L4Q', fetch_range(zip64, 56))
    directory_size, directory_offset = info[8:10]
    if directory_size > 64 * 1024**2:
        raise RuntimeError('Unexpectedly large archive directory')
    data = fetch_range(directory_offset, directory_size)
    (CACHE / 'directory.bin').write_bytes(data)
    files, offset = {}, 0
    while offset < len(data):
        item = struct.unpack_from('<4s6H3L5H2L', data, offset)
        if item[0] != b'PK\x01\x02':
            raise RuntimeError('Invalid archive index')
        method, compressed, size = item[4], item[8], item[9]
        name_length, extra_length, comment_length, file_offset = item[10], item[11], item[12], item[16]
        name = data[offset+46:offset+46+name_length].decode()
        extra = data[offset+46+name_length:offset+46+name_length+extra_length]
        k = 0
        while k < len(extra):
            kind, length = struct.unpack_from('<HH', extra, k)
            if kind == 1:
                cursor = k + 4
                if size == 0xffffffff:
                    size = struct.unpack_from('<Q', extra, cursor)[0]
                    cursor += 8
                if compressed == 0xffffffff:
                    compressed = struct.unpack_from('<Q', extra, cursor)[0]
                    cursor += 8
                if file_offset == 0xffffffff:
                    file_offset = struct.unpack_from('<Q', extra, cursor)[0]
            k += 4 + length
        files[name] = [file_offset, compressed, size, method]
        offset += 46 + name_length + extra_length + comment_length
    path.write_text(json.dumps(files))
    return files


FILES = archive_index()


def extract(name):
    target = CACHE / 'extracted' / name
    if target.exists():
        return target.read_bytes()
    offset, compressed, size, method = FILES[name]
    if compressed > 16 * 1024**2:
        raise RuntimeError('Unexpectedly large tile')
    header = fetch_range(offset, 30)
    name_length, extra_length = struct.unpack_from('<HH', header, 26)
    data = fetch_range(offset+30+name_length+extra_length, compressed)
    if method == 8:
        data = zlib.decompress(data, -15)
    elif method != 0:
        raise RuntimeError(f'Unsupported ZIP compression {method}')
    if len(data) != size:
        raise RuntimeError('Archive entry size mismatch')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return data


def spatial_nodes():
    target = CACHE / 'nodes.json'
    if target.exists():
        return json.loads(target.read_text())
    entries = [(name, value) for name, value in FILES.items() if name.startswith('nodepages/')]
    start = min(value[0] for _, value in entries)
    end = max(value[0]+value[1]+200 for _, value in entries)
    data = fetch_range(start, end-start)
    nodes = {}
    for name, (offset, compressed, size, method) in entries:
        cursor = offset-start
        name_length, extra_length = struct.unpack_from('<HH', data, cursor+26)
        content = data[cursor+30+name_length+extra_length:cursor+30+name_length+extra_length+compressed]
        if method == 8:
            content = zlib.decompress(content, -15)
        page = json.loads(gzip.decompress(content))
        nodes.update({str(node['index']): node for node in page['nodes']})
    target.write_text(json.dumps(nodes))
    return nodes


TO_UTM = Transformer.from_crs(4326, 25832, always_xy=True)
TO_GEO = Transformer.from_crs(25832, 4326, always_xy=True)
ORIGIN = TO_UTM.transform(11.671, 48.265)


def convert(node):
    resource = node['mesh']['geometry']['resource']
    target = OUT / 'tiles' / f'{resource}.bin'
    texture = OUT / 'tiles' / f'{resource}.webp'
    metadata = CACHE / f'{resource}-converted.json'
    if target.exists() and texture.exists() and metadata.exists():
        return json.loads(metadata.read_text())
    raw = gzip.decompress(extract(f'nodes/{resource}/geometries/0.bin.gz'))
    count, features = struct.unpack_from('<II', raw)
    utm = np.frombuffer(raw, dtype='<f4', offset=8, count=count*3).reshape(-1, 3).astype(np.float64)
    utm += np.array(node['obb']['center'])
    longitude, latitude = TO_GEO.transform(utm[:, 0], utm[:, 1])
    positions = np.empty_like(utm)
    positions[:, 0] = (longitude-11.671)*111320*np.cos(48.265*np.pi/180)
    positions[:, 1] = utm[:, 2]-477
    positions[:, 2] = -(latitude-48.265)*111320
    uv = np.frombuffer(raw, dtype='<f4', offset=8+count*12, count=count*2).reshape(-1, 2)
    minimum, maximum = positions.min(axis=0), positions.max(axis=0)
    scale = np.maximum(maximum-minimum, 0.00001)
    packed = np.concatenate([
        np.rint((positions-minimum)/scale*65535).astype('<u2'),
        np.rint(np.clip(uv, 0, 1)*65535).astype('<u2')], axis=1)
    unique, indices = np.unique(packed, axis=0, return_inverse=True)
    body = unique.astype('<u2').tobytes()
    body += b'\x00'*((-len(body)) % 4)
    target.write_bytes(struct.pack('<4sIII', b'MCM1', len(unique), len(indices), 0)+body+indices.astype('<u4').tobytes())
    image = Image.open(io.BytesIO(extract(f'nodes/{resource}/textures/0.jpg')))
    image.save(texture, 'WEBP', quality=88, method=4)
    entry = {'id': resource, 'geometry': f'tiles/{resource}.bin', 'texture': f'tiles/{resource}.webp',
             'min': minimum.tolist(), 'scale': scale.tolist(), 'center': ((minimum+maximum)/2).tolist(),
             'radius': float(np.linalg.norm(maximum-minimum)/2), 'vertices': len(unique),
             'triangles': count//3, 'bytes': target.stat().st_size+texture.stat().st_size}
    metadata.write_text(json.dumps(entry))
    return entry


def main():
    selected = []
    for node in spatial_nodes().values():
        if node.get('children') or 'mesh' not in node:
            continue
        center, half = node['obb']['center'], node['obb']['halfSize']
        radius = math.sqrt(sum(value*value for value in half))
        if abs(center[0]-ORIGIN[0]) < 800+radius and abs(center[1]-ORIGIN[1]) < 850+radius:
            selected.append(node)
    entries = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(convert, selected):
            entries.append(result)
            if len(entries) % 20 == 0:
                print(f'Prepared {len(entries)} / {len(selected)} tiles', flush=True)
    entries.sort(key=lambda entry: entry['id'])
    manifest = {'version': 1, 'name': 'TUM Garching — official aerial photogrammetry mesh',
        'source': {'provider': 'Bayerische Vermessungsverwaltung',
                   'attribution': 'Bayerische Vermessungsverwaltung – www.geodaten.bayern.de',
                   'license': 'CC BY 4.0', 'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                   'url': SOURCE, 'lot': '124023_0', 'surveyYear': 2024,
                   'retrieved': '2026-10-20',
                   'modifications': 'Campus subset, converted from I3S to indexed quantized triangles; JPEG textures re-encoded as WebP. Gameplay edits are local.'},
        'origin': {'lat': 48.265, 'lon': 11.671, 'orthometricHeight': 477, 'utm32': list(ORIGIN)},
        'tiles': entries, 'totalTriangles': sum(entry['triangles'] for entry in entries),
        'totalBytes': sum(entry['bytes'] for entry in entries)}
    (OUT/'manifest.json').write_text(json.dumps(manifest, separators=(',', ':')))
    print(f"Ready: {len(entries)} real tiles; {manifest['totalTriangles']:,} triangles; {manifest['totalBytes']/1e6:.1f} MB")


if __name__ == '__main__':
    main()

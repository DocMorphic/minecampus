#!/usr/bin/env python3
"""Run an isolated loopback-only vanilla server and resource-pack download test.

This is a development fixture, NOT a remotely reachable production server.
Requires Java 21, the outdoor ZIPs, and the official 1.21.1 version metadata.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import threading
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.cache/vanilla-campus-probe/server-lab'
OUTPUT = ROOT / 'dist-minecraft/vanilla-campus'


def prepare(metadata):
    LAB.mkdir(parents=True, exist_ok=True)
    spec = json.loads(metadata.read_text())['downloads']['server']
    jar = LAB / 'server-1.21.1.jar'
    if not jar.exists():
        with urllib.request.urlopen(spec['url'], timeout=60) as response:
            jar.write_bytes(response.read())
    if hashlib.sha1(jar.read_bytes()).hexdigest() != spec['sha1']:
        raise ValueError('Official server download checksum mismatch')
    pack = (OUTPUT / 'Minecampus-outdoor-resourcepack.zip').read_bytes()
    pack_sha = hashlib.sha1(pack).hexdigest()
    properties = {
        'server-ip': '127.0.0.1', 'server-port': '25579',
        # Test identities never leave this machine. Production must authenticate.
        'online-mode': 'false', 'enforce-secure-profile': 'false',
        'enable-rcon': 'false', 'enable-query': 'false', 'max-players': '4',
        'motd': 'Minecampus vanilla mesh laboratory', 'gamemode': 'creative',
        'difficulty': 'peaceful', 'view-distance': '10', 'simulation-distance': '5',
        'entity-broadcast-range-percentage': '400',
        'spawn-protection': '0', 'allow-flight': 'true',
        'level-name': 'outdoor-world', 'level-type': 'minecraft:flat',
        'generate-structures': 'false',
        'generator-settings': json.dumps({'biome': 'minecraft:plains', 'layers': [
            {'block': 'minecraft:bedrock', 'height': 1},
            {'block': 'minecraft:dirt', 'height': 122},
            {'block': 'minecraft:grass_block', 'height': 1}],
            'lakes': False, 'features': False, 'structure_overrides': []}),
        'initial-enabled-packs': 'vanilla,file/probe',
        'resource-pack': 'http://127.0.0.1:8127/campus.zip',
        'resource-pack-sha1': pack_sha, 'require-resource-pack': 'true',
        'resource-pack-prompt': json.dumps({'text': 'Download the Garching outdoor campus preview?'}),
    }
    (LAB / 'server.properties').write_text(''.join(k + '=' + v + '\n' for k, v in properties.items()))
    datapack = LAB / 'outdoor-world/datapacks/probe'
    if datapack.exists():
        shutil.rmtree(datapack)  # Only this tool's generated test fixture.
    with zipfile.ZipFile(OUTPUT / 'Minecampus-outdoor-datapack.zip') as archive:
        archive.extractall(datapack)
    functions = datapack / 'data/minecampus_scene/function'
    (functions / 'load.mcfunction').write_text(
        'scoreboard objectives add campus_probe dummy\n'
        'gamerule doDaylightCycle false\ntime set noon\n'
        'gamerule doMobSpawning false\nsetworldspawn 210 65 -48\n'
        'function minecampus_scene:setup\n')
    (functions / 'tick.mcfunction').write_text(
        'execute as @a unless score @s campus_probe matches 1 run function minecampus_scene:welcome\n')
    (functions / 'welcome.mcfunction').write_text(
        'scoreboard players set @s campus_probe 1\n'
        'tp @s 210 65 -48 facing 245 75 -95\n'
        'tellraw @s {"text":"Garching outdoor preview: Atom-Ei and MLZ. Building collision and destruction are unfinished.","color":"gold"}\n')
    tags = datapack / 'data/minecraft/tags/function'
    tags.mkdir(parents=True, exist_ok=True)
    for name in ['load', 'tick']:
        (tags / (name + '.json')).write_text(json.dumps({'values': ['minecampus_scene:' + name]}))
    (LAB / 'manifest.json').write_text(json.dumps({
        'version': '1.21.1', 'serverJarSha1': spec['sha1'],
        'resourcePackSha1': pack_sha, 'resourcePackBytes': len(pack),
        'loopbackOnly': True, 'productionReady': False}, indent=2) + '\n')
    return jar, pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, default=Path.home() /
                        'Library/Application Support/minecraft/versions/1.21.1/1.21.1.json')
    parser.add_argument('--java', default='java')
    parser.add_argument('--accept-eula', action='store_true',
                        help='Accept https://aka.ms/MinecraftEULA for this local server')
    args = parser.parse_args()
    eula = LAB / 'eula.txt'
    accepted = eula.exists() and any(line.strip().lower() == 'eula=true' for line in eula.read_text().splitlines())
    if not args.accept_eula and not accepted:
        parser.error('Review the Minecraft EULA, then pass --accept-eula for the local test server.')
    jar, pack = prepare(args.metadata)
    if args.accept_eula:
        (LAB / 'eula.txt').write_text('eula=true\n')

    class PackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/campus.zip':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Length', str(len(pack)))
            self.end_headers()
            self.wfile.write(pack)
            with (LAB / 'pack-downloads.jsonl').open('a') as log:
                log.write(json.dumps({'status': 200, 'bytes': len(pack),
                                      'sha1': hashlib.sha1(pack).hexdigest()}) + '\n')

        def log_message(self, format, *values):
            print('Pack HTTP:', format % values, flush=True)

    http = ThreadingHTTPServer(('127.0.0.1', 8127), PackHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    print('Local test only: Minecraft 127.0.0.1:25579; pack 127.0.0.1:8127', flush=True)
    try:
        subprocess.run([args.java, '-Xmx2G', '-jar', str(jar), 'nogui'], cwd=LAB, check=True)
    finally:
        http.shutdown()
        http.server_close()


if __name__ == '__main__':
    main()

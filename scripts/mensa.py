#!/usr/bin/env python3
"""Generate a real Minecraft structure and a non-destructive Mensa study datapack."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'minecraft/mensa'
OUTPUT = ROOT / 'dist-minecraft'
PACK = SOURCE / 'pack'
BLOCKS = {}
BLOCK_ENTITIES = {}


# Minimal typed NBT encoder: all generated geometry is native Minecraft blocks.
def tag(kind, value):
    return kind, value


def string(value):
    payload = value.encode('utf8')
    return struct.pack('>H', len(payload)) + payload


def encode(kind, value):
    if kind == 1:
        return struct.pack('>b', value)
    if kind == 3:
        return struct.pack('>i', value)
    if kind == 8:
        return string(value)
    if kind == 9:
        subtype, values = value
        return bytes([subtype]) + struct.pack('>i', len(values)) + b''.join(encode(subtype, v) for v in values)
    if kind == 10:
        return b''.join(bytes([k]) + string(name) + encode(k, item) for name, (k, item) in value.items()) + b'\0'
    raise ValueError(f'Unsupported NBT type {kind}')


def state(block):
    if '[' not in block:
        return {'Name': tag(8, 'minecraft:' + block)}
    name, props = block[:-1].split('[', 1)
    return {'Name': tag(8, 'minecraft:' + name),
            'Properties': tag(10, {k: tag(8, v) for k, v in (p.split('=') for p in props.split(','))})}


def setblock(x, y, z, block, nbt=None):
    BLOCKS[x, y, z] = block
    BLOCK_ENTITIES.pop((x, y, z), None)
    if nbt:
        BLOCK_ENTITIES[x, y, z] = nbt


def box(x0, y0, z0, x1, y1, z1, block):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                setblock(x, y, z, block)


def clear(x0, y0, z0, x1, y1, z1):
    box(x0, y0, z0, x1, y1, z1, 'air')


def sign(x, y, z, lines, facing='south'):
    front = {'messages': tag(9, (8, [json.dumps({'text': line, 'color': 'black'}) for line in lines])),
             'color': tag(8, 'black'), 'has_glowing_text': tag(1, 0)}
    setblock(x, y, z, f'birch_wall_sign[facing={facing},waterlogged=false]',
             {'id': tag(8, 'minecraft:sign'), 'front_text': tag(10, front), 'is_waxed': tag(1, 1)})


def table(x, y, z, length=5, along='x', dark=False):
    wood = 'dark_oak' if dark else 'birch'
    for i in range(length):
        tx, tz = (x+i, z) if along == 'x' else (x, z+i)
        connections = 'east=true,west=true,north=false,south=false' if along == 'x' else 'east=false,west=false,north=true,south=true'
        setblock(tx, y, tz, f'{wood}_fence[{connections},waterlogged=false]')
        setblock(tx, y+1, tz, 'white_carpet' if not dark else 'brown_carpet')
        if i % 2 == 0:
            if along == 'x':
                setblock(tx, y, tz-1, 'dark_oak_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]')
                setblock(tx, y, tz+1, 'dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
            else:
                setblock(tx-1, y, tz, 'dark_oak_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]')
                setblock(tx+1, y, tz, 'dark_oak_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]')


def door(x, z, hinge):
    for y, half in [(1, 'lower'), (2, 'upper')]:
        setblock(x, y, z, f'birch_door[facing=north,half={half},hinge={hinge},open=false,powered=false]')
    for dz in [-1, 1]:
        setblock(x, 1, z+dz, 'birch_pressure_plate[powered=false]')


def tree(x, z, height=8):
    box(x-2, 0, z-2, x+2, 0, z+2, 'dirt')
    box(x, 1, z, x, height, z, 'spruce_log[axis=y]')
    for y, radius in [(height-4, 2), (height-2, 2), (height, 1)]:
        for dx in range(-radius, radius+1):
            for dz in range(-radius, radius+1):
                if abs(dx)+abs(dz) <= radius+1 and (dx or dz):
                    setblock(x+dx, y, z+dz, 'spruce_leaves[persistent=true,distance=1,waterlogged=false]')
    setblock(x, height+1, z, 'spruce_leaves[persistent=true,distance=1,waterlogged=false]')


def geometry():
    BLOCKS.clear()
    BLOCK_ENTITIES.clear()
    # Approx. 76 × 74 m footprint; courtyard from OSM relation 7726478.
    box(-10, 0, -10, 86, 0, 90, 'smooth_stone')
    box(46, 0, 91, 52, 0, 91, 'smooth_stone_slab[type=bottom,waterlogged=false]')
    box(0, 0, 0, 75, 0, 73, 'polished_andesite')
    for x in range(-8, 87, 4):
        box(x, 0, 75, x, 0, 89, 'stone')
    for z in range(-8, 91, 4):
        box(-9, 0, z, 85, 0, z, 'stone')
    # Floor plates around the open-to-sky courtyard, not a sealed building box.
    for x in range(76):
        for z in range(74):
            if not (14 <= x <= 41 and 32 <= z <= 60):
                setblock(x, 6, z, 'smooth_stone')
                setblock(x, 14, z, 'smooth_stone')
    # Glazed lower level and pale vertical timber outer skin.
    for y in range(1, 14):
        for x in range(76):
            for z in [0, 73]:
                block = 'glass' if y not in (5, 6, 13) else 'stripped_birch_wood[axis=y]'
                if x % 4 == 0:
                    block = 'stripped_birch_wood[axis=y]'
                setblock(x, y, z, block)
        for z in range(74):
            for x in [0, 75]:
                block = 'glass' if y not in (5, 6, 13) else 'stripped_birch_wood[axis=y]'
                if z % 4 == 0:
                    block = 'stripped_birch_wood[axis=y]'
                setblock(x, y, z, block)
    # Screen fins: thin native wooden trapdoors rather than full-metre projections.
    for x in range(1, 75, 2):
        for y in range(7, 13):
            for z, facing in [(-1, 'south'), (74, 'north')]:
                setblock(x, y, z, f'birch_trapdoor[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]')
    # Service core north; lower café/utility rooms are approximate partitions.
    box(1, 1, 1, 74, 5, 22, 'white_concrete')
    clear(2, 1, 2, 73, 4, 21)
    for x in [12, 24, 40, 57, 67]:
        box(x, 1, 2, x, 4, 20, 'white_concrete')
        clear(x, 1, 17, x, 2, 18)
    clear(8, 1, 22, 11, 3, 22)
    clear(43, 1, 22, 54, 4, 22)
    # East service rooms, with a corridor outside along the courtyard.
    box(58, 1, 28, 74, 5, 61, 'white_concrete')
    clear(59, 1, 29, 73, 4, 60)
    for z in [38, 49]:
        box(59, 1, z, 73, 4, z, 'white_concrete')
    for z in [32, 43, 55]:
        clear(58, 1, z, 58, 2, z+1)
    # Café west, open foyer south, exposed concrete columns on a clear grid.
    for x in [2, 12, 44, 56, 73]:
        for z in [25, 37, 49, 61, 71]:
            if not (x in (44, 56) and z in (49, 61)):
                box(x, 1, z, x, 5, z, 'light_gray_concrete')
    # Courtyard glass around an actual empty volume through both storeys.
    for y in range(1, 14):
        for x in range(13, 43):
            for z in [31, 61]:
                setblock(x, y, z, 'glass')
        for z in range(32, 61):
            for x in [13, 42]:
                setblock(x, y, z, 'glass')
    # Open courtyard passages on the ground floor, with beam above.
    clear(26, 1, 61, 29, 3, 61)
    clear(42, 1, 43, 42, 3, 46)
    clear(13, 1, 43, 13, 3, 46)
    box(14, 0, 32, 41, 0, 60, 'smooth_stone')
    box(18, 0, 37, 37, 0, 55, 'gravel')
    tree(24, 44)
    tree(33, 49, 7)
    for x in [16, 39]:
        box(x, 1, 36, x, 1, 56, 'birch_slab[type=bottom,waterlogged=false]')
    # Broad, traversable foyer stair. Upper-floor opening supplies head clearance.
    clear(45, 6, 54, 52, 6, 59)
    for step in range(1, 7):
        z = 59-step
        box(46, 1, z, 51, step-1, z, 'smooth_stone') if step > 1 else None
        box(46, step, z, 51, step, z,
            'smooth_quartz_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
    box(45, 6, 50, 52, 6, 52, 'smooth_stone')
    for x in [45, 52]:
        box(x, 7, 54, x, 7, 59, 'glass_pane[north=true,south=true,east=false,west=false,waterlogged=false]')
    # Recessed concrete coffer grid across the bright upper dining hall.
    for x in range(2, 75, 4):
        for z in range(24, 73):
            if not (12 <= x <= 43 and 30 <= z <= 62):
                setblock(x, 12, z, 'light_gray_concrete')
    for z in range(25, 73, 4):
        for x in range(1, 75):
            if not (12 <= x <= 43 and 30 <= z <= 62):
                setblock(x, 12, z, 'light_gray_concrete')
    for x in [4, 12, 44, 56, 72]:
        for z in [27, 43, 63, 71]:
            if not (14 <= x <= 42 and 31 <= z <= 61):
                box(x, 7, z, x, 11, z, 'light_gray_concrete')
    # White free-flow serving islands and rear working kitchen.
    box(1, 7, 1, 74, 11, 8, 'white_concrete')
    clear(2, 7, 2, 73, 10, 7)
    for x in [8, 22, 36, 50, 64]:
        clear(x, 7, 8, x+3, 9, 8)
    for x in [18, 32, 46, 60]:
        for z in [13, 22]:
            box(x, 7, z, x+6, 7, z+3, 'smooth_quartz')
            box(x+1, 8, z+1, x+5, 8, z+2, 'glass_pane[north=true,south=true,east=true,west=true,waterlogged=false]')
            box(x-1, 11, z-1, x+7, 11, z+4, 'white_concrete')
            box(x, 10, z, x+6, 10, z, 'sea_lantern')
    # Real, usable containers and cooking blocks, not painted-on food stations.
    for x, label, food in [(19, 'Bread / Brot', 'bread'), (33, 'Vegetables', 'carrot'), (47, 'Baked potatoes', 'baked_potato'), (61, 'Fruit / Obst', 'apple')]:
        setblock(x, 7, 16, 'barrel[facing=south,open=false]',
                 {'id': tag(8, 'minecraft:barrel'), 'CustomName': tag(8, json.dumps({'text': label})),
                  'Items': tag(9, (10, [{'Slot': tag(1, 0), 'id': tag(8, 'minecraft:'+food), 'count': tag(3, 32)}]))})
    for x in range(4, 72, 4):
        setblock(x, 7, 4, 'smoker[facing=south,lit=false]')
        setblock(x+1, 7, 4, 'water_cauldron[level=3]')
    # Representative dining rows, with clear aisles around the stair and courtyard.
    for z in range(33, 71, 6):
        table(4, 7, z, 6)
        for x in [56, 65]:
            table(x, 7, z, 6)
    for z in [65, 71]:
        for x in [17, 27, 37]:
            table(x, 7, z, 6)
    for z in range(29, 66, 7):
        table(4, 1, z, 6, dark=True)
    # Ground-floor café counter.
    box(3, 1, 25, 10, 1, 25, 'smooth_quartz')
    for x in [4, 7]:
        setblock(x, 2, 25, 'brewing_stand')
    # Real light sources integrated into ceiling grids.
    for x in range(6, 74, 8):
        for z in range(26, 74, 8):
            if not (12 <= x <= 43 and 30 <= z <= 62):
                setblock(x+2, 13, z+2, 'sea_lantern')
                setblock(x, 5, z, 'sea_lantern')
    # Vanilla light blocks reproduce the broad architectural lighting of the references;
    # they have no collision and don't require shaders, textures, or a paid provider.
    for x in range(3, 75, 4):
        for z in range(3, 73, 4):
            if 14 <= x <= 41 and 32 <= z <= 60:
                continue
            for y in [3, 9]:
                if BLOCKS.get((x,y,z), 'air') == 'air':
                    setblock(x,y,z,'light[level=15,waterlogged=false]')
    # Enterable main façade and weather canopy.
    clear(46, 1, 73, 53, 4, 73)
    for x in [46, 47, 50, 51, 52, 53]:
        box(x, 1, 73, x, 4, 73, 'glass')
    door(48, 73, 'left')
    door(49, 73, 'right')
    box(44, 5, 74, 55, 5, 78, 'smooth_stone_slab[type=top,waterlogged=false]')
    box(48, 4, 73, 49, 4, 73, 'stripped_birch_wood[axis=y]')
    sign(48, 4, 74, ['MENSA', 'GARCHING', 'Eingang / Entry', 'Café · Dining'])
    setblock(55, 2, 61, 'white_concrete')
    sign(55, 2, 62, ['SPEISESAAL', 'Dining upstairs', '← Treppe / Stairs', 'Level 1'])
    setblock(11, 2, 24, 'stripped_birch_wood[axis=y]')
    sign(11, 2, 25, ['STUBISTRO', 'Café', 'Ground floor', 'Preview layout'])
    sign(14, 2, 62, ['INNENHOF', 'Courtyard', 'Open to sky', 'Pines & seating'])
    # A sign at the approach explicitly labels reconstruction fidelity.
    box(57, 1, 81, 61, 3, 81, 'stripped_birch_wood[axis=y]')
    sign(59, 3, 82, ['MENSA STUDY', 'Plans + OSM', 'Approx. interior', '/function'])
    sign(59, 2, 82, ['Return to campus:', 'minecampus_mensa:', 'back', 'No map fees here'])
    return BLOCKS


def write_structure():
    geometry()
    # Include the approach in the template; stored coordinates start at zero.
    minimum = tuple(min(pos[i] for pos in BLOCKS) for i in range(3))
    maximum = tuple(max(pos[i] for pos in BLOCKS) for i in range(3))
    palette = sorted(set(BLOCKS.values()))
    ids = {name: i for i, name in enumerate(palette)}
    blocks = []
    for pos, block in sorted(BLOCKS.items()):
        record = {'pos': tag(9, (3, [pos[i]-minimum[i] for i in range(3)])), 'state': tag(3, ids[block])}
        if pos in BLOCK_ENTITIES:
            record['nbt'] = tag(10, BLOCK_ENTITIES[pos])
        blocks.append(record)
    nbt = {'DataVersion': tag(3, 3955), 'author': tag(8, 'DocMorphic / Minecampus; footprint © OpenStreetMap contributors'),
           'size': tag(9, (3, [maximum[i]-minimum[i]+1 for i in range(3)])),
           'palette': tag(9, (10, [state(s) for s in palette])),
           'blocks': tag(9, (10, blocks)), 'entities': tag(9, (10, []))}
    target = PACK / 'data/minecampus_mensa/structure/mensa.nbt'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(b'\x0a\0\0' + encode(10, nbt), mtime=0))
    summary = {'blocks': len(BLOCKS), 'palette': len(palette), 'size': [maximum[i]-minimum[i]+1 for i in range(3)],
               'template_offset': list(minimum), 'placement': [-10, 64, -10],
               'spawn': [49, 64, 94], 'upper_floor_y': 70, 'courtyard': [14, 32, 41, 60]}
    (SOURCE / 'geometry-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return target


def build():
    write_structure()
    OUTPUT.mkdir(exist_ok=True)
    target = OUTPUT / 'Minecampus-Mensa-Preview.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACK.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(PACK).as_posix())
        for file in ['README.md', 'references.json']:
            archive.write(SOURCE/file, file)
        archive.write(ROOT/'minecraft/LICENSE', 'LICENSE')
    print(f'Built {target}')
    return target


def install(world):
    target = build()
    if not (world/'level.dat').is_file():
        raise RuntimeError(f'Not an existing Minecraft save: {world}')
    destination = world/'datapacks/Minecampus-Mensa-Preview.zip'
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        backup = ROOT/'.minecampus/backups/Minecampus-Mensa-Preview.previous.zip'
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, backup)
    staging = destination.with_suffix('.tmp')
    shutil.copy2(target, staging)
    staging.replace(destination)
    print('Installed Mensa preview datapack. Existing campus chunks were not edited.')
    print('Save & Quit to Title, reopen the same world, then: /function minecampus_mensa:visit')
    print('Return to your saved campus position: /function minecampus_mensa:back')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'install'])
    parser.add_argument('--world', type=Path, default=ROOT/'.minecampus/java/saves/Minecampus Garching')
    args = parser.parse_args()
    if args.action == 'install':
        install(args.world)
    else:
        build()

# minecampus

**Survive the real TUM Garching campus as Steve. Gather. Craft. Build. Face the night.**

The default world is the **actual Bavarian aerial-survey mesh**, with real campus imagery and geometry: 273 textured tiles, 3,005,649 triangles, roofs, trees, terrain, paths, and parked cars. No Google key or external map service is required to play. The campus data is bundled in this repository (~105 MB).

## Run

Requires Node.js 22+ and a desktop browser with WebGL.

```sh
npm install
npm run dev
```

Open the localhost URL printed by Vite. The nearest survey tiles load first, followed by the surrounding campus. The first load transfers about 105 MB from the local server; later loads can use the browser cache.

```sh
npm test        # geometry damage, picking, real data integrity, coordinates, saves
npm run build  # self-contained static output in dist/
npm run preview
```

## Survival and creative play

Survival is the default. Walk and jump on the measured campus surface, mine blocks and small chunks of the survey mesh, gather dropped items, craft tools and shelter, and keep your health and hunger up. A starter kit and game-generated resource patches near the spawn help you get going. Game resources are additions to the surveyed world.

- 36 inventory slots, nine hotbar slots, finite stacks, drag-and-drop, right-click stack splitting, and shift-click transfers.
- Personal 2 × 2 crafting and placeable 3 × 3 crafting tables. The recipe book arranges available ingredients; collect the output to complete crafting.
- Wood, stone, and iron tools with mining speeds, harvest requirements, combat damage, and durability. Equip crafted iron armor through the inventory.
- Usable chests and fuel-consuming furnaces: cook meat, smelt iron ore, and turn sand into glass. Furnaces run while the game is playing; menus pause the world.
- Food consumption, hunger, saturation, sprint exhaustion, regeneration, fall damage, death, dropped possessions, and respawning. Beds set spawn and skip nighttime.
- Wheat seeds can be planted; crops mature after 90 seconds of playing. Harvest mature crops for wheat and seeds.
- Pigs, cows, and sheep wander the campus and drop food/materials when killed. Zombies chase and attack after dark; creepers approach, fuse, and blast actual geometry. Attacks require line of sight. Nearby torches suppress new hostile spawns.
- A ten-minute day/night cycle, stars, moon, held torches and placed torch illumination. **Night is simulated lighting on daytime survey imagery, not a separate nighttime scan.** N toggles day/night immediately; the cycle can be disabled in settings.

Choose Creative in settings for free flight, unlimited block placement, an item catalog, and immunity to damage. This is an original Minecraft-inspired browser survival sandbox, not the complete Minecraft game: multiplayer, redstone, liquids, dimensions, and the full vanilla recipe/mob catalog are not implemented. The real surface remains a triangle mesh with simulated excavated interiors; placed blocks use a one-metre voxel grid.

| Control          | Action                                                                    |
| ---------------- | ------------------------------------------------------------------------- |
| WASD             | Walk; fly in Creative or Photo mode                                       |
| Space / Shift    | Jump / sprint; rise / boost in Creative                                   |
| C                | Descend in flight; bypass station interaction when placing                |
| Mouse / arrows   | Look; drag if pointer lock is unavailable                                 |
| Hold left mouse  | Mine or attack                                                            |
| Right mouse      | Place, eat, open a station, use a bed, or ignite TNT with flint and steel |
| E                | Open / close inventory                                                    |
| 1–9 / wheel      | Select hotbar slot                                                        |
| F                | Eat held food                                                             |
| Q                | Drop one held item                                                        |
| N                | Toggle day / night                                                        |
| B / G (Creative) | Air-drop TNT / remotely prime nearby TNT                                  |
| M / P / V        | Explore / Photo mode / camera view                                        |
| Enter (Photo)    | Capture attributed PNG                                                    |
| R / Escape       | Return to spawn / pause                                                   |

TNT carves a 6 m sphere in Survival, or 16 m in Creative, from actual geometry. It throws textured fragments and chain-primes nearby charges. Damage changes triangle topology and raycasts. Cavities get simulated lining because the survey only contains exterior surfaces. Mining makes smaller cuts.

World edits, inventory, health, hunger, equipment, containers, crops, clock, mobs, and pickups auto-save locally. Legacy three-metre block edits are migrated to one-metre coordinates. Settings includes world reset, asset retries, and rendering mode selection.

## Campus explorer and photo mode

Open **Explore** or press **M** to jump to Informatik & Mathematik, StudiTUM, the campus U6 stop, the Institute for Advanced Study, or the Oskar von Miller tower. The viewpoints use coordinates from the bundled real map data. Letters A–E on the minimap are also clickable shortcuts; telemetry shows the nearest landmark.

Press **B** in Creative while flying to drop a TNT charge. It inherits your motion, falls under gravity, and sweeps its path against actual campus geometry to avoid passing through roofs. Impact starts a short fuse. Nearby explosions also prime falling charges. At most 12 can be active, with a short cooldown. Dropped charges pause with the game; they are temporary and clear when switching world modes. Their resulting damage auto-saves normally.

Explosions include flash, rising smoke, textured fragments, and nearby camera shake. You can turn off shake in settings; it defaults off when the browser requests reduced motion.

Press **P** or choose **Photo** for a clean view. TNT, smoke, and debris freeze while you fly and frame the scene. Use the lens slider or scroll over the scene to change field of view; **V** toggles Steve's camera. **Enter** / **Take photo** creates a PNG and opens its preview with an explicit download link. The image has no game HUD and includes location and source attribution. Press **P** or Escape to return to play. The original lens setting is restored. PNG export is available for the bundled real-campus and stylized modes, not the optional Google integration.

## What the real assets are

Source: **Bayerische Vermessungsverwaltung – www.geodaten.bayern.de**, official [DOM-Mesh](https://www.geodaten.bayern.de/odd/m/3/html/datenhinweise/datenhinweise_dommesh.html), **2024 aerial survey**, lot `124023_0`, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The mesh is derived from measured surfaces and aerial photographs, rather than OSM extrusions or generic building textures. It covers approximately 1.6 × 1.7 km around the campus, with extra edge tiles. Heights use the source's DHHN2016 datum, with a local 477 m origin.

The provider describes it as **2.5D**: it captures visible exterior surfaces. Vertical facades and vegetation can appear stretched or blurry, especially close up; there are no surveyed interiors, basements, or full structural physics. These are limitations of the aerial source, not a claim that this is a street-level scan. The character, inventory blocks, particles, and cavity lining are game assets.

See [asset attribution and source details](public/realworld/NOTICE.md).

## Additional world modes

- **Stylized footprint reconstruction**: the earlier OSM-based voxel campus remains available in settings. It has a separate save and is explicitly labeled stylized.
- **Google photorealistic tiles**: optional experimental streaming integration. It needs a restricted browser key, Map Tiles API, billing, and coverage. See [Google setup](https://developers.google.com/maps/documentation/tile/3d-tiles). You can enter a key in settings or use `.env.example`. The key is browser-visible; restrict it to your origin. This optional mode has not been verified with a live key and uses shader cutouts. It is not needed for the default real-world version.

## Prepare the real assets again

The assets are already included; ordinary development does not require Python or a data download.

The official regional archive is ~53 GiB. The preparation script uses HTTP byte ranges to fetch only its index, spatial pages, and the campus subset. It refuses responses that ignore byte ranges.

```sh
python3 -m venv .cache/geodata-venv
.cache/geodata-venv/bin/pip install -r scripts/geodata-requirements.txt
.cache/geodata-venv/bin/python scripts/prepare-survey.py
```

It converts I3S into indexed, quantized local triangles with WebP texture atlases. Source downloads stay in ignored `.cache/`; the runtime data and source manifest live in `public/realworld/`. See [ASSETS.md](ASSETS.md) for the binary format.

Refresh the optional OSM map with `node scripts/refresh-campus.mjs`.

## Architecture

- `src/survey.js` — real mesh loading, BVH picking, persistence replay, simulated cavity lining
- `src/mesh-damage.js` — sphere carving with UV-preserving boundary subdivision and textured fragments
- `src/survey-format.js` — quantized tile decoder and integrity checks
- `src/main.js` — survival/creative orchestration, character, input, TNT, saves, minimap
- `src/items.js`, `src/crafting.js` — stack operations, item definitions, recipes, smelting
- `src/survival.js`, `src/survival-ui.js` — player state, hunger, equipment, inventory and stations
- `src/physics.js` — ground movement, swept wall/floor checks, jumping and falling
- `src/life.js`, `src/environment.js` — animals, hostiles, pickups, resources, sky and torch lighting
- `src/held-item.js` — animated first-person hand and held item
- `src/landmarks.js` — map-derived landmark viewpoints and proximity
- `src/air-tnt.js` — falling charges, swept collision, impact fuses, chain priming
- `src/blast-effects.js` — flash and smoke effects
- `src/photo.js` — attributed PNG capture
- `src/campus.js` — instanced placeable blocks and optional stylized map
- `src/photoreal.js` — optional Google tile integration
- `scripts/prepare-survey.py` — reproducible source extraction and conversion

Research and references: [RESEARCH.md](RESEARCH.md).

Original code is MIT; map/survey data retain their separate licenses. See [THIRD_PARTY.md](THIRD_PARTY.md). Independent fan experiment, unaffiliated with TUM, Mojang, Microsoft, Google, or the Bavarian survey administration.

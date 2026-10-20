# minecampus

**Fly through the real TUM Garching campus as Steve. Build. Mine. Detonate.**

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

## Controls

| Control            | Action                                                             |
| ------------------ | ------------------------------------------------------------------ |
| WASD               | Fly horizontally                                                   |
| Space / C          | Rise / descend                                                     |
| Shift              | Boost                                                              |
| Mouse              | Look; drag to look if pointer lock is unavailable                  |
| Arrow keys         | Alternative camera controls                                        |
| Left click         | Place the selected block on a real campus surface or another block |
| Right click        | Mine a placed block or cut the real mesh                           |
| 1–6 / wheel        | TNT, grass, stone, oak, brick, glass                               |
| E                  | Prime TNT within 220 m; fuse lasts about 2.5 seconds               |
| Q                  | Drop TNT while flying                                              |
| M                  | Landmark menu and fast travel                                      |
| P                  | Photo mode                                                         |
| Enter (photo mode) | Capture photo for preview and PNG export                           |
| V                  | First-person / Steve chase camera                                  |
| R                  | Return above CIT / Informatik & Mathematik                         |
| Escape             | Pause and release mouse                                            |

TNT carves a 16 m sphere out of actual mesh geometry, throws textured fragments from the damaged surface, and chain-primes nearby TNT. Damage changes the triangle topology and subsequent raycasts; it is not just a shader mask. Blast cavities get a simulated interior lining, because the survey only contains exterior surfaces. Mining makes smaller cuts.

Blocks and survey damage auto-save in this browser and survive reloads. Pausing freezes fuses. Settings includes reset, asset retries, world mode selection, and return to spawn. Creative flight permits passing through structures. Flight bounds keep you within the included campus area.

## Campus explorer and photo mode

Open **Explore** or press **M** to jump to Informatik & Mathematik, StudiTUM, the campus U6 stop, the Institute for Advanced Study, or the Oskar von Miller tower. The viewpoints use coordinates from the bundled real map data. Letters A–E on the minimap are also clickable shortcuts; telemetry shows the nearest landmark.

Press **Q** while flying to drop a TNT charge. It inherits your motion, falls under gravity, and sweeps its path against actual campus geometry to avoid passing through roofs. Impact starts a short fuse. Nearby explosions also prime falling charges. At most 12 can be active, with a short cooldown. Dropped charges pause with the game; they are temporary and clear when switching world modes. Their resulting damage auto-saves normally.

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
- `src/main.js` — flight, character, input, inventory, TNT, effects, saves, minimap
- `src/landmarks.js` — map-derived landmark viewpoints and proximity
- `src/air-tnt.js` — falling charges, swept collision, impact fuses, chain priming
- `src/blast-effects.js` — flash and smoke effects
- `src/photo.js` — attributed PNG capture
- `src/campus.js` — instanced placeable blocks and optional stylized map
- `src/photoreal.js` — optional Google tile integration
- `scripts/prepare-survey.py` — reproducible source extraction and conversion

Research and references: [RESEARCH.md](RESEARCH.md).

Original code is MIT; map/survey data retain their separate licenses. See [THIRD_PARTY.md](THIRD_PARTY.md). Independent fan experiment, unaffiliated with TUM, Mojang, Microsoft, Google, or the Bavarian survey administration.

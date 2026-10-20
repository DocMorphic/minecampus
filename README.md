# minecampus

**Your campus. Your sandbox.** Fly over TUM Garching as a Steve-style block character, build in mid-air, and detonate TNT across a real campus layout.

A local-first browser game built with Three.js, Vite, OpenStreetMap, and optional Google Photorealistic 3D Tiles. No Minecraft installation needed.

## Run

Requires Node.js 22+.

```sh
npm install
npm run dev
```

Open the localhost URL printed by Vite. Desktop keyboard and mouse recommended. WebGL is required.

```sh
npm test       # coordinate, picking, instance-removal, blast and save tests
npm run build # production output in dist/
npm run preview
```

## Play

| Control           | Action                                                      |
| ----------------- | ----------------------------------------------------------- |
| WASD              | Fly horizontally                                            |
| Space / C         | Rise / descend                                              |
| Shift             | Boost                                                       |
| Mouse             | Look around; drag if pointer lock is unavailable            |
| Arrow keys        | Alternative camera controls                                 |
| Left click        | Place selected block at the crosshair                       |
| Right click       | Mine a block                                                |
| 1–6 / mouse wheel | TNT, grass, stone, oak, brick, glass                        |
| E                 | Prime placed TNT within 220 m; fuse lasts about 2.5 seconds |
| V                 | First-person / Steve chase camera                           |
| R                 | Return to spawn                                             |
| Escape            | Pause and release the mouse                                 |

TNT removes blocks in a 16 m sphere and triggers nearby TNT. You can mine and stack blocks, including on roofs. The pause menu freezes fuses. Flight intentionally allows passing through structures. Open map edits save in this browser; settings includes a reset.

## Two world modes

**Open map campus (default, no key).** Bundled real OpenStreetMap data covers approximately 1.7 × 1.8 km around Garching. It includes 272 building footprints, roads, and mapped land/water areas. Buildings become destructible 3 m shell voxels. Heights use mapped heights or level counts where available, otherwise an estimate. This is a stylized reconstruction of the real layout, not a surveyed model or a photorealistic scan. Roofs and facades are procedural; terrain is flat.

**Photorealistic 3D (optional).** Open settings, select Google photorealistic 3D, and enter a restricted browser API key with **Map Tiles API** enabled and billing configured. See [Google's setup documentation](https://developers.google.com/maps/documentation/tile/3d-tiles). Alternatively copy `.env.example` to `.env` and set `VITE_GOOGLE_MAPS_API_KEY`. Vite variables are browser-visible: use an origin-restricted browser key, never a server secret. The settings input stays in tab memory and is not saved to storage.

This mode streams actual textured geometry into the same local east/up/south coordinate frame. It requires provider coverage, network access, and an eligible Maps account. Ground starts at an estimated 525 m WGS84 ellipsoid elevation; adjust in settings if the camera appears above/below the surface. Photorealistic operation has not been end-to-end verified with a live key.

In photorealistic mode TNT creates shader cutouts (up to 32 recent blast regions), with block debris. It does not physically fracture the source tile mesh. Mining also creates small cutouts. Block edits and cutouts in this mode are session-only. Source tiles stream in memory without being archived or exported. Attribution is collected from visible tiles and shown on screen. Switch back to open map mode to restore your saved voxel campus.

## Research

See [RESEARCH.md](RESEARCH.md) for similar projects, source links, architectural decisions, and the investigation of Reverse Engineer Anything. The exact X video the original idea refers to could not be identified reliably.

## Data refresh

The default map is bundled, so normal play needs no Overpass service. To deliberately refresh it:

```sh
node scripts/refresh-campus.mjs
```

An alternate Overpass interpreter URL can be passed as the first argument. The refresh tool preserves the existing file on HTTP errors or empty data. The data snapshot was retrieved on 20 October 2026.

## Source layout

- `src/campus.js` — campus footprint voxelization, instanced blocks, edits, blast damage, saves
- `src/geo.js` — local projection and voxel ray traversal
- `src/main.js` — game loop, cameras, input, TNT, particles, minimap, UI
- `src/photoreal.js` — Google tiles, coordinate transform, attribution, visual cutouts
- `src/steve.js` / `src/textures.js` — original procedural character and block artwork
- `public/data/garching-osm.json` — attributed OSM snapshot

## Licensing

Original project code is MIT. OpenStreetMap data is © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/); the data is not relicensed under MIT. Google tiles retain Google's and its providers' terms. See [THIRD_PARTY.md](THIRD_PARTY.md). This is an independent fan experiment, unaffiliated with TUM, Mojang, Microsoft, or Google.

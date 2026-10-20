# Research and implementation notes

Research date: 20 October 2026.

## Closest public examples

### MineMaps — Minecraft in Google Maps

- https://minemaps.fun/
- Its own site describes playing at real addresses, building/moving/mining, and TNT interactions, originally using Street View; it also advertises a 3D mode.
- It is a close product reference for a low-friction browser experience with familiar controls. We did not retrieve or copy its implementation.

### Voxel Earth — real places converted to Minecraft

- https://github.com/ryanhlewis/VoxelEarth
- https://github.com/voxelearth/web-client
- The maintainers document a pipeline from 3D Tiles through decoding and voxelization to Minecraft blocks, plus a browser viewer.
- Useful architecture reference if future work should voxelize textured campus geometry, rather than use the current OSM footprint reconstruction.
- This project does not embed Voxel Earth's pipeline or claim to run Minecraft Java.

### Soar — real-world flight in the browser

- https://github.com/heilcheng/soar
- Its README describes Cesium rendering Google Photorealistic 3D Tiles and Three.js handling a bird, flight, and effects, with a chase camera.
- Useful evidence that the real-world streaming plus independent character layer approach works. Minecampus uses a single Three.js renderer with 3DTilesRendererJS instead of copying Soar's dual-renderer implementation.

### 3DTilesRendererJS — rendering foundation

- https://github.com/NASA-AMMOS/3DTilesRendererJS
- Official source documents Three.js tile rendering, Google authentication, glTF/Draco loading, ellipsoid coordinate math, and attribution collection.
- Minecampus uses this package directly. Google tiles are transformed into a local east/up/south frame centred on Garching.

## X research limit

Web searches targeting X and Steve/Minecraft/real-world map demos did not reliably identify the exact clips being referenced. The examples above were verified on their own sites/repositories. They should not be presented as the authors of a particular X clip. A direct clip URL would allow more precise comparison later.

## Reverse Engineer Anything (REA)

- Canonical repository: https://github.com/morluto/rea
- The official README describes tooling for investigating binaries, JavaScript/Electron applications, and runtime behaviour, with evidence-driven output.
- There are similarly named forks and mirror sites. The canonical README advises using its official distribution sources.
- REA was investigated but not installed. Public implementation/documentation already explains the relevant mapping and rendering techniques; native binary reverse engineering adds no necessary step here.

## Campus data options

### OpenStreetMap (implemented default)

- https://www.openstreetmap.org/copyright
- Real Garching footprints and road centre-lines, obtained via Overpass. Bundled snapshot: 272 buildings, with geometry in latitude/longitude.
- Reliable no-key startup, editable geometry, and an open-data source. Approximate/absent heights, no aerial texture, flat terrain, and incomplete multipolygon handling limit fidelity.
- Snapshot bbox: west 11.659, south 48.257, east 11.682, north 48.273.

### Google Photorealistic 3D Tiles (optional integration)

- https://developers.google.com/maps/documentation/tile/3d-tiles
- Official documentation requires an API key, Map Tiles API, billing, compatible tile rendering, and attribution. Coverage/account eligibility matter; Google documents EEA-specific conditions as well.
- Do not assume a no-key photorealistic scene is available. We did not use an extracted key from another demo.
- Shader holes simulate destruction in streamed triangle meshes; they are visual cutouts, not permanent geometry edits or a full voxelization pipeline.

### TUM open data / digital twins (future investigation)

- https://www.asg.ed.tum.de/gis/offene-daten/
- https://twinview.zv.tum.de/
- TUM's open-data page points to its TUM2TWIN work, and TwinView presents campus building scans. We did not establish that an openly licensed, complete, browser-ready Garching mesh is available. Some digital twin data concerns the Munich main campus; do not assume it covers Garching.

## Next fidelity improvement

A licensed Garching photogrammetry/CityGML asset could be used for detailed geometry and voxelization. For the current playable build, open map mode supplies actual campus arrangement and deterministic destruction; optional Google mode supplies streamed visual realism after the user provides an eligible browser key.

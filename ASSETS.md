# Real campus data and runtime format

The default scene uses 273 leaf tiles extracted from the official Bavarian `124023_0` DOM-Mesh SLPK. The source is an I3S IntegratedMesh 1.7 in EPSG:25832 with heights in DHHN2016. Its 2024 aerial textures and geometry remain under CC BY 4.0; see `public/realworld/NOTICE.md`.

The source archive is ~57.2 GB in decimal units. The exporter reads its ZIP64 directory with HTTP Range, indexes the I3S node pages, and selects leaf nodes intersecting the campus rectangle. The exact selection uses a conservative bounding-sphere intersection around UTM origin `(698213.9657, 5349203.4379)`, half-width 800 m and half-height 850 m. Edge tiles extend beyond this rectangle.

Original per-node vertex positions are relative to the node's OBB centre; they are translated back to UTM, transformed to WGS84, then projected into the same local east/up/south coordinates as the game's map. Vertical zero is 477 m DHHN2016. UVs retain the I3S upper-left convention (`Texture.flipY = false`). JPEG texture atlases are re-encoded to WebP quality 88. No generated building imagery substitutes for source imagery.

## MCM1 tile

All numeric fields use little-endian byte order.

| Offset               | Type                      | Meaning                           |
| -------------------- | ------------------------- | --------------------------------- |
| 0                    | 4 ASCII bytes             | `MCM1` magic                      |
| 4                    | uint32                    | Number of unique vertices         |
| 8                    | uint32                    | Number of triangle indices        |
| 12                   | uint32                    | Reserved, zero                    |
| 16                   | uint16 × vertex count × 5 | Interleaved quantized `X Y Z U V` |
| following attributes | zero padding              | Align to 4 bytes                  |
| aligned offset       | uint32 × index count      | Triangle indices                  |

Each tile's `min` and `scale` are stored in `manifest.json`. Decode positions with `min + quantized / 65535 * scale` and UVs with `quantized / 65535`. Deduplication uses the full XYZUV tuple, retaining texture seams. Original triangle order and topology remain intact before gameplay damage.

The runtime decoder checks the magic, byte length, maximum counts, and every index. Tests verify all included tiles and check the real CIT roof's position and UV coordinates.

## Damage

The survey mesh uses BVHs for picking and blast intersection queries. A blast removes intersecting triangles; boundary triangles are recursively split while interpolating UVs, preserving source texture alignment. The geometry index and vertex arrays are replaced, and its BVH rebuilt. Raycasts then recognize the physical opening.

Textured pieces are emitted from the original damaged triangles. A dark, game-generated hemispherical lining gives a cavity a visible interior; it is not surveyed indoor data. Additional blasts also cut existing cavity linings.

Saved edits record world-space blast centres and radii, replayed on every tile as it loads. Placed inventory blocks are stored alongside this edit list. The source files remain unchanged. Reset clears the browser's corresponding save.

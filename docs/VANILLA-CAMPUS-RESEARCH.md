# Realistic campus with vanilla-client joining

Research date: 2026-10-31. Status: conversion prototype, not a playable server.

The intended guest flow is **Minecraft Java → Multiplayer → server address → accept the server resource pack**. This avoids a separately installed mod, launcher bundle or guest map key. It still downloads campus data through Minecraft. Windows, macOS and Linux clients must use the same supported Java Edition version.

The earlier assertion that an unmodified client necessarily requires rebuilding the campus out of cubes was too broad. Resource packs can override core shaders and encode arbitrary textured meshes. This offers a plausible rendering port; it does not automatically port RealWorldMC collision, terrain edits or lighting.

## Existing implementations

- [Godlander/objmc](https://github.com/Godlander/objmc), MIT: converts OBJ geometry into model faces plus textures that encode vertices, decoded by resource-pack shaders. Its documentation recommends optimizing face counts, warns about culling, and describes block models as more efficient than entity models. This is the basis of our probe.
- [JagerMeistars/obj-cubed](https://github.com/JagerMeistars/obj-cubed): a maintained fork with additional authoring features. Its current formats target newer Minecraft versions; version matching is necessary.
- [3DEngine](https://resourcepack.ai/docs/3d-engine): documents importing OBJ/GLB/glTF meshes into a server plugin and sending a generated resource pack to vanilla players. Its documented target is Minecraft 26.3, so it is not a drop-in plugin for this project's 1.21.1 setup. We have not installed or benchmarked it. It demonstrates an existing implementation of the desired distribution approach.
- [Paper's server properties](https://docs.papermc.io/paper/reference/server-properties/#resource-pack): document the resource-pack URL, hash, prompt and required-pack settings. Hosting a reachable server and pack URL remains necessary.

These sources establish the technique and joining mechanism, not performance for our campus. Core shader overrides also need a fixed supported Minecraft version; changing versions or combining other core shader packs may break them.

## Prototype in this repository

`scripts/build-vanilla-campus-probe.py` converts the existing warehouse exterior and aerial roof into a 403-triangle, five-part model. It uses the existing BVV-based geometry, CC0 material and BVV roof imagery; these retain the attribution in `THIRD_PARTY.md`. No Google tiles, Minecraft binaries or credentials are included in the output.

The script pins objmc commit `940ed38dd0ca87739aa7fadd7ff5924aaf4227de`, preserves its MIT license, records upstream and patched converter hashes, and targets Java 1.21.1. Local patches remove Windows console cosmetics and correct the historical CLI compression default. Texture paths are placed in the item atlas directories, and source dimensions are rounded up to powers of two to avoid disabling atlas mipmaps. The shaders are adapted by pack metadata only, not rewritten.

Prerequisites: generated `dist-minecraft/exterior` assets, Python with Pillow, Tkinter (imported by upstream), and network access for the pinned converter. The existing geodata environment supplies these locally.

```sh
.cache/geodata-venv/bin/python scripts/build-vanilla-campus-probe.py
```

Outputs are in `dist-minecraft/vanilla-probe/`: a resource-pack ZIP, datapack ZIP, and `validation.json`. Build staging is confined to `.cache/vanilla-campus-probe/`. This does not alter the installed campus, its saves, or existing friend packages.

For a manual isolated check, use a new creative Java 1.21.1 world, enable the generated resource pack, install the datapack into that world's `datapacks` folder and run `/reload`. Stand on open ground and run `/function minecampus_probe:place`. Remove the displays with `/function minecampus_probe:clear`. The model is centered horizontally at the command position. It has no collision or destruction behavior.

Export checks cover ECT integrity, source/encoder hashes, triangle counts, encoded texture markers and ZIP CRCs. A local unmodified client loaded the prototype pack and atlas. The desktop automation interface could not bind to its Java window, so **visual rendering is unverified**. Shader uniform warnings remain to investigate. Server delivery, remote joining, campus-scale performance and collision/destruction have not been tested. False flags in the generated validation report must not be interpreted as passed checks.

## Campus-scale implementation path

The main exterior manifest has 483 tiles containing approximately **3,058,064 triangles**: 987,348 ground, 700,174 reconstruction and 1,370,542 vegetation triangles. This excludes auxiliary roof/collision streams and distant streamed imagery. The existing source contains about 434 MiB of raw RGBA texture data with substantial duplication. These figures are input measurements, not expected resource-pack sizes or GPU benchmarks.

1. Visually verify the small model, scale, UVs, depth, lighting and culling on unmodified 1.21.1. Test a server-sent pack with a second vanilla client.
2. Compare efficient chunk-sized block meshes against item displays, preserving the recognizable buildings and textures. Deduplicate textures, simplify vegetation and reduce distant detail. Benchmark a representative campus area before committing to the whole scene.
3. Generate server-side terrain/collision and handle construction, breaking and TNT damage so visible meshes stay consistent with gameplay. Vanilla inventory, crafting, food, mobs, combat and sound already come from Minecraft; custom campus geometry interaction does not.
4. Package only redistributable assets into a bounded campus, host the resource pack and authenticated Minecraft server, and test actual remote joining across the supported operating systems. Avoid guest credentials by using the open campus layer instead of Google/Cesium streaming.

This is a feasible direction to investigate, not a completed replacement for the current Fabric release. There is no new public vanilla server address yet.

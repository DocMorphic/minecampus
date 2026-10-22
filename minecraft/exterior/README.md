# Garching exterior meshes

This is a native Minecraft Java 1.21.1 upgrade. The surrounding campus remains Google's textured 3D photogrammetry, streamed through the user's configured provider. Near the ground, the central campus adds:

- A 600 × 600 m surveyed terrain mesh, with official DGM1 heights and DOP20 aerial imagery at 20 cm per pixel.
- Two Galileo building components with surveyed footprints/roof geometry, recessed window geometry, glass reflections and shaded metal panels.
- Three surveyed grass-roof promenade structures, including their sloping roof surfaces.
- Fine ground material detail and atmospheric distance fading.

Elevated flight uses the photographic mesh; the detailed ground scene activates on descent, with hysteresis to prevent repeated switching near the transition. An explicit loading message remains while geometry streams.

The Galileo window pattern is reconstructed from a CC0 photograph and repeated across the surveyed walls. It is an architectural approximation. Other façades, trees and street objects retain the quality limits of the original scan. There are no reconstructed interiors in this update.

## Play

Run `python3 scripts/minecraft.py install`, then launch **Minecampus — TUM Garching** from the official Minecraft Launcher. An existing provider configuration is retained. A fresh installation still needs the masked provider setup described in the [native guide](../README.md).

Create a **TUM Garching — Minecampus** world for an undamaged campus. Existing saves retain their player builds and recorded excavation/TNT damage. The deleted Mensa interior preview is no longer included.

## How collisions and damage work

Both new chunks and existing nearby Garching chunks receive proxy blocks voxelized from the same survey surfaces. The migration keeps ordinary Minecraft blocks and positions in the authoritative edit journal. It suppresses recording of its own repairs, and stores completed chunks so the operation survives save/reload. Actual player mining, placement and TNT continue through Minecraft and RealWorldMC's damage system.

The collision grid remains Minecraft's one-metre block grid. A sloping photographic surface and its supporting block tops can differ by up to approximately half a block. A repeated application must preserve edits, rather than infer player damage from a changed terrain LOD.

## Rebuild

Use Python 3.9+ in an isolated environment, JDK 21, Node.js 22+ and Git:

```sh
python3 -m venv .venv-exterior
.venv-exterior/bin/pip install -r minecraft/exterior/requirements.txt
.venv-exterior/bin/python scripts/build-exterior.py --download
python3 scripts/validate-exterior.py
python3 scripts/build-exterior-release.py --java-home /absolute/path/to/jdk-21
```

The downloader fetches only the public inputs pinned in [sources.json](sources.json). Source data is about 150 MB. Output remains in ignored `dist-minecraft/`; it contains no provider credentials or saved worlds. Official download URLs can be updated by their publisher: a changed input hash fails verification until the source manifest is deliberately updated.

The release builder checks the upstream JAR and embedded service hashes, checks out the pinned Apache-2.0 source into a generated cache directory, applies [the patch](patches/realworldmc-exterior.patch), compiles it and adds the open-data meshes to the existing portable service. It preserves the upstream runtime/licenses and adds asset notices. No Minecraft assets or Google tile files are bundled.

[Research](RESEARCH.md) · [Native validation](VALIDATION.md) · [Third-party notices](../../THIRD_PARTY.md)

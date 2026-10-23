# Exterior Preview 0.5

This playable development snapshot adds the IAS exterior, survey-aligned photographic walls, the former Mensa terrace frontage and retaining walls, UYA's outer façades, UYE's east/north glazing, the masonry warehouse exterior, width-mapped road materials, the Telefonzentrale west end, the COS exterior, approximate finished-site grading, mapped site paving, benches, bicycle stands, an inferred planting bed, a smooth forecourt grade and the GRS north wing, stair tower, connecting bridges, repaired GRS II exterior and GRS III square wing/rounded tower, the small GRS II/III connector and a paved courtyard approach, survey-fitted tree crowns, mapped ground materials and full DGM1 terrain sampling. It also adds local mesh shadows that follow the sun, react to terrain damage, and turn off at night. It runs inside Minecraft Java 1.21.1 with the existing Minecampus add-on and Fabric setup.

The campus is still unfinished: several neighboring walls remain blurry, paths have inconsistent detail, and reconstructed window divisions/materials are approximate. Interiors are outside this pass. The public default installer remains on 0.4.0.

## Play the installed copy

On the development machine, restart the official Minecraft Launcher, open **Installations**, select **Minecampus — Exterior Preview 0.5**, and click **Play**. Open **Minecampus Garching** from Singleplayer. The copied world preserves inventory and edits as they stood when installed. Further progress belongs to this preview copy; the original **Minecampus — TUM Garching** installation remains separate.

Allow the map to finish streaming before judging geometry. The photographic façade pass can take several minutes on first entry. Existing local map credentials are reused; no new key is needed.

## Install the same snapshot alongside an existing setup

1. Quit Minecraft and its launcher.
2. Download `RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar` from the [0.5 development preview release](https://github.com/DocMorphic/minecampus/releases/tag/exterior-0.5.0-dev.11) into this repository's `dist-minecraft/` directory.
3. On macOS/Linux, run `python3 scripts/install-exterior-preview.py` from the repository root. This requires the normal Minecampus installation and its map setup to exist already. It verifies the artifact hash, checks world locks, copies saves into a separate instance, verifies every copied save file, and adds the preview launcher profile. For an existing preview, use `python3 scripts/install-exterior-preview.py --update` instead. This verifies the recorded mod, refuses an open world, backs up the old mod, and replaces only that mod while verifying that saves and local settings stay unchanged.
4. Restart the launcher and follow the play instructions above.

The installer uses the current user's local map configuration, stored privately in the new instance. Credentials, saves, Minecraft assets and streamed provider imagery are absent from the public download.

## Evidence

The released JAR is the exact native-tested artifact: SHA-256 `a2fc7761fbda0828f351b72f0fd79de04da92373d914c23b38e89a4711cebe5b`. Thirty-five route views retain the existing 33 gameplay/geometry checks and add GPU lighting checks at every camera. A separate seven-capture check verifies actual TNT damage in the shadow map, restoration, morning/evening/night, framebuffer replacement on texture reload, and retained mipmap sampling. The 27 service tests and three updater tests also pass. See [the validation record](runtime-shadow-development-validation.json).

All geometry, photographic materials, terrain and the bundled service remain byte-identical to dev.10. Collision migration remains v18. The new pass draws a local 4096² depth map from the loaded campus meshes, including leaf cutouts. It uses Minecraft's sun direction for both shadows and material lighting. Texture reloading now regenerates shared material mipmaps even when Minecraft reuses the same texture IDs.

Only map meshes cast and receive these new shadows. Vanilla blocks, players and mobs do not participate, and aerial images retain their baked shadows. Glass still uses an approximate sky/ground reflection. Small sampling patterns can remain at thin edges, and shadows fade at the local map boundary. These are known limits of this preview.

![GRS courtyard with mesh shadows](../../docs/screenshots/campus-runtime-shadow-courtyard.jpg)

The broader visual-quality goal remains open. Functional checks establish playability of the tested cases, not completion of the campus reconstruction.

# Exterior Preview 0.5

This playable development snapshot adds the IAS exterior, survey-aligned photographic walls, the former Mensa terrace frontage and retaining walls, UYA's outer façades, UYE's east/north glazing, the masonry warehouse exterior, width-mapped road materials, the Telefonzentrale west end, the COS exterior, approximate finished-site grading, mapped site paving, benches, bicycle stands, an inferred planting bed, a smooth forecourt grade and the GRS north wing, stair tower, connecting bridges, repaired GRS II exterior and GRS III square wing/rounded tower, the small GRS II/III connector and a paved courtyard approach, survey-fitted tree crowns, mapped ground materials and full DGM1 terrain sampling. Four main asphalt promenade corridors, eight crossing/entrance paths and smoother ground-material boundaries reduce blurry path margins. Galileo’s northern sunken courtyard now has retaining walls, a lower paved floor, five stair flights, handrails and lower exterior glazing, replacing the stretched terrain bank. It also adds local mesh shadows that follow the sun, react to terrain damage, and turn off at night. It runs inside Minecraft Java 1.21.1 with the existing Minecampus add-on and Fabric setup.

The campus is still unfinished: several neighboring walls remain blurry, paths have inconsistent detail, and reconstructed window divisions/materials are approximate. Interiors are outside this pass. The public default installer remains on 0.4.0.

## Play the installed copy

On the development machine, restart the official Minecraft Launcher, open **Installations**, select **Minecampus — Exterior Preview 0.5**, and click **Play**. Open **Minecampus Garching** from Singleplayer. The copied world preserves inventory and edits as they stood when installed. Further progress belongs to this preview copy; the original **Minecampus — TUM Garching** installation remains separate.

Allow the map to finish streaming before judging geometry. The photographic façade pass can take several minutes on first entry. Existing local map credentials are reused; no new key is needed.

## Install the same snapshot alongside an existing setup

1. Quit Minecraft and its launcher.
2. Download `RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar` from the [0.5 development preview release](https://github.com/DocMorphic/minecampus/releases/tag/exterior-0.5.0-dev.14) into this repository's `dist-minecraft/` directory.
3. On macOS/Linux, run `python3 scripts/install-exterior-preview.py` from the repository root. This requires the normal Minecampus installation and its map setup to exist already. It verifies the artifact hash, checks world locks, copies saves into a separate instance, verifies every copied save file, and adds the preview launcher profile. For an existing preview, use `python3 scripts/install-exterior-preview.py --update` instead. This verifies the recorded mod, refuses an open world, backs up the old mod, and replaces only that mod while verifying that saves and local settings stay unchanged.
4. Restart the launcher and follow the play instructions above.

The installer uses the current user's local map configuration, stored privately in the new instance. Credentials, saves, Minecraft assets and streamed provider imagery are absent from the public download.

## Evidence

The released JAR is the exact native-tested artifact: SHA-256 `ab7922f5ca2fcf05797bb1b1b98b2120333a5500b50d39a868bd43ccb517c72d`. [Detailed evidence](galileo-court-development-validation.json) records 42 fresh native captures, all 35 earlier checks, eight courtyard gravity controls, the 42-frame GPU lighting route, and seven separate TNT/sky/reload captures. The service suite has 28 passing tests; terrain/updater tests have eight.

The courtyard replaces approximately 681 m² of stretched terrain with a bounded cut and fitted structures. Two ground tiles change; 95 earlier render tiles, all previous ground-material masks, survey guides and old architecture stay unchanged. The lower floor follows the median BVV DGM height. The OSM court/wall/stair records establish the envelope, 4 m width and 27 risers; flight stations, wall dimensions, lower glazing and a 0.65 m stair alignment correction are estimates. The lower landing connects to the open court. Interiors and reference photographs are not included.

Collision migration is v19 and preserves ordinary player blocks and recorded edits. Gravity tests land within 0.35 m of the visible floor/landings, using the existing one-metre proxy grid. This does not provide fine collision for every visual tread. Galileo facade fidelity, courtyard landscaping, some building-base joins and neighbouring source artifacts remain unfinished.

![Galileo courtyard before](../../docs/screenshots/campus-galileo-court-floor-before.jpg)

![Galileo courtyard after](../../docs/screenshots/campus-galileo-court-floor-after.jpg)

![Galileo courtyard stairs](../../docs/screenshots/campus-galileo-court-stairs-after.jpg)

![Northern crossing with asphalt](../../docs/screenshots/campus-crosspath-north-after.jpg)

Pale margins around the sculpture and some junctions remain. Galileo’s former stretched bank is now reconstructed; courtyard landscaping and some facade-base joins still need work. Older aerial shading and approximate facade/reflection detail also remain unfinished.

Only map meshes cast and receive these new shadows. Vanilla blocks, players and mobs do not participate, and aerial images retain their baked shadows. Glass still uses an approximate sky/ground reflection. Small sampling patterns can remain at thin edges, and shadows fade at the local map boundary. These are known limits of this preview.

![GRS courtyard with mesh shadows](../../docs/screenshots/campus-runtime-shadow-courtyard.jpg)

The broader visual-quality goal remains open. Functional checks establish playability of the tested cases, not completion of the campus reconstruction.

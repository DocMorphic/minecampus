# Exterior Preview 0.5

This playable development snapshot adds the IAS exterior, survey-aligned photographic walls, the former Mensa terrace frontage and retaining walls, UYA's outer façades, UYE's east/north glazing, the masonry warehouse exterior, width-mapped road materials, the Telefonzentrale west end, the COS exterior, approximate finished-site grading, mapped site paving, benches, bicycle stands, an inferred planting bed, a smooth forecourt grade and the GRS north wing, stair tower, connecting bridges, repaired GRS II exterior and GRS III square wing/rounded tower, the small GRS II/III connector and a paved courtyard approach, survey-fitted tree crowns, mapped ground materials and full DGM1 terrain sampling. Four main asphalt promenade corridors, eight crossing/entrance paths and smoother ground-material boundaries reduce blurry path margins. Galileo’s northern sunken courtyard now has retaining walls, a lower paved floor, five stair flights, handrails and lower exterior glazing, replacing the stretched terrain bank. The two Galileo facades now have separate pale metal panels, recessed glazing, fine joints and narrow ventilation fins in place of the repeated photographic strip. It also adds local mesh shadows that follow the sun, react to terrain damage, and turn off at night. It runs inside Minecraft Java 1.21.1 with the existing Minecampus add-on and Fabric setup.

The campus is still unfinished: several neighboring walls remain blurry, paths have inconsistent detail, and reconstructed window divisions/materials are approximate. Interiors are outside this pass. The public default installer remains on 0.4.0.

## Play the installed copy

On the development machine, restart the official Minecraft Launcher, open **Installations**, select **Minecampus — Exterior Preview 0.5**, and click **Play**. Open **Minecampus Garching** from Singleplayer. The copied world preserves inventory and edits as they stood when installed. Further progress belongs to this preview copy; the original **Minecampus — TUM Garching** installation remains separate.

Allow the map to finish streaming before judging geometry. The photographic façade pass can take several minutes on first entry. Existing local map credentials are reused; no new key is needed.

## Install the same snapshot alongside an existing setup

1. Quit Minecraft and its launcher.
2. Download `RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar` from the [0.5 development preview release](https://github.com/DocMorphic/minecampus/releases/tag/exterior-0.5.0-dev.15) into this repository's `dist-minecraft/` directory.
3. On macOS/Linux, run `python3 scripts/install-exterior-preview.py` from the repository root. This requires the normal Minecampus installation and its map setup to exist already. It verifies the artifact hash, checks world locks, copies saves into a separate instance, verifies every copied save file, and adds the preview launcher profile. For an existing preview, use `python3 scripts/install-exterior-preview.py --update` instead. This verifies the recorded mod, refuses an open world, backs up the old mod, and replaces only that mod while verifying that saves and local settings stay unchanged.
4. Restart the launcher and follow the play instructions above.

The installer uses the current user's local map configuration, stored privately in the new instance. Credentials, saves, Minecraft assets and streamed provider imagery are absent from the public download.

## Evidence

The released JAR is the exact native-tested artifact: SHA-256 `c7fdbce22d557420cae0a07dfd502fc53362d0319f8174928ca9f6349b4ea6fd`. [Detailed evidence](galileo-facade-development-validation.json) records 47 fresh native captures, 40 geometry/gameplay checks, eight courtyard gravity controls, the 47-frame GPU lighting route, and seven separate TNT/sky/reload captures.

This checkpoint replaces only the two Galileo wall meshes. Both embedded survey roofs, the other 97 render tiles, terrain, courtyard, vegetation and existing guides remain unchanged. The panel/window system follows the contractor and completed exterior photographs. Its 1.4 m modules, floor divisions and row sequences remain estimates; exact entrance and transparent ground-floor zones are unfinished. Contractor photographs are research references, not texture assets.

The earlier courtyard repair remains intact: about 681 m² of bounded terrain cut, retaining walls, 27 risers across five flights and a connected lower landing. Collision migration is now v20 and preserves ordinary player blocks and recorded edits. The existing one-metre proxy grid still approximates visual treads.

![Galileo facade before](../../docs/screenshots/campus-galileo-facade-before.jpg)

![Galileo facade after](../../docs/screenshots/campus-galileo-facade-after.jpg)

![Galileo aerial view](../../docs/screenshots/campus-galileo-facade-aerial.jpg)

![Galileo courtyard stairs](../../docs/screenshots/campus-galileo-court-stairs-after.jpg)

![Northern crossing with asphalt](../../docs/screenshots/campus-crosspath-north-after.jpg)

Pale margins around the sculpture and some junctions remain. Galileo’s former stretched bank is now reconstructed; courtyard landscaping and some facade-base joins still need work. Older aerial shading and approximate facade/reflection detail also remain unfinished.

Only map meshes cast and receive these new shadows. Vanilla blocks, players and mobs do not participate, and aerial images retain their baked shadows. Glass still uses an approximate sky/ground reflection. Small sampling patterns can remain at thin edges, and shadows fade at the local map boundary. These are known limits of this preview.

![GRS courtyard with mesh shadows](../../docs/screenshots/campus-runtime-shadow-courtyard.jpg)

The broader visual-quality goal remains open. Functional checks establish playability of the tested cases, not completion of the campus reconstruction.

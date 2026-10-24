# Exterior Preview 0.5

This playable development snapshot adds the IAS exterior, survey-aligned photographic walls, the former Mensa terrace frontage and retaining walls, UYA's outer façades, UYE's east/north glazing, the masonry warehouse exterior, width-mapped road materials, the Telefonzentrale west end, the COS exterior, approximate finished-site grading, mapped site paving, benches, bicycle stands, an inferred planting bed, a smooth forecourt grade and the GRS north wing, stair tower, connecting bridges, repaired GRS II exterior and GRS III square wing/rounded tower, the small GRS II/III connector and a paved courtyard approach, survey-fitted tree crowns, mapped ground materials and full DGM1 terrain sampling. Four main asphalt promenade corridors, eight crossing/entrance paths and smoother ground-material boundaries reduce blurry path margins. Galileo’s northern sunken courtyard now has retaining walls, a lower paved floor, five stair flights, handrails and lower exterior glazing, replacing the stretched terrain bank. The two Galileo facades now have separate pale metal panels, recessed glazing, fine joints and narrow ventilation fins in place of the repeated photographic strip. It also adds local mesh shadows that follow the sun, react to terrain damage, and turn off at night. Nearby Galileo glazing now reflects loaded campus meshes as you move, with day/night lighting and damage-aware panes. Three spurious pits in Galileo’s western paved frontage are now replaced by a bounded, source-informed grade. The two eastern access ramps now have source-profile slopes, retaining walls, coping and shallow exterior entrance recesses. The neighbouring MLZ UYW/UYL buildings now have surveyed envelopes with distinct recessed window groups, concrete panel joints, closed service doors and preserved stepped roofs. The surveyed campus now stays visible at every altitude, including an airborne start and views from outside the survey boundary. It runs inside Minecraft Java 1.21.1 with the existing Minecampus add-on and Fabric setup.

The campus is still unfinished: several neighboring walls remain blurry, paths have inconsistent detail, and reconstructed window divisions/materials are approximate. Interiors are outside this pass. The public default installer remains on 0.4.0.

## Play the installed copy

On the development machine, restart the official Minecraft Launcher, open **Installations**, select **Minecampus — Exterior Preview 0.5**, and click **Play**. Open **Minecampus Garching** from Singleplayer. The copied world preserves inventory and edits as they stood when installed. Further progress belongs to this preview copy; the original **Minecampus — TUM Garching** installation remains separate.

Allow the map to finish streaming before judging geometry. The photographic façade pass can take several minutes on first entry. Existing local map credentials are reused; no new key is needed.

## Install the same snapshot alongside an existing setup

1. Quit Minecraft and its launcher.
2. Download `RealWorldMC-Minecampus-Exterior-0.5.0-dev-mc1.21.1.jar` from the [0.5 development preview release](https://github.com/DocMorphic/minecampus/releases/tag/exterior-0.5.0-dev.20) into this repository's `dist-minecraft/` directory.
3. On macOS/Linux, run `python3 scripts/install-exterior-preview.py` from the repository root. This requires the normal Minecampus installation and its map setup to exist already. It verifies the artifact hash, checks world locks, copies saves into a separate instance, verifies every copied save file, and adds the preview launcher profile. For an existing preview, use `python3 scripts/install-exterior-preview.py --update` instead. This verifies the recorded mod, refuses an open world, backs up the old mod, and replaces only that mod while verifying that saves and local settings stay unchanged.
4. Restart the launcher and follow the play instructions above.

The installer uses the current user's local map configuration, stored privately in the new instance. Credentials, saves, Minecraft assets and streamed provider imagery are absent from the public download.

## Evidence

The released JAR is the exact native-tested artifact: SHA-256 `949d518e117f173e61180582ea4efeeda15e3fe466cc9b89ed9a207549c76c50`. [Detailed evidence](altitude-development-validation.json) records the full 57-view route, all 40 existing checks, 50 MLZ opening rays, ten wall collision controls, all 17 courtyard/frontage/ramp gravity probes, both 57-frame GPU shadow/reflection routes and a separate twelve-view altitude sequence. Thirty service tests pass. Every route and flight image was reviewed.

The previous build hid 91 of 103 reconstructed render tiles when starting above the campus or ascending through its height threshold. Intermediate views could differ depending on whether the player approached from above or below. The map service now keeps the complete surveyed scene at every height, including views from outside the survey coverage. Its existing bounded source cleanup remains in place. The native sequence retains all 103 render tiles across airborne startup, ascent, descent, an outside-camera view and return.

![Airborne campus before](../../docs/screenshots/campus-altitude-before.jpg)

![Airborne campus after](../../docs/screenshots/campus-altitude-after.jpg)

![Wider campus after](../../docs/screenshots/campus-altitude-wide-after.jpg)

Only the packaged map service changes: all 269 mesh/roof/collision files, the manifest, renderer classes, shaders and textures are byte-identical to dev.19. The flight check samples settled spectator positions through the relevant heights; it is not a continuous-flight recording or a controlled performance benchmark. Reconstruction still has approximate architecture, missing roof equipment, baked image colours and coarse untreated neighbours.

The preceding MLZ checkpoint reconstructed the two MLZ workshop/laboratory buildings beside Galileo as three surveyed bodies. Official photographs and FRM II/TUM footage guide the individual opening groups, recessed glazing and large concrete panels. The southern upper-window groups also follow the photographic baseline. Dimensions, lower obscured openings and small architectural details remain estimates. The survey roof triangles and all 100 previous render meshes are byte-identical; only verified shared-wall overlaps are removed. A bounded cleanup removes the tracked floating wall and roof fragments while protecting other building footprints.

![MLZ central lane before](../../docs/screenshots/campus-mlz-courtyard-before.jpg)

![MLZ central lane after](../../docs/screenshots/campus-mlz-courtyard-after.jpg)

![MLZ east approach after](../../docs/screenshots/campus-mlz-east-after.jpg)

![MLZ southern overview after](../../docs/screenshots/campus-mlz-south-after.jpg)

The southern comparison is elevated above adjacent workshops; the lane and ramp views provide ground-level verification. Roof equipment, surrounding workshops, landscaping and baked ground colours remain unfinished. This checkpoint does not complete the broader realism goal. [Source assumptions](mlz-exteriors.json) and [research references](photos/galileo-east-neighbours-reference.json) distinguish observed features from estimates.

The preceding ramp checkpoint replaced the stretched banks around Galileo’s two eastern ramps with approximately 349.17 m² of bounded cuts, sloped floors, retaining walls and entrance recesses. The runs and height profiles follow mapped driveways and pinned source elevations. The 3.6 m width, wall/coping dimensions and shallow portal geometry are inferred from orthophotos and cross-sections; this is not an as-built survey, and no garage interior is included. That ramp update changed two ground tiles and left its other 97 existing meshes byte-identical; this MLZ update preserves all of those meshes.

![Northern ramp before](../../docs/screenshots/campus-galileo-ramp-north-before.jpg)

![Northern ramp after](../../docs/screenshots/campus-galileo-ramp-north-after.jpg)

![Both eastern ramps](../../docs/screenshots/campus-galileo-ramps-overview-after.jpg)

Six native player drops support both slopes within their gradient-derived one-metre voxel bounds. Maximum measured standing offset is about 0.520 m; collision remains an approximation of the visual slope. The northern courtyard and western frontage repair pass their existing gravity checks.

The renderer adds material routing for the MLZ mesh; shadow/reflection code and shaders remain unchanged. Additional moving-camera, night, resource-reload and disconnect/reopen evidence remains [recorded against dev.16](reflection-development-validation.json); the current route freshly verifies lighting, reflections, TNT and collision preservation. Baked vehicle/shadow colours remain visible in paving, and neighbouring workshops still have coarse photographic surfaces.

![Galileo reflecting the campus](../../docs/screenshots/campus-galileo-reflections.jpg)

The panel/window system follows contractor and completed exterior photographs. Its 1.4 m modules, floor divisions and row sequences remain estimates; exact entrance and transparent ground-floor zones are unfinished. Contractor photographs are research references, not texture assets.

The earlier courtyard repair remains intact: about 681 m² of bounded terrain cut, retaining walls, 27 risers across five flights and a connected lower landing. Collision migration is now v23 and preserves ordinary player blocks and recorded edits. The existing one-metre proxy grid still approximates visual treads.

![Galileo facade before](../../docs/screenshots/campus-galileo-facade-before.jpg)

![Galileo facade after](../../docs/screenshots/campus-galileo-facade-after.jpg)

![Galileo aerial view](../../docs/screenshots/campus-galileo-facade-aerial.jpg)

![Galileo courtyard stairs](../../docs/screenshots/campus-galileo-court-stairs-after.jpg)

![Northern crossing with asphalt](../../docs/screenshots/campus-crosspath-north-after.jpg)

Pale margins around the sculpture and some junctions remain. Galileo’s former stretched bank is now reconstructed; courtyard landscaping and some facade-base joins still need work. Older aerial shading and approximate facade/reflection detail also remain unfinished.

Only map meshes cast and receive these new shadows. Vanilla blocks, players and mobs do not participate, and aerial images retain their baked shadows. One nearby Galileo facade plane reflects loaded map meshes; other glass uses the approximate sky/ground fallback. Vanilla blocks and entities are absent from these reflections. The reflected sky is a clear colour without clouds or stars, and only already-loaded tiles appear. Small sampling patterns can remain at thin edges, and shadows fade at the local map boundary. These are known limits of this preview.

![GRS courtyard with mesh shadows](../../docs/screenshots/campus-runtime-shadow-courtyard.jpg)

The broader visual-quality goal remains open. Functional checks establish playability of the tested cases, not completion of the campus reconstruction.

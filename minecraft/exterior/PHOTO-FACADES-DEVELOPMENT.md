# Survey-aligned photographic façades — 23 October 2026

This development pass improves building geometry and removes specific floating scan fragments in actual Minecraft Java. The overall realism goal remains unfinished. The installed and published playable preview is still 0.4.0; the changes below are in the source-buildable 0.5.0-dev artifact.

## First verified artifact: `7ebdfa0f…`

The sections through “Verification and limits” below describe the first artifact exactly. Later changes are recorded separately at the end.

## What changed

Eighty BVV LoD2 building envelopes are candidates for photographic wall reconstruction. The runtime projects the existing provider material onto each measured wall, choosing the closest source surface along its normal. A wall needs at least 80% observed coverage, no disconnected unfilled region and no fill extending more than two metres from observed pixels. A building switches only when acceptable walls account for at least half its wall area. Unsupported faces retain their original scan geometry.

In the verified native run, **56 buildings supplied acceptable walls; 24 retained their original meshes**. This is not 56 fully detailed architectural models. The survey fixes silhouettes and wall/roof edges; the original photography still determines visible detail. The seven separately reconstructed detailed building components, including IAS, remain distinct from these envelopes.

Roofs use public BVV geometry and DOP20 imagery. The package contains public survey surfaces, collision geometry and the projection code. Provider pixels are generated in memory through the existing configured client, retain provider credits, and are not packaged or saved by the projection pipeline. Unsupported or unavailable source material falls back to the original scene.

The vegetation detector now recognizes brown as well as green crowns, increasing the inferred count from 734 to 740. The source-limit camera exposed a missed autumn tree beside a low roof. A roof-aware foliage mask retires that old canopy without deleting the measured building beneath it. Finite wall-segment distance also removes stray original triangles around reconstructed building corners.

## Same native Minecraft camera

Position `150 65 -220`, yaw `-90`, pitch `0`, noon, after full streaming readiness. Both exports retain the complete framebuffer and its attribution.

Before this pass, with the prior IAS development build:

![Original distorted source walls and floating canopy](../../docs/screenshots/campus-photo-surfaces-before.jpg)

After:

![Survey-aligned walls and reconstructed canopy](../../docs/screenshots/campus-photo-surfaces-development.jpg)

The floating canopy and the small triangle hanging beside the right-hand wall are gone. Native ray picks at their former screen positions now hit reconstructed vegetation and a survey-aligned façade. The shaded wall is still visibly blurry; this comparison does not establish finished realism.

The same pilot building from its north side, at `205 65 -238`, yaw/pitch `0 0`:

![North façade with photographed window positions](../../docs/screenshots/campus-photo-surfaces-north.jpg)

Window positions are more legible on this face, but the source remains low resolution at walking distance. No invented window grid or AI-generated image was substituted for missing photography.

## Verification and limits

The exact packaged JAR completed nine native ground/aerial/TNT/promenade/source-limit/IAS/photographic-façade captures. All five native assertions passed: scene readiness, player-edit preservation, TNT excavation/restoration and ground landing, IAS terrace landing, and landing on the survey roof supporting the pilot façade. That roof is at Y=72.264896 at the test point; the native one-metre collision grid lands the player at Y=72, within half a block.

All 19 service tests pass, including source-depth selection, incomplete coverage, openings, unsupported-face retention, corner ownership, save-datum translation, source-array immutability and roof-aware canopy removal. Generated binary geometry, texture lengths, finite positions, UV bounds, foliage masks and roof-height arrays pass validation. All 46 backed-up original world files remain byte-for-byte unchanged; the ephemeral session lock is excluded.

Exact artifact and framebuffer hashes, runtime acceptance records and native assertion text are in [photo-facades-development-validation.json](photo-facades-development-validation.json).

Remaining work includes sharper, source-supported façade detail, residual artifacts on rejected surfaces, site furniture and the fidelity of the separately reconstructed landmark materials. The imagery dates and surveyed geometry can also differ. These limitations are why this pass remains development evidence rather than a declaration that the campus is finished.

## Follow-up artifact: `d1c03a6e…`

This follow-up evaluates only the wall area above surveyed ground and accepts usable faces independently. The same per-face requirements remain: 80% observed photography, no unfilled region and at most two metres of filling. In the new native run, 79 of 80 buildings supplied at least one usable face. This count says nothing about complete building fidelity; unsupported faces remain visibly coarse. The former Mensa (`DEBY_LOD2_5284422`) now supplies photographed survey walls rather than being rejected because its survey foundation extends below surrounding terrain.

The tenth native viewpoint, `0 64.25 -216`, yaw/pitch `180 -5`, exposes the former Mensa approach. Newly generated chunks revealed visible source dirt filler in a protected margin beside the steep bank. Generation now normalizes that filler to invisible, mineable map material within survey coverage, preserving bedrock, water, unrelated regions and the source byte cache. Existing ordinary blocks remain protected; this is not a destructive old-save cleanup.

The overhang mask now includes shadowed green foliage and covers the whole guide cell before downsampling. The following same-camera comparison isolates these two cleanup changes in fresh worlds, after independent visible-face acceptance was already enabled:

![Fresh-world approach before margin corrections](../../docs/screenshots/campus-former-mensa-margin-before.jpg)

![Fresh-world approach after margin corrections; unresolved fragments remain visible](../../docs/screenshots/campus-former-mensa-margin-after.jpg)

The exposed dirt patch is gone. At screen coordinate `(0.745, 0.615)`, native block picking changes from `minecraft:dirt` to invisible `earthcraft:map_dirt` at the same block `(10, 64, -231)`. At `(0.96, 0.40)`, the removed scan triangle now gives a sky miss. Other triangles remain, including the one hit at `(0.84, 0.43)`. This view still fails the realism goal and is deliberately retained as evidence of unfinished work.

The packaged follow-up passed all ten captures, all five native assertions, 21 service tests and geometry validation. All 46 backed-up original world files remain unchanged. The fresh-world collision migration changed zero proxies, so this run does not replace historical proof of migration on existing chunks. Exact artifact/frame hashes, coverage records, ray picks and native results are in [visible-facades-development-validation.json](visible-facades-development-validation.json). The installed/public preview remains 0.4.0.

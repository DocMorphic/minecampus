# Survey-aligned photographic façades — 23 October 2026

This development pass improves building geometry and removes specific floating scan fragments in actual Minecraft Java. The overall realism goal remains unfinished. The installed and published playable preview is still 0.4.0; the changes below are in the source-buildable 0.5.0-dev artifact.

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

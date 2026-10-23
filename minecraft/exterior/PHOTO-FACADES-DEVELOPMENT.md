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

## Former Mensa structural frontage: `cb804d81…`

The next close-up showed that a straight photographic sheet still failed to express the building’s concrete frame and recessed glazing. Five surveyed terrace faces now have eleven reference-informed concrete bays, with piers, beams, a shallow exterior apron, recessed glass divisions, low opaque panels and a rooftop maintenance railing. The broad face measures 43.03 m in BVV geometry and is divided into six bays; four stepped faces add five bays. The envelope lengths and elevations are surveyed. Pier dimensions, pane divisions and the 1.1 m recess are estimates from the [TUM exterior reference](https://www.ed.tum.de/ed/news-single-view-start/article/tum-ed-bezieht-alte-mensa-in-garching-nach-umbau/), photographed by Susanne Höcht. No interior is generated.

The TUM photograph is not packaged as a texture. Concrete uses the existing CC0 Poly Haven material, neutralized and brightened; glass is an original approximate material with the existing runtime reflection shader. These are reconstructed materials, not new site photography. This is a partial frontage and does not increase the complete detailed-building count.

At the new native terrace camera, `0 68 -238`, yaw/pitch `180 0`, the previous build:

![Former Mensa frontage before structural reconstruction](../../docs/screenshots/campus-mensa-front-before.jpg)

The reconstructed frontage, after correcting gaps between the recessed glazing and columns:

![Concrete frame and recessed glazing in actual Minecraft](../../docs/screenshots/campus-mensa-front-after.jpg)

The wider approach remains visibly unfinished:

![Unresolved source fragments around the former Mensa approach](../../docs/screenshots/campus-mensa-front-approach.jpg)

The photographic pipeline omits a face once its structural replacement owns it, preventing an old flat sheet from covering the new recess. The auxiliary collision surface also omits that old face. A new native assertion verifies air at the former wall position `(5,68,-247)`, solid recessed glazing at `(5,68,-249)` and the overhead canopy at `(5,70,-247)` after collision migration. The exact packaged artifact completed eleven viewpoints and all six native assertions; all 21 service tests pass. All 46 backed-up original save files remain unchanged.

[Exact artifact, native captures, source qualifications and validation](mensa-front-development-validation.json). The overall goal remains open. Remaining work includes the approach’s scan fragments, terrace artwork and pavement, untreated elevations, roof detail and campus-wide fidelity. The installed/public preview is still 0.4.0.

## Terrace retaining walls: `0b4d1eac…`

Fixed native rays identified the large lower-approach fragments as the old source mesh along BVV wall 39 of `DEBY_LOD2_5284422`. This outer terrace wall is 50.10 m long, with only 42.9% photographic coverage of its visible area; keeping its unsupported source mesh preserved the jagged shapes. The existing licensed IAS panorama shows concrete terrace walls and railing beside the building:

![Concrete terrace-wall reference beside IAS](../../docs/screenshots/campus-mensa-retaining-reference.jpg)

Reference: [High Contrast, CC BY 3.0 DE](https://commons.wikimedia.org/wiki/File:TU_M%C3%BCnchen_Garching_-_Institute_for_Advanced_Study.jpg), cropped from the existing source photograph. The crop is a material/structure reference, not a matching-camera comparison or a survey of every surface detail.

Four lower faces (39, 18, 0 and 27) now use their measured geometry with physically scaled concrete texture. Railing segments are added only where the sampled ground profile shows an exposed drop, keeping the adjoining paved plateau connection open. The source and auxiliary collision faces relinquish ownership to the reconstruction, as for the upper frontage. No interior is added.

At the established approach camera, after full native streaming readiness:

![Surveyed concrete terrace edge replacing the jagged lower scan](../../docs/screenshots/campus-mensa-retaining-after.jpg)

Compare the [previous same-camera capture](../../docs/screenshots/campus-mensa-front-approach.jpg). The large lower fragments are gone. A new native assertion requires the three diagnostic rays at `(0.18,0.55)`, `(0.35,0.58)` and `(0.58,0.56)` to hit the reconstructed wall tile. All eleven viewpoints, seven native assertions, 21 service tests and generated-geometry validation passed. All 46 original backed-up save files remain unchanged. [Exact artifact and evidence](mensa-retaining-development-validation.json).

The overhead fragments remain visible. A public-survey diagnostic links their location to a connected tall canopy extending beyond the currently generated circular crown. Crown ownership currently excludes protected building footprints and clips assigned foliage near the seed; the next correction needs to retain real overhang and fit the crown’s shape. The overall realism goal remains unfinished, and the installed/public preview remains 0.4.0.

## Survey-fitted crowns: `f7a3ff1a…`

The terrace diagnostic showed that the nearby tall canopy extends well beyond its trunk candidate. Crown fitting now assigns connected DOP20 foliage to tree candidates using DOM20 height above surveyed roofs and terrain. It keeps trunk placement separate from crown extent, allows measured overhang over low roofs, and samples foliage positions within that footprint instead of forcing every tree into a circle around its height peak. The 14 m ownership limit is a guard against joining distant vegetation, not a claimed measured crown radius.

The representative trunk remains at approximately `(11.96,63.99,-220.53)`. Its fitted foliage samples extend north to `Z=-232.06`, with a sample centroid at `Z=-224.25`; the previous circular crown ended near `Z=-227.09`. Branches, lower crown boundaries, species and individual leaves remain procedural estimates. DOM measures the upper surface and does not measure a solid foliage volume down to the ground. The lower boundary therefore preserves exposed trunks; unsupported low samples do not become tall-tree foliage. The development scene now contains 739 inferred trees in 36 groups.

At the same native approach camera:

![Survey-fitted canopy above the Mensa terrace, with the old floating fragments removed](../../docs/screenshots/campus-mensa-crown-after.jpg)

Compare the [previous retaining-wall capture](../../docs/screenshots/campus-mensa-retaining-after.jpg). The two tracked overhead source fragments are removed. New diagnostic rays ignore reconstructed vegetation when testing for old triangles, so merely covering an artifact with a leaf card cannot pass. The three retaining-wall rays still require the measured wall geometry behind any intervening foliage.

The final package passed all eleven captures, eight native checks, 21 service tests and binary geometry validation. The collision fixture migrated 184 proxy blocks while preserving its player block and recorded excavation; all 46 backed-up original save files remain byte-identical. Exact package hashes, all eleven captures and native gameplay results are recorded in [crown-fit-development-validation.json](crown-fit-development-validation.json). This is a canopy correction, not a completed campus realism goal. The low-resolution ground imagery, simplified branches/species, pavement and terrace details, and remaining untreated architecture still need work. The installed/public preview remains 0.4.0.

## Mapped ground materials: `b74ed266…`

The previous ground shader inferred materials from aerial colour and lit every ground normal as though it were horizontal. Blurred shadows and roof/tree colours therefore dominated the terrace bank. The current pass uses closed OpenStreetMap polygons to identify 180 lawns and two paved areas, with twelve water/court exclusions. Their outlines were compared with the BVV orthophoto before use. Mapped material detail fades toward the original imagery at longer viewing distances; unknown surfaces keep their photographic treatment. No terrain vertices or collision rules change.

The [landscape designer’s project description](https://la-bar.de/text-hochschulcampus-garching-tu-muenchen/) supports folded lawns, grey concrete paving and a red asphalt campus band. The polygon outlines and material tags come from [the bundled OSM extract](ground-surfaces.geojson), under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Paver sizes, joints and lawn grain are approximate render materials, not a new survey of those details.

At the existing Galileo ground camera, before:

![Walking-height ground before mapped materials](../../docs/screenshots/campus-ground-material-before.jpg)

After:

![Mapped lawn boundaries and close-range ground grain](../../docs/screenshots/campus-ground-material-after.jpg)

At the established Mensa approach:

![Mensa bank with mapped lawn material and slope-aware shading](../../docs/screenshots/campus-mensa-ground-after.jpg)

The white strip beside the bank remains outside the mapped lawn. It needs geometry/reference work; this pass does not paint it over. A new camera at `25 65 -125`, yaw/pitch `90 25`, shows the approximate paving material in the mapped MW walkway:

![Close-up of mapped paving in the native Minecraft client](../../docs/screenshots/campus-paving-detail-after.jpg)

All twelve native captures, eight gameplay/geometry assertions, six material alignment/exclusion controls, 21 service tests and binary geometry validation passed. The original save’s 46 backed-up files remain unchanged. The full renderer fingerprint is now recorded alongside the upstream patch and service bundle hashes, so shader/resource changes are traceable. [Exact artifact and validation](ground-material-development-validation.json).

The overall goal remains open. Fine terrain edges, unmapped path materials, terrace stairs/artwork and the remaining coarse façades are still incomplete. The installed/public preview remains 0.4.0.


## Full DGM1 terrain sampling: `5dba4904…`

The previous mesh used two-metre spacing and selected each containing raster pixel. DGM1 stores samples at pixel centres: the [GDAL geotransform convention](https://gdal.org/en/stable/tutorials/geotransforms_tut.html) places those centres half a pixel inward from the transform origin. The new sampler merges the adjacent elevation files before bilinear interpolation. Every source sample inside the 600 × 600 m campus now becomes an interior mesh vertex; shared 100 m tile boundaries use the same interpolated heights. The two-metre guide remains for source filtering, while rendering and collision voxelization use the one-metre mesh.

Against the source raster, all 360,000 interior positions agree within 0.000022 m and adjoining tile edges match exactly. This measures encoding fidelity, not real-world survey accuracy. The old mesh differed from source samples by more than 25 cm at 3,926 positions outside protected footprints, including 193 in the selected terrace window. Those figures describe the previous interpolation error, not changes to the underlying survey.

At the same Mensa approach camera:

![Mensa bank after retaining the full DGM1 elevation sampling](../../docs/screenshots/campus-mensa-terrain-after.jpg)

Compare the [previous two-metre capture](../../docs/screenshots/campus-mensa-ground-after.jpg). The diagonal bank edge is cleaner. Steep-face texture stretch, approximate materials and untreated façades remain visible; this is not final campus-quality evidence.

The native bank probe originally assumed a landing at Y=63 and failed at Y=62. Independent triangle interpolation established the actual rendered surface at Y=62.378458, so the probe now checks that measured height with the existing half-block tolerance. Collision migration advances to v5 to realign previous proxy blocks, retaining the existing protections for ordinary blocks and recorded edits. Exact artifact hashes, source checks, native results and original-save verification are recorded in [terrain-development-validation.json](terrain-development-validation.json). The installed/public preview remains 0.4.0 and the overall goal remains open.


## Slope-correct material projection: `ed108ef3…`

The finer Mensa bank still stretched its ground material vertically because every microtexture used a downward X/Z projection. Ground materials now blend three world-space projections according to the surveyed surface normal. Near-vertical mapped lawns also reduce stretched aerial shading, retaining material grain and geometric lighting. Ordinary flat ground retains its top projection; negligible axes and distant detail are skipped to avoid unnecessary texture sampling.

![Mensa bank after correcting stretched material projection](../../docs/screenshots/campus-mensa-slope-material-after.jpg)

Compare the [previous full-resolution terrain pass](../../docs/screenshots/campus-mensa-terrain-after.jpg). All twelve native route captures and nine gameplay/geometry checks passed, and all 46 backed-up original save files remain unchanged. The mesh and service bundle are identical to the previous terrain-validated build.

Separate runs reported highly variable frame rates, so a development-only resource-pack comparison switched baseline/candidate/baseline in one loaded scene. Its median readings were 41.5, 42 and 35 FPS. This does not demonstrate a slowdown from the candidate, but concurrent system load and advancing daylight limit the comparison; it is not a universal performance guarantee. The first comparison exhausted its timeout after slow streaming, so the harness now gives loading and measurement separate bounded intervals. Future runs also freeze daylight.

[Exact artifact, captures, checks and comparison data](slope-material-development-validation.json). Untreated façades, unmapped paths and terrace detail remain unfinished. The next structural reference is [UYA](RESEARCH.md#uya-exterior-reference-for-the-next-façade-pass). The installed/public preview is still 0.4.0; the overall goal remains open.


## UYA outer façades: `b0ecb5ad…`

The pilot photographic building, BVV `DEBY_LOD2_5284443`, is UYA. Its streamed walls remained too blurred to read at walking height. The [pinned ESO reference](photos/uya-eso-reference.json) shows two narrow roof courts, pale upper walls, 24 upper windows on the long elevation and 11 on the short elevation, with contrasting glazing and ochre lower panels. The roof and footprint match the public survey. [Reference image, attribution and identity evidence](RESEARCH.md#uya-exterior-reference-for-the-next-façade-pass).

Four outer faces now use the surveyed wall polygons with recessed windows, frames, sills, lower glazed bays and infill. The long faces measure 50.87/50.96 m and the short faces 32.00/31.98 m. The short elevations' eaves dip below their outer corners; the common window heads stay below that measured dip. Window dimensions, 0.18 m recesses, lower divisions and materials are estimates. Opposite elevations repeat the observed upper-window pattern by inference. No interior is added.

The existing north-facing camera, before:

![UYA's previously blurred long elevation](../../docs/screenshots/campus-uya-north-before.jpg)

After:

![UYA with recessed upper windows and separate lower panels in Minecraft](../../docs/screenshots/campus-uya-north-after.jpg)

The approach from the west also shows the short elevation:

![UYA's rebuilt outer façade beside neighboring untreated buildings](../../docs/screenshots/campus-uya-west-after.jpg)

The neighboring photographic walls remain conspicuously coarse. UYE/gatehouse `DEBY_LOD2_31360854` is the right foreground fragment in the west view; diagnostic rays now hit UYA's reconstruction on its own outer walls. The small warehouse `DEBY_LOD2_52738492` also needs treatment. This pass does not establish a finished route.

The roof file is byte-identical to the preceding package, preserving both courtyard openings. Eight inner courtyard faces retain their photographic treatment. Collision migration v6 replaces old proxy geometry while retaining ordinary blocks and recorded edits. Both UYA viewpoints require the new tile to be loaded. All twelve route captures, nine native gameplay/geometry checks, 21 service tests and binary geometry validation passed; the original save's 46 backed-up files remain unchanged. [Exact artifact and validation](uya-development-validation.json).

The installed/public preview remains 0.4.0. The broader realism goal stays open for the remaining coarse structures, paths, terrace detail and courtyard detail.

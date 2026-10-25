# Native verification harness

`CampusExteriorCheck.java` is a development-only Fabric client initializer. It is not included in the playable pack. Run it in a separate Fabric Loom project against the exact release JAR as a mod dependency, with a matching Minecraft/Fabric version and the normal owned-game development assets. Supply provider configuration only in an ignored local run directory.

For a single viewpoint, use `minecampus.inspectOnly=true` with `minecampus.inspectStage` set to the camera index; this inspection does not replace the full gameplay check.

Use a copy of the campus save named `campus-check`; never point this harness at an original save. `minecampus.checkWorld` may select another isolated name matching `campus-check(-[a-z0-9]+)*`. A fresh generation check should copy only the test save metadata, region definition and datapacks, leaving chunk data behind. It changes the test scene, creates temporary block/damage fixtures, triggers native TNT, restores test damage and captures native framebuffers. Register this class as the test mod's client entrypoint. The managed embedded service must come from the release JAR, without development RealWorldMC classes on the classpath.

Delete previous result files before each run, then assert that `campus-client-result.txt`, `campus-collision-result.txt`, `campus-gameplay-result.txt` and `campus-terrace-result.txt` each begin with `PASS:`. For an isolated inspection, require a fresh `campus-inspection-result.txt`; Minecraft's exit code alone is insufficient, even when Gradle reports success. Capture readiness requires pending tile expansions to reach zero, all requested tiles to load and the view to remain stable. Preserve the full frame and attribution when exporting images.

For the photographic façade development build, set `minecampus.requirePhotographicFacade=true`. This requires the pilot's reconstructed tile to be displayed at the source-limit viewpoint and adds a gravity check against its measured roof height. Also delete and require a fresh `campus-roof-result.txt`. The harness captures twelve viewpoints, including both sides of that building, the former Mensa approach and terrace, and a close-up of the mapped MW paving; a clear face must not conceal a blurry one in the evidence. Set `minecampus.requireVisibleFacade=true` to require the former Mensa’s reconstructed wall tile at its camera. Diagnostic ray picks report both the visible mesh and native block hits, helping distinguish photographic defects from exposed collision filler.

See [validation](../VALIDATION.md) for the tested release hash and evidence. The harness establishes specific rendering/gameplay checks, not the overall architectural realism goal.

For the structural former Mensa frontage, set `minecampus.requireMensaFront=true` and delete/require a fresh `campus-frontage-result.txt` alongside the other result files. The eleventh camera requires the reconstructed frontage tile. The full run verifies that the former flat collision wall is open at a representative bay, while the recessed glazing and overhead canopy remain solid. This check runs after the isolated world’s collision migration; inspection-only captures do not establish collision correctness.

For the retaining-wall pass, also set `minecampus.requireMensaRetaining=true` and delete/require a fresh `campus-retaining-result.txt`. Three fixed rays in the lower approach must hit the reconstructed wall tile rather than the original jagged scan. The structural ray ignores reconstructed vegetation so an intervening tree cannot invalidate a wall check. The ordinary visible ray remains in the diagnostics. This verifies those wall fragments only.

For the crown-fitting pass, set `minecampus.requireMensaCanopy=true` and delete/require a fresh `campus-canopy-result.txt`. Two fixed rays through the former overhead artifacts must find no old source triangle within 30 m, including behind reconstructed foliage. Merely hiding an artifact behind a new leaf card cannot pass this check. Inspect the full captures as well: this assertion cannot establish natural crown shape, foliage density, or overall visual quality.

For the finer terrain pass, set `minecampus.requireFineTerrain=true` and delete/require a fresh `campus-bank-result.txt`. After the other gameplay checks, native gravity drops the player at `(14.5,68,-228.5)` beside the Mensa bank. `scripts/validate-terrain.py` independently recovers the rendered triangle height there, Y=62.378458; the block proxy must support the player within 0.51 m of that surface after alignment. `minecampus.bankOnly=true` runs just this isolated gravity probe and does not establish capture or other gameplay success. A failed probe must not be reported as a successful full run.

For a material performance comparison, compile `CampusMaterialBenchmark.java` alongside the main harness. Supply `benchmark-baseline.fsh` and `benchmark-candidate.fsh` in the isolated run directory, then set `minecampus.materialBenchmark=true`, `minecampus.inspectOnly=true` and the desired `minecampus.inspectStage`. After streaming readiness, this creates a temporary QA resource pack and compares baseline/candidate/baseline in the same loaded scene. Each phase verifies the active shader resource, reapplies the same texture filtering, warms up for six seconds and collects six one-second FPS readings. Require a fresh `campus-material-benchmark.json` and inspect its three captures; a `PASS` means measurements completed, not that the candidate is faster. Keep ordinary native captures/results separately before benchmarking. Concurrent system load and shader reloads can affect measurements, so do not describe a single local comparison as a universal FPS guarantee.


For the UYA outer-façade reconstruction, set `minecampus.requireUyaExterior=true`. Both existing UYA viewpoints (indices 6 and 8) must display its dedicated reconstruction tile. Keep the photographic-roof check enabled: the public surveyed roof and two courtyard openings still belong to the existing roof tile. The standard roof-gravity and migration checks remain required. Viewport tile presence is only a loading gate; visually inspect the short and long elevations and verify the roof bytes against the preceding package.


The UYE development pass enables `minecampus.requireUyeExterior=true`. At source-limit camera 6, the existing diagnostic ray at normalized `(0.9, 0.45)` must hit reconstruction tile `1_000_030_007` behind any foliage. `campus-uye-result.txt` is an additional required PASS file alongside the previous nine. Collision storage advances to v7. The exact native run and roof-preservation check are recorded in `uye-development-validation.json`.


The warehouse pass enables `minecampus.requireWarehouseExterior=true`. Source-limit camera 6 checks two formerly blurred foreground rays at `(0.12, 0.60)` and `(0.22, 0.56)`. New camera 12 (`183 65 -231.5 90 3.5`) checks the central east-opening ray. All three must hit tile `1_000_030_008`; `campus-warehouse-result.txt` is the eleventh required PASS file. The route now captures thirteen frames, and collision storage advances to v8. See `warehouse-development-validation.json`.


The road-material pass adds camera 13 (`51 65 -190 0 40`), bringing the full run to fourteen frames. Inspect `campus-road-detail.png` and compare the existing route views against the previous artifact. `validate-ground-surfaces.py` checks source/resource hashes, six road/path centre and edge controls, the existing material controls and mapped-area exclusions. This material-only change retains collision storage v8.

The Telefonzentrale pass adds camera 14 (`130 65 -269 -65 5`) for its west elevation. With `minecampus.requireTelefonzentraleExterior=true`, rays through all four window centres must hit reconstruction tile `1_000_030_009` on BVV building `DEBY_LOD2_8486669` (TUM 5130). Require `campus-telefonzentrale-result.txt` alongside the previous eleven checks. Diagnostic rays record the hit triangle and a frame before assertions, so failed checks remain inspectable; source triangles are local evidence and are not redistributed as assets. The full route has fifteen frames. Collision storage advances to v9. The adjoining Siemensbau (5103) retains its previous photographic walls.


The COS pass adds cameras 15–17: `128 65 -267 -140 -13`, `190 65 -270 140 -15`, and `125 120 -240 -145 31`. With `minecampus.requireCosExterior=true`, three west-window rays, three south-opening rays and one aerial roof ray must hit `1_000_030_010`. Require `campus-cos-result.txt` alongside the previous twelve results; the full run captures eighteen frames. The aerial view verifies that COS survives the transition to the distant photographic mode. Its embedded roof part must match the previous survey-roof bytes. Collision migration advances to v11. `campus-cos-ground-result.txt` additionally checks native gravity at `(186.5,-288.5)`, where the old construction mound has been replaced by the inferred finished-site grade (approximately Y=63.153). This brings the full run to fourteen required results. The reference photo is a documented approximation for opening dimensions and hidden elevations, not an as-built facade schedule.


The COS release also requires `campus-texture-result.txt` (fifteen results total). At camera 15, the harness verifies that the packaged shader is active with no resource-pack override. It checks the COS timber, one ground tile and eight shared material textures: trilinear minification, generated mip levels and `GL_TEXTURE_MAX_LOD` at least as high as the maximum allocated level. `campus-texture-sampling.json` records these values. This guards the level-zero clamp inherited from Minecraft texture allocation, which previously prevented generated mipmaps from being sampled.

## COS forecourt

The site pass adds camera 18 (`162 64 -270 -171 14`), outside the neighbouring surveyed footprints. The earlier exploratory camera at `(162,-262)` was inside Siemensbau and is not a valid walking view. With `minecampus.requireCosSite=true`, require `campus-cos-site-result.txt` and `campus-cos-bench-result.txt` in addition to the previous fifteen checks. The full run has nineteen captures and seventeen results. Three rays must reach the visible furniture tile `1_000_030_011` (both benches and a rack); native gravity must land at Y=64 on the bench proxy above a visible seat at approximately Y=63.84. Collision migration advances to v12.

`collisionParts` selects solid bench parts for voxelization while leaving thin rack tubes render-only. A service test verifies both collision filtering and preservation of all rendered parts. Ground validation checks the ten derived material patches, source hashes and exclusions; all 36 terrain tiles remain unchanged from dev.3. Path widths, furniture dimensions and exact rack arrangement remain explicit estimates.

## COS landscape and apron

Camera 19 (`154 64 -272 180 20`) inspects the soil bed and low edging. `minecampus.requireCosLandscape=true` checks that one ray reaches surveyed ground with the packaged inverse-alpha soil mask and brown rendered pixels, and another reaches the 12 cm curb. It writes `campus-cos-landscape-result.txt`. `campus-cos-apron-result.txt` checks gravity at `(163.5,-276.5)`: the revised mesh is Y=63.46271 and its proxy top is Y=63, replacing the previous Y=64 proxy. Collision migration advances to v13. The complete result set now has nineteen checks.

Camera 20 (`178 64 -337 0 12`) supplies the north-lawn view. The full route includes all twenty-one cameras. Inspect-only captures establish streaming readiness and require visual review.

Five terrain tests cover source sampling, bounded radial grading and the smooth apron with neighbour exclusions. The full terrain verifier independently reconstructs both grading functions, checks all 360,000 samples and shared edges, and checks the native apron probe. Ground-material validation includes the soil channel (`1 - alpha`) and existing mapped-area exclusions. All twelve native texture samplers must have usable mip levels.

The apron probe uses packaged voxel output rather than rounding a single terrain-centre height. At `(161.5,-276.5)`, a sloping triangle crosses the half-height threshold within the one-metre cell, so both versions correctly produce a Y=64 top. That exploratory assertion was invalid. Independent before/after voxelization establishes `(163.5,-276.5)` as a stable Y=64 → Y=63 control, which native gravity verifies. The renderer's block-sized collision remains an approximation of fractional mesh heights.


## GRS north wing

The GRS pass adds north and west facade cameras 21–22 (`214 64 -342 -15 -10` and `191 63 -314 -90 -20`). With `minecampus.requireGrsExterior=true`, three projected world-space rays on each elevation must hit tile `1_000_030_012`. Require `campus-grs-north-result.txt` and `campus-grs-west-result.txt` alongside the previous nineteen results. The full route has twenty-three captures. Existing camera 20 provides a direct comparison with the distorted building beside COS. Collision migration advances to v14.

Binary preservation checks compare all 89 previous render tiles and the other 79 photographic-facade plans byte-for-byte or structurally. The new component embeds the byte-identical surveyed roof, and the east bridge junction remains outside the reconstructed facade strips. Historical architect photographs establish the facade character; exact frame sizes, colours and less-visible elevations remain estimates.


## GRS stair tower and bridges

Cameras 23–25 add north (`251 64 -318 -14 -12`), courtyard (`238 64 -292 -118 -8`) and aerial (`242 96 -310 -40 56`) views. Enable `minecampus.requireGrsConnectors=true`. Two ground rays per view must hit the tower and west bridge (`1_000_030_013` and `1_000_030_014`). Four aerial structural rays, excluding foliage intersections, must hit those components, the south junction (`1_000_030_015`) and the unchanged neighbouring GRS roof (`1_000_050_060`). Require `campus-grs-connectors-north-result.txt`, `campus-grs-connectors-courtyard-result.txt` and `campus-grs-connectors-aerial-result.txt`: 24 required results and 26 captures total. Collision migration advances to v15.

Preservation checks verify all 90 prior render tiles, 79 other existing facade plans, all three exact embedded survey roofs, and boundary exclusions around every unrelated surveyed footprint. Service tests cover boundary holes and adjacent wall/roof preservation. Small connector plans append to the existing 80 entries, preserving their runtime IDs. Tests establish geometry and gameplay behavior; visual review and reference qualifications remain necessary.


## GRS II missing-wall repair

Cameras 26–27 add west (`225 64 -280 -90 -7`) and east (`286 64 -278 90 -7`) elevations, outside neighbouring footprints. Enable `minecampus.requireGrsMain=true`. Three structural rays per view must stop at tile `1_000_030_016`; foliage intersections are excluded. Camera 24 also gains a direct ray to the formerly absent west wall at `(247.83,66.5,-294.39)`, and camera 25's neighbouring-roof target now expects this complete-envelope tile instead of `1_000_050_060`. The embedded roof bytes are unchanged. Require `campus-grs-main-west-result.txt` and `campus-grs-main-east-result.txt`: 26 required results and 28 captures total. Collision migration advances to v16.

Before-repair diagnostics establish that the visible overhead plane belongs to the valid survey roof; other rays pass through the west facade to the far wall/ground. Preservation checks verify all 92 unaffected earlier render tiles, 81 other facade plans, the main roof, and north-wing material parts 0/1/2/4. Only its unsupported brace geometry in part 3 is removed. All 12 main-wing survey faces are reconstructed, with cleanup exclusions protecting neighbouring footprints. This tests the exterior repair, not completion of the wider campus.


## GRS III exterior

Cameras 28–32 add west (`222 64 -240 -90 -7`), south (`249 64 -210 180 -8`), east (`278 64 -237 90 -7`), rounded tower (`262 64 -255 90 -15`) and aerial (`280 105 -208 140 56`) views. Enable `minecampus.requireGrsIII=true`. Three rays on each main elevation and two each for the tower/link and roof must hit tile `1_000_030_017`, ignoring foliage only for structural diagnosis. All ground cameras are outside survey footprints, with eye height approximately 1.45–1.82 m over the DGM. Require the five `campus-grs-iii-{west,south,east,tower,aerial}-result.txt` files, for 31 required results and 33 captures total. The longer route uses an 11,000-tick timeout. Collision migration advances to v17.

Binary preservation verifies all 94 previous render tiles, the 50-triangle embedded roof, 81 other facade plans, stable runtime IDs, protected neighbouring footprints and unchanged terrain/material guides. The same-camera west comparison includes heavy foreground foliage; south/east views must also be reviewed. Passing rays or screenshots do not establish whole-campus completion.


## GRS courtyard connector and path

Cameras 33–34 add the path (`262 64 -255 90 20`) and the same upward courtyard camera (`262 64 -255 90 -15`) used for the previous fragment diagnosis. Enable `minecampus.requireGrsCourtyard=true`. The path test requires two direct terrain hits with the green paving mask plus a direct hit on the 6 cm edging tile `1_000_030_019`. The connector test requires the old high fragment to be absent, the old lower fragment ray to reach `1_000_030_018`, and an explicit unobstructed GRS II target `(255.351174,68.8,-259.074938)` to retain `1_000_030_016`. The old neighbour pixel was correctly occluded by the newly closed connector; it is not a valid preservation ray. Require `campus-grs-courtyard-path-result.txt` and `campus-grs-courtyard-connector-result.txt`: 33 results and 35 captures total. Collision migration is v18.

Stage 32's first aerial target is corrected to `(246.593168,73.385192,-238.988457)`, on the main GRS III raised roof. Both previous targets reached the tower roof; the main roof had visual but not direct ray coverage. The second tower-roof ray remains.

Preservation verifies all 95 previous tiles and 82 plans, stable runtime IDs, the connector's embedded two-triangle roof, neighbouring-footprint exclusions and unchanged terrain. All 1,527 changed material pixels were previously unassigned, lie inside the inferred path and outside buildings; all existing mapped material pixels remain unchanged. Edging has an empty collision-part list. These checks do not establish whole-campus completion.


## Runtime mesh shadows

`CampusShadowChecks` runs before every route capture when `minecampus.requireRuntimeShadows=true`. It verifies that `CampusShadows` comes from the packaged JAR, compares the actual GPU sun direction with Minecraft's sky rotation, and checks the day/weather strength. Require `campus-shadow-route-result.json` to report PASS with all configured sequential stages (37 after the promenade pass), in addition to the existing 33 result files. FPS values are individual route readings, not a controlled performance benchmark.

`CampusShadowFunctionalCheck` runs separately in the isolated `run-campus-check` save. Enable `minecampus.shadowFunctional=true` with `minecampus.inspectOnly=true`. The maintained harness selects camera `38 73 -59 -135 50` and calls its `tick(mc)` after streaming readiness, instead of advancing the normal route. Copy the packaged source shader to `expected-runtime-shadow.fsh`; the check rejects resource overrides and a renderer loaded from harness classes. Do not copy the experimental renderer or hook into this run.

The functional check uses actual primed TNT at `(44.5,67,-62.5)`, compares a 512² region of the rendered depth map, restores only its newly recorded edits, and compares the restored depth. It then verifies GPU lighting and captures morning, evening and night, requiring the daytime shadow pass to stop at night. Finally it reloads resources, verifies replacement and destruction of the old framebuffer, compares depth again, and checks mipmapped sampling on all ten shared materials. Require the final `campus-shadow-functional.json` PASS and seven fresh captures. Preserve the full route output before this separate run, and compare capture timestamps with the relevant run start and JAR build time. These fixtures must never run against a user's save.

The new pass applies only to the map meshes. Vanilla blocks, players and mobs do not participate. Existing aerial-image shadows remain baked into those images.


## Promenade surface detail

Cameras 35–36 add the narrow lawn path (`60 66 -100 180 10`) and eastern building-side path (`80 65 -100 0 10`). Enable `minecampus.requirePromenade=true`. `CampusPromenadeChecks` reads back four path controls and three diagnosed facade-seam locations from the GPU material mask and requires blue asphalt coverage, then independently intersects the loaded survey terrain below each point. Require `campus-promenade-result.txt` and inspect `campus-promenade-controls.json`. The full route now contains 37 views and 34 ordinary result files, plus the runtime-shadow route check.

For a focused two-camera review, set `minecampus.startStage=35`, `minecampus.promenadeReview=true` and `minecampus.requirePromenade=true`; omit `inspectOnly` and the sequential shadow-route requirement. Require `campus-promenade-review-result.txt` and both fresh captures. This focused review does not replace the full route.

Run `.cache/geodata-venv/bin/python scripts/validate-promenade.py --baseline <prior-build-directory>` after building. The baseline directory must contain the previous `manifest.json`, `ground_surfaces.png` and an inventory mapping prior output paths to SHA-256 hashes. It checks all 97 prior mesh bytes and terrain/architecture/vegetation guides, the seven controls, mapped-area exclusions, and the maximum 20 cm texture margin under building footprints. The 4x coverage mask may change existing boundary pixels; existing material interiors must stay unchanged. Thin vector boundaries absent from the old raster are checked against the actual prior outlines within the half-texel-diagonal and frame-fit tolerance.

Widths/offsets are inferred from BVV DOP20 and kept separate from OSM tags. The southern bend uses a narrower corridor. The footprint margin is texture padding under facades, with no geometry, collision or interior change.

## Promenade cross-paths

Cameras 37–38 inspect the southern crossing (`35 65 24 -100 12`) and northern diagonal (`65 66 -140 -150 10`). Enable `minecampus.requireCrosspaths=true`. `CampusCrosspathChecks` uses eight fixed source-control positions and the shared GPU-mask/loaded-terrain readback in `CampusPromenadeChecks`. Require `campus-crosspaths-result.txt`, eight records in `campus-crosspaths-controls.json`, and fresh captures. The full route now has 39 views and 35 ordinary result files, plus the shadow-route check.

A focused review uses `minecampus.startStage=35`, `minecampus.crosspathReview=true`, and the cross-path requirement, without the sequential shadow-route flag. Require `campus-crosspath-review-result.txt`. This takes the two promenade cameras and the two new crossing cameras. For a preceding-artifact baseline, omit the new cross-path requirement. Camera 38 also records two diagnostic rays into the adjacent warped strip; those observations are not pass/fail proof that the strip is repaired.

Run `.cache/geodata-venv/bin/python scripts/validate-crosspaths.py --baseline <prior-build-directory>`. The baseline format matches the promenade validator. It verifies bounded non-overlapping additions outside prior materials and complete surveyed footprints, unchanged grass/paving/soil channels, non-decreasing asphalt coverage, every changed texel within the new corridor footprint tolerance, eight material controls, all 97 mesh bytes, and byte-identical prior promenade polygons. Widths and offsets remain explicitly inferred, not surveyed.

## Galileo northern sunken court

Cameras 39–41 add the upper edge (`104 65 -176 0 25`), courtyard floor (`105 60.5 -153 170 -6`) and west stairs (`95 65 -171 10 30`). The focused review starts at camera 38, uses `minecampus.galileoCourtReview=true` and `minecampus.requireGalileoCourt=true`, and requires `campus-galileo-court-review-result.txt` plus `campus-galileo-court-collision.json`. The full route has 42 captures and a 14,000-tick deadline to include the added gravity probes. Filter diagnostic mesh intersections to displayed tile IDs; the renderer retains undisplayed earlier provider tiles in its cache.

`CampusGalileoCourtChecks` checks the packaged courtyard mesh under the lower floor, each of five stair landings and two turning-apron positions, then drops the actual Minecraft player onto each. The player must be grounded within 0.51 m of the mesh and the chunk must have completed collision migration v19. These are gravity/landing checks; they do not claim continuous stair-height movement. The existing one-metre proxy approximation remains. All tests use the isolated `campus-check` world, never the player's save.

`validate-galileo-court.py --baseline <directory>` expects the preceding artifact's complete exterior directory at `<directory>/exterior`. It verifies exactly two bounded ground cuts, unchanged surrounding tile bytes, original barycentric XYZ/UV interpolation at cut edges, preserved ground textures, connected lower landing/floor, 27 risers, median surveyed floor height, unchanged old architecture and all previous masks/guides. `validate-terrain.py` checks the surviving original DGM-centred samples; newly clipped boundary vertices are covered by the courtyard validator.

The 4 m stair width and 27 risers are OSM tags. The five-flight layout follows DGM plateaux; endpoints and riser allocation are estimates. Its centreline is shifted 0.65 m west to reconcile the width with the separately mapped retaining wall. Lower landing extension, wall/parapet thickness, handrails, lower exterior glazing and pavement grain are inferred. Interiors and the unrelated Wasserwand/escalators are excluded.


## Galileo facade panels

Cameras 42–46 inspect the west, southwest, east, northwest aerial and north-detail views. A focused run starts at 42 with `minecampus.galileoFacadeReview=true`. Add `minecampus.requireGalileoFacade=true` to require `campus-galileo-facade-{42..46}-result.txt`. The full route now has 47 captures and a 17,000-tick deadline.

`CampusGalileoFacadeChecks` samples a 7 × 5 grid of native camera rays against displayed meshes, excluding foliage only for structural diagnosis. Each walking view must reach both Galileo's metal and recessed glass parts; the aerial view must reach a preserved roof part. Diagnostics record every ray, the material-part counts and the packaged renderer JAR. These are loading/geometry checks, not proof of photorealism or an accurate window schedule. Inspect all five images against the preceding artifact and primary source photos.

`validate-galileo-facade.py --baseline <directory>` requires the previous complete exterior directory in `<directory>/exterior`. It verifies the exact two-mesh scope, byte-identical roof parts, unchanged 97 other render tiles and all old manifests/guides. It independently projects the generated recessed backing triangles onto each of the 95 survey walls and checks coverage. Collision migration is v20; the standard save-edit migration and gameplay checks remain required before installing the candidate.

## Campus reflections

`CampusReflectionChecks` runs alongside each full-route capture with `minecampus.requireReflections=true` and `minecampus.verifyReflectionState=true`. Require 47 sequential records and PASS in `campus-reflection-route-result.json`. The four walking Galileo cameras must have active reflected glass. The checks read actual shader strength, the native texture binding and GL errors, and require every tested reflection pass to restore its recorded state. The existing geometry, gameplay, collision and shadow checks still apply.

For focused integration, enable `minecampus.reflectionIntegration=true`, `minecampus.inspectOnly=true`, `minecampus.inspectStage=42` and state verification. Register `CampusReflectionMotionCheck` alongside `CampusExteriorCheck`. Copy the packaged `campus_ground.fsh` to `expected-runtime-reflection.fsh`. No experimental shader pack or renderer classes should be on the QA classpath. Require `campus-reflection-benchmark.json`: off/on/off, west/southwest/east/north views, night, resource reload, return to daylight and continuous motion. Motion checks read the GPU matrix after each frame and compare it with that frame's camera. Review the native captures; the short FPS samples are not a general performance promise.

For destruction and world lifecycle, use `minecampus.reflectionFunctional=true`, `minecampus.inspectOnly=true`, `minecampus.inspectStage=42` and register `CampusReflectionLifecycleCheck`. The harness chooses the elevated diagnostic camera `58 72 -63 -90 18` so reflected terrain is visible. **Use an explicitly named copied `campus-check` world and preserve that fixture before running.** This test restores pre-existing QA map edits to prepare pristine geometry; it must never run in a user's save. It then detonates real TNT against terrain and glass, compares the reflection depth target and surviving glass area, restores only the new test edits, checks complete-glass removal using an isolated clipped tile, disconnects normally and reopens the same QA world. Require `campus-reflection-functional.json` PASS, exact or bounded recorded restoration residuals, destroyed old framebuffer/cleared world references, a fresh reflection target after reopening, and fresh native/target captures.

The reflection renderer only includes loaded map meshes. Vanilla blocks, players and mobs, other glass facades, back-facing provider coverage and reflection-edge aliasing remain separate limitations. No new collision migration or building geometry is introduced by this pass.

## Galileo western frontage grade

Cameras 47–48 show the three former terrain depressions from an elevated diagnostic view and walking height. The full route now contains 49 frames. Set `minecampus.requireGalileoGrade=true` to run `CampusGalileoGradeChecks` after camera 48. It picks the packaged ground surface at three former pits, requires a plausible reconstructed paving height, then drops the native player onto each and requires collision migration completion and a standing height within 0.51 m of the visible surface. Require fresh `campus-galileo-grade-collision.json` with three probes and the exact packaged JAR name.

A focused run starts at 47 with `minecampus.galileoGradeReview=true`; require two captures and `campus-galileo-grade-review-result.txt`. Omit `requireGalileoGrade` only for the preceding-artifact visual baseline. Full-route shadow/reflection flags require sequential captures starting at zero and must not be enabled in the focused run.

Run `scripts/validate-galileo-grade.py --baseline <directory>` with the geodata Python environment, where the baseline contains the preceding `exterior/` directory. It checks the exact one-ground-tile scope, unchanged texture/UV bytes and other 98 mesh files, changes restricted to the recorded collars, unchanged unrelated terrain/surface/vegetation guides, and the three old/new surface heights. `validate-terrain.py` checks the whole encoded survey grid with the explicitly recorded inferred grades. Collision storage advances to v21; the existing full-route player-edit preservation and native TNT checks remain required. The grade is inferred from surrounding survey samples and site imagery, not new survey data.

For the Galileo eastern ramps, set `minecampus.requireGalileoRamps=true` and delete/require a fresh `campus-galileo-ramps-collision.json`. The route now contains 52 views. The last three views cover both ramps from above and each descending approach; the overhead camera stays above the neighbouring roof. `minecampus.galileoRampsReview=true` with `minecampus.startStage=49` isolates these views and six native gravity drops when the requirement flag is enabled. Each drop first ray-checks the displayed ramp-floor part of tile `1000030022`, then checks the actual player's resting height against that surface after collision migration. The ramp tolerance adds the displayed triangle's height variation across a half-cell in X/Z to the existing 0.51 m vertical rounding bound; each measured bound must remain below 0.65 m. Earlier courtyard/frontage controls remain in the full route. A passing probe is collision evidence, not proof of precise as-built dimensions or complete campus realism.

## MLZ workshop/laboratory exteriors

Cameras 52–56 cover UYW's northern face, the lane between UYW/UYL, UYL's southern face, both east ends and the roof overview. The southern camera is elevated above the adjacent workshops; ground-level attempts were blocked by their survey bodies or projecting scan geometry. Courtyard and ramp approaches provide the ground-level checks. A focused comparison starts at 49 with `minecampus.mlzReview=true`, preserving the three existing ramp approaches as context. Enable `minecampus.requireMlz=true` for the candidate and full route; omit it only for the preceding-artifact visual baseline. Require fresh `campus-mlz-52-result.json` through `campus-mlz-56-result.json` and the focused review marker. Rays from outside selected openings must hit the displayed reconstruction's glazing, service door or frame, with no old photographic wall in front. The full route now contains 57 views; existing gravity/gameplay controls remain required.

Run `scripts/validate-mlz.py --baseline <directory>` with the geodata Python environment. It checks all 100 existing render meshes, all 83 survey roofs, unrelated photographic plans/collision files, the exact roof part of each new body, and the four collinear opposite-facing shared-wall pairs. Only their overlapping height intervals are removed; UYL's exposed upper wall remains. Source photograph/video proportions and unobserved faces remain estimates even when these checks pass.

The MLZ route checks 50 opening rays and ten native Minecraft wall colliders. Pixel rays at stages 50/53/55 must hit the reconstructed MLZ walls where old floating fragments appeared. At stage 54, two tracked above-roof rays must no longer hit provider scan geometry. The static validator also checks both roof-fragment coordinates against the bounded cleanup height and excludes neighbouring footprints with a 0.5 m guard.

## Altitude continuity

`minecampus.altitudeFunctional=true` with `minecampus.startStage=49` runs a separate twelve-view sequence through `CampusAltitudeChecks`, beginning at Y=150 before descending to the ground. It then ascends through Y=100/125/150/175, descends through the same heights, looks back from outside the survey coverage, and returns to the initial viewpoint. The QA-only `altitude-required-tiles.json` contains all runtime IDs from the packaged manifest. With `minecampus.requireAltitudeContinuity=true`, each settled frame must display all those render tiles and contain no old aerial-mode source IDs. Omit that requirement only to record the preceding-artifact baseline, where missing IDs remain explicit in the report. The sequence waits for complete streaming/upload readiness and records captures, renderer artifact, tile IDs and observational FPS samples. These samples are not a controlled performance benchmark. The ordinary 57-view route remains independent.

## Source-study routes

`minecampus.siteInspection=true` with `minecampus.startStage=49` loads `site-inspection.json` from the isolated QA run directory. The plan has a lowercase/hyphenated `name` and a `cameras` array; each camera supplies a `label` and Minecraft teleport `position` (`x y z yaw pitch`). `CampusSiteInspection` waits for streaming readiness and then settles at each position before capturing. Preserve the exact plan, checker sources, artifact hash and fresh output alongside the report. A capture-only PASS establishes that the route ran; it does not establish visual quality or correct architecture.

Gravity probes first hover at their specified drop position until the native collision alignment journal confirms the destination chunk. This preparation has a bounded 1,200-ready-tick wait. The checker then returns to the same starting position, disables flight and performs the unchanged landing, body-clearance and support-height assertions. Each completed probe records `alignmentWaitTicks`; a preparation timeout remains a failed inspection with diagnostics. This prevents a cold, newly generated chunk from being judged after an arbitrary five-second delay.

Optional per-camera `probes` contain a surface `target`, outward unit `normal`, expected `tile` and `part`. Each ray starts 0.6 m outside its target, checks the nearest displayed triangle and requires the expected surface within 2.5 cm. Optional `collider: true` also requires a native map-block collider across that wall. Choose controls in clear exterior space, particularly beside neighbouring buildings; these controls establish visibility/collision, not accuracy of inferred opening dimensions.

Where a surveyed tree legitimately occludes the wall, a plan may list the exact manifest `kind: vegetation` IDs in `vegetationTileIds`. The report records the first hit including vegetation and separately checks the nearest structural surface behind those listed tiles. Provider/source meshes are never excluded by this exception. Inspect the captures as well; a structural ray through foliage is not proof of an unobstructed camera view.

An explicitly targeted vegetation tile/part remains eligible in this ray test, so trunk controls measure the actual wood mesh while incidental leaf cards remain excluded. A failed surface or screen-ray assertion saves the failing camera and message with a FAIL report before stopping; it must not leave a misleading RUNNING report.

Copy `siemensbau-5103-inspection.json` to the isolated run directory as `site-inspection.json` for the maintained 14-view Siemensbau check. Require all 14 captures, 68 structural opening rays and two native colliders, with the exact packaged renderer hash in the report. Cameras `north-east` and `west` are retained as source-study context but are obstructed by adjoining buildings; the close gap and oblique cameras provide the usable target views. These views do not certify the neighbouring buildings or measured opening accuracy. Run the ordinary 57-view route separately. Changes to the shared shadow receiver also require the packaged TNT/time-of-day/reload functional check.

The RCM-Technikum checkpoint uses `rcm-technikum-5104-inspection.json` with the
same `runSiteInspection` workflow. Its 14 cameras include 15 RCM wall/opening
rays, 33 retained Siemensbau opening rays and three native wall-collision
controls. Copy that plan to the QA run directory as `site-inspection.json`.
The two eastern approaches have tree occlusion, and the narrow southern gap
is a close surface check; use the additional elevated/close views when judging
the full envelope. A captured camera or passing ray does not replace visual
comparison with the baseline.

A site-inspection camera may include `materialControls` with a resource `texture`,
`bounds` (`left, bottom, right, top` in Minecraft X/Z), square texture `size`, and
`points` containing `x`, `z`, and expected four-channel `rgba` bytes.
`CampusMaterialMaskCheck` reads those pixels from the uploaded level-zero atlas
and records `gpuMaterialControls` in that camera's result. This verifies uploaded
classification pixels; the camera images and geometry probes remain necessary
to establish their visible use on the intended ground meshes.

## Central campus quality review

`central-quality-review.json` retains 24 established cameras from the main route,
including two aerial views, and 12 standing controls on encoded terrain or ramp
surfaces. It covers the promenade, Galileo, former Mensa, IAS, COS, Graduate
School and MLZ so a successful local reconstruction does not substitute for
reviewing the main campus. Camera indices, source hash, standing-surface manifest
hash and reference artifact hash are recorded in the plan.

Use `runSiteInspection` with an isolated copied QA world and the explicitly
selected packaged JAR. Archive the exact plan, checker, artifact and outputs.
Require 24 camera records and 12 completed standing controls; inspect camera,
reflection and walking captures separately from the functional PASS. If terrain
or ramp geometry changes, regenerate the standing targets/support heights from
the new encoded surfaces before treating the plan as current. This review is
additional to the detailed site controls and does not certify full visual quality.

The plan enables `captureWalking` and `reflectionEvidence` explicitly. The first
63 run omitted these flags and therefore has 24 camera images and its failure
image only; do not infer walking/reflection captures from camera options alone.

The central promenade slope at `(60,-100)` exposed full-block terrain collision
in63: native standing Y=66, while the rendered support height is65.27549.
Run `node scripts/test-exterior-central-ground.mjs <extracted-service-directory>`
after extracting the packaged service and installing its pinned dependencies.
This exercises its actual voxelizer at eleven terrain controls and both save
datums. The Galileo ramp remains in the native route and is not represented as
a terrain-only control. Repeat the native route in a copied saved world to
verify migration and clearance.


`atom-ei-canopies.json` contains the 17-camera, 12-standing-control inspection used for candidate 74, including three oblique-sun canopy views and restoration of daylight before walking. `atom-ei-material.json` contains the six matched material views and two retained standing controls for candidate 76. Copy the selected plan to the isolated run directory as `site-inspection.json`; bind `referenceArtifactSha256` to the actual candidate JAR before running `CampusSiteInspection`. Require a fresh `PASS:` report and review every capture. These local checks do not replace the broader central-campus route or establish overall visual acceptance.


`atom-ei-west-entrance.json` inspects the measured west roof replacement with 13 cameras and 13 standing controls. It includes direct glazing rays, required scene-reflection selection, reflections disabled, an oblique approach, the roof underside and evening light. The six new walking probes use a 1 m drop: their initial full body must clear the roof collision as well as their final standing body. `test-exterior-atom-west-entrance.mjs` checks that condition at both supported datums, reproduces the prior wall obstructions and verifies roof/glazing collision. The original 2 m inspection setup was interrupted because it started inside the roof cells. Always use a fresh isolated save copy when repeating that migration.

Candidate 77 clearance run completed the 13 camera views and seven retained standing controls, then exited 1 at the first new west probe: its expected surface identity differs from the rendered tile 1000000033/part 0 (distance 0.60265154 m). The six new west standing controls remain unverified. Reconcile the probe with the displayed terrain before repeating the run; do not relax the surface or clearance assertion to obtain a pass. See `../atom-west-development-validation.json` for the exact failed probe and reviewed visual limitations.

Candidate 78 derives all six west controls from the encoded terrain and validates their declared tile, part and height before native inspection. It uses continuous glass backing behind the raised frames and a bounded cleanup seam shared with reconstructed canopies 338 and 340. The optional `diagnosticBounds` captures only nearby displayed provider triangle coordinates into the local QA directory; keep those diagnostic dumps local. Run the complete 13-camera/13-standing plan and review the approach, front and underside views before treating either visual defect as resolved.

Candidate 78 completed the full inspection with exit 0: 13 camera views, 13 standing/body checks and 35 reviewed captures. The bounded west provider-fragment count is zero in seven matched views. Preserve this plan when correcting the remaining pane-to-pane joints; successful collision checks do not establish full visual acceptance.

Candidate 79 completes the same 13-view/13-standing inspection with exit 0 and 35 reviewed captures. The validator now requires all five internal pane edges to be shared exactly in the exported float32 mesh, and reproduces their absence in the preceding 78 mesh. The close-up joint lines are resolved in the game; wider campus quality remains open. Evidence: `../atom-west-joints-development-validation.json`.

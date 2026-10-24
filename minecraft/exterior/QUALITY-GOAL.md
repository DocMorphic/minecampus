# Walking-height quality goal — unfinished

The target is a consistently convincing central Garching exterior in actual Minecraft, assessed from walking routes and aerial views. Passing compilation, a TNT test or one attractive aerial screenshot is insufficient to declare that goal complete.

## Playable preview

The 0.4.0 preview contains 600 × 600 m of surveyed terrain/20 cm aerial imagery, 734 inferred tree/canopy instances in 36 groups, two Galileo components, three main MW components, the Graduate School and three grass-roof promenade structures. The 117 intersecting building guides protect original architecture, including buildings whose centres fall outside the reconstruction boundary. They are **not** 117 completed detailed models.

The outdoor photo layer is retired away from protected building and roof coverage. This removes the free-standing scan fragments that remained after adding new trees. The protection and retirement lookups use raster/spatial caches to keep mesh processing practical. Survey heights are transformed through the official GCG2016 geoid; different save origin heights are handled explicitly.

## Remaining work

- Substantial façade/mesh artifacts remain on buildings outside the six detailed components. The source-inspection capture shows them openly.
- Window repetition, auditorium roof simplification, Graduate School bands and vegetation appearance remain reconstructions rather than measured architectural detail.
- Some foliage fused to protected building/roof meshes remains. Outdoor props retired with the original scan are not all reconstructed.
- Leaf cards are visual foliage; their gameplay behaviour is not a complete native leaf-block simulation.
- The day imagery does not become a measured night scan. Interiors remain out of scope.

Next quality work should prioritize the remaining source façades and site-specific architectural fidelity, using consistent ground cameras and explicit before/after evidence. Do not mark the overall realism goal complete on the strength of the preview's functional tests.

[Actual game captures and functional validation](VALIDATION.md) · [Sources and rebuild](README.md)

## Next development pass

The IAS exterior has been reconstructed from BVV component `DEBY_LOD2_8486677`, the architect’s project reference and High Contrast’s CC BY 3.0 DE photograph. It adds the recessed south atrium, glazed entrance floor, raised terrace/stair, panel joints, folded side screens and rooftop sunshade. This extends the development scene to seven detailed building components; the published 0.4.0 preview still contains six.

The same native camera was captured before/after. The new gravity check landed the player on the IAS terrace at Y=67; all eight native views and the TNT/ground/preservation checks passed. Development evidence is recorded separately so the published preview’s validation remains attributable to its exact JAR. Remaining coarse neighbouring façades are still open work.

[IAS development comparison and validation](IAS-DEVELOPMENT.md)

## Photographic façade development

The next pass projects the existing provider photography onto BVV survey walls and uses surveyed roof geometry with DOP20 imagery. This straightens building edges while retaining actual photographed material. Eighty envelopes are candidates; coverage checks decide which faces can be used. Unsupported faces keep their original mesh. These are measured envelopes with photographic surfaces, not eighty completed detailed architectural reconstructions.

The canopy detector now also recognizes brown foliage. The source-limit camera identified an autumn tree missed by the previous green-only detector, leaving a floating remnant of the original scan. Roof-aware retirement protects the measured building below the canopy. Building-corner retirement uses finite wall distance so scan triangles cannot survive simply because they fall beyond a wall endpoint.

The source photography still limits detail, especially on shaded façades. The goal remains open: straight geometry and functional tests do not establish a consistently realistic campus. See [photographic façade development evidence](PHOTO-FACADES-DEVELOPMENT.md).

## Visible-wall and fresh-generation follow-up

Coverage now excludes the portion of survey walls buried beneath DGM terrain, using a sampled terrain profile along each wall. Each visible face must independently meet the same 80% observed-photography and two-metre fill limit. A valid face no longer depends on the coverage of the building’s other faces. Unsupported faces still retain their source geometry. This recovers the former Mensa’s usable walls without claiming that the whole building has been reconstructed.

The former Mensa approach is now an explicit tenth native camera. A fresh isolated world exposed visible vanilla dirt filler along a steep, protected terrain margin; newly generated chunks now use invisible, mineable map material for this filler. Existing ordinary blocks remain protected by the migration policy. The vegetation overhang mask also covers complete guide cells before downsampling, avoiding missed narrow edges.

The new close-up remains a failing visual-quality case: coarse scan fragments and blurry material are still present around the approach. Ground-level reference photography should guide the next exterior reconstruction. TUM’s [April 2025 report and exterior photograph](https://www.ed.tum.de/ed/news-single-view-start/article/tum-ed-bezieht-alte-mensa-in-garching-nach-umbau/) show the renovated former Mensa, including its concrete frame, glazing and terrace artwork; that image is reference material, not a bundled texture. The newer Mensa at Boltzmannstraße 19 is a different building.

## Former Mensa terrace frontage

The terrace close-up exposed a limitation of reprojection: large dark and pale scan features were flattened onto the building’s wall, obscuring its frame and glazing. The development scene now reconstructs five south-facing terrace surfaces as eleven concrete bays with recessed glazing. BVV fixes the five face lengths and elevations; the main face is 43.03 m wide. TUM’s 2025 exterior photograph guides the frame, low glazing panels and rooftop maintenance railing. Exact pier sizes, glazing subdivisions and recess depth remain estimates. The photo is used as a reference only, not redistributed as a texture.

This is one partial frontage, not an eighth complete detailed building. Other elevations and roof equipment retain their existing source/survey treatment. The main facade is clearer, but the approach’s residual scan fragments, pavement detail, terrace artwork and the broader campus quality remain open work. A near-terrace viewpoint is now retained alongside the original approach camera so the recesses cannot be hidden by a distant view.

## Terrace retaining walls and next canopy correction

Ray diagnostics assigned the large lower-approach fragments to the 50.10 m outer survey wall, whose visible photographic coverage was only 42.9%. Four measured lower faces now use continuous concrete geometry, with railing only along sampled exposed drops. The existing licensed IAS panorama supplies a visible concrete terrace-wall reference. This removes the major jagged lower edge without changing the terrain envelope or adjoining plateau connection.

The remaining overhead fragments need a different correction. A 0.5 m diagnostic window over the terrace edge found a connected tall foliage patch extending north to approximately Z=-233.5, while the nearby generated circular crown is centred near Z=-220.5 with radius 6.56 m. Current crown ownership excludes protected footprints, then clips each assigned region to an 8 m radius; that loses real overhang. Next work should fit shifted/elongated crowns from connected survey foliage and protect the roofs beneath them. The diagnostic is not evidence for inventing a separate shrub.

## Survey-fitted canopy follow-up

Crown fitting now follows connected DOP20 foliage and DOM20 elevations independently of trunk placement, including canopy overhang above low survey roofs. The representative terrace tree extends north beyond its previous circular limit. Roof-aware source retirement uses the fitted crown coverage, and native rays check for residual old triangles even behind the new foliage. The lower crown boundary and branch layout remain estimates; the survey supplies the upper surface and footprint, not a complete botanical model.

The two tracked overhead terrace fragments are corrected in the development build. Ground imagery and the terrace bank remain visibly coarse, and vegetation species/branch detail, stairs, artwork and the broader architectural work remain unfinished. The goal stays open. See the [crown-fitting evidence](PHOTO-FACADES-DEVELOPMENT.md#survey-fitted-crowns-f7a3ff1a).

## Mapped ground materials

The development renderer now uses 180 OSM lawn polygons and two explicitly mapped paved areas, with twelve mapped water/court exclusions. A 4096² classification texture anchors close-range materials to their mapped footprints. Ground normals follow the terrain slope, and shared material textures now use anisotropic filtering. Paving units and lawn grain remain estimates, with the original aerial imagery supplying broad colour/shadow context. The native route check now includes a twelfth camera for close-range paving.

This improves surface readability without changing terrain geometry or player collision. The current two-metre ground grid still rounds/facets steep edges even though DGM1 provides finer source sampling. That geometry, unmapped paths, terrace details and untreated façades remain the next work. All eight native checks, six material control samples and 21 service tests passed; all 46 backed-up original save files remain unchanged. The installed/public preview is still 0.4.0. [Exact ground-material evidence](ground-material-development-validation.json).


## One-metre terrain and pixel-centred sampling

The development mesh now preserves all 360,000 DGM1 interior samples with continuous tile boundaries. Bilinear sampling uses pixel centres and crosses the merged source-file seam. This removes the previous two-metre terrain simplification and corrects the half-pixel sampling offset. The Mensa bank's diagonal edge is visibly cleaner. Collision migration v5 uses the finer mesh while retaining ordinary player blocks and the edit journal.

Source-encoding accuracy does not establish the accuracy or currency of the survey. The ground remains a heightfield, Minecraft collision remains a block grid, and source-filtering guides remain two-metre samples. Steep-face material stretching, unmapped paths, terrace detail and untreated façades still prevent completion of the realism goal. [Terrain evidence](terrain-development-validation.json); installed/public release remains 0.4.0.


## Steep-ground material correction

Three-axis ground material projection removes the prominent vertical stretch on the Mensa bank. The exact development package passed twelve native viewpoints and nine gameplay/geometry checks. A loaded-scene shader comparison did not demonstrate a frame-rate regression, but system load and changing daylight limit that measurement. The original save remains unchanged. [Material evidence](slope-material-development-validation.json).

The next substantial gap is the coarse UYA façade visible in the source-limit and north-facing cameras. A pinned ESO reference identifies its two roof courts, pale upper walls, individual windows and contrasting lower panels. Fit those features to the BVV envelope while distinguishing measured geometry from inferred divisions. The goal remains open.


## UYA exterior reconstruction

The four outer UYA walls now have recessed windows, frames, sills and separate lower infill/glazing on the BVV envelope. The visible ESO reference supports 24/11 upper-window rhythms; opposite elevations and exact divisions remain inferred. The survey roof and both courtyard openings are byte-identical to the preceding package, with eight inner faces still using photography. Twelve native viewpoints and nine gameplay/geometry checks passed. [UYA evidence](uya-development-validation.json).

The two street-level views now make UYA recognizable, but the adjacent UYE/gatehouse (`DEBY_LOD2_31360854`) and small warehouse (`DEBY_LOD2_52738492`) remain conspicuously coarse. Those foreground structures and unmapped path surfaces are the next gaps in a consistently convincing route. The overall goal remains open; a playable preview should expose the accumulated development improvements without modifying the user's original save.

## Playable development snapshot

The exact UYA-tested artifact is now installed in **Minecampus — Exterior Preview 0.5**, alongside the original installation. All 121 source save files were copied and hash-verified; the 46 original backed-up world files remain byte-identical. Local map setup was copied privately and pointed at the preview's own service directory. The installer refuses an existing destination or profile and checks open-world locks before copying. [Play and download instructions](PREVIEW-0.5.md). This makes the accumulated improvements available for play while the remaining exterior work continues; the overall goal remains active.


## UYE foreground replacement

Two visible UYE elevations now use a pale roof fascia and recessed framed glazing on the survey envelope. The exact model passed twelve native viewpoints and ten checks, including a ray that verifies replacement of the previous foreground fragment. The original save remains unchanged. West/south elevations retain photography, and exact framing remains inferred. [UYE evidence](uye-development-validation.json).

The warehouse on the opposite side of the same route still has poor photographic walls. Path surfaces also remain inconsistent: the current mask uses closed polygons, while the OSM snapshot contains many linear paths with useful material tags. Those structures and path coverage are next; the goal remains active. The installed 0.5 preview is unchanged until the next tested snapshot.


## Warehouse route and next ground coverage

The blurred warehouse wall is replaced with survey-aligned masonry, a pale roof edge and an estimated east opening. A new close-up accompanies the existing route camera. Thirteen native views and eleven checks passed; the original save remains unchanged. The close-up reveals additional untreated structures farther north, and hidden warehouse openings remain unknown. [Warehouse evidence](warehouse-development-validation.json).

The next broad improvement is road/path material coverage. The current OSM XML contains nineteen eligible asphalt/paving ways with explicit widths, totaling 1,343.8 m within the campus. Their buffered candidate surfaces cover 7,179.14 m². An aerial overlay follows the main roads and intersects only 15.85 m² of mapped lawn, with no mapped water/court exclusions touched. These are derived candidates, not rendered surfaces or measured curbs. Check building intersections and edge transitions, then add close-range material coverage and verify the walking routes. The goal remains active.

## Road coverage and second playable snapshot

The nineteen explicit-width road/path strips are now built and native-verified. They add 7,163.29 m² of material coverage after building/mapped-area exclusions. Fourteen viewpoints, eleven native gameplay/geometry checks and twelve material controls passed. The exact artifact is published as `exterior-0.5.0-dev.2` and installed in the separate preview, with all 121 preview save files and private settings verified unchanged. The original installation is unchanged. [Road evidence](road-development-validation.json).

The sharper road exposes the remaining coarse sidewalks and margins. Curbs, northern building detail, terrace artwork and broader route fidelity remain unfinished. The warehouse-east camera identifies the next building as BVV `DEBY_LOD2_5284457`, TUM building 5103 (Betriebsgebäude II / Verwaltung). Ground photos beside the Nobel steles show the smaller adjacent Telefonzentrale (5130), not Siemensbau itself; the native camera and distinct survey envelopes establish that distinction. Siemensbau does not yet have a verified opening schedule. The goal remains active.


## Telefonzentrale identity and west façade

The four-window reconstruction is now on the correct Telefonzentrale envelope (5130), verified by four native window rays and a matching before/after camera. The unverified Siemensbau windows were removed before recording the final artifact. Fifteen frames, twelve native checks and 22 service tests pass; the original save is unchanged. [Evidence](telefonzentrale-development-validation.json). The installed preview remains dev.2.

The new view exposes poor neighboring façades and missing site detail. A useful next source candidate is the [Center for Organoid Systems, TUM 5132](https://nav.tum.de/building/cos): NavigaTUM supplies Alexander Pach's exterior photograph under CC BY 4.0. Its address matches OSM way 1275027418, and that footprint overlaps the convex outer BVV envelope `DEBY_LOD2_108698313` with 0.933 intersection-over-union. Verify the visible wall orientation and current geometry before reconstructing it; this research does not establish that every degraded background surface belongs to COS. The realism goal remains open.


## COS and third playable snapshot

COS (TUM 5132) now has its surveyed complete envelope and roof, photograph-informed west/south timber facades, and inferred rear openings. It remains visible in aerial mode. The older terrain scan's construction mounds are replaced by explicit local grading, with nearby buildings excluded; native gravity verifies the former mound position. Eighteen views, fifteen native checks, 25 service tests and terrain verification pass. [COS evidence](cos-development-validation.json) and [play instructions](PREVIEW-0.5.md) accompany `exterior-0.5.0-dev.3`, which also includes Telefonzentrale.

The goal remains open. COS still needs convincing ground materials, site objects and reduced timber repetition; aerial surroundings retain the old construction-site imagery. Siemensbau and several larger neighbouring facades remain visibly coarse. Address these limitations using the current route views and sourced exterior evidence; do not equate passing native checks with visual completion.


## COS site materials and furniture

The dev.4 snapshot adds ten bounded material patches, two mapped bench lines and ten inferred bicycle stands. Nineteen native views, seventeen checks and 26 service tests pass. Terrain tiles and existing mapped material pixels remain unchanged; native gravity verifies the bench collider. [Site evidence](cos-site-development-validation.json).

The corrected forecourt view is outside Siemensbau's surveyed footprint; the exploratory `(162,-262)` camera was inside it and is excluded. The current ground view still shows pale old construction imagery between mapped patches. Next, resolve these margins with source-informed planting/paving rather than assuming that every unmapped region is paved. Improve the nearby coarse facade once sufficient reference evidence exists. The quality goal remains active.


## COS landscape infill and apron

Dev.5 replaces a bounded portion of the old construction imagery with inferred forecourt paving, a soil bed and north lawn. Low bed edging follows a smooth apron grade anchored to the facade and DGM driveway. The close visual review caught and corrected the previous radial grading hump; native gravity distinguishes the corrected ground proxy from the old one. Twenty-one route captures, nineteen native checks, 26 service tests and five terrain tests pass. [Evidence](cos-landscape-development-validation.json).

The goal remains active. The west-side margins and eastern parking still need believable surfaces; the broader campus needs consistent curbs, ground detail and better coarse facades. Reconstructed planting and facade details are approximate. Aerial ground retains older photography. Continue from these visible limitations rather than equating a tested checkpoint with completion.


## GRS north-wing facade

Dev.6 replaces the distorted long GRS wing beside COS with a survey-aligned facade informed by the architect's photographs. Recessed glazing, frame divisions, fascia and braces establish the building's characteristic structure. The roof, all 89 prior render tiles and the other 79 facade plans remain unchanged. Twenty-three native route views and twenty-one checks verify this package. [Evidence](grs-development-validation.json).

The goal remains active. The neighbouring GRS wings/tower and Siemensbau still need exterior treatment. Approximate glazing reflections, pale ground margins, older aerial imagery and some repetitive vegetation limit overall realism. Current reconstruction dimensions and colours remain explicit estimates.


## GRS stair tower and connecting bridges

Dev.7 adds the surveyed octagonal tower, west bridge and short south junction, with reference-informed exterior details and exact embedded survey roofs. Cleanup boundaries exclude adjacent buildings. All 90 preceding render tiles and 79 other facade plans remain unchanged. Twenty-six native views and twenty-four checks verify the package, including preservation of the neighbouring roof. [Evidence](grs-connectors-development-validation.json).

The goal remains active. Courtyard camera 24 exposes a broad stretched source surface overhead beside the tower; identify its native hit tile and survey ownership before editing it. It may be a valid roof exposed by missing or unsupported west-wall photography, so do not assume the roof itself is wrong. The main/south GRS wings and Siemensbau remain visibly coarse; parking and ground margins still need treatment. Reconstructed colours and opening dimensions are estimates, and the wider campus does not yet meet the requested realism standard.


## GRS II closed exterior and corrected source mapping

Dev.8 resolves the courtyard's apparent floating roof by reconstructing the missing west wall and the complete GRS II envelope. Native diagnosis establishes that the roof itself was valid. The full architect plan also corrects the earlier north-wing reference attribution; its unsupported braces are removed. The matching GRS II facade now carries the observed architectural character, with dimensions and hidden elevations explicitly estimated. Twenty-eight views, twenty-six native checks and exact roof/asset preservation evidence verify this checkpoint. [Evidence](grs-main-development-validation.json).

The goal remains active. GRS III (`DEBY_LOD2_5284472`) to the south is a strong next candidate: the [architect's 1994–1996 project page](https://claudia-schreiber-architektur.de/projekte/neubau-buero-und-laborgebaeude-iii-garching) supplies exterior photographs, a plan and sections. The square building, roof lantern and separate rounded tower appear consistent with the surveyed southern group, but confirm the footprint and orientation before reconstructing it. Its basement is partly exposed on sloping ground. The current survey roof already contains 50 triangles spanning Y=72.30–75.25, so inspect that geometry and the roof lantern before changing it. Ground margins and Siemensbau remain visibly poor. Keep the full campus realism objective open.


## GRS III exterior checkpoint

Dev.9 reconstructs GRS III's square main wing and rounded stair tower using the surveyed envelope and architect's historical exterior evidence. Three window bands, eight perimeter columns, floor edges, blinds and upper braces replace distorted photography. All 94 previous render tiles and all 50 original GRS III roof triangles remain unchanged. Thirty-three native views and thirty-one native checks verify the package. [Evidence](grs-iii-development-validation.json).

The goal remains active. Courtyard ground between GRS II and III is the next useful local improvement: the architect's courtyard photograph shows a narrow paved approach to the rounded tower door with planting beside it. The BVV 20 cm orthophoto confirms the courtyard gap and the east-side path, but tree canopy obscures some surface boundaries. Map a bounded, explicitly inferred path between the tower entrance and east walk, protect both building footprints, and inspect the actual ground-level view before changing grade or filling the entire gap. The central raised roof keeps its surveyed/photo surface; a detailed glazed steel reconstruction remains unfinished. Siemensbau, parking and broader route materials remain visibly coarse.

A follow-up native inspection identifies the sharp stray fragment behind the rounded tower: two provider hits lie on or within 0.26 m of the separate 4.28 m² survey connector `DEBY_LOD2_5284469`, between GRS II and III. Its bounds are X=246.48–249.08, Z=−260.63–−258.40, roof Y=71.99; one fragment reaches Y=74.16. The 20 m² facade-candidate threshold excludes this small connector, while neighbour-safe cleanup correctly protects its footprint. Add an explicit small-link reconstruction and roof-preserving ownership boundary before the courtyard surface pass. Diagnostic rays are retained in the dev.9 evidence; they do not count as additional full-route checks. The bounded courtyard path candidate is approximately 1.8 m wide, 41.05 m² after building exclusions, with DGM heights 63.80–63.97. The path is researched but not implemented.


## GRS courtyard connector and approach

Dev.10 replaces the small connector's distorted scan fragments with its survey envelope and exact roof. An inferred 1.8 m paved approach with low edging now reaches the rounded tower door. Thirty-five native captures and thirty-three checks verify the package. All 95 previous render tiles, 82 facade plans and terrain guides are unchanged; 1,527 formerly unassigned material pixels become paving within the bounded path. [Evidence](grs-courtyard-development-validation.json).

The goal remains active. Remaining coarse structures include Siemensbau: [LRZ's building-specific service notice](https://status.lrz.de/issues/muenchner-wissenschaftsnetz-mwn/2025-08-05-schwenk-garching/) independently confirms that TUM 5103 / Betriebsgebäude II at Boltzmannstraße 10 is also called Siemensbau. The previously viewed sculpture photographs mostly depict Telefonzentrale, so do not reuse those openings for Siemensbau. A convincing facade still needs verified reference coverage.

A broader visual limitation is now apparent across the rebuilt buildings: `campus_ground.fsh` gives glass a procedural sky/ground approximation and applies local diffuse/material shading, without scene reflections or architectural cast shadows. Investigate source-geometry-based lighting and compare representative walking views before publishing a global rendering change. A read-only feasibility study rasterized 2,969 survey roof triangles from 117 buildings into a 2,048² height field at 0.328 m per pixel in about 1.3 seconds. This is not a game rendering change: verify current reconstructed roof overrides, handle roof-edge/self-shadow bias, preserve player-edit behavior, and benchmark the actual shader before integration. Preserve frame rate and source attribution. Courtyard planting, margins, parking and several coarse roofs/walls remain unfinished; neither this checkpoint nor green tests establish full-campus realism.


## Shadow feasibility review after dev.10

The courtyard update is published as `exterior-0.5.0-dev.10`; its installed and uploaded JAR hashes match. An isolated, fixed-sun survey-shell shadow experiment was then evaluated in the courtyard camera. A corrected baseline/candidate/baseline run produced median readings of 94, 89.5 and 96 FPS. The candidate adds shading but creates visible bands on the rounded tower and roof-edge halos. This is a rejected experiment, not a preview feature. [Evidence and comparison frames](shadow-feasibility-review.json).

The first exploratory run used a stale private two-phase COS test harness and is excluded from the reported comparison. The final run uses the maintained three-phase harness plus only the isolated texture binding and an explicit region-height check. The private harness has been restored to the maintained source, and the experimental resource pack archived outside the game's resource-pack directory.

The experiment also cannot follow TNT damage or moving sunlight. A stronger next approach is a bounded depth pass using the actual loaded `MapTile` buffers after their damage refresh, with explicit GL state restoration, alpha-cutout foliage and region/height handling. Test actual destruction and day/night transitions as well as performance and multiple walking routes before enabling it. The existing renderer uses a fixed material-light direction; reconcile this with the cast-shadow direction rather than adding contradictory lighting. [Khronos texture-access documentation](https://wikis.khronos.org/opengl/Sampler_(GLSL)) explains the unfiltered, bounds-checked depth samples used in the study. Ground margins, Siemensbau and other coarse surfaces still require source-informed work. The overall realism goal remains active.

## Runtime mesh shadow development

A new isolated depth pass now draws the actual loaded `MapTile` buffers, including leaf alpha cutouts. The first coarse version exposed thin-slat sampling patterns and measured 77 FPS between 92/94 FPS baselines. A 100 ms redraw throttle, exact-texel receiver-plane comparisons and a finer 4096² map over 128 m improved the courtyard result. The final three-phase run measured 95 / 89.5 / 95.5 FPS; both baseline screenshots are pixel-identical. These are local readings, not a general performance guarantee. [Source, configuration, ray probes and captures](runtime-shadow-development-review.json).

The implementation is retained in `experiments/shadows`, outside the production build inputs. The tested dev.10 JAR and installed preview remain unchanged. This is a working renderer prototype, not an accepted global visual change: small edge patterns remain, and actual TNT response, moving sunlight, night, player movement, wider routes and lifecycle/state handling still need verification. Only map meshes participate; vanilla blocks and entities are not shadow casters or receivers in this experiment. The QA hook is after the existing map renderer and supplies the next frame; production integration must run after damage refresh and before material drawing. Replace the rough caster bound with the actual light frustum.

Continue with a native TNT/depth-map before/after/restoration check in the isolated save, plus consistent sun direction and a night cutoff. The local Minecraft 1.21.1 sky renderer applies Y(−90°), then X(time-of-day × 360°), to the sun at positive Y; its world direction is therefore (−sin(angle), cos(angle), 0). Use that same direction for material lighting and shadows, and inspect morning/noon/evening/night frames. Do not treat an unchanged precomputed shadow or merely receiving the damage event as proof of the rendered result. Ground margins, Siemensbau and the broader campus fidelity remain unfinished. The overall goal stays active.


## Integrated sunlight and mesh-shadow checkpoint

The runtime prototype is now integrated into the renderer after damaged buffers refresh and before map material drawing. A local 4096² depth pass follows Minecraft's sunlight, includes leaf alpha cutouts, and stops at night. Material lighting follows the same sky direction. The light frustum replaces the prototype's coarse caster bound, and resource/world resets retire the framebuffer.

The packaged native functional check verifies actual TNT changing depth, exact restoration, morning/evening/night lighting, and a full resource reload. The reload test exposed a pre-existing material-cache weakness: Minecraft reuses texture IDs but resets mipmap sampling. Shader registration now invalidates the shared-material preparation cache, and all ten materials retain proper sampling after reload. The final release evidence also requires the unchanged 35-camera route and 33 geometry/gameplay checks against the exact corrected JAR. See [validation](runtime-shadow-development-validation.json).

This is still a development checkpoint. Only map meshes participate in the shadow pass; vanilla blocks and entities do not. Photographs retain baked shadows, glass has no real scene reflections, and small shadow-edge sampling patterns remain possible. Ground margins, courtyard planting, parking and Siemensbau remain visibly unfinished. The full campus-quality goal stays active.

Next source work should focus on the unmapped pale paths/margins visible from the central promenade and COS area, with bounded surface polygons checked against the BVV orthophoto and existing OSM/building exclusions. Do not recolour every bright pixel: paving, road markings, roofs and real light aggregate can all be bright. The current material mask has extensive mapped grass but leaves many paths and margins on the low-resolution orthophoto. Siemensbau reference searches still return the unrelated modern Siemens Technology Center; [NavigaTUM 5103](https://nav.tum.de/building/5103) and the [LRZ network plan](https://www.lrz.de/services/netz/mwn-netzkonzept/mwn-netzkonzept-2019.pdf) identify the older building but do not establish its window layout. Do not borrow the new centre's facade.


A read-only promenade source check identified four long OSM paths with asphalt surface tags but no width: [30275349](https://www.openstreetmap.org/way/30275349), [32458178](https://www.openstreetmap.org/way/32458178), [386192514](https://www.openstreetmap.org/way/386192514) and [617369303](https://www.openstreetmap.org/way/617369303). Their current API records were fetched and checked on 2026-10-24. The existing explicit-width importer intentionally excludes them. Local research is in `.cache/promenade-path-source-study.json`, with raw API responses under `.cache/promenade-path-references`; orthophoto/mask comparison crops are `.cache/ground-margin-study-promenade.jpg` and `.cache/ground-margin-study-cos.jpg`. Measure source-supported widths before generating bounded material strips. Do not use a blanket paving infill: the mapped surface on these four paths is asphalt, and crossings/adjacent areas need separate treatment.

The corrected dev.11 artifact is installed in the separate Exterior Preview profile. The updater verified all 121 preview-save files and local settings unchanged, retained the previous JAR for rollback, and all 46 files in the original save still match the backup. The final native route completed successfully with 35 fresh captures and 33 existing checks; the separate functional run supplied seven fresh captures and five lighting states, including reload.


## Promenade material checkpoint

Four widthless OSM asphalt paths are now bounded using explicitly estimated BVV orthophoto widths and offsets. Approximately 3,707 m² receives detailed asphalt, while all earlier mapped material interiors retain their classification. Four samples per axis smooth raster boundaries; a 20 cm texture-only margin beneath facades avoids photographic bleed. The full set of 97 render tiles, building geometry, vegetation, terrain and collision version v18 stays unchanged.

A native three-ray diagnosis rejected the initial assumption that the bright facade-base strip was a wall fragment: each ray hit surveyed ground, about 20–23 cm outside the original corridor. Extending the eastern edge while retaining its western edge covers those controls. The focused native review passes seven GPU material/ground controls and shows the corrected coverage. A lighter textured strip remains from baked aerial shading; neither this fix nor green checks establish fully realistic lighting.

Continue with the short transverse and diagonal paths around the promenade, using their own OSM surface classifications and orthophoto boundaries. The read-only candidate inventory in `.cache/campus-path-candidates.json` contains both asphalt and paving/sett paths, so do not blanket-fill the crossings. Reconstructed glazing, older aerial shadows, Siemensbau, detailed roofs, ground margins and landscaping remain unfinished. The full quality goal remains active.

A follow-up read-only study fetched current full OSM ways 28193721, 403912530 and 403912532 and confirmed asphalt tags without widths. Source hashes and nine orthophoto transects are under `.cache/promenade-crosspath-source-study.json` and `.cache/promenade-crosspath-width-sections.jpg`. The first is roughly 2.5 m wide and the third roughly 4 m, provisionally; the second's mapped line sits near/outside one edge and needs segment-specific offsets. Intersections overstate widths. These are research observations, not implemented surfaces or surveyed dimensions.

The exact dev.12 candidate completed the native 37-view route with 34 ordinary checks, the 37-frame GPU lighting check and all seven promenade controls. All captures were fresh and reviewed. The installed preview updater verified 121 save files and local settings unchanged; all 46 original-save files still match the original backup. [Artifact and validation evidence](promenade-development-validation.json). Renderer classes and shaders are byte-identical to dev.11; the separate lighting/TNT/reload functional run remains dev.11 evidence.


## Cross-path materials and Galileo courtyard diagnosis

Eight crossing/entrance ways now add approximately 611 m² of bounded asphalt. The original OSM lines and tags are retained separately from inferred widths/offsets. The first walking review exposed a wider southern apron: its eastern section is now explicitly wider. A one-millimetre overlap at adjoining width stations prevents a zero-area seam after coordinate round-tripping. Existing lawns, paving, soil, previous asphalt coverage, all 97 render tiles, terrain and collision v18 remain unchanged. Source dimensions are estimates; pale unmapped margins around the sculpture and adjacent paving remain unfinished.

Camera 38 exposes a much more consequential geometry problem at Galileo's northern sunken courtyard. Both rays hit survey terrain tile `1_000_000_027`, at approximately `(116.70,63.50,-164.29)` and `(114.91,63.26,-156.17)`. They do not hit a stray provider facade. OSM way `579584070` identifies a lower courtyard; mapped concrete walls and a 27-step stair, the BVV orthophoto and the [landscape architect's completed exterior photograph](https://slam.green/wp-content/uploads/2024/07/SCC_Munich_Exterior_02-1024x683.jpg) establish that the stretched bank should be presented as a bounded court with retaining structures. The court footprint is approximately 435 m², MC X=93.92–116.29, Z=−168.51–−142.10. Its 2 m terrain-guide samples span Y=60.19–63.84; sample the finer DGM and exterior levels before choosing the finished floor/rim heights.

The [landscape architect's project page](https://slam.green/projekt/galileo-neue-mitte-am-hochschulcampus-garching-muenchen/) also provides a plan and a Senkgarten section. The section is design evidence, not proof that every planting or water detail was built. [Pinned source records, coordinates and diagnostic rays](photos/galileo-north-court-reference.json). Reference images are retained only in the private research cache, not redistributed as game textures. The same completed exterior photo provides much stronger evidence for Galileo's facade panel/window rhythm than the current coarse photographic shell.

Next, fit retaining walls and the stair to the mapped court edges and surveyed levels, correct the stretched terrain presentation within that boundary, and verify both the promenade view and a walking route down the steps. Preserve the lower courtyard and neighbouring buildings; do not flatten the real depression. Leave building interiors out. Broader facade fidelity, Siemensbau, roof detail, reflections and landscaping remain part of the active goal.

The fine DGM study samples 874 points more than 3 m inside the court: median DHHN2016 elevation is 470.559 m. The mapped 19.63 m stair line descends from about 474.76 to 470.59 m and contains several clear intermediate plateaus. Preserve those landings rather than replacing the route with a single slope. The 27-step OSM tag does not by itself identify flight-by-flight riser counts. Nearby Wasserwand and escalator features are outside this court and explicitly excluded in the source record.

The exact dev.13 artifact completed 39 fresh native captures, 35 ordinary checks and the 39-frame GPU lighting route. Eight new material controls and all seven preceding promenade controls pass. All views were reviewed; the terrain and facade limitations above remain visible. The separate preview updater verified 121 save files and settings unchanged; all 46 original-save files match their backup. [Validation](crosspath-development-validation.json). The overall realism goal remains active.


## Galileo northern courtyard reconstruction checkpoint

The courtyard now has three concrete retaining sides, an outer stair retaining face, coping, 27 risers over five flights/landings, slim render-only handrails, a connected lower turn, pavement detail and lower north-facing exterior glazing. The floor uses the fine DGM median of 470.56 m DHHN2016 (MC Y≈60.30). OSM's 4 m width overlaps its separately mapped wall when used with the raw stair centreline; a documented 0.65 m west adjustment fits them together. Flight endpoints, allocation of risers, wall dimensions, lower-landing extension and pane spacing remain inferred.

The ground cut is approximately 681 m² across two tiles. Remaining triangles retain original positions/UVs, including barycentric interpolation at the boundary. All other 95 render tiles, old architecture, material masks and survey guides are unchanged. Native review exposed an overly broad protection margin leaving terrain through the facade, a stair/wall overlap, and an unconnected lower turn; the final mesh corrects these. It also closes the rear retaining face. There is no building interior.

The exact artifact `ab7922f5ca2fcf05797bb1b1b98b2120333a5500b50d39a868bd43ccb517c72d` passes 42 native views, all 35 earlier checks, eight courtyard gravity probes and the complete GPU lighting route. A separate exact-artifact run verifies TNT, sun changes, night and resource reload with seven captures. Collision migration v19 retains saved edits/player blocks. This confirms the tested bounded repair, not whole-campus realism. [Evidence](galileo-court-development-validation.json).

Continue with Galileo's main facade: the repeated existing texture misses the alternating metal/glass rhythm and transparent ground-floor band. [New primary contractor/architect source study](photos/galileo-facade-reference.json) identifies matte light/dark grey and aluminium finishes, unitised and mullion/transom systems, and a useful facade-section photograph. Preserve BVV roof/envelope geometry and distinguish measured dimensions from inferred modules. Courtyard planting/seating, some building-base joins, Siemensbau, older aerial shadows, reflections and other coarse neighbouring structures remain unfinished. The overall goal stays active.

The separate Exterior Preview installation now contains this exact verified artifact. Its updater verified all 121 preview-save files and local settings unchanged and retained the old mod for rollback. All 46 original-save files still match the original backup.


## Galileo panel facade checkpoint

The two Galileo components now use separate smooth pale metal panels, recessed glass, narrow dark ventilation fins and fine frame/joint geometry. The former photographic strip is removed from their walls. All 95 BVV wall faces retain complete backing, and both exact survey-roof parts plus the other 97 render tiles are unchanged. The contractor's close-up supports alternating opaque/glazed groups and matte metal finishes; module widths, floor divisions and the row sequence remain estimates. Native review rejected the first candidate's broad ground-floor glass band and heavy frames; the final candidate continues the observed panel system to the base with slimmer frames. Exact entrances and local transparent zones remain unfinished.

Artifact `c7fdbce22d557420cae0a07dfd502fc53362d0319f8174928ca9f6349b4ea6fd` passes the full 47-view native route, 40 ordinary checks, eight courtyard gravity controls and the 47-frame GPU lighting check. Five 7 × 5 ray grids confirm visible metal/glass parts and the preserved aerial roof. A separate exact-artifact run verifies TNT, lighting changes, night and resource reload with seven new captures. [Evidence](galileo-facade-development-validation.json). These checks prove the tested change and preservation; they do not establish whole-campus realism.

The next conspicuous renderer limitation is glazing: it still reflects an analytic sky/ground approximation instead of the visible campus. [Read-only reflection study](reflection-study.json) compares a bounded nearby planar reflection with a local cubemap. Prototype outside production inputs and verify camera motion, actual mesh damage, sky changes, performance and resource lifecycle before integration. This creates no interior. Courtyard landscaping/seating, exact facade openings, base joins, roof detail, Siemensbau, other coarse neighbours and baked aerial shadows also remain unfinished. The full goal remains active.

The separate preview installation contains this exact verified artifact. The updater verified all 121 preview-save files and local settings unchanged, with the previous JAR retained for rollback. All 46 original-save files still match their backup.


## Isolated Galileo reflection checkpoint

A separate QA overlay now reflects the actual loaded campus geometry in one nearby Galileo facade plane. The nine-stage native run covers west off/on/off, southwest, east and north views, night, resource reload and return to daylight. A diagnostic pane mask confirms that the reflected image reaches the correct glass; 1,059,269 neutral-material control pixels are unchanged, and switching the effect off restores the entire original frame exactly. Reflected sky is no longer multiplied by the pane's surface shadow. [Prototype code, limits and procedure](experiments/reflections/README.md); [recorded evidence](experiments/reflections/validation.json).

This remains an experiment. The managed extra texture slot initially failed because Minecraft's texture cache has twelve entries; the final candidate uses a separately bound hardware unit and passes the recorded state/uniform/GL-error checks. The western stationary comparison measured 85.5 FPS off, 68 on and 86.5 off again on the tested M1 Max. Reflection edges, continuous motion, plane transitions, destruction, complete state/lifecycle handling and production integration still require work. The east-side view also exposes distorted terrain at the building base. The installed dev.15 artifact remains unchanged. No release or installer update was made for this prototype; the broader realism goal remains active.


## Integrated Galileo reflection checkpoint

The packaged renderer now refreshes one nearby surviving Galileo facade plane after damage updates and before the main material draw. Camera perspective updates in the same frame, with a small selection hysteresis at corners. A separate hardware texture unit avoids Minecraft's twelve-entry texture cache. Resource/world resets destroy the old target and release the world/plane references.

The exact dev.16 candidate passes 47 fresh native views, 40 existing checks, eight courtyard gravity controls and both 47-stage lighting/reflection routes. Ten additional phases cover off/on/off, west/southwest/east/north, night, resource reload, return to daylight and continuous movement. The moving check verifies 1,185 GPU matrices over 22.56 m. Actual TNT changes reflected depth and glass area; restoration has zero measured residual. A normal disconnect/reopen retires the old target and creates a fresh one. The reopened capture still shows the provider-loading overlay, so this verifies target lifecycle, not fully settled provider streaming. [Evidence](reflection-development-validation.json).

The western comparison measured 87.5 / 69.5 / 88 FPS off/on/off on the tested M1 Max. All 1,059,269 neutral control pixels are unchanged, and off-again reproduces the baseline. Only loaded map meshes participate: vanilla blocks/entities, recursive reflections and sky objects are absent. Other facade planes retain their analytic fallback, and thin edges/plane transitions can still show artifacts. All 99 meshes, terrain, roofs and collision v20 remain byte-identical to dev.15.

Next, diagnose the distorted ground along Galileo against the fine DGM, mapped site structures and the landscape architect's completed-site photos. Preserve the real northern sunken courtyard and distinguish QA TNT excavation from pre-existing terrain defects. Exact ground-floor openings, building-base joins, other coarse neighbours, baked aerial shadows and landscaping remain unfinished. The full realism goal remains active.

The exact dev.16 artifact is installed in the separate preview. The updater verified all 121 preview-save files and settings unchanged, retained dev.15 for rollback, and all 121 files across the original instance saves stayed unchanged. The original campus world still matches all 46 backup files.


A read-only [Galileo ground diagnosis](photos/galileo-ground-diagnosis.json) confirms a western pit at MC `(67,-59)` in both the encoded terrain and raw DGM, independent of TNT. The source raster is about 472.84 m DHHN2016 there, versus 475.03–475.10 m at four controls 5 m away. The pinned orthophoto shows paved frontage, and the landscape plan shows a continuous western route. This supports a bounded reconstruction study, not flattening the whole site. Source acquisition dates and exact finished levels remain unresolved. The real northern courtyard and eastern access ramps must be preserved. No terrain has changed in this diagnosis; the installed/released dev.16 artifact remains intact.


## Galileo western frontage grading checkpoint

Three conspicuous pits on the paved western frontage are now repaired within two explicitly bounded grade patches (about 294 m² including blend collars). The plane fits use surrounding pinned DGM samples; the pinned orthophoto and SLAM landscape plan support a continuous paved route. Finished levels are inferred, not newly surveyed. [Source and controls](galileo-frontage-grade.json).

Only `ground-698200-5349200.ect` changes. The other 98 render meshes, textures, northern sunken courtyard, eastern ramps and guide entries outside the patches remain unchanged. The largest height correction is 3.326 m; 252 DGM grid centres receive frontage grading. Independent validation checks every changed vertex against the allowed boundary and all 359,319 source sample centres against DGM plus the recorded grades. Collision migration advances to v21; renderer classes and shaders remain byte-identical to dev.16.

The exact dev.17 candidate passes 49 fresh native views, 40 geometry/gameplay checks, eight courtyard gravity controls, three new frontage gravity controls and both 49-stage lighting/reflection routes. The player lands at Y=65 over all three former pits. Both focused before/after views and every full route image have been reviewed. [Evidence](galileo-grade-development-validation.json); [before](../../docs/screenshots/campus-galileo-grade-before.jpg); [after](../../docs/screenshots/campus-galileo-grade-after.jpg). Earlier reflection movement/night/reload/disconnect checks remain evidence for dev.16, not fresh functional runs of this candidate.

The goal stays active. Bright vehicle/shadow colour patches remain baked into the repaired paving. The next geometry target is the eastern Galileo access: [source study](photos/galileo-east-ramp-reference.json) pins two sloping mapped driveways, a wall and official site/operator references. Raw DGM profiles drop several metres there; these are real access ramps and must not be flattened. Resolve widths, cross-sections and retaining faces before rebuilding the exterior ramps. Exact facade openings, courtyard landscaping, Siemensbau and coarse neighbouring structures also remain unfinished.

The exact dev.17 artifact is installed in the separate preview. All 121 preview-save files and four settings files are unchanged, dev.16 is retained for rollback, all 121 original-instance save files are unchanged, and the original campus world matches all 46 files in its backup.


## Galileo eastern ramps — native-verified checkpoint

Two exterior ramps now follow their mapped driveway runs and the pinned DGM centreline profiles, including the gentler southern entry transition. Explicit retaining walls, coping and shallow dark entrance recesses replace the stretched source banks. The 3.6 m width, wall dimensions and portal details are inferred from the orthophoto and cross-sections; no underground interior is reconstructed. [Source and assumptions](galileo-east-ramps.json).

The bounded cut covers approximately 349.17 m² across two ground tiles. The other 97 previous render meshes, northern courtyard, western frontage repair and surrounding guides remain unchanged. The source-grid check accounts for all 358,967 remaining sample centres and preserves adjoining tile seams. The service supports bounded collision planes for the sloped floors; all 21 service checks pass. Collision migration is v22.

Candidate `cb831505de563ead526a75acf6597dcb28b2dc084ef44a82c8451cd0ccb4779b` passes three focused native views and six actual player drops. A first-pass portal gap has been closed and rechecked visually. Ramp collision uses the displayed surface gradient to bound one-metre voxel rounding; measured offsets remain at most 0.520 m with local bounds below 0.611 m. This is approximate voxel collision, not a continuously sloped Minecraft collision shape.

The exact candidate passes 52 fresh native views, 40 geometry/gameplay checks, eight courtyard, three frontage and six ramp gravity probes, and both 52-frame lighting/reflection routes. All 52 route images and the three focused before/after views have been reviewed. [Evidence](galileo-ramps-development-validation.json); [before](../../docs/screenshots/campus-galileo-ramp-north-before.jpg); [after](../../docs/screenshots/campus-galileo-ramp-north-after.jpg). The full campus-quality goal remains active. The east-ramp views also expose distorted UYW/UYL neighbours: a new [official-photo and survey-envelope study](photos/galileo-east-neighbours-reference.json) identifies the next reconstruction targets. Exact building openings, courtyard landscaping, baked image colours, Siemensbau and other coarse visible structures remain unfinished.

The exact dev.18 artifact is installed in the separate preview. All 121 preview-save files and four settings files are unchanged, dev.17 is retained for rollback, all 121 original-instance save files are unchanged, and the original campus world matches all 46 files in its backup.

## MLZ UYW/UYL exterior checkpoint

The two workshop/laboratory buildings beside Galileo now have three reconstructed survey bodies, with per-face window groups, recessed glazing, concrete panel joints and closed exterior doors. UYW's northern face follows six/six/three/five opening groups identified in official footage. UYL's split survey bodies retain their stepped roofs and exposed upper walls; only four verified shared-wall overlaps are removed. [Source assumptions](mlz-exteriors.json); [official photo/video references](photos/galileo-east-neighbours-reference.json). No interiors are built. Some dimensions and obscured lower openings remain explicitly inferred. Six southern upper-window groups follow the photographic baseline.

The geometry check passes: all 100 prior render meshes, all 83 photographic survey roofs, unrelated facade plans and their collision files remain unchanged. The exact roofs are included in the new bodies. Collision migration advances to v23. The exact candidate passes 57 fresh native views, all 40 existing geometry/gameplay checks, 50 opening rays, 10 native wall collision checks, all 17 gravity probes and both 57-frame lighting/reflection routes. All 57 route captures and eight focused comparisons were reviewed. The known floating wall and roof fragments are absent at the tracked controls. [Evidence](mlz-development-validation.json); [central lane before](../../docs/screenshots/campus-mlz-courtyard-before.jpg); [after](../../docs/screenshots/campus-mlz-courtyard-after.jpg). The southern comparison is elevated above adjacent workshops, while lane/ramp views remain at ground level.

The broader realism goal remains active. Adjacent workshops, roof equipment, landscaping, ground-image colours and exact architectural detail remain unfinished. The high-altitude Galileo camera still falls back to older photographic geometry; that discontinuity is a concrete next renderer/service correction.

The exact dev.19 artifact is installed in the separate preview. All 121 preview save files and four settings files are unchanged; dev.18 is retained for rollback. All 121 original-instance save files and the 46 original world-backup files also remain unchanged.

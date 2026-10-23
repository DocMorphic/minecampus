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

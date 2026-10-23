## Native Minecraft pack (0.2.0)


The `minecraft/` add-on and installer are MIT. The dependency lock references RealWorldMC 1.0.3 (Apache-2.0) and Fabric API (Apache-2.0); upstream JARs carry their notices and licences. Source: https://github.com/Teddy563/realworldmc and https://github.com/FabricMC/fabric.

Minecraft Java itself and its official Steve skins, entity models, block/item textures, and sounds are provided by the user's authenticated official launcher installation. They are not copied into this repository or its modpack. Google/Cesium map imagery is streamed using the user's eligible credentials and is not included in the pack. Provider attribution must remain visible. Native setup and terrain limitations are documented in `minecraft/README.md`.

## Historical browser prototype

The notices below refer to the earlier browser game, including its original procedural imitation assets and bundled Bavarian survey.

# Third-party notices

- **Bayerische Vermessungsverwaltung – www.geodaten.bayern.de**: actual campus geometry and imagery in `public/realworld/`, official 2024 DOM-Mesh lot `124023_0`, CC BY 4.0. [License](https://creativecommons.org/licenses/by/4.0/), [source and modifications](public/realworld/NOTICE.md). These assets are not relicensed under MIT. Attribution appears in real campus mode.
- **three-mesh-bvh**: MIT, https://github.com/gkjohnson/three-mesh-bvh . Used for real mesh raycasting and blast queries. The dependency retains its package license.
- Asset preparation uses NumPy, Pillow, and pyproj under their respective package licenses; those tools are development dependencies, not browser runtime code.

- **OpenStreetMap**: the bundled `public/data/garching-osm.json` is © OpenStreetMap contributors, distributed under ODbL 1.0. https://www.openstreetmap.org/copyright and https://opendatacommons.org/licenses/odbl/1-0/ . Attribution is displayed in open map mode. Treat this dataset separately from the project's MIT-licensed code.
- **Three.js**: MIT, https://github.com/mrdoob/three.js . The dependency retains its package license.
- **3DTilesRendererJS**: Apache-2.0, https://github.com/NASA-AMMOS/3DTilesRendererJS . The dependency retains its package license.
- **Draco**: Apache-2.0, https://github.com/google/draco . Decoder runtime files in `public/draco/` are copied from Three.js's bundled glTF Draco distribution; license text is included beside them.
- **Google Maps**: optional streamed map content is owned by Google and its data providers and subject to their terms. It is not bundled in this repository. Visible-tile copyright attribution is collected dynamically.
- **Fonts**: DM Sans, Barlow Condensed, and Space Mono are requested from Google Fonts. Fonts are not bundled; local CSS fallbacks apply if unavailable.
- The block character and block textures are original procedural art. No Minecraft game textures, skin files, or proprietary game code are bundled. Minecraft and Steve are associated with Mojang/Microsoft; this project is unaffiliated.

## Native exterior update

The modified RealWorldMC 1.0.3 renderer/service is based on Apache-2.0 source commit `6f18d1f3ba5a02dadee4b14bcb96578bf3941d13`. The patch, original license and build recipe are in `minecraft/exterior/`.

Terrain DGM1, orthophotos DOP20 and CityGML LoD2 are © Bayerische Vermessungsverwaltung, [official open-data catalogue](https://geodaten.bayern.de/opengeodata/), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Derived meshes crop and reproject these datasets, triangulate surfaces and combine them with reconstructed window detail.

Vertical coordinates use the [GCG2016 grid distributed by PROJ](https://cdn.proj.org/de_bkg_gcg2016.tif), derived from © GeoBasis-DE / BKG 2023, CC BY 4.0. Bilinear grid interpolation converts DHHN2016 heights to ellipsoid heights.

The Galileo façade strip is derived from [Galileo Garching Nordende](https://commons.wikimedia.org/wiki/File:Galileo_Garching_Nordende.jpg) by MaxEmanuel (18 August 2021), released as [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). It is rectified and repeated; individual window placement is a reconstruction. The reference image and metadata are in `minecraft/exterior/photos/`.

Input URLs and SHA-256 hashes are pinned in `minecraft/exterior/sources.json`. Release assets contain open-data derivatives and code; Google tile content, provider credentials and Minecraft game assets are excluded. Game screenshots retain provider attribution.

### Walking-height development assets

- BVV DOM20 surface heights (CC BY 4.0), combined with DGM1 and DOP20 to infer canopy locations and height. Tree branching, crown subdivision and species appearance are reconstructed, not individually surveyed. Inputs and checksums: `minecraft/exterior/vegetation-sources.json`.
- Poly Haven `jacaranda_tree` leaf/bark atlases, `concrete_wall_007` and `grass_ground` colour/normal maps (CC0 1.0): https://polyhaven.com/a/jacaranda_tree, https://polyhaven.com/a/concrete_wall_007, https://polyhaven.com/a/grass_ground. Leaf atlases are applied to reconstructed branches; material maps are converted to PNG and sampled as local surface detail. The installed game makes no Poly Haven API requests. Source manifests record download URLs and checksums.
- Renardo la vulpo, “Garching, Eberhard-von-Kuenheim-Bau, 2.jpeg” (CC BY-SA 4.0): https://commons.wikimedia.org/wiki/File:Garching,_Eberhard-von-Kuenheim-Bau,_2.jpeg. Photo included in `minecraft/exterior/photos/`; a concrete façade patch is cropped and repeated. The combined MW mesh/material adaptation is provided under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/), with BVV survey attribution retained. Its repeated windows, auditorium details and shading fins are architectural approximations. This asset licence does not change the separately licensed Java/Python/JavaScript code.

### IAS exterior development

High Contrast, “TU München Garching - Institute for Advanced Study.jpg” (2013), [CC BY 3.0 DE](https://creativecommons.org/licenses/by/3.0/de/), [source](https://commons.wikimedia.org/wiki/File:TU_M%C3%BCnchen_Garching_-_Institute_for_Advanced_Study.jpg). Metal and glazing crops are resized and applied to reconstructed geometry. The image and checksum metadata are in `minecraft/exterior/photos/ias.*`. The IAS building envelope comes from BVV LoD2; its atrium, panel repetition, folded screens and entrance terrace are reference-informed approximations. [Fritsch + Tschaidse's project](https://fritsch-tschaidse.de/en/projects/tu-munich-institute-for-advanced-study.html) supplies architectural reference only; its photographs are not redistributed.


### UYA architectural reference

Ernst A. Graf/ESO, [“A view of the Garching research campus”](https://www.eso.org/public/ireland/images/170818035-cc/), published 3 November 2017, [CC BY 4.0 under ESO's usage terms](https://www.eso.org/public/outreach/copyright/). The cropped reference in `docs/screenshots/campus-uya-reference.jpg` is credited beside the image and pinned in `minecraft/exterior/photos/uya-eso-reference.json`. It informs the exterior window rhythm and materials; it is not included as a game texture. The runtime envelope/roof comes from BVV, with original approximate wall, glass and infill materials. Opposite elevations and lower bay divisions are inferred rather than individually photographed.


## Warehouse masonry material

The development exterior uses [Poly Haven Brick Wall 001](https://polyhaven.com/a/brick_wall_001), photographed by Dimitrios Savva and processed by Rob Tuytel, under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The 2K diffuse map is warmed by RGB multipliers 1.18/1.20/1.10; the matching OpenGL normal map is retained. The texture repeats at an inferred 1.5 m scale, adapted from the source's stated 3 m span. This approximates masonry appearance and is not a scanned material from the Garching warehouse. Source and converted-resource hashes are pinned in `minecraft/exterior/material-sources.json`.

The warehouse reference crop is Ernst A. Graf/ESO, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), from the [2017 campus aerial](https://www.eso.org/public/ireland/images/170818035-cc/). It is a documented reference rather than a runtime texture.


## Road and path surface detail

Explicit-width road/path centre-lines in `minecraft/exterior/path-widths.json` are © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright). The release includes derived strips as `path-surfaces.geojson`; these exclude BVV building footprints and previously mapped ground surfaces. Buffer edges are estimates from tagged widths, not surveyed curbs.

[Poly Haven Asphalt 04](https://polyhaven.com/a/asphalt_04), photographed by Sergej Majboroda and processed by Jenelle van Heerden, supplies the 2K diffuse and OpenGL normal maps under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The decoded RGB maps are converted to PNG without recolouring and repeat at the source's stated four-metre scale. This is an approximate road material, not a scan of Garching's roads. Source/resource hashes are in `minecraft/exterior/material-sources.json`.


## Telefonzentrale exterior reference

The west end of TUM building 5130 is informed by Heinz Theuerkauf's [2018 front view](https://www.flickr.com/photos/26095468@N04/44227697504/) and [oblique view](https://www.flickr.com/photos/26095468@N04/43135332700/), plus Bayreuth2009's [2014 campus sculpture photograph](https://commons.wikimedia.org/wiki/File:Garching,_Forschungszentrum_(Campus),_moderne_Kunst.jpg), CC BY 3.0. These photographs are visual references only; none of their pixels are bundled. The model uses the BVV envelope, existing CC0 concrete grain and original approximate glass/trim materials. Opening sizes, recess depth and continuation of the roof fascia are inferred. The reference metadata identifies the smaller Telefonzentrale separately from the adjacent Siemensbau.


## Center for Organoid Systems (COS)

[Alexander Pach's COS exterior photograph](https://nav.tum.de/building/cos) is supplied by NavigaTUM under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The original WebP and provenance are in `minecraft/exterior/photos/cos-reference.*`. An unobstructed timber patch is rectified, resized and repeated at an approximate scale on the BVV survey envelope. Window geometry and dark/metal materials are reconstructed; hidden elevations and exact dimensions are inferred. The game HUD retains the photographer's credit.

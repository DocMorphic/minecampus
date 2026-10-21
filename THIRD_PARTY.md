## Native Minecraft pack (0.2.0)

The Mensa study additionally uses a small derived building/courtyard footprint from OpenStreetMap relation 7726478, © OpenStreetMap contributors (ODbL 1.0). Its original block model is a rounded interpretation; architectural plans and photographs on meck architekten's project page were consulted as references, not redistributed as model textures or assets. Provenance and reconstruction limits are in `minecraft/mensa/references.json` and `minecraft/mensa/README.md`.

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

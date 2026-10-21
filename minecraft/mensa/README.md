# Mensa architectural study

A first walkable reconstruction of the **2019 Mensa at Boltzmannstraße 19**, built entirely from actual Minecraft blocks. This is an architectural preview, not a photorealistic BIM model or an interior scan.

![Mensa preview rendered in Minecraft](../../docs/screenshots/mensa-dining.png)

[Validation and exterior/interior captures](VALIDATION.md).

## Try it in the existing campus save

```sh
python3 scripts/mensa.py install
```

Save and Quit to Title, then reopen **Minecampus Garching**. New dimensions register when a world opens; `/reload` alone is insufficient. Keep commands enabled.

```mcfunction
/function minecampus_mensa:visit
```

The preview assembles on the first visit; wait for the green **Mensa ready** message. Walk from the paved approach through the pressure-plate entrance. The broad staircase leads to the upstairs dining hall and serving islands. Explore the courtyard and downstairs café. Barrels contain real food; smokers, doors and building blocks are normal interactive Minecraft objects. The preview has no map-service requests or streaming fees of its own.

```mcfunction
/function minecampus_mensa:back
```

This returns each player to their own campus coordinates and view direction, saved when they entered. Visiting again preserves edits in the Mensa preview. The preview does not change game mode or global time/weather. Do not remove the datapack while a player is in its dimension; return to campus first. The campus dimension still uses its usual map service when you return.

## What follows evidence

The approximate 76 × 74 metre exterior and the off-centre 28 × 29 metre courtyard follow OpenStreetMap relation **7726478**, rounded to the Minecraft grid. The published ground/upper-floor plans and architectural photographs inform the café/foyer downstairs, east-side stair, upstairs free-flow serving area, surrounding dining hall, exposed concrete ceiling grid, glazing, and pale timber envelope.

Sources: [meck architekten](https://meck-architekten.de/projekte/mensa-campus-garching), [TUM project description](https://www.tum.de/ueber-die-tum/ziele-und-werte/leitbild/33146), and [OpenStreetMap footprint](https://www.openstreetmap.org/relation/7726478). The photo/plan files are references only and are not redistributed as textures or assets. Footprint data © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright).

## What is approximate

Floor heights, partition dimensions, façade bay rhythm, glazing details, service spaces, menu stations, tree species/placement and furniture counts are approximations. This does not recreate all 1,500 seats or claim to match every room. Vanilla block materials deliberately keep the build interactive and destructible; they do not provide photorealistic material shading. This first version occupies a separate, axis-aligned preview dimension. It is not a seamless replacement placed over the scanned Mensa; that integration follows review of the walk-through and geometry.

## Source and build

`scripts/mensa.py` generates the deterministic, gzip-compressed Minecraft structure NBT and `dist-minecraft/Minecampus-Mensa-Preview.zip`. `references.json` records provenance and limits. The generator and original modelling use the repository's MIT licence; Minecraft textures and models come from the user's installed game. No Cesium/Google credentials enter this pack.

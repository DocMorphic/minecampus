# Survival playtest — 20 October 2026

Verified with the localhost WebGL game in the in-app browser:

- Entered Survival and settled on the surveyed campus surface.
- Crafted four planks from one log using the recipe book, collected the output, and confirmed seven logs remained from the original eight.
- Placed a crafting table on real ground; its hotbar slot became empty. Used the placed table and confirmed the 3 × 3 crafting grid opened.
- Crafted bread from three wheat. Ate the bread; hunger increased from 16 to 20, and the bread was consumed.
- Shift-clicked torches from the backpack into an empty hotbar slot.
- Switched to night and confirmed actual survey textures darkened, stars appeared, and a held torch lit nearby surfaces.
- Observed nighttime mobs, health loss from an encounter, and a creeper blast changing the surveyed ground.
- Verified death dialog, respawn, and automatic collection of dropped inventory on returning to the death location.
- Used landmark travel and Photo mode for a nighttime view of the real CIT building.

Automated validation: `npm test` passes 30 tests, including stack conservation, atomic crafting and ingredient checks, mirrored recipes, smelting and output limits, food consumption, armor and immunity, tool wear, save migration, ground/wall collision, nighttime spawning, zombie attacks, and creeper explosions. `npm run build` passes.

Night lighting and mobs are game simulations. The aerial survey is daytime imagery, with close-range facade/vegetation limitations. This release implements a substantial survival loop, not complete vanilla Minecraft feature parity.

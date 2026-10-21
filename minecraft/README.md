# Minecampus for Minecraft Java

This is the native Minecraft version: **Minecraft Java 1.21.1 + Fabric + RealWorldMC**, with a TUM Garching world preset. Minecraft supplies Steve/player skins, models, textures, inventory, crafting, furnaces, food, combat, TNT, mobs, sounds and networking. The campus add-on supplies coordinates and a few convenience functions; it does not recreate those game systems.

## Install on this Mac

Requires the official Minecraft Launcher, a Java Edition account, Python 3 and Node.js 22+. The launcher manages the game's Java runtime. Close the launcher before installing the profile, then reopen it afterward.

```sh
python3 scripts/minecraft.py install
python3 scripts/minecraft.py doctor
```

This adds **Minecampus — TUM Garching** under the launcher's **Installations** tab. It uses the separate `.minecampus/java/` game directory. Existing installations and worlds are preserved. The first profile edit is backed up beside the launcher's profile file. Enable **Modded** in the launcher's installation filters if the profile is hidden.

For another launcher: `python3 scripts/minecraft.py build` creates `dist-minecraft/Minecampus-0.2.0-mc1.21.1.mrpack`, importable into Prism or Modrinth. macOS needs Node.js 22+ installed independently; the upstream embedded runtime is for Windows. The Mac installer sets the absolute Node path so Finder's limited PATH is not a problem.

## Set up the world

1. Sign into the official launcher with the account that owns Java Edition. Under **Skins**, choose the official **Steve** skin and use it for this installation.
2. Launch **Minecampus — TUM Garching**. Complete **RealWorldMC setup**, using your own eligible map credentials. Fields are masked. Use **Test connection**, then **Save & finish**.
3. Choose **Singleplayer → Create New World**. Name it **Minecampus Garching**. Enable commands so the campus helper functions are available. Choose Creative for flying immediately, or Survival for normal hunger/combat.
4. In **World**, cycle **World Type** to **TUM Garching — Minecampus**. This explicitly fixes the origin at **48.265° N, 11.671° E**; there is no random city selection. Leave the data packs supplied by the mods enabled.
5. Create the world and allow time for the provider's terrain to stream. Do not create it before credentials pass setup. If it fails, check the provider error rather than continuing with missing terrain.

Minecraft controls: WASD, mouse look, Space to jump, double-tap Space to fly in Creative, Shift to descend, E for inventory/crafting, left click to mine/attack, right click to place/use/eat, number keys for hotbar, F5 for third person. On some Mac keyboards use Fn+F5. Place TNT, then ignite it with flint and steel.

You receive real vanilla starter items once per player. Additional commands (require commands/operator permission):

| Command | Action |
| --- | --- |
| `/function minecampus:help` | Show campus controls |
| `/function minecampus:kit` | Refill tools, food, building/crafting materials, TNT and ignition |
| `/function minecampus:creative` | Creative mode and normal Minecraft flight |
| `/function minecampus:survival` | Survival, normal difficulty, natural mobs and day/night |
| `/function minecampus:night` | Midnight, monster spawning enabled |
| `/function minecampus:day` | Clear daytime |
| `/function minecampus:animals` | Spawn pairs of actual cows, pigs, sheep and chickens beside you; use on open ground |
| `/earth setup` | Change/test provider access |
| `/earth goto 48.265, 11.671` | Travel back to the campus coordinates |
| `/earth fly` | RealWorldMC's additional flight mode |

The scanned terrain does not generate normal underground ores, caves, or structures. Starter supplies include saplings, seeds, dirt, iron, coal and water so you can craft, farm, smelt and build. The Nether and End use normal vanilla generation. The add-on's welcome kit applies to any new player in worlds made with this profile; use a different installation for unrelated vanilla saves.

## Map access

**Google direct:** create a Google Cloud project, link billing, enable **Map Tiles API**, create a key, restrict its API access to Map Tiles API, and enter it in Minecraft setup. Website/referrer restrictions do not work for this desktop service. Place-name searching additionally needs Geocoding API; the fixed campus coordinates do not.

**German/EEA billing:** new EEA projects cannot request Google's Photorealistic 3D Tiles directly; Google returns HTTP 403. See [Google's current EEA guide](https://developers.google.com/maps/comms/eea/map-tiles). Check eligibility before setting up a direct key.

**Cesium ion:** sign into [Cesium ion](https://ion.cesium.com/), open the asset depot, add **Google Photorealistic 3D Tiles** to your assets if your account is eligible, and create an access token with **assets:read** for that asset. RealWorldMC's default Google asset ID is **2275207**. Select **Cesium** in Minecraft setup, paste that token and test. Confirm the asset ID/account access if a token fails. Cesium does not guarantee access for every account; it has its own eligibility and usage terms. Optional Street View needs a separate Google Map Tiles API key.

API requests can incur charges. Budget alerts are notifications, not a hard spending cap. Keep provider attribution visible. Keys are saved only inside the local game instance's `realworldmc-service/` folder, which is ignored by Git. Never put a credential in the public repo or shared modpack.

## Multiplayer and visual limits


If the scenery looks coarse, save your world, then run `python3 scripts/minecraft.py quality` and fully quit/relaunch Minecraft. This prioritizes the local campus: a 2-pixel screen-error target, a 1.5 km map radius, a 1,200-tile budget and a 1440-pixel selection viewport. It preserves provider credentials and existing collision terrain, and backs up the old service config privately. It may use more GPU memory and download more nearby detail; monitor your free streaming allowance. This is a tuning option, not a promise of better source imagery. Stay still briefly while detail streams; pausing the world can also pause the view-selection updates.

Minecraft itself provides multiplayer. For same-network play, **Esc → Open to LAN**, then friends join through Multiplayer with the same pack and their own map access. However, upstream does **not** support public streamed-world hosting as a ready-made setup, and this campus pack's LAN flow has not yet been playtested. The browser prototype's room codes do not apply to this version. Do not advertise native campus multiplayer as verified until two actual clients have joined and shared edits have been checked.

RealWorldMC displays textured 3D scenery over approximate collision blocks. Mining/TNT edits cut the scanned surface and expose Minecraft materials. This is aerial photogrammetry: building interiors are inferred, close surfaces may stretch, and daytime photos dim at night rather than becoming measured nighttime photography. Garching coverage and street-level detail still require a live provider and in-game visual check. There is no silent fallback to the older Bavarian mesh.

## Build and dependencies

`python3 scripts/minecraft.py build` packages the resource-only Fabric add-on and an importable `.mrpack`. Downloads are pinned in `minecraft/dependencies.json` and checked by SHA-256/SHA-512 before use. The pack references upstream downloads; it does not redistribute Minecraft game code, skins, textures or sounds. Those come from the official authenticated game installation.

RealWorldMC 1.0.3: [source](https://github.com/Teddy563/realworldmc), Apache-2.0; source inspected at `6f18d1f3ba5a02dadee4b14bcb96578bf3941d13`. Fabric API uses Apache-2.0. The Minecampus add-on and setup script use the [MIT license](LICENSE). Map imagery has separate provider terms.

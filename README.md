# Minecampus

**Actual Minecraft Java at TUM Garching.**

The native version uses **Minecraft Java 1.21.1, Fabric, and [RealWorldMC](https://github.com/Teddy563/realworldmc)** to combine the real game with streamed, textured real-world terrain. Minecraft supplies its own Steve/player skins, models, blocks, inventory, crafting, combat, food, mobs, TNT and sound assets.

## Install and play

Install the official Minecraft Launcher and sign in with a Java Edition account. With Python 3 and Node.js 22+ installed, close the launcher and run:

```sh
python3 scripts/minecraft.py install
```

Reopen the launcher, select **Installations → Minecampus — TUM Garching**, and press **Play**. Choose the official **Steve** under Skins if you want Steve specifically. Complete the mod's masked map setup, then create a world with **World Type: TUM Garching — Minecampus**. Enable commands for the campus helper functions.

**Map access is required.** New Google projects with German/EEA billing cannot request Photorealistic 3D Tiles directly. The setup also supports eligible Cesium ion access to Google's 3D tiles. Read the [complete native setup and play guide](minecraft/README.md) before creating the world.

```sh
python3 scripts/minecraft.py build   # creates an importable .mrpack in dist-minecraft/
python3 scripts/minecraft.py doctor  # local readiness, without printing credentials
python3 -m unittest discover -s minecraft/tests
```

The fixed campus origin is **48.265° N, 11.671° E**. You receive real Minecraft starter supplies; `/function minecampus:help` lists mode, time, kit and animal commands. Use normal Minecraft controls and F5 for third person.

## Verification status

The pack builds, pinned mod downloads pass integrity checks, the official-launcher profile installs, and the upstream terrain/photo services start on macOS arm64 with Node 22. Garching's live Google terrain, close-up visual quality, native mining/TNT and two-client multiplayer still need in-game checks with working account/provider access. **This is not yet a verified, finished campus playthrough.**

RealWorldMC's collision terrain approximates its photo mesh. Scanned buildings have no measured interiors, vanilla ores/caves are not generated in the campus dimension, and night dims daytime imagery. Starter materials support crafting and farming; the Nether and End use vanilla generation. Upstream public streamed-world hosting is not ready-made. LAN play is a test path, not a verified feature of this pack yet.

## Earlier browser prototype

The Three.js browser game remains in this repo as an earlier, independent prototype. It uses procedural imitation characters, textures, gameplay and sounds. It is **not actual Minecraft**. Its Bavarian aerial mesh is a 2.5D survey with poor ground-level facades; it should not be presented as a photorealistic street-level campus. [Prototype documentation](BROWSER-PROTOTYPE.md).

`npm run dev` still runs that browser prototype. Use the native installation above for actual Minecraft.

## Sources and assets

[Research and architecture](RESEARCH.md) · [Third-party notices](THIRD_PARTY.md) · [Native pack source](minecraft/)

The public repository does not bundle Minecraft's proprietary game assets. The official launcher obtains those for your authenticated game installation. The Minecampus add-on is MIT; RealWorldMC and Fabric API are Apache-2.0; map content has separate provider terms.

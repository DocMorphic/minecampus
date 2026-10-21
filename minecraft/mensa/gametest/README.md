# Native Minecraft validation

Run with a **Java 21 JDK** (the development harness is incompatible with the machine's default Java 27):

```sh
python3 scripts/test-mensa.py --java-home /absolute/path/to/jdk21/Contents/Home --capture
```

This uses the Apache-2.0 RealWorldMC source at the revision pinned in the script, in ignored `.cache/realworldmc`. It copies only the Mensa test fixtures into that task-owned development checkout. It does not load the user's account, keys or campus save. Gradle obtains Minecraft development dependencies and assets from their normal sources. No Google/Cesium requests are needed.

`MensaTests.java` runs inside the real Minecraft 1.21.1 server, using Fabric's GameTest harness. It checks the native structure loader and `/place` command, block/door/pressure-plate registration, stair headroom, the courtyard opening and dining roof, usable barrel item NBT, collision clearance at representative walking points, and per-player visit/return coordinates and camera rotation.

The harness normally discards custom dimension registry entries and builds only its flat preset. `flat.json` explicitly includes the study dimension **for tests only**. This fixture is not shipped in the datapack and does not override the user's world presets.

With `--capture`, `MensaClientCheck.java` opens a separate copied test world in a hidden development client and captures four actual Minecraft frames. It uses vanilla rendering and textures, without shaders or external map services. Images and `mensa-client-result.txt` are written to `.cache/realworldmc/mod/run-mensa-check/`. Camera placement and captures are automated; this is not a human playtest or multiplayer proof.

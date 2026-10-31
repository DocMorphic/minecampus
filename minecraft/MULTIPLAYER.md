# Play Minecampus with remote friends

Want guests to join with stock Minecraft and just a server address? See the
[vanilla resource-pack research and prototype](../docs/VANILLA-CAMPUS-RESEARCH.md).
That route is under investigation; the download instructions below still use Fabric.

This preview contains the reviewed campus renderer, Minecraft Java 1.21.1,
Fabric 0.19.5, Fabric API and the Minecampus starter add-on. The campus renderer
is exactly the same build installed in Exterior Preview 0.5 (candidate 110).
The host uses e4mc 6.2.3 for an internet address. Two-player campus rendering,
shared destruction and combat still need a real remote-player check.

## Host — existing Mac installation

1. Fully quit Minecraft and relaunch **Minecampus — Exterior Preview 0.5**.
   e4mc is installed in that profile; it takes effect on restart.
2. Open your existing **Minecampus Garching** world.
3. Press **Esc → Open to LAN**. Choose the game mode for joining players.
   Leave commands disabled for guests unless you want them to have commands.
4. Select **Start LAN World**. Wait for e4mc to print a public address in chat.
5. Send that address to your friends. Keep the world and Minecraft running.
   Closing the world ends the session; use the address shown for each session.

## Friends on Windows, Mac or Linux — easiest setup

Share **[this download page](https://github.com/DocMorphic/minecampus/releases/tag/friends-0.5.0-2)** with the whole group. Everyone picks the ZIP for their computer. All packages use the exact same reviewed campus renderer and can attempt to join the same host address.

| Computer | Download | Open after extracting |
| --- | --- | --- |
| Windows 10/11, Intel/AMD 64-bit | [Windows ZIP](https://github.com/DocMorphic/minecampus/releases/download/friends-0.5.0-2/Minecampus-Friends-Windows-0.5.0-friends-2.zip) | `Play Minecampus.cmd` |
| Mac, Apple Silicon or Intel, macOS 12+ | [Mac ZIP](https://github.com/DocMorphic/minecampus/releases/download/friends-0.5.0-2/Minecampus-Friends-Mac-0.5.0-friends-2.zip) | `Play Minecampus.command` |
| Linux, ordinary Intel/AMD 64-bit PC | [Linux x64 ZIP](https://github.com/DocMorphic/minecampus/releases/download/friends-0.5.0-2/Minecampus-Friends-Linux-x64-0.5.0-friends-2.zip) | `Play Minecampus.sh` |
| Linux, ARM64 machine | [Linux ARM64 ZIP](https://github.com/DocMorphic/minecampus/releases/download/friends-0.5.0-2/Minecampus-Friends-Linux-ARM64-0.5.0-friends-2.zip) | `Play Minecampus.sh` |

1. **Extract the entire ZIP**, then open the Play file above from the extracted folder. On Linux, use **Run as a Program**; if the file manager opens it as text, open a terminal in that folder and run `bash "Play Minecampus.sh"`.
2. Sign in with the Microsoft account that owns Java Edition. If the first sign-in leaves you in Prism, double-click **Minecampus – Join a friend**.
3. Complete the in-game map setup with your own eligible Cesium/Google access, then **Multiplayer → Direct Connection → paste the host's address → Join Server**.

Prism, the matching mods and Node runtime are included. Java, Minecraft and Fabric download automatically on first launch; no pack import or manual runtime installation is needed. The Mac bundle chooses Intel or Apple Silicon automatically. Linux uses the official AppImage in extraction mode, avoiding a FUSE install; it needs a modern glibc desktop distribution and working graphics drivers. Alpine/musl and 32-bit systems are unsupported. Windows ARM is not included.

Keep the extracted folder together and start using its Play file. It contains private settings after first use. Share the original public ZIP, not your used folder. The unmodified official Prism Launcher uses a separate data directory and does not change existing Minecraft installations.

The archives, public input hashes, runtime selection, permissions and settings preservation are checked. **Full game launch on every platform and an actual remote multi-player session remain untested.** If macOS prompts about downloaded software, use its normal **Privacy & Security → Open Anyway** approval for the trusted download; do not disable Gatekeeper. If Windows blocks the bundle, use the standard Prism import route below; do not disable Windows protection.

Everyone joins the **same current e4mc address**. Test one guest first, then add people gradually: the host's CPU, memory and upload connection limit the practical group size. No capacity claim has been measured for this campus.

## Alternative — use an existing launcher

1. Download `Minecampus-0.5.0-multiplayer-preview.mrpack` from this repository's
   `exterior-0.5.0-campus110-multiplayer` prerelease. Do not use the older 0.4 pack.
2. In **Prism Launcher**, choose **Add Instance → Import** and select the file.
   Alternatively import the `.mrpack` in the Modrinth App.
3. Sign in with your own Microsoft account that owns Minecraft Java Edition.
   In Prism, **Settings → Java**, enable **Autodetect Java version** and
   **Auto-download Mojang Java** so it downloads Java 21 automatically.
4. On macOS/Linux, install Node.js 22 or newer; the renderer detects common
   installation locations automatically. If it reports that Node is missing,
   open the instance's Minecraft folder in Terminal and run
   `python3 configure-node.py`, then restart. Alternatively set `nodeExecutable`
   in `config/realworldmc.json` to the full path printed by `which node`.
   Windows uses the renderer's bundled runtime when available.
5. Launch the imported instance and complete RealWorldMC setup using your own
   eligible Cesium ion token or Google Map Tiles access. Test and save it.
   Provider access and quotas are separate from the free connection tunnel.
6. Choose **Multiplayer → Direct Connection**, paste the host's e4mc address,
   and select **Join Server**. Do not create a separate campus world.

Friends need the campus mods but do not need e4mc to join. The pack contains no
host saves, account files, private settings or map credentials. Do not distribute
your whole `.minecampus` directory.

## First connection check

Have one friend join first. Both players should see the same campus and each
other. Place and break a few ordinary blocks, try one small TNT blast away from
anything you want to keep, then reconnect and check that the changes persist.
Test combat in Survival. Report a disconnect message or missing scenery before
inviting the rest of the group; a working tunnel alone does not prove renderer
compatibility. RealWorldMC's special flight helpers have singleplayer-only paths;
ordinary Creative flight is the initial multiplayer option.

If no public address appears, confirm the host restarted the correct profile
and that `e4mc-fabric-6.2.3.jar` is in its mods folder. For a mod mismatch, everyone
must use this exact preview. For blank campus scenery, verify the guest's map
setup and local Node runtime. A tunnel cannot supply those credentials.

Sources: [e4mc](https://modrinth.com/mod/e4mc),
[Prism import guide](https://prismlauncher.org/wiki/getting-started/download-modpacks/),
[Node.js](https://nodejs.org/en/download).

Rebuild the shareable pack with `python3 scripts/build-multiplayer-pack.py`.
Rebuild a portable bundle with `python3 scripts/build-friends-launcher.py --platform Windows`
(or `Mac`, `Linux-x64`, `Linux-ARM64`).
Its public dependencies are pinned in `minecraft/friends-launcher.json`; it
preserves the existing reviewed renderer and includes no game/account files.
The host-only dependency and its published checksum are pinned in
`minecraft/remote-hosting.json`. Opening the world to the internet remains a
manual in-game action.

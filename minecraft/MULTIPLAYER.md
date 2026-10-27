# Play Minecampus with remote friends

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

## Friends — one-time installation

1. Download `Minecampus-0.5.0-multiplayer-preview.mrpack` from this repository's
   `exterior-0.5.0-campus110-multiplayer` prerelease. Do not use the older 0.4 pack.
2. In **Prism Launcher**, choose **Add Instance → Import** and select the file.
   Alternatively import the `.mrpack` in the Modrinth App.
3. Sign in with your own Microsoft account that owns Minecraft Java Edition.
   The launcher needs Java 21 for this Minecraft version.
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
The host-only dependency and its published checksum are pinned in
`minecraft/remote-hosting.json`. Opening the world to the internet remains a
manual in-game action.

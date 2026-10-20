# Co-op, combat, and audio playtest — 20 October 2026

Production build served by the Node/WebSocket server at localhost, with two independent in-app browser clients named CampusHost and CampusGuest.

Verified in the browser:

- Hosted a room, joined through its invite URL, and saw `Co-op · 2/8` plus the remote Steve avatar and player name in the actual campus scene.
- The guest placed a log. Its count decreased from eight to seven; both players' worlds changed from 75 to 76 blocks.
- Rejoined the room after a client reload. Shared edits and each player's separate inventory were restored.
- Equipped a bow and held/released F to fire. After the host accepted the shot, arrows decreased from 16 to 15 and bow durability from 192 to 191.
- Placed TNT as the guest, lit it with flint and steel, and retreated. Both clients then reported **72 blocks / 1 blast**, and actual surveyed geometry was carved. Both client consoles had no runtime errors during the explosion test.
- Flew together over CIT in Creative mode. `screenshots/multiplayer.png` records the two-player view with the remote named avatar and real campus imagery.
- Restarted the production server and joined the saved room through its LAN address on the test computer; shared edits and its blast count were restored.
- Closed the original host's tab. The remaining client automatically showed **1 player · You are hosting**, retaining the room.
- Tested the audio control. The browser reported **Audio running · 48000 Hz**. Sound waveforms and routing are covered by automated checks; this does not constitute subjective listening QA.

`npm test` passes **48 tests**. They include actual WebSocket clients for creation/joining, movement and action routing, targeted damage, snapshots and late joining, room isolation, host promotion, disk persistence, duplicate identities, and malformed inputs. Gameplay tests cover duplicate-mining prevention, container locks, furnace pause/resume, bow/melee request cooldowns, ammunition/tool wear behavior, swept arrow collision, co-op friendly fire, directional shields, skeleton shooting, spider/chicken entities, and all 33 original sound waveforms. Earlier geometry, survival, inventory, and crafting checks remain included.

`npm run build` succeeds. The production entry serves the app and `/health` successfully and supports the same live co-op connection as development.

Physical cross-device LAN access and an internet deployment were not tested. Internet play requires a reachable running Node server; GitHub/static hosting alone does not run rooms. Docker/Compose files are supplied but were not executed (Docker is unavailable on the test host). Room saves stay in ignored `.minecampus/`, and solo saves remain separate from multiplayer sessions.

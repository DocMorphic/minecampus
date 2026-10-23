# Native verification harness

`CampusExteriorCheck.java` is a development-only Fabric client initializer. It is not included in the playable pack. Run it in a separate Fabric Loom project against the exact release JAR as a mod dependency, with a matching Minecraft/Fabric version and the normal owned-game development assets. Supply provider configuration only in an ignored local run directory.

For a single viewpoint, use `minecampus.inspectOnly=true` with `minecampus.inspectStage` set to the camera index; this inspection does not replace the full gameplay check.

Use a copy of the campus save named `campus-check`; never point this harness at an original save. It changes the test scene, creates temporary block/damage fixtures, triggers native TNT, restores test damage and captures native framebuffers. Register this class as the test mod's client entrypoint. The managed embedded service must come from the release JAR, without development RealWorldMC classes on the classpath.

Assert that `campus-client-result.txt`, `campus-collision-result.txt` `campus-gameplay-result.txt` and `campus-terrace-result.txt` each begin with `PASS:`; Minecraft's exit code alone is insufficient. Capture readiness requires pending tile expansions to reach zero, all requested tiles to load and the view to remain stable. Preserve the full frame and attribution when exporting images.

See [validation](../VALIDATION.md) for the tested release hash and evidence. The harness establishes specific rendering/gameplay checks, not the overall architectural realism goal.

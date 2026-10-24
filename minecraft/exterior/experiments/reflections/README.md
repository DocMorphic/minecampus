# Isolated campus reflection experiment

This code is a QA client and resource-pack overlay, not part of the distributed mod or installer. It renders the already loaded campus mesh through a camera reflected across one nearby Galileo glass plane. It does not download another map, add interiors, or replace the Minecraft client.

Run `python3 minecraft/exterior/experiments/reflections/setup.py` from the repository root after preparing the existing `.cache/exterior-release-check` fixture and current local exterior release. The script clones that **test fixture**, including its private configuration and copied world, into `.cache/exterior-reflection-check`. It copies only the current service bundle. Existing experiment saves are reused. Do not point this fixture at a personal save. Nothing in the script reads or writes the installed preview or original player save.

Run the existing Gradle wrapper with Java 21, selecting `.cache/exterior-reflection-check` as the project and `runClient` as the task. The isolated run produces nine native screenshots, offscreen reflection targets, per-phase results and `campus-reflection-benchmark.json`. Archive existing results before another run. The check requires the packaged renderer to remain on the dependency classpath; it does not replace `MapRenderer` with a QA implementation.

The initial comparison is reflection off/on/off at the same western facade camera. Later phases visit the southwest, east and north, change to night, reload resources at night, and return west at noon. Each phase has 120 ticks of warmup and six one-second FPS samples. Results verify shader strength, the actual reflection texture unit/binding, GL errors and the recorded graphics-state restoration checks. A completed run still requires visual review and pixel comparisons; it is not an acceptance test for whole-campus realism.

## Renderer details

Pane planes come from the actual glass triangles. Only coplanar, parallel glass receives the selected reflection; other walls retain their existing analytic fallback. The camera matrix uses JOML's normalized plane reflection. The pass clips objects behind the plane, culls against its mirrored frustum, and draws the existing damage-aware mesh buffers with cutout foliage. It renders no recursive glass reflections, vanilla blocks or entities. The target is 1024 × 576. Reflected geometry receives the world's day/night lighting; the sky clear colour comes from the level. Reflected radiance is mixed after the pane's direct-light shadow, so a shadow on a window does not also shadow the reflected sky.

Minecraft 1.21.1's `ShaderInstance.setDefaultUniforms` and `GlStateManager` texture cache support only units 0–11. Merely calling `RenderSystem.setShaderTexture(12, ...)` does not supply the sampler, and using a thirteenth managed shader sampler crashes the texture cache. This experiment instead declares `PlanarTexture` as an integer uniform set to hardware unit 12, binds that unit with raw GL calls, and restores the previously active unit. It never sends unit 12 through Minecraft's cache. Hardware support is checked. Production must gracefully disable the effect on unsupported hardware.

The callback runs independently of the packaged renderer. Its ordering relative to the renderer is not a production contract; any possible previous-frame consumption must be resolved by an explicit integration point before the main material draw. The pass checks framebuffer bindings, viewport, depth state, culling, blending, polygon-offset enable and scissor state; it also restores the clear colour, active texture and program. The current assertions are not an exhaustive proof of every GL state or compatibility with other render mods.

## Remaining acceptance work

- Continuous camera motion and plane transitions, with a defined same-frame render order.
- Gameplay and TNT damage visible in reflections, including partial and complete pane removal.
- World disconnect/re-entry and explicit resource disposal.
- Wider provider coverage behind the camera, vanilla blocks/entities, and other campus facades.
- Performance improvements and comparison while moving; do not treat this short stationary benchmark as a general FPS promise.
- Reflection-edge aliasing, pane tint, self-reflection artifacts and the remaining facade surface-shadow noise.
- A packaged build, the established full native route, save-preserving installation and release verification before delivery.

Primary references: [JOML Matrix4f reflection](https://joml-ci.github.io/JOML/apidocs/org/joml/Matrix4f.html), [Khronos framebuffer objects](https://wikis.khronos.org/opengl/Framebuffer_Objects). Minecraft API limits above were checked directly in the locally mapped 1.21.1 classes.

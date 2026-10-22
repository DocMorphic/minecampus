# Campus exterior quality work — 22 October 2026

The target is recognizable real Garching architecture inside Minecraft Java, with clear building silhouettes and textured vertical façades at walking height. An aerial-only screenshot is insufficient evidence. Interior reconstruction is out of scope; the Mensa approximation has been removed.

## Source comparison

- **Google Photorealistic 3D Tiles through the existing Cesium ion asset** remains the current source. It supplies full textured triangle meshes, including vertical surfaces, rather than extruding satellite imagery. Native-client captures must establish the finest source detail actually drawn; selecting more tiles alone is not proof of improvement.
- **Bavarian DOM-Mesh**, [official data notes](https://www.geodaten.bayern.de/odd/m/3/html/datenhinweise/datenhinweise_dommesh.html): 2.5D, derived from DOM20 and nadir aerial photographs. The provider explicitly lists soft roof edges, smeared façades, hanging trees and overlap artifacts. This is not an appropriate replacement for improved street-level façades. Its CC BY 4.0 licence is useful, but does not change those geometric limits.
- **Bavarian DOP20 / LoD2**, [official catalogue](https://geodaten.bayern.de/opengeodata/): orthophotos can improve overhead appearance; LoD2 provides cleaner building envelopes and roof forms. Neither supplies measured façade textures or façade detail by itself. Combining these would be a reconstruction, not a higher-resolution photographic survey.
- **TUM2TWIN**, [UAS mesh documentation](https://tum2t.win/datasets/cm-mesh): actual textured oblique/nadir photogrammetry, but of TUM's **Downtown campus**. It cannot be substituted for Garching.

## Native-renderer findings

Inspected RealWorldMC release source `6f18d1f3ba5a02dadee4b14bcb96578bf3941d13`, the v1.0.3 release commit. The map uses original decoded texture dimensions, trilinear mipmaps and up to 16× anisotropic filtering. Collision blocks are invisible; they do not explain coarse visible buildings. Tiles are drawn as textured triangles, and coarse parent tiles are retained until all replacement children arrive. Download order currently requests two ancestor levels before requested detail, with a 128-request queue cap. This makes loading/readiness an important measurement before changing source or adding shaders.

## Verification protocol

Use an isolated copy of the user's save. Keep the user save and credentials out of tracked files. Capture the user's last ground-level camera, an oblique aerial camera and additional recognisable landmarks. Keep identical cameras, source service and lighting between comparisons. Record renderer readiness and tile counts alongside frames. No claim of photographic street-level quality is warranted if the source itself lacks the required detail.

## Final selection and measured results

The fully loaded source scene reached approximately 3.6 million triangles with no pending requests; its ground-level defects remained. The local Google leaf geometry reports approximately 2 m geometric error, with no finer child. More requests cannot manufacture missing surface detail.

The release therefore combines DGM1 terrain, DOP20 imagery, two LoD2 Galileo components reconstructed using a CC0 façade reference, and three surveyed promenade roof structures. Official GCG2016 geoid heights align these meshes with the existing world. It retains Google's photographic mesh during elevated flight and uses the reconstruction near ground, with transition hysteresis. A nearest-child-first download experiment caused missing coverage and was rejected; the original coverage-first order remains. Snapping photographic walls to survey planes was also rejected after producing holes.

See [validation](VALIDATION.md) for the actual packaged Minecraft ground/aerial captures, walking, TNT and preservation checks. No source found in this research supplies an unrestricted, measured street-level scan of every Garching façade. Remaining scan artifacts are an explicit limitation.

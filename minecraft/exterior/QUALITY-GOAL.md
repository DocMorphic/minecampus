# Walking-height quality goal — unfinished

The target is a consistently convincing central Garching exterior in actual Minecraft, assessed from walking routes and aerial views. Passing compilation, a TNT test or one attractive aerial screenshot is insufficient to declare that goal complete.

## Playable preview

The 0.4.0 preview contains 600 × 600 m of surveyed terrain/20 cm aerial imagery, 734 inferred tree/canopy instances in 36 groups, two Galileo components, three main MW components, the Graduate School and three grass-roof promenade structures. The 117 intersecting building guides protect original architecture, including buildings whose centres fall outside the reconstruction boundary. They are **not** 117 completed detailed models.

The outdoor photo layer is retired away from protected building and roof coverage. This removes the free-standing scan fragments that remained after adding new trees. The protection and retirement lookups use raster/spatial caches to keep mesh processing practical. Survey heights are transformed through the official GCG2016 geoid; different save origin heights are handled explicitly.

## Remaining work

- Substantial façade/mesh artifacts remain on buildings outside the six detailed components. The source-inspection capture shows them openly.
- Window repetition, auditorium roof simplification, Graduate School bands and vegetation appearance remain reconstructions rather than measured architectural detail.
- Some foliage fused to protected building/roof meshes remains. Outdoor props retired with the original scan are not all reconstructed.
- Leaf cards are visual foliage; their gameplay behaviour is not a complete native leaf-block simulation.
- The day imagery does not become a measured night scan. Interiors remain out of scope.

Next quality work should prioritize the remaining source façades and site-specific architectural fidelity, using consistent ground cameras and explicit before/after evidence. Do not mark the overall realism goal complete on the strength of the preview's functional tests.

[Actual game captures and functional validation](VALIDATION.md) · [Sources and rebuild](README.md)

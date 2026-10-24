// DGM-guided river surface estimate. This supplies terrain samples to upstream
// water carving; it does not prescribe a surveyed bathymetry or new fluid type.
import {supplementalSurfaces} from './supplemental-surfaces.mjs';

const samplers = new WeakMap();
export function surveyedWaterGround(features, original, x0, z0, width) {
  const local = (features ?? []).filter(feature => feature.surveyGround);
  if (!local.length) return original;
  const result = Float64Array.from(original);
  for (const feature of local) {
    const guide = feature.surveyGround;
    let sampler = samplers.get(guide);
    if (!sampler) {
      sampler = supplementalSurfaces([{rings:guide.rings, terrainGuide:guide.terrainGuide}]);
      samplers.set(guide, sampler);
    }
    const shift = guide.heightOffset ?? 0;
    if (!Number.isFinite(shift)) throw Error('Invalid surveyed river datum');
    for (let z=0; z<width; z++) for (let x=0; x<width; x++) {
      const height = sampler.at(x0+x+.5, z0+z+.5)?.floor;
      if (height == null) continue;
      // Match the upstream rasterizer's voxel-centre convention. The resulting
      // water level still uses its median and the existing bank/bed algorithm.
      result[z*width+x] = Math.floor(height+shift-.5);
    }
  }
  return result;
}

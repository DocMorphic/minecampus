"""Patch pinned upstream voxelization with measured fractional ground supports."""
def patch_voxel(source):
    def replace(old,new):
        nonlocal source
        assert source.count(old)==1, 'Upstream voxel patch mismatch: '+old[:80]
        source=source.replace(old,new)
    replace("import { sampleColor } from './tiles.mjs';", "import { sampleColor } from './tiles.mjs';\nimport { terrainColumnHeight, terrainColumnSupport, terrainSupportCode } from './terrain-column.mjs';")
    replace('  const colors = new Map();', '''  const terrainTops = new Uint8Array(plane * height);
  const fullGeometry = new Uint8Array(plane * height);
  const colors = new Map();''')
    replace('const miny = Math.min(ay, by, cy) - 0.5, maxy = Math.max(ay, by, cy) - 0.5;', '''const miny = Math.min(ay, by, cy) - (prim.campusHeightfield ? 1 : 0.5);
        const maxy = Math.max(ay, by, cy) - (prim.campusHeightfield ? 0 : 0.5);''')
    replace('              if (!single) {', '''              let terrainSupport = null;
              if (prim.campusHeightfield) {
                const surfaceY = terrainColumnHeight(tri, x, z);
                if (surfaceY === null) continue;
                terrainSupport = terrainColumnSupport(surfaceY);
                if (y !== terrainSupport.y) continue;
              } else if (!single) {''')
    replace('              vox[i] = 1;', '''              vox[i] = 1;
              if (terrainSupport) terrainTops[i] = Math.max(terrainTops[i], terrainSupport.height);
              else fullGeometry[i] = 1;''')
    replace("import { sampleColor } from './tiles.mjs';", "import { sampleColor } from './tiles.mjs';\nimport { surveyedWaterGround } from './water-survey.mjs';")
    replace('  const mask = rasterizePolygons(features, x0, z0, w);',
            '  const mask = rasterizePolygons(features, x0, z0, w);\n  g0 = surveyedWaterGround(features, g0, x0, z0, w);')
    replace('  removeIsolated(vox, colors, w, height);', '''  if (opts.surfaceOnly) {
    // Actual branch/trunk occupancy over a channel, without inventing a ground
    // column below it. Only local reconstructed vegetation uses this path.
    for (const [i, acc] of colors)
      vox[i] = classify(acc[0]/acc[3], acc[1]/acc[3], acc[2]/acc[3], 3);
    return {vox};
  }
  removeIsolated(vox, colors, w, height);''')
    # Encode last: classification, filling, water and shoreline retain their original material codes.
    replace('  return { vox, ground, surfaceColumns:', '''  for (let i = 0; i < vox.length; i++) {
    if (terrainTops[i] && !fullGeometry[i] && !water?.isWater[i % plane])
      vox[i] = terrainSupportCode(vox[i], terrainTops[i]);
  }
  return { vox, ground, surfaceColumns:''')
    return source

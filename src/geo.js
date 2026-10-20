export const ORIGIN = { lat: 48.265, lon: 11.671 };
export const BLOCK = 1;
export function project(lat, lon) {
  return [
    (lon - ORIGIN.lon) * 111320 * Math.cos((ORIGIN.lat * Math.PI) / 180),
    -(lat - ORIGIN.lat) * 111320,
  ];
}
export function unproject(x, z) {
  return {
    lat: ORIGIN.lat - z / 111320,
    lon: ORIGIN.lon + x / (111320 * Math.cos((ORIGIN.lat * Math.PI) / 180)),
  };
}
export function insidePolygon(x, z, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, zi] = points[i],
      [xj, zj] = points[j];
    if (zi > z !== zj > z && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi)
      inside = !inside;
  }
  return inside;
}
export const blockKey = (x, y, z) => `${x},${y},${z}`;
// Amanatides–Woo traversal: bounded work independent of the campus's voxel count.
export function traceVoxels(origin, direction, getBlock, maxDistance = 240) {
  const o = [origin.x, origin.y, origin.z],
    d = [direction.x, direction.y, direction.z];
  const cell = o.map((v) => Math.floor(v / BLOCK));
  const step = d.map((v) => Math.sign(v));
  const delta = d.map((v) => (v === 0 ? Infinity : Math.abs(BLOCK / v)));
  const next = d.map((v, i) =>
    v === 0 ? Infinity : ((cell[i] + (v > 0 ? 1 : 0)) * BLOCK - o[i]) / v,
  );
  let t = 0,
    normal = [0, 1, 0];
  while (t <= maxDistance) {
    const block = getBlock(...cell);
    if (block) return { block, cell: [...cell], normal, distance: t };
    let axis = next[0] < next[1] ? 0 : 1;
    if (next[2] < next[axis]) axis = 2;
    if (!Number.isFinite(next[axis])) break;
    t = next[axis];
    cell[axis] += step[axis];
    next[axis] += delta[axis];
    normal = [0, 0, 0];
    normal[axis] = -step[axis];
  }
  return null;
}

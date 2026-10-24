// Sample surveyed heightfields at the centre of each Minecraft column. Ordinary
// meshes still use triangle/box overlap, including walls, trunks and roof edges.
export function terrainColumnHeight(triangle, x, z) {
  const [ax, ay, az, bx, by, bz, cx, cy, cz] = triangle;
  const ux = bx - ax, uz = bz - az, vx = cx - ax, vz = cz - az;
  const determinant = ux * vz - uz * vx;
  if (!Number.isFinite(determinant) || Math.abs(determinant) < 1e-10) return null;
  const px = x + .5 - ax, pz = z + .5 - az;
  const b = (px * vz - pz * vx) / determinant;
  const c = (ux * pz - uz * px) / determinant;
  // Shared diagonal vertices are floats after ECT/ECEF conversion. Permit
  // numerical seam noise without extrapolating into neighbouring columns.
  if (b < -1e-7 || c < -1e-7 || b + c > 1 + 1e-7) return null;
  const height = ay + b * (by - ay) + c * (cy - ay);
  return Number.isFinite(height) ? height : null;
}

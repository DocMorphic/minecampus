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

// Round measured ground to the nearest sixteenth, representing integer tops as
// a full block below that height. This also works at negative world elevations.
export function terrainColumnSupport(surfaceY) {
  if (!Number.isFinite(surfaceY)) throw new RangeError('Invalid terrain height');
  const units = Math.round(surfaceY * 16);
  const y = Math.ceil(units / 16) - 1;
  return { y, height: units - y * 16 };
}

export function terrainSupportCode(material, height) {
  if (material < 1 || material > 9 || height === 16) return material;
  if (!Number.isInteger(height) || height < 1 || height > 16) throw new RangeError('Invalid terrain support');
  return 32 + (material - 1) * 16 + height - 1;
}

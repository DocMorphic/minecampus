import * as THREE from "three";
const closest = new THREE.Vector3();
const triangle = new THREE.Triangle();
const sphere = new THREE.Sphere();
const vertex = (position, uv, i) => ({
  p: new THREE.Vector3().fromBufferAttribute(position, i),
  uv: new THREE.Vector2().fromBufferAttribute(uv, i),
});
const midpoint = (a, b) => ({
  p: a.p.clone().add(b.p).multiplyScalar(0.5),
  uv: a.uv.clone().add(b.uv).multiplyScalar(0.5),
});
function keepOutside(a, b, c, center, radius, result, depth = 0) {
  const r2 = radius * radius,
    da = a.p.distanceToSquared(center),
    db = b.p.distanceToSquared(center),
    dc = c.p.distanceToSquared(center);
  if (da < r2 && db < r2 && dc < r2) return;
  triangle.set(a.p, b.p, c.p);
  triangle.closestPointToPoint(center, closest);
  if (closest.distanceToSquared(center) >= r2) {
    result.push(a, b, c);
    return;
  }
  const ab = a.p.distanceToSquared(b.p),
    bc = b.p.distanceToSquared(c.p),
    ca = c.p.distanceToSquared(a.p),
    longest = Math.max(ab, bc, ca);
  if (longest < 0.7 * 0.7 || depth >= 9) {
    const centroid = a.p
      .clone()
      .add(b.p)
      .add(c.p)
      .multiplyScalar(1 / 3);
    if (centroid.distanceToSquared(center) >= r2) result.push(a, b, c);
    return;
  }
  if (ab === longest) {
    const m = midpoint(a, b);
    keepOutside(a, m, c, center, radius, result, depth + 1);
    keepOutside(m, b, c, center, radius, result, depth + 1);
  } else if (bc === longest) {
    const m = midpoint(b, c);
    keepOutside(a, b, m, center, radius, result, depth + 1);
    keepOutside(a, m, c, center, radius, result, depth + 1);
  } else {
    const m = midpoint(c, a);
    keepOutside(a, b, m, center, radius, result, depth + 1);
    keepOutside(m, b, c, center, radius, result, depth + 1);
  }
}
// Changes the actual triangle topology. Raycasts and subsequent edits see the hole.
export function carveMesh(geometry, center, radius, { fragments = true } = {}) {
  if (!(radius > 0) || !geometry.index) return { removed: 0, fragments: [] };
  const position = geometry.attributes.position,
    uv = geometry.attributes.uv,
    index = geometry.index.array,
    candidates = new Set();
  sphere.set(center, radius);
  if (geometry.boundsTree) {
    geometry.boundsTree.shapecast({
      intersectsBounds: (box) => sphere.intersectsBox(box),
      intersectsTriangle: (tri, i) => {
        tri.closestPointToPoint(center, closest);
        if (closest.distanceToSquared(center) < radius * radius)
          candidates.add(i);
        return false;
      },
    });
  } else {
    for (let i = 0; i < index.length; i += 3) {
      triangle.setFromAttributeAndIndices(
        position,
        index[i],
        index[i + 1],
        index[i + 2],
      );
      triangle.closestPointToPoint(center, closest);
      if (closest.distanceToSquared(center) < radius * radius)
        candidates.add(i / 3);
    }
  }
  if (!candidates.size) return { removed: 0, fragments: [] };
  const newIndex = [],
    newPositions = Array.from(position.array),
    newUV = Array.from(uv.array),
    shards = [];
  let removed = 0;
  for (let i = 0; i < index.length; i += 3) {
    if (!candidates.has(i / 3)) {
      newIndex.push(index[i], index[i + 1], index[i + 2]);
      continue;
    }
    const a = vertex(position, uv, index[i]),
      b = vertex(position, uv, index[i + 1]),
      c = vertex(position, uv, index[i + 2]),
      kept = [];
    keepOutside(a, b, c, center, radius, kept);
    removed++;
    if (fragments && shards.length < 24) {
      const mid = a.p
        .clone()
        .add(b.p)
        .add(c.p)
        .multiplyScalar(1 / 3);
      if (
        mid.distanceTo(center) < radius &&
        Math.max(
          a.p.distanceTo(b.p),
          b.p.distanceTo(c.p),
          c.p.distanceTo(a.p),
        ) < 7
      )
        shards.push({
          center: mid,
          positions: [
            ...a.p.clone().sub(mid).toArray(),
            ...b.p.clone().sub(mid).toArray(),
            ...c.p.clone().sub(mid).toArray(),
          ],
          uv: [...a.uv.toArray(), ...b.uv.toArray(), ...c.uv.toArray()],
        });
    }
    for (const v of kept) {
      newIndex.push(newPositions.length / 3);
      newPositions.push(...v.p.toArray());
      newUV.push(...v.uv.toArray());
    }
  }
  geometry.boundsTree = null;
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(newPositions, 3),
  );
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(newUV, 2));
  geometry.setIndex(newIndex);
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return { removed, fragments: shards };
}

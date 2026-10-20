import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import * as THREE from "three";
import { MeshBVH, acceleratedRaycast } from "three-mesh-bvh";
import { carveMesh } from "../src/mesh-damage.js";
import { decodeSurveyTile } from "../src/survey-format.js";
const manifest = JSON.parse(
  readFileSync(new URL("../public/realworld/manifest.json", import.meta.url)),
);
function ground() {
  const g = new THREE.PlaneGeometry(40, 40, 20, 20);
  g.rotateX(-Math.PI / 2);
  g.boundsTree = new MeshBVH(g);
  return g;
}
function ray(g, x, z) {
  const mesh = new THREE.Mesh(
    g,
    new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }),
  );
  mesh.raycast = acceleratedRaycast;
  return new THREE.Raycaster(
    new THREE.Vector3(x, 40, z),
    new THREE.Vector3(0, -1, 0),
  ).intersectObject(mesh)[0];
}
test("a blast changes real topology and raycasts pass through the hole", () => {
  const g = ground();
  assert.ok(ray(g, 0, 0));
  const result = carveMesh(g, new THREE.Vector3(0, 0, 0), 5);
  assert.ok(result.removed > 0);
  g.boundsTree = new MeshBVH(g);
  assert.equal(ray(g, 0, 0), undefined);
  assert.ok(ray(g, 15, 0));
  assert.ok(g.attributes.uv.count === g.attributes.position.count);
  g.dispose();
});
test("carving intersects large triangles even when all vertices are outside the blast", () => {
  const g = new THREE.PlaneGeometry(40, 40, 1, 1);
  g.rotateX(-Math.PI / 2);
  g.boundsTree = new MeshBVH(g);
  carveMesh(g, new THREE.Vector3(0, 0, 0), 4);
  g.boundsTree = new MeshBVH(g);
  assert.equal(ray(g, 0, 0), undefined);
  assert.ok(ray(g, 12, 12));
  g.dispose();
});
test("damage replay is deterministic and does not alter a distant surface", () => {
  const a = ground(),
    b = ground(),
    p = new THREE.Vector3(3, 0, 2);
  carveMesh(a, p, 4);
  carveMesh(
    b,
    new THREE.Vector3(...JSON.parse(JSON.stringify(p.toArray()))),
    4,
  );
  assert.deepEqual([...a.index.array], [...b.index.array]);
  const old = [...b.index.array];
  const r = carveMesh(b, new THREE.Vector3(100, 100, 100), 2);
  assert.equal(r.removed, 0);
  assert.deepEqual([...b.index.array], old);
  a.dispose();
  b.dispose();
});
test("every bundled survey tile is valid and attributed to the actual aerial survey", () => {
  assert.equal(manifest.source.provider, "Bayerische Vermessungsverwaltung");
  assert.equal(manifest.source.license, "CC BY 4.0");
  assert.equal(manifest.source.surveyYear, 2024);
  assert.ok(manifest.tiles.length > 250);
  let triangles = 0;
  for (const meta of manifest.tiles) {
    const file = readFileSync(
      new URL("../public/realworld/" + meta.geometry, import.meta.url),
    );
    const array = file.buffer.slice(
        file.byteOffset,
        file.byteOffset + file.byteLength,
      ),
      d = decodeSurveyTile(array, meta);
    assert.ok(d.indices.length > 0);
    assert.equal(d.indices.length / 3, meta.triangles);
    assert.ok(
      existsSync(
        new URL("../public/realworld/" + meta.texture, import.meta.url),
      ),
    );
    triangles += meta.triangles;
  }
  assert.equal(triangles, manifest.totalTriangles);
  assert.ok(triangles > 3000000);
});
test("the real CIT roof has surveyed elevation and textured geometry", () => {
  let hit;
  const r = new THREE.Raycaster(
    new THREE.Vector3(-175, 100, 283),
    new THREE.Vector3(0, -1, 0),
  );
  for (const meta of manifest.tiles) {
    if (
      Math.hypot(meta.center[0] + 175, meta.center[2] - 283) >
      meta.radius + 10
    )
      continue;
    const f = readFileSync(
      new URL("../public/realworld/" + meta.geometry, import.meta.url),
    );
    const d = decodeSurveyTile(
        f.buffer.slice(f.byteOffset, f.byteOffset + f.byteLength),
        meta,
      ),
      g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(d.positions, 3));
    g.setAttribute("uv", new THREE.BufferAttribute(d.uv, 2));
    g.setIndex(new THREE.BufferAttribute(d.indices, 1));
    const m = new THREE.Mesh(
      g,
      new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }),
    );
    const found = r.intersectObject(m)[0];
    if (found && (!hit || found.distance < hit.distance)) hit = found;
  }
  assert.ok(hit, "CIT roof should be present");
  assert.ok(hit.point.y > 5 && hit.point.y < 40);
  assert.ok(hit.uv.x >= 0 && hit.uv.x <= 1);
});

test("repeated real-world blasts keep a solid pickable simulated cavity and replay", async () => {
  const { SurveyWorld } = await import("../src/survey.js");
  globalThis.document = {
    createElement: () => ({
      width: 32,
      height: 32,
      getContext: () => ({ fillRect() {}, fillText() {} }),
    }),
  };
  const a = new SurveyWorld(new THREE.Scene(), { tiles: [] });
  const p = new THREE.Vector3(10, 20, 30);
  for (let i = 0; i < 3; i++) a.explode(p, 16);
  assert.equal(a.craters.length, 1);
  assert.ok(
    a.raycast(
      new THREE.Raycaster(
        new THREE.Vector3(10, 70, 30),
        new THREE.Vector3(0, -1, 0),
      ),
    ),
  );
  const saved = JSON.parse(JSON.stringify(a.serialize())),
    b = new SurveyWorld(new THREE.Scene(), { tiles: [] }, saved);
  assert.equal(b.craters.length, 1);
  assert.equal(b.edits.length, 3);
  assert.ok(
    b.raycast(
      new THREE.Raycaster(
        new THREE.Vector3(10, 70, 30),
        new THREE.Vector3(0, -1, 0),
      ),
    ),
  );
  a.dispose();
  b.dispose();
});

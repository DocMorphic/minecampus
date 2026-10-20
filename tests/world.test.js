import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  project,
  unproject,
  insidePolygon,
  traceVoxels,
  blockKey,
} from "../src/geo.js";
test("Garching coordinates round-trip with east/up/south axes", () => {
  const [x, z] = project(48.26243, 11.66823);
  assert.ok(x < 0 && z > 0);
  const g = unproject(x, z);
  assert.ok(Math.abs(g.lat - 48.26243) < 1e-10);
  assert.ok(Math.abs(g.lon - 11.66823) < 1e-10);
});
test("concave courtyard footprints do not fill the courtyard", () => {
  const p = [
    [0, 0],
    [9, 0],
    [9, 9],
    [6, 9],
    [6, 3],
    [3, 3],
    [3, 9],
    [0, 9],
  ];
  assert.ok(insidePolygon(1, 5, p));
  assert.equal(insidePolygon(4, 5, p), false);
  assert.ok(insidePolygon(4, 1, p));
});
test("voxel picking returns the nearest surface and correct placement normal", () => {
  const blocks = new Map([
    ["0,0,0", { name: "near" }],
    ["0,0,-3", { name: "far" }],
  ]);
  const hit = traceVoxels(
    { x: 1.5, y: 1.5, z: 20 },
    { x: 0, y: 0, z: -1 },
    (x, y, z) => blocks.get(blockKey(x, y, z)),
  );
  assert.equal(hit.block.name, "near");
  assert.deepEqual(hit.normal, [0, 0, 1]);
  assert.deepEqual(hit.cell, [0, 0, 0]);
  assert.equal(hit.distance, 17);
});
test("negative coordinates, vertical rays and max reach are handled", () => {
  const get = (x, y, z) =>
    x === -1 && y === 0 && z === -1 ? { solid: true } : null;
  const hit = traceVoxels({ x: -1, y: 30, z: -1 }, { x: 0, y: -1, z: 0 }, get);
  assert.deepEqual(hit.cell, [-1, 0, -1]);
  assert.deepEqual(hit.normal, [0, 1, 0]);
  assert.equal(
    traceVoxels({ x: -1, y: 30, z: -1 }, { x: 0, y: -1, z: 0 }, get, 10),
    null,
  );
  assert.equal(
    traceVoxels({ x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: 0 }, () => null),
    null,
  );
});
test("bundled campus includes real CIT and StudiTUM footprints", () => {
  const data = JSON.parse(
    readFileSync(new URL("../public/data/garching-osm.json", import.meta.url)),
  );
  assert.equal(data.license, "ODbL-1.0");
  assert.ok(
    data.elements.some((f) =>
      f.tags.name?.includes("Informatik und Mathematik"),
    ),
  );
  assert.ok(data.elements.some((f) => f.tags.name === "StudiTUM"));
  assert.ok(data.elements.filter((f) => f.tags.building).length >= 200);
});

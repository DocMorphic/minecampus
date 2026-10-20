import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as THREE from "three";
import { campusLandmarks, nearestLandmark } from "../src/landmarks.js";
import { createCharge, stepCharge, AirTNT } from "../src/air-tnt.js";
const features = JSON.parse(
  readFileSync(new URL("../public/data/garching-osm.json", import.meta.url)),
).elements;
test("five landmark viewpoints come from real campus features and stay in the playable area", () => {
  const places = campusLandmarks(features);
  assert.equal(places.length, 5);
  assert.equal(new Set(places.map((p) => p.id)).size, 5);
  for (const p of places) {
    assert.ok(features.some((f) => f.id === p.way));
    assert.ok(Math.abs(p.spawn[0]) < 700 && Math.abs(p.spawn[2]) < 750);
    assert.ok(p.spawn[1] >= 42 && p.spawn[1] <= 105);
    assert.ok(p.pitch < 0 && p.pitch > -1.4);
    assert.ok(Math.abs(p.lat - 48.265) < 0.01);
  }
  const cit = places.find((p) => p.id === "cit");
  assert.ok(cit.x < 0 && cit.z > 0);
  assert.equal(nearestLandmark(places, cit.x, cit.z).place.id, "cit");
  assert.equal(nearestLandmark([], 0, 0), null);
});
test("fast falling TNT sweeps its path and rests above a surface before detonating", () => {
  const c = createCharge(
    new THREE.Vector3(0, 2, 0),
    new THREE.Vector3(0, -100, 0),
  );
  const terrain = (o, d, length) => {
    const distance = -o.y / d.y;
    return distance >= 0 && distance <= length
      ? {
          distance,
          point: o.clone().addScaledVector(d, distance),
          normal: new THREE.Vector3(0, 1, 0),
        }
      : null;
  };
  assert.equal(stepCharge(c, 0.05, terrain), "landed");
  assert.equal(c.position.y, 1.3);
  assert.equal(c.settled, true);
  assert.ok(c.fuse > 0.8);
  let state;
  for (let i = 0; i < 20; i++) {
    state = stepCharge(c, 0.05, terrain);
    if (state === "detonate") break;
  }
  assert.equal(state, "detonate");
});
test("airborne TNT follows gravity and has a bounded lifetime even without terrain", () => {
  const p = new THREE.Vector3(0, 400, 0),
    v = new THREE.Vector3(10, 0, 0),
    c = createCharge(p, v);
  stepCharge(c, 0.05, () => null);
  assert.ok(c.position.x > 0 && c.position.y < 400);
  assert.equal(p.y, 400);
  assert.equal(v.y, 0);
  let state;
  for (let i = 0; i < 170; i++) {
    state = stepCharge(c, 0.05, () => null);
    if (state === "detonate") break;
  }
  assert.equal(state, "detonate");
});
test("air charges enforce cooldown, chain-prime nearby charges, and clean up their meshes", () => {
  const scene = new THREE.Scene(),
    detonations = [];
  const air = new AirTNT(
    scene,
    new THREE.MeshLambertMaterial(),
    () => null,
    (p) => detonations.push(p.clone()),
  );
  assert.ok(air.drop(new THREE.Vector3(0, 50, 0), new THREE.Vector3()));
  assert.equal(
    air.drop(new THREE.Vector3(0, 50, 0), new THREE.Vector3()),
    false,
  );
  air.update(0.5);
  assert.ok(air.drop(new THREE.Vector3(3, 50, 0), new THREE.Vector3()));
  air.primeNearby(new THREE.Vector3(0, 50, 0), 16);
  for (let i = 0; i < 10; i++) air.update(0.05);
  assert.equal(detonations.length, 2);
  assert.equal(air.charges.length, 0);
  assert.equal(scene.children.length, 0);
  air.dispose();
});

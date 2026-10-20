import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { Campus } from "../src/campus.js";
// Canvas drawing is irrelevant to state tests; Three.js instance matrices run normally.
globalThis.document = {
  createElement: () => ({
    width: 32,
    height: 32,
    getContext: () => ({ fillRect() {}, fillText() {} }),
  }),
};
test("swap-removing instances preserves remaining blocks and placement transforms", () => {
  const c = new Campus(new THREE.Scene(), { elements: [] });
  const a = c.place(0, 0, 0, "stone"),
    b = c.place(1, 0, 0, "stone"),
    d = c.place(2, 0, 0, "stone");
  c.remove(b);
  assert.equal(c.batches.stone.mesh.count, 2);
  assert.equal(c.get(1, 0, 0), undefined);
  assert.equal(d.index, 1);
  const matrix = new THREE.Matrix4();
  c.batches.stone.mesh.getMatrixAt(1, matrix);
  const p = new THREE.Vector3().setFromMatrixPosition(matrix);
  assert.deepEqual(p.toArray(), [7.5, 1.5, 1.5]);
  assert.equal(c.get(0, 0, 0), a);
  c.dispose();
});
test("blast radius removes nearby blocks and leaves distant edits; state round-trips", () => {
  const scene = new THREE.Scene(),
    c = new Campus(scene, { elements: [] });
  c.place(0, 0, 0, "tnt");
  c.place(1, 0, 0, "brick");
  c.place(20, 0, 0, "wood");
  const removed = c.explode(new THREE.Vector3(1.5, 1.5, 1.5), 10);
  assert.equal(removed.length, 2);
  assert.equal(c.blocks.size, 1);
  const snapshot = JSON.parse(JSON.stringify(c.serialize())),
    copy = new Campus(scene, { elements: [] }, snapshot);
  assert.equal(copy.get(20, 0, 0).type, "wood");
  assert.equal(copy.blocks.size, 1);
  assert.equal(copy.place(20, 0, 0, "grass"), false);
  c.dispose();
  copy.dispose();
});

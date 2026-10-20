import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { Survival, migrateWorldSave } from "../src/survival.js";
import {
  makeStack,
  addStack,
  clickSlot,
  takeItems,
  canHarvest,
} from "../src/items.js";
import {
  RECIPES,
  fillRecipe,
  craftOutput,
  matchRecipe,
  tickFurnace,
} from "../src/crafting.js";
import { stepWalker } from "../src/physics.js";
import { Life } from "../src/life.js";
const grid = () => Array(9).fill(null),
  empty = () => Array(36).fill(null);
const flat = (o, d, n) => {
  if (d.y >= 0) return null;
  const t = -o.y / d.y;
  return t >= 0 && t <= n
    ? {
        distance: t,
        point: o.clone().addScaledVector(d, t),
        normal: new THREE.Vector3(0, 1, 0),
      }
    : null;
};
test("inventory splitting and merging conserves item count and respects limits", () => {
  const slots = [makeStack("wood", 63), null];
  let cursor = makeStack("wood", 4);
  cursor = clickSlot(slots, 0, cursor);
  assert.equal(slots[0].count, 64);
  assert.equal(cursor.count, 3);
  cursor = clickSlot(slots, 1, cursor, 2);
  assert.equal(slots[1].count, 1);
  assert.equal(cursor.count, 2);
  cursor = clickSlot(slots, 1, cursor);
  assert.equal(cursor, null);
  cursor = clickSlot(slots, 0, null, 2);
  assert.equal(cursor.count, 32);
  assert.equal(slots[0].count, 32);
  assert.equal(addStack(slots, { id: "wood", count: 100 }), 7);
  assert.equal(
    slots.reduce((n, s) => n + s.count, 0),
    128,
  );
});
test("ingredient consumption is atomic when material is missing", () => {
  const slots = [makeStack("wood", 4)];
  const before = structuredClone(slots);
  assert.equal(takeItems(slots, { wood: 3, stone: 1 }), false);
  assert.deepEqual(slots, before);
});
test("recipe autofill and collecting output consumes exactly one log for four planks", () => {
  const slots = empty(),
    g = grid();
  slots[0] = makeStack("wood", 3);
  assert.ok(
    fillRecipe(
      slots,
      g,
      2,
      RECIPES.find((r) => r.id === "planks"),
    ),
  );
  assert.equal(slots[0].count, 2);
  const result = craftOutput(g, 2, null);
  assert.ok(result.ok);
  assert.equal(result.cursor.count, 4);
  assert.equal(result.cursor.id, "planks");
  assert.equal(g[0], null);
  assert.equal(craftOutput(g, 2, null).ok, false);
});
test("full output and missing ingredients never consume crafting inputs", () => {
  const g = grid();
  g[0] = makeStack("wood");
  assert.equal(craftOutput(g, 2, makeStack("planks", 64)).ok, false);
  assert.equal(g[0].count, 1);
  const slots = empty(),
    before = structuredClone(g);
  assert.equal(
    fillRecipe(
      slots,
      g,
      2,
      RECIPES.find((r) => r.id === "torch"),
    ),
    false,
  );
  assert.deepEqual(g, before);
});
test("3 by 3 recipes reject a small grid and mirrored axes are recognized", () => {
  const r = RECIPES.find((r) => r.id === "stone_axe"),
    g = grid(),
    slots = empty();
  slots[0] = makeStack("stone", 3);
  slots[1] = makeStack("stick", 2);
  assert.equal(fillRecipe(slots, g, 2, r), false);
  assert.ok(fillRecipe(slots, g, 3, r));
  const mirrored = grid();
  for (let y = 0; y < 3; y++)
    for (let x = 0; x < 3; x++) mirrored[y * 3 + x] = g[y * 3 + 2 - x];
  assert.equal(matchRecipe(mirrored, 3).id, "stone_axe");
});
test("furnaces consume fuel and input, preserve blocked output, and cook meat", () => {
  const f = {
    slots: [makeStack("raw_beef", 2), makeStack("coal"), null],
    burn: 0,
    cook: 0,
  };
  for (let i = 0; i < 161; i++) tickFurnace(f, 0.05);
  assert.equal(f.slots[0].count, 1);
  assert.equal(f.slots[1], null);
  assert.equal(f.slots[2].id, "cooked_beef");
  f.slots[2] = makeStack("cooked_beef", 64);
  for (let i = 0; i < 200; i++) tickFurnace(f, 0.05);
  assert.equal(f.slots[0].count, 1);
  assert.equal(f.slots[2].count, 64);
});
test("eating completes over time and restores hunger while consuming one food", () => {
  const s = new Survival();
  s.selected = 3;
  s.hunger = 10;
  assert.ok(s.beginEating());
  s.tick(0.6);
  assert.equal(s.hunger, 10);
  s.tick(0.61);
  assert.equal(s.hunger, 14);
  assert.equal(s.held.count, 4);
  assert.equal(s.eating, null);
  s.hunger = 20;
  assert.equal(s.beginEating(), false);
});
test("changing selected food cancels eating without consuming it", () => {
  const s = new Survival();
  s.selected = 3;
  s.hunger = 10;
  s.beginEating();
  s.selected = 0;
  s.tick(2);
  assert.equal(s.inventory[3].count, 5);
  assert.equal(s.hunger, 10);
});
test("armor mitigates damage, immunity prevents repeated hits, distant blasts cause no damage", () => {
  const s = new Survival();
  assert.equal(s.damage(0), 0);
  assert.equal(s.health, 20);
  s.armor.chestplate = makeStack("iron_chestplate");
  assert.equal(s.damage(10), 7.6);
  assert.equal(s.health, 12.4);
  assert.equal(s.damage(10), 0);
  s.tick(1);
  assert.equal(s.damage(10), 7.6);
  s.mode = "creative";
  s.tick(1);
  assert.equal(s.damage(100), 0);
});
test("tool durability, harvest tiers and player data persist", () => {
  const s = new Survival();
  s.selected = 1;
  s.wear();
  const restored = new Survival(s.serialize());
  assert.equal(restored.held.durability, 58);
  assert.equal(canHarvest("iron_ore", makeStack("wooden_pickaxe")), false);
  assert.equal(canHarvest("iron_ore", makeStack("stone_pickaxe")), true);
  restored.held.durability = 1;
  restored.wear();
  assert.equal(restored.held, null);
});
test("old 3m block saves migrate without moving mesh damage", () => {
  const old = {
    placed: [{ x: -2, y: 1, z: 3, type: "tnt" }],
    removed: ["0,0,0"],
    blasts: [{ position: [1, 2, 3], radius: 16 }],
  };
  const next = migrateWorldSave(old);
  assert.deepEqual(next.placed[0], { x: -5, y: 4, z: 10, type: "tnt" });
  assert.equal(next.removed.length, 27);
  assert.deepEqual(next.blasts, old.blasts);
  assert.deepEqual(migrateWorldSave(next), next);
});
test("walking lands on real raycast ground, jumps, and stops at walls", () => {
  const b = {
    position: new THREE.Vector3(0, 5, 0),
    velocity: new THREE.Vector3(),
    fallFrom: 5,
    grounded: false,
  };
  let landed = 0;
  for (let i = 0; i < 100; i++)
    landed = Math.max(
      landed,
      stepWalker(b, 0.02, { move: new THREE.Vector3() }, flat).landed,
    );
  assert.ok(landed > 4.9);
  assert.ok(Math.abs(b.position.y - 0.015) < 0.001);
  stepWalker(b, 0.02, { move: new THREE.Vector3(), jump: true }, flat);
  assert.ok(b.position.y > 0.1);
  const wall = (o, d, n) => {
    if (d.x > 0 && o.x <= 1) {
      const t = (1 - o.x) / d.x;
      if (t <= n)
        return {
          distance: t,
          point: o.clone().addScaledVector(d, t),
          normal: new THREE.Vector3(-1, 0, 0),
        };
    }
    return flat(o, d, n);
  };
  for (let i = 0; i < 150; i++)
    stepWalker(b, 0.02, { move: new THREE.Vector3(1, 0, 0) }, wall);
  assert.ok(b.position.x <= 0.7);
});
test("hostile mobs spawn at night, zombies attack, and creepers detonate", () => {
  let night = false,
    damage = 0,
    blasts = 0;
  const s = new Survival(),
    scene = new THREE.Scene(),
    campus = { placed: new Map(), place: () => null },
    life = new Life(scene, s, {
      trace: flat,
      player: () => new THREE.Vector3(),
      night: () => night,
      damage: (n) => (damage += n),
      explosion: () => blasts++,
      pickup: () => {},
    });
  life.update(2, campus);
  assert.equal(
    life.mobs.some((m) =>
      ["creeper", "zombie", "skeleton", "spider"].includes(m.kind),
    ),
    false,
  );
  night = true;
  life.update(0.1, campus);
  assert.ok(
    life.mobs.some((m) =>
      ["creeper", "zombie", "skeleton", "spider"].includes(m.kind),
    ),
  );
  const zombie = life.spawn("zombie", new THREE.Vector3(1, 0, 0));
  life.update(0.1, campus);
  assert.ok(damage >= 3);
  life.remove(zombie);
  const creeper = life.spawn("creeper", new THREE.Vector3(1, 0, 0));
  for (let i = 0; i < 18; i++) life.update(0.1, campus);
  assert.ok(blasts > 0);
  assert.equal(life.mobs.includes(creeper), false);
});

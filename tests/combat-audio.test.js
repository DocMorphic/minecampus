import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { SOUND_NAMES, synthSound } from "../src/game-audio.js";
import { Projectiles, bowShot, shieldDamage } from "../src/projectiles.js";
import { Life, HOSTILE } from "../src/life.js";
import { Survival } from "../src/survival.js";
import { makeStack } from "../src/items.js";
import { createRoomAuthority } from "../src/room-actions.js";
const v = (...n) => new THREE.Vector3(...n),
  flat = (o, d, len) => {
    if (d.y >= 0) return null;
    const distance = -o.y / d.y;
    return distance >= 0 && distance <= len
      ? {
          distance,
          point: o.clone().addScaledVector(d, distance),
          normal: v(0, 1, 0),
        }
      : null;
  };
function authority() {
  const blocks = new Map(),
    state = new Survival(),
    drops = [],
    sounds = [],
    ctx = {
      survival: state,
      campus: {
        blocks,
        placed: blocks,
        place(x, y, z, type) {
          const key = `${x},${y},${z}`;
          if (blocks.has(key)) return null;
          const b = { x, y, z, type, key };
          blocks.set(key, b);
          return b;
        },
        remove(b) {
          blocks.delete(b.key);
        },
      },
      real: { edits: [], explode() {} },
      life: {
        mobs: [],
        drop: (s, p) => drops.push({ s, p }),
        hit(m, n) {
          m.health -= n;
        },
      },
      projectiles: { fire() {} },
      stationLocks: new Map(),
      fuses: new Map(),
    };
  let now = 1000;
  const action = createRoomAuthority({
    context: () => ctx,
    localId: () => "host",
    localPosition: () => v(0, 0, 0),
    gamePlayers: () => [],
    emitSound: (...a) => sounds.push(a),
    terrainSegment: () => null,
    now: () => now,
  });
  const actor = { id: "guest", position: [0, 0, 0], held: "wooden_pickaxe" };
  return { ctx, action, actor, drops, sounds, advance: () => (now += 1000) };
}
test("all original sounds produce bounded, non-silent waveforms and TNT has a bass tail", () => {
  for (const name of SOUND_NAMES) {
    const wave = synthSound(name, 22050, 42);
    let energy = 0;
    for (const sample of wave) {
      assert.ok(Number.isFinite(sample));
      assert.ok(Math.abs(sample) <= 1);
      energy += sample * sample;
    }
    assert.ok(energy > 0.01, `${name} must not be silent`);
  }
  const blast = synthSound("explosion", 22050);
  assert.ok(blast.length > 22050);
  assert.deepEqual(synthSound("hit", 22050, 4), synthSound("hit", 22050, 4));
  assert.notDeepEqual(synthSound("hit", 22050, 4), synthSound("hit", 22050, 5));
});
test("charged bows scale projectile speed and damage", () => {
  assert.ok(bowShot(1).speed > bowShot(0.2).speed);
  assert.equal(bowShot(2).damage, bowShot(1).damage);
  assert.equal(bowShot(-1).speed, bowShot(0).speed);
});
test("shield blocks frontal hits, wears down and leaves rear attacks exposed", () => {
  const s = new Survival();
  s.armor.offhand = makeStack("shield");
  s.blocking = true;
  assert.equal(shieldDamage(s, 10, v(0, 0, -2), v(0, 0, 0), 0), 1.5);
  assert.equal(s.armor.offhand.durability, 239);
  assert.equal(shieldDamage(s, 10, v(0, 0, 2), v(0, 0, 0), 0), 10);
  s.armor.offhand.durability = 1;
  shieldDamage(s, 4, v(0, 0, -2), v(0, 0, 0), 0);
  assert.equal(s.armor.offhand, null);
});
test("arrows use swept terrain collisions and cannot hit a mob behind a wall", () => {
  const scene = new THREE.Scene(),
    mob = { id: "z", kind: "zombie", position: v(0, 0, -4) },
    hits = [];
  const p = new Projectiles(scene, {
    trace: (o, d, len) => {
      const t = (-2 - o.z) / d.z;
      return t >= 0 && t <= len
        ? { distance: t, point: o.clone().addScaledVector(d, t) }
        : null;
    },
    mobs: () => [mob],
    players: () => [],
    hitMob: (m) => hits.push(m),
    hitPlayer: () => {},
    sound: () => {},
  });
  p.fire(v(0, 1, 0), v(0, 0, -100), "player", 8);
  p.update(0.1);
  assert.equal(hits.length, 0);
  assert.equal(p.arrows.length, 0);
});
test("skeleton arrows damage players and player arrows preserve co-op friendly fire", () => {
  let damage = 0;
  const player = {
      id: "guest",
      position: v(0, 0, -2),
      health: 20,
      active: true,
    },
    p = new Projectiles(new THREE.Scene(), {
      trace: () => null,
      mobs: () => [],
      players: () => [player],
      hitMob: () => {},
      hitPlayer: (_, n) => (damage += n),
      sound: () => {},
    });
  p.fire(v(0, 1, 0), v(0, 0, -40), "host", 8);
  p.update(0.1);
  assert.equal(damage, 0);
  p.fire(v(0, 1, 0), v(0, 0, -40), "mob-skeleton", 4);
  p.update(0.1);
  assert.equal(damage, 4);
});
test("skeleton ranged attacks, spiders and chickens are real entities and snapshots retain IDs", () => {
  let shots = 0;
  const s = new Survival(),
    life = new Life(new THREE.Scene(), s, {
      trace: flat,
      player: () => v(0, 0, 0),
      night: () => true,
      damage: () => {},
      explosion: () => {},
      pickup: () => {},
      shoot: () => shots++,
    });
  life.spawn("skeleton", v(0, 0, -10));
  life.spawn("spider", v(3, 0, 0));
  life.spawn("chicken", v(3, 0, 4));
  life.update(0.1, { placed: new Map(), place: () => null });
  assert.ok(shots >= 1);
  assert.ok(HOSTILE.includes("spider"));
  const replica = new Life(new THREE.Scene(), new Survival(), {
    trace: flat,
    player: () => v(0, 0, 0),
    night: () => true,
    damage: () => {},
    explosion: () => {},
    pickup: () => {},
  });
  replica.applySnapshot(life.serialize());
  assert.deepEqual(
    replica.mobs.map((m) => m.id),
    life.mobs.map((m) => m.id),
  );
  replica.clear();
  assert.equal(replica.mobs.length, 0);
});
test("room authority rejects occupied and distant placement, and duplicate mining yields once", async () => {
  const a = authority();
  await a.action({ kind: "place", cell: [2, 0, 0], type: "wood" }, a.actor);
  await assert.rejects(
    a.action({ kind: "place", cell: [2, 0, 0], type: "wood" }, a.actor),
    /occupied/,
  );
  await assert.rejects(
    a.action({ kind: "place", cell: [200, 0, 0], type: "wood" }, a.actor),
    /closer/,
  );
  await a.action({ kind: "mine", key: "2,0,0" }, a.actor);
  await assert.rejects(
    a.action({ kind: "mine", key: "2,0,0" }, a.actor),
    /gone/,
  );
  assert.equal(a.drops.length, 1);
});
test("shared chest locks prevent simultaneous edits and breaking a station in use", async () => {
  const a = authority();
  a.ctx.campus.place(2, 0, 0, "chest");
  await a.action(
    { kind: "station_open", key: "2,0,0", type: "chest" },
    a.actor,
  );
  await assert.rejects(
    a.action(
      { kind: "station_open", key: "2,0,0", type: "chest" },
      { ...a.actor, id: "other" },
    ),
    /Another player/,
  );
  await assert.rejects(
    a.action({ kind: "mine", key: "2,0,0" }, a.actor),
    /using/,
  );
  const contents = Array(27).fill(null);
  contents[0] = makeStack("wood", 4);
  await a.action(
    { kind: "station_write", key: "2,0,0", type: "chest", value: contents },
    a.actor,
  );
  assert.equal(a.ctx.survival.chests["2,0,0"][0].count, 4);
  await a.action(
    { kind: "station_close", key: "2,0,0", type: "chest" },
    a.actor,
  );
  const next = await a.action(
    { kind: "station_open", key: "2,0,0", type: "chest" },
    { ...a.actor, id: "other" },
  );
  assert.equal(next.value[0].count, 4);
});
test("furnaces pause during container editing and resume on lock release", async () => {
  const a = authority();
  a.ctx.campus.place(2, 0, 0, "furnace");
  await a.action(
    { kind: "station_open", key: "2,0,0", type: "furnace" },
    a.actor,
  );
  const f = a.ctx.survival.furnaces["2,0,0"];
  f.slots = [makeStack("iron_ore"), makeStack("coal"), null];
  a.ctx.survival.tick(5);
  assert.equal(f.slots[1].count, 1);
  await a.action(
    { kind: "station_close", key: "2,0,0", type: "furnace" },
    a.actor,
  );
  for (let i = 0; i < 170; i++) a.ctx.survival.tick(0.05);
  assert.equal(f.slots[2].id, "iron");
});
test("the host routes bow shots and melee hits with cooldowns without timing errors", async () => {
  const a = authority();
  let shots = 0;
  a.ctx.projectiles.fire = () => shots++;
  await a.action(
    { kind: "shoot", direction: [0, 0, -1], charge: 1 },
    { ...a.actor, held: "bow" },
  );
  assert.equal(shots, 1);
  await assert.rejects(
    a.action(
      { kind: "shoot", direction: [0, 0, -1], charge: 1 },
      { ...a.actor, held: "bow" },
    ),
    /Draw the bow/,
  );
  a.ctx.life.mobs = [{ id: "mob", health: 20, position: v(2, 0, 0) }];
  a.advance();
  await a.action(
    { kind: "attack", id: "mob" },
    { ...a.actor, held: "iron_sword" },
  );
  assert.equal(a.ctx.life.mobs[0].health, 14);
  await assert.rejects(
    a.action({ kind: "attack", id: "mob" }, { ...a.actor, held: "iron_sword" }),
    /Wait/,
  );
});
test("an acknowledged action wears the tool that was used, even after switching slots", () => {
  const s = new Survival(),
    bow = s.inventory.find((x) => x?.id === "bow");
  s.selected = 1;
  s.wearStack(bow);
  assert.equal(bow.durability, 191);
  assert.equal(s.held.durability, 59);
});

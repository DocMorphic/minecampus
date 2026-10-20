import * as THREE from "three";
import { ITEMS, makeStack, canHarvest } from "./items.js";
import { bowShot } from "./projectiles.js";
import { materialSound } from "./game-audio.js";
export function createRoomAuthority({
  context,
  localId,
  localPosition,
  gamePlayers,
  emitSound,
  terrainSegment,
  now: clock = () => performance.now(),
}) {
  return async function hostAction(action, actor) {
    const { survival, campus, real, life, projectiles, stationLocks, fuses } =
      context();
    const position =
      actor.id === localId()
        ? localPosition()
        : new THREE.Vector3(...actor.position);
    const creative = survival.mode === "creative";
    const reach = creative ? 270 : 6.5;
    const nearby = (point) => {
      if (
        !Array.isArray(point) ||
        point.length !== 3 ||
        !point.every(Number.isFinite) ||
        new THREE.Vector3(...point).distanceTo(position) > reach
      )
        throw Error("Move closer to that target.");
      return new THREE.Vector3(...point);
    };
    const block = () => {
      const b = campus.blocks.get(action.key);
      if (!b) throw Error("That block is gone.");
      nearby([b.x + 0.5, b.y + 0.5, b.z + 0.5]);
      return b;
    };
    const tool = actor.held ? makeStack(actor.held) : null;
    if (action.kind === "place") {
      if (
        !Array.isArray(action.cell) ||
        action.cell.length !== 3 ||
        !action.cell.every(Number.isInteger) ||
        !ITEMS[action.type]?.block
      )
        throw Error("Invalid block.");
      nearby(action.cell);
      if (campus.placed.size >= 12000)
        throw Error("This room has reached its block limit.");
      if (
        gamePlayers().some(
          (p) =>
            p.active &&
            Math.abs(action.cell[0] + 0.5 - p.position.x) < 0.8 &&
            Math.abs(action.cell[2] + 0.5 - p.position.z) < 0.8 &&
            action.cell[1] < p.position.y + 1.8 &&
            action.cell[1] + 1 > p.position.y,
        )
      )
        throw Error("A player is standing there.");
      const b = campus.place(...action.cell, action.type);
      if (!b) throw Error("That space is occupied.");
      if (action.type === "wheat_crop") survival.crops[b.key] = 0;
      emitSound(
        "place_" + materialSound(b.type),
        new THREE.Vector3(...action.cell),
      );
      return { ok: true };
    }
    if (action.kind === "mine") {
      let id, point;
      if (action.key) {
        const b = block();
        if (stationLocks.has(b.key))
          throw Error("Someone is using that station.");
        id = b.type;
        point = new THREE.Vector3(b.x + 0.5, b.y + 0.5, b.z + 0.5);
        campus.remove(b);
        fuses.delete(b.key);
        for (const map of [survival.chests, survival.furnaces]) {
          const c = map[b.key];
          if (c) {
            for (const stack of c.slots || c)
              if (stack) life.drop(stack, point);
            delete map[b.key];
          }
        }
        if (!creative && canHarvest(id, tool)) {
          if (id === "wheat_crop") {
            life.drop(makeStack("seeds", 2), point);
            if ((survival.crops[b.key] || 0) >= 90)
              life.drop(makeStack("wheat"), point);
            delete survival.crops[b.key];
          } else life.drop(makeStack(ITEMS[id]?.drop || id), point);
          if (id === "leaves" && Math.random() < 0.4)
            life.drop(makeStack("apple"), point);
        }
      } else {
        point = nearby(action.point);
        if (real.edits.length >= 2048)
          throw Error("This room has reached its terrain edit limit.");
        const direction = point
          .clone()
          .sub(position.clone().add(new THREE.Vector3(0, 1.62, 0)));
        const hit = terrainSegment(
          position.clone().add(new THREE.Vector3(0, 1.62, 0)),
          direction.clone().normalize(),
          direction.length() + 0.3,
        );
        if (!hit || hit.point.distanceTo(point) > 0.6)
          throw Error("That surface is obstructed.");
        id = (action.normal?.[1] || 0) > 0.65 ? "dirt" : "stone";
        real.explode(point, 0.7);
        if (!creative && canHarvest(id, tool)) life.drop(makeStack(id), point);
        if (id === "stone" && Math.random() < 0.12)
          life.drop(makeStack("flint"), point);
      }
      emitSound("break", point);
      return { ok: true };
    }
    if (action.kind === "attack") {
      const m = life.mobs.find((m) => m.id === action.id);
      if (!m) throw Error("That mob is gone.");
      nearby(m.position.toArray());
      const start = position.clone().add(new THREE.Vector3(0, 1.2, 0)),
        delta = m.position
          .clone()
          .add(new THREE.Vector3(0, 0.9, 0))
          .sub(start);
      if (
        terrainSegment(
          start,
          delta.clone().normalize(),
          Math.max(0, delta.length() - 0.5),
        )
      )
        throw Error("The mob is behind a wall.");
      const now = clock();
      if (now - (hostAction.cooldowns?.get(actor.id) || -1000) < 400)
        throw Error("Wait for your next swing.");
      hostAction.cooldowns ??= new Map();
      hostAction.cooldowns.set(actor.id, now);
      life.hit(m, ITEMS[actor.held]?.damage || 1, position);
      return { ok: true };
    }
    if (action.kind === "shoot") {
      if (actor.held !== "bow") throw Error("Hold a bow first.");
      const dir = action.direction;
      if (!dir?.every(Number.isFinite) || dir.length !== 3)
        throw Error("Invalid shot.");
      const direction = new THREE.Vector3(...dir);
      if (direction.length() < 0.9 || direction.length() > 1.1)
        throw Error("Invalid shot.");
      const now = clock();
      hostAction.bows ??= new Map();
      if (now - (hostAction.bows.get(actor.id) || -1000) < 250)
        throw Error("Draw the bow before shooting.");
      hostAction.bows.set(actor.id, now);
      const shot = bowShot(Number(action.charge) || 0),
        origin = position
          .clone()
          .add(new THREE.Vector3(0, 1.5, 0))
          .addScaledVector(direction, 0.7);
      projectiles.fire(
        origin,
        direction.multiplyScalar(shot.speed),
        actor.id,
        shot.damage,
      );
      return { ok: true };
    }
    if (action.kind === "ignite") {
      const b = block();
      if (b.type !== "tnt" || actor.held !== "flint_steel")
        throw Error("Use flint and steel on TNT.");
      if (!fuses.has(b.key)) fuses.set(b.key, { b, time: 2.5 });
      emitSound("fuse", new THREE.Vector3(b.x, b.y, b.z));
      return { ok: true };
    }
    if (action.kind === "drop") {
      const point = nearby(action.point),
        stack = action.stack;
      if (
        !ITEMS[stack?.id] ||
        !Number.isInteger(stack.count) ||
        stack.count < 1 ||
        stack.count > 64
      )
        throw Error("Invalid dropped item.");
      life.drop(stack, point);
      return { ok: true };
    }
    if (action.kind === "sleep") {
      const b = block();
      if (b.type !== "bed") throw Error("Use a bed.");
      if (
        life.mobs.some(
          (m) =>
            ["zombie", "creeper", "skeleton", "spider"].includes(m.kind) &&
            m.position.distanceTo(position) < 10,
        )
      )
        throw Error("Monsters are too close to sleep.");
      if (survival.time >= 19 || survival.time < 5.5) survival.time = 8;
      return { ok: true };
    }
    if (action.kind === "station_open") {
      const b = block();
      if (!["chest", "furnace"].includes(b.type) || action.type !== b.type)
        throw Error("Invalid station.");
      if (stationLocks.has(b.key) && stationLocks.get(b.key) !== actor.id)
        throw Error("Another player is using that station.");
      stationLocks.set(b.key, actor.id);
      const map = b.type === "chest" ? survival.chests : survival.furnaces;
      const value = (map[b.key] ??=
        b.type === "chest"
          ? Array(27).fill(null)
          : { slots: [null, null, null], burn: 0, cook: 0 });
      if (b.type === "furnace") value.paused = true;
      return { value: structuredClone(value) };
    }
    if (action.kind === "station_write") {
      if (campus.blocks.get(action.key)?.type !== action.type)
        throw Error("That station is gone.");
      if (stationLocks.get(action.key) !== actor.id)
        throw Error("Reopen the station to edit it.");
      const slots =
        action.type === "chest" ? action.value : action.value?.slots;
      const expected = action.type === "chest" ? 27 : 3;
      if (
        !Array.isArray(slots) ||
        slots.length !== expected ||
        slots.some(
          (s) =>
            s &&
            (!ITEMS[s.id] ||
              !Number.isInteger(s.count) ||
              s.count < 1 ||
              s.count > (ITEMS[s.id].stack || 64)),
        )
      )
        throw Error("Invalid container contents.");
      if (action.type === "chest") {
        if (actor.id !== localId())
          survival.chests[action.key] = structuredClone(slots);
      } else {
        const old = survival.furnaces[action.key];
        if (old && actor.id !== localId()) old.slots = structuredClone(slots);
      }
      return { ok: true };
    }
    if (action.kind === "station_close") {
      if (stationLocks.get(action.key) === actor.id) {
        stationLocks.delete(action.key);
        if (survival.furnaces[action.key])
          survival.furnaces[action.key].paused = false;
      }
      return { ok: true };
    }
    throw Error("Unknown action.");
  };
}

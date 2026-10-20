import * as THREE from "three";
import { ITEMS, makeStack, addStack } from "./items.js";
const cube = new THREE.BoxGeometry(1, 1, 1),
  down = new THREE.Vector3(0, -1, 0);
const HOSTILE = ["zombie", "creeper"];
function model(kind) {
  const group = new THREE.Group(),
    materials = [];
  const box = (w, h, d, x, y, z, color) => {
    const mat = new THREE.MeshLambertMaterial({ color });
    materials.push(mat);
    const mesh = new THREE.Mesh(cube, mat);
    mesh.scale.set(w, h, d);
    mesh.position.set(x, y, z);
    group.add(mesh);
    return mesh;
  };
  if (HOSTILE.includes(kind)) {
    const skin = kind === "creeper" ? 0x509e3b : 0x55844a;
    box(0.65, 0.65, 0.65, 0, 1.45, 0, skin);
    box(0.5, 0.75, 0.35, 0, 0.85, 0, kind === "creeper" ? skin : 0x388e91);
    if (kind === "creeper") {
      for (const x of [-0.22, 0.22])
        for (const z of [-0.2, 0.2]) box(0.25, 0.4, 0.3, x, 0.2, z, 0x3b762d);
      box(0.12, 0.13, 0.01, -0.14, 1.5, 0.331, 0x122812);
      box(0.12, 0.13, 0.01, 0.14, 1.5, 0.331, 0x122812);
      box(0.2, 0.22, 0.01, 0, 1.27, 0.332, 0x122812);
    } else {
      for (const side of [-1, 1]) {
        box(0.2, 0.45, 0.23, side * 0.15, 0.25, 0, 0x434e87);
        box(0.2, 0.2, 0.65, side * 0.38, 1.02, 0.25, skin);
      }
      box(0.13, 0.08, 0.01, -0.15, 1.5, 0.331, 0x151d15);
      box(0.13, 0.08, 0.01, 0.15, 1.5, 0.331, 0x151d15);
    }
  } else {
    const color =
      kind === "pig" ? 0xe69b9c : kind === "sheep" ? 0xe6e4d9 : 0x6e5342;
    box(0.8, 0.65, 1.2, 0, 0.7, 0, color);
    box(0.5, 0.5, 0.6, 0, 0.95, 0.7, kind === "sheep" ? 0xc5b6a1 : color);
    for (const x of [-0.26, 0.26])
      for (const z of [-0.4, 0.4])
        box(0.18, 0.45, 0.18, x, 0.24, z, kind === "pig" ? 0xc78285 : 0x57463a);
    box(0.07, 0.07, 0.01, -0.16, 1.05, 1.006, 0x181a19);
    box(0.07, 0.07, 0.01, 0.16, 1.05, 1.006, 0x181a19);
    if (kind === "cow") {
      box(0.25, 0.3, 0.02, -0.2, 0.8, 0.61, 0xe4e1d4);
      box(0.22, 0.3, 0.03, 0.3, 0.65, 0.2, 0xe4e1d4);
    }
    if (kind === "pig") box(0.25, 0.15, 0.08, 0, 0.9, 1.03, 0xbe6e78);
  }
  group.userData.materials = materials;
  return group;
}
export class Life {
  constructor(
    scene,
    state,
    { trace, player, night, damage, explosion, pickup },
    saved = {},
  ) {
    this.scene = scene;
    this.state = state;
    this.trace = trace;
    this.player = player;
    this.night = night;
    this.damage = damage;
    this.explosion = explosion;
    this.pickup = pickup;
    this.mobs = [];
    this.drops = [];
    this.spawnTimer = 1;
    this.seedTimer = 0;
    this.passiveSeeded = false;
    this.iconCache = new Map();
    for (const m of saved.mobs || [])
      if (
        ["pig", "cow", "sheep", "zombie", "creeper"].includes(m.kind) &&
        m.position?.every(Number.isFinite)
      )
        this.spawn(m.kind, new THREE.Vector3(...m.position), m.health);
    for (const d of saved.drops || [])
      if (ITEMS[d.stack?.id] && d.position?.every(Number.isFinite))
        this.drop(d.stack, new THREE.Vector3(...d.position), d.age || 0);
  }
  ground(x, z, top = 120) {
    return this.trace(new THREE.Vector3(x, top, z), down, 250);
  }
  spawn(kind, position, health) {
    const mesh = model(kind);
    mesh.position.copy(position);
    this.scene.add(mesh);
    const m = {
      kind,
      position: position.clone(),
      mesh,
      health: health ?? (HOSTILE.includes(kind) ? 20 : 10),
      age: 0,
      attack: 0,
      fuse: 0,
      angle: Math.random() * Math.PI * 2,
      turn: 0,
      flash: 0,
      vy: 0,
    };
    this.mobs.push(m);
    return m;
  }
  remove(m) {
    this.mobs.splice(this.mobs.indexOf(m), 1);
    this.scene.remove(m.mesh);
    m.mesh.userData.materials.forEach((x) => x.dispose());
  }
  drop(stack, position, age = 0) {
    if (!stack || !ITEMS[stack.id] || stack.count <= 0) return;
    const c = document.createElement("canvas");
    c.width = c.height = 48;
    const x = c.getContext("2d");
    x.font = "34px sans-serif";
    x.textAlign = "center";
    x.textBaseline = "middle";
    x.fillText(ITEMS[stack.id].icon, 24, 24);
    const texture = new THREE.CanvasTexture(c),
      material = new THREE.SpriteMaterial({ map: texture, depthWrite: false }),
      mesh = new THREE.Sprite(material);
    mesh.scale.setScalar(0.5);
    mesh.position.copy(position).add(new THREE.Vector3(0, 0.4, 0));
    this.scene.add(mesh);
    this.drops.push({
      stack: { ...stack },
      position: position.clone(),
      mesh,
      age,
      vy: 0,
    });
  }
  kill(m, loot = true) {
    const p = m.position.clone();
    this.remove(m);
    this.state.xp += HOSTILE.includes(m.kind) ? 5 : 1;
    if (!loot) return;
    const drops =
      m.kind === "creeper"
        ? [["gunpowder", 2]]
        : m.kind === "zombie"
          ? [["rotten_flesh", 1]]
          : m.kind === "pig"
            ? [["raw_pork", 2]]
            : m.kind === "sheep"
              ? [
                  ["wool", 2],
                  ["raw_beef", 1],
                ]
              : [
                  ["raw_beef", 2],
                  ["leather", 1],
                ];
    for (const [id, count] of drops)
      this.drop(
        makeStack(id, count),
        p.clone().add(new THREE.Vector3((Math.random() - 0.5) * 0.5, 0.2, 0)),
      );
  }
  hit(m, damage, from) {
    if (!this.mobs.includes(m)) return;
    m.health -= damage;
    m.flash = 0.25;
    const push = m.position.clone().sub(from);
    push.y = 0;
    if (push.length()) m.position.addScaledVector(push.normalize(), 0.35);
    if (m.health <= 0) this.kill(m);
  }
  target(ray, reach) {
    let best = null;
    for (const m of this.mobs) {
      const sphere = new THREE.Sphere(
        m.position
          .clone()
          .add(new THREE.Vector3(0, HOSTILE.includes(m.kind) ? 0.9 : 0.65, 0)),
        0.7,
      );
      const p = ray.intersectSphere(sphere, new THREE.Vector3());
      if (p) {
        const distance = p.distanceTo(ray.origin);
        if (distance <= reach && (!best || distance < best.distance))
          best = { mob: m, distance };
      }
    }
    return best;
  }
  blast(position, radius) {
    for (const m of [...this.mobs]) {
      const d = m.position.distanceTo(position);
      if (d < radius + 2)
        this.hit(m, Math.max(1, (1 - d / (radius + 2)) * 28), position);
    }
  }
  seedResources(campus) {
    if (this.state.resourceAreas.includes("starter-camp")) return;
    let added = 0;
    const clusters = [
      [-89, 349, "wood"],
      [-90, 345, "leaves"],
      [-91, 347, "leaves"],
      [-82, 348, "coal_ore"],
      [-81, 348, "stone"],
      [-82, 347, "stone"],
      [-79, 348, "iron_ore"],
      [-78, 348, "stone"],
      [-78, 347, "sand"],
      [-77, 348, "sand"],
      [-97, 347, "wheat_crop"],
      [-96, 347, "wheat_crop"],
      [-95, 347, "wheat_crop"],
    ];
    for (let i = 0; i < 36; i++)
      clusters.push([
        -88 + (i % 9),
        339 - Math.floor(i / 9),
        i % 4 === 0 ? "coal_ore" : i % 4 === 1 ? "iron_ore" : "stone",
      ]);
    for (let i = 0; i < 8; i++) clusters.push([-93 + i, 342, "wood"]);
    for (const [x, z, type] of clusters) {
      const h = this.ground(x + 0.5, z + 0.5);
      if (!h || h.point.y > 6) continue;
      const y = Math.ceil(h.point.y);
      if (campus.place(x, y, z, type)) {
        added++;
        if (type === "wood") {
          campus.place(x, y + 1, z, "wood");
          campus.place(x, y + 2, z, "leaves");
        }
        if (type === "wheat_crop") this.state.crops[`${x},${y},${z}`] = 90;
      }
    }
    if (added > 3) this.state.resourceAreas.push("starter-camp");
  }
  update(dt, campus) {
    const player = this.player();
    this.seedTimer -= dt;
    if (this.seedTimer <= 0) {
      this.seedTimer = 3;
      this.seedResources(campus);
      if (this.mobs.filter((m) => !HOSTILE.includes(m.kind)).length < 3) {
        const kind = ["pig", "cow", "sheep"][Math.floor(Math.random() * 3)],
          a = Math.random() * Math.PI * 2,
          x = player.x + Math.cos(a) * 12,
          z = player.z + Math.sin(a) * 12,
          h = this.ground(x, z);
        if (h && h.point.y < 6) this.spawn(kind, h.point);
      }
    }
    this.spawnTimer -= dt;
    if (
      this.night() &&
      this.spawnTimer <= 0 &&
      this.mobs.filter((m) => HOSTILE.includes(m.kind)).length < 6
    ) {
      this.spawnTimer = 5;
      const a = Math.random() * Math.PI * 2,
        r = 18 + Math.random() * 12,
        x = player.x + Math.cos(a) * r,
        z = player.z + Math.sin(a) * r,
        h = this.ground(x, z);
      const lit = [...campus.placed.values()].some(
        (b) => b.type === "torch" && Math.hypot(b.x - x, b.z - z) < 9,
      );
      if (h && !lit && Math.abs(h.point.y - player.y) < 15)
        this.spawn(Math.random() < 0.35 ? "creeper" : "zombie", h.point);
    }
    for (const m of [...this.mobs]) {
      m.age += dt;
      m.attack = Math.max(0, m.attack - dt);
      m.flash = Math.max(0, m.flash - dt);
      const hostile = HOSTILE.includes(m.kind),
        distance = m.position.distanceTo(player);
      if (distance > 140 || m.position.y < -35) {
        this.remove(m);
        continue;
      }
      if (hostile && !this.night()) {
        m.health -= dt * 2;
        if (m.health <= 0) {
          this.kill(m, false);
          continue;
        }
      }
      let direction = new THREE.Vector3();
      let speed = 0;
      if (hostile && distance < 40) {
        direction.copy(player).sub(m.position);
        direction.y = 0;
        if (direction.length()) direction.normalize();
        speed = m.kind === "creeper" ? 1.25 : 1.4;
        const sight = player
          .clone()
          .add(new THREE.Vector3(0, 1, 0))
          .sub(m.position.clone().add(new THREE.Vector3(0, 1, 0)));
        const occluded = this.trace(
          m.position.clone().add(new THREE.Vector3(0, 1, 0)),
          sight.clone().normalize(),
          sight.length(),
        );
        if (
          m.kind === "zombie" &&
          distance < 2.15 &&
          m.attack === 0 &&
          !occluded
        ) {
          this.damage(3);
          m.attack = 1.3;
        }
        if (m.kind === "creeper") {
          if (distance < 2.6 && !occluded) m.fuse += dt;
          else m.fuse = Math.max(0, m.fuse - dt * 2);
          if (m.fuse > 1.6) {
            const pos = m.position.clone();
            this.remove(m);
            this.explosion(pos, 5);
            continue;
          }
          if (m.fuse > 0) speed = 0;
        }
      } else {
        m.turn -= dt;
        if (m.turn <= 0) {
          m.turn = 3 + Math.random() * 4;
          m.angle += Math.random() * 2 - 1;
        }
        direction.set(Math.sin(m.angle), 0, Math.cos(m.angle));
        speed = this.night() ? 0.15 : 0.6;
      }
      const next = m.position.clone().addScaledVector(direction, speed * dt);
      if (speed) {
        const wall = this.trace(
          m.position.clone().add(new THREE.Vector3(0, 0.8, 0)),
          direction,
          0.5 + speed * dt,
        );
        if (wall && Math.abs(wall.normal?.y || 0) < 0.5) {
          next.copy(m.position);
          m.angle += 1.7;
        } else m.mesh.rotation.y = Math.atan2(direction.x, direction.z);
      }
      const ground = this.trace(
        new THREE.Vector3(next.x, m.position.y + 1, next.z),
        down,
        8,
      );
      if (ground && ground.point.y - m.position.y <= 0.6) {
        m.vy -= 22 * dt;
        next.y = m.position.y + m.vy * dt;
        if (next.y <= ground.point.y + 0.02) {
          next.y = ground.point.y + 0.02;
          m.vy = 0;
        }
      } else if (!ground) {
        m.vy -= 22 * dt;
        next.y += m.vy * dt;
      } else next.copy(m.position);
      m.position.copy(next);
      m.mesh.position.copy(next);
      for (const mat of m.mesh.userData.materials)
        mat.emissive.setHex(
          m.flash > 0
            ? 0x990000
            : m.fuse > 0 && Math.floor(m.fuse * 10) % 2 === 0
              ? 0xaaaaaa
              : 0,
        );
    }
    for (let i = this.drops.length - 1; i >= 0; i--) {
      const d = this.drops[i];
      d.age += dt;
      d.vy -= 12 * dt;
      const g = this.trace(
        d.position.clone().add(new THREE.Vector3(0, 0.3, 0)),
        down,
        0.4 + Math.abs(d.vy * dt),
      );
      if (g && d.position.y + d.vy * dt < g.point.y + 0.2) {
        d.position.y = g.point.y + 0.2;
        d.vy = 0;
      } else d.position.y += d.vy * dt;
      d.mesh.position
        .copy(d.position)
        .add(new THREE.Vector3(0, 0.13 + Math.sin(d.age * 3) * 0.07, 0));
      if (
        d.age > 0.7 &&
        d.position.distanceTo(
          player.clone().add(new THREE.Vector3(0, 0.5, 0)),
        ) < 1.8
      ) {
        const left = addStack(this.state.inventory, d.stack);
        if (left < d.stack.count) {
          const picked = d.stack.count - left;
          d.stack.count = left;
          this.pickup(d.stack.id, picked);
        }
      }
      if (!d.stack.count || d.age > 300 || d.position.y < -40) {
        this.scene.remove(d.mesh);
        d.mesh.material.map.dispose();
        d.mesh.material.dispose();
        this.drops.splice(i, 1);
      }
    }
  }
  serialize() {
    return {
      mobs: this.mobs.map((m) => ({
        kind: m.kind,
        position: m.position.toArray(),
        health: m.health,
      })),
      drops: this.drops.map((d) => ({
        stack: d.stack,
        position: d.position.toArray(),
        age: d.age,
      })),
    };
  }
}

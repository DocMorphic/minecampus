import { newId } from "./id.js";
import * as THREE from "three";
export function bowShot(charge) {
  const power = Math.max(0, Math.min(1, charge));
  return { speed: 20 + power * 18, damage: 3 + power * 5 };
}
export function shieldDamage(state, amount, from, position, yaw) {
  if (!state.blocking || !from) return amount;
  const shield = state.held?.id === "shield" ? state.held : state.armor.offhand;
  if (shield?.id !== "shield") return amount;
  const incoming = from.clone().sub(position);
  incoming.y = 0;
  const facing = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
  if (incoming.normalize().dot(facing) < 0.15) return amount;
  if (state.mode !== "creative" && --shield.durability <= 0) {
    if (state.held === shield) state.inventory[state.selected] = null;
    else state.armor.offhand = null;
  }
  return amount * 0.15;
}
const shaft = new THREE.BoxGeometry(0.035, 0.035, 0.65),
  tip = new THREE.ConeGeometry(0.075, 0.18, 4),
  wood = new THREE.MeshLambertMaterial({ color: 0x9c794d }),
  metal = new THREE.MeshLambertMaterial({ color: 0xcbd0ca });
export class Projectiles {
  constructor(scene, { trace, mobs, players, hitMob, hitPlayer, sound }) {
    this.scene = scene;
    Object.assign(this, { trace, mobs, players, hitMob, hitPlayer, sound });
    this.arrows = [];
  }
  fire(position, velocity, owner, damage, id = newId()) {
    if (this.arrows.length >= 96) return null;
    const mesh = new THREE.Group();
    mesh.add(new THREE.Mesh(shaft, wood));
    const head = new THREE.Mesh(tip, metal);
    head.rotation.x = Math.PI / 2;
    head.position.z = 0.38;
    mesh.add(head);
    mesh.position.copy(position);
    this.scene.add(mesh);
    const a = {
      id,
      position: position.clone(),
      velocity: velocity.clone(),
      owner,
      damage,
      age: 0,
      mesh,
    };
    this.arrows.push(a);
    return a;
  }
  remove(a) {
    const i = this.arrows.indexOf(a);
    if (i >= 0) this.arrows.splice(i, 1);
    this.scene.remove(a.mesh);
  }
  update(dt) {
    for (const a of [...this.arrows]) {
      a.age += dt;
      a.velocity.y -= 9.8 * dt;
      const delta = a.velocity.clone().multiplyScalar(dt),
        length = delta.length(),
        direction = delta.clone().normalize();
      let nearest = this.trace(a.position, direction, length),
        hitMob = null,
        hitPlayer = null;
      const ray = new THREE.Ray(a.position, direction);
      for (const m of this.mobs()) {
        if (a.owner === `mob-${m.id}`) continue;
        const p = ray.intersectSphere(
          new THREE.Sphere(
            m.position
              .clone()
              .add(new THREE.Vector3(0, m.kind === "spider" ? 0.4 : 0.9, 0)),
            m.kind === "spider" ? 0.7 : 0.55,
          ),
          new THREE.Vector3(),
        );
        const distance = p?.distanceTo(a.position);
        if (
          p &&
          distance <= length &&
          (!nearest || distance < nearest.distance)
        ) {
          nearest = { distance, point: p };
          hitMob = m;
          hitPlayer = null;
        }
      }
      if (a.owner.startsWith("mob-"))
        for (const p of this.players()) {
          if (p.health <= 0 || !p.active) continue;
          const point = ray.intersectSphere(
            new THREE.Sphere(
              p.position.clone().add(new THREE.Vector3(0, 0.95, 0)),
              0.55,
            ),
            new THREE.Vector3(),
          );
          const distance = point?.distanceTo(a.position);
          if (
            point &&
            distance <= length &&
            (!nearest || distance < nearest.distance)
          ) {
            nearest = { distance, point };
            hitPlayer = p;
            hitMob = null;
          }
        }
      if (nearest) {
        if (hitMob) this.hitMob(hitMob, a.damage, a.position);
        if (hitPlayer) this.hitPlayer(hitPlayer.id, a.damage, a.position);
        this.sound("arrow_hit", nearest.point);
        this.remove(a);
        continue;
      }
      a.position.add(delta);
      a.mesh.position.copy(a.position);
      a.mesh.lookAt(a.position.clone().add(a.velocity));
      if (a.age > 6 || a.position.y < -40) this.remove(a);
    }
  }
  serialize() {
    return this.arrows.map((a) => ({
      id: a.id,
      position: a.position.toArray(),
      velocity: a.velocity.toArray(),
      owner: a.owner,
      damage: a.damage,
      age: a.age,
    }));
  }
  applySnapshot(records = []) {
    const ids = new Set(records.map((r) => r.id));
    for (const a of [...this.arrows]) if (!ids.has(a.id)) this.remove(a);
    for (const r of records) {
      if (
        !r.position?.every(Number.isFinite) ||
        !r.velocity?.every(Number.isFinite)
      )
        continue;
      let a = this.arrows.find((x) => x.id === r.id);
      if (!a)
        a = this.fire(
          new THREE.Vector3(...r.position),
          new THREE.Vector3(...r.velocity),
          r.owner,
          r.damage,
          r.id,
        );
      if (a) {
        a.position.set(...r.position);
        a.velocity.set(...r.velocity);
        a.mesh.position.copy(a.position);
        a.mesh.lookAt(a.position.clone().add(a.velocity));
      }
    }
  }
  clear() {
    for (const a of [...this.arrows]) this.remove(a);
  }
}

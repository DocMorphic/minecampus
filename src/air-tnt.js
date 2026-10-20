import * as THREE from "three";
export function createCharge(position, velocity) {
  return {
    position: position.clone(),
    velocity: velocity.clone().add(new THREE.Vector3(0, -4, 0)),
    age: 0,
    fuse: null,
    settled: false,
  };
}
export function stepCharge(charge, dt, raycast) {
  if (!(dt > 0) || !Number.isFinite(dt)) return "flying";
  dt = Math.min(dt, 0.05);
  charge.age += dt;
  if (charge.fuse !== null) {
    charge.fuse -= dt;
    if (charge.fuse <= 0) return "detonate";
  }
  if (charge.age >= 8) return "detonate";
  if (charge.settled) return "settled";
  charge.velocity.y -= 24 * dt;
  const next = charge.position.clone().addScaledVector(charge.velocity, dt),
    segment = next.clone().sub(charge.position),
    length = segment.length();
  const hit =
    length > 0
      ? raycast(charge.position, segment.clone().normalize(), length)
      : null;
  if (hit && hit.distance <= length) {
    const normal = hit.normal?.clone() || new THREE.Vector3(0, 1, 0);
    if (normal.dot(segment) > 0) normal.negate();
    charge.position.copy(hit.point).addScaledVector(normal, 0.45);
    charge.velocity.setScalar(0);
    charge.settled = true;
    charge.fuse = Math.min(charge.fuse ?? Infinity, 0.9);
    return "landed";
  }
  charge.position.copy(next);
  return "flying";
}
export class AirTNT {
  constructor(scene, material, raycast, onDetonate) {
    this.scene = scene;
    this.material = material;
    this.raycast = raycast;
    this.onDetonate = onDetonate;
    this.charges = [];
    this.cooldown = 0;
    this.geometry = new THREE.BoxGeometry(.85, .85, .85);
  }
  drop(position, velocity) {
    if (this.charges.length >= 12 || this.cooldown > 0) return false;
    const charge = createCharge(position, velocity);
    charge.mesh = new THREE.Mesh(this.geometry, this.material.clone());
    charge.mesh.position.copy(position);
    this.scene.add(charge.mesh);
    this.charges.push(charge);
    this.cooldown = 0.45;
    return true;
  }
  primeNearby(position, radius) {
    for (const charge of this.charges)
      if (charge.position.distanceTo(position) < radius)
        charge.fuse = Math.min(
          charge.fuse ?? Infinity,
          0.15 + Math.random() * 0.15,
        );
  }
  update(dt) {
    this.cooldown = Math.max(0, this.cooldown - dt);
    for (const charge of [...this.charges]) {
      if (!this.charges.includes(charge)) continue;
      const state = stepCharge(charge, dt, this.raycast);
      charge.mesh.position.copy(charge.position);
      if (state === "detonate") {
        this.remove(charge);
        this.onDetonate(charge.position);
        continue;
      }
      if (!charge.settled) {
        charge.mesh.rotation.x += dt * 1.5;
        charge.mesh.rotation.z += dt * 0.7;
      }
      if (charge.fuse !== null) {
        const flash = Math.floor(charge.fuse * 12) % 2 === 0;
        charge.mesh.material.emissive?.setHex(flash ? 0xaaaaaa : 0);
        charge.mesh.scale.setScalar(1 + Math.sin(charge.age * 25) * 0.04);
      }
    }
  }
  remove(charge) {
    this.scene.remove(charge.mesh);
    charge.mesh.material.dispose();
    this.charges.splice(this.charges.indexOf(charge), 1);
  }
  clear() {
    for (const charge of [...this.charges]) this.remove(charge);
    this.cooldown = 0;
  }
  dispose() {
    this.clear();
    this.geometry.dispose();
    this.material.dispose();
  }
}

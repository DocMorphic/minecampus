import * as THREE from "three";
const UP = new THREE.Vector3(0, 1, 0),
  DOWN = new THREE.Vector3(0, -1, 0);
export function stepWalker(body, dt, input, trace) {
  dt = Math.min(0.05, Math.max(0, dt));
  const height = body.height || 1.8,
    radius = body.radius || 0.3,
    step = 0.55;
  const move = input.move.clone();
  move.y = 0;
  if (move.length() > 1) move.normalize();
  move.multiplyScalar(input.sprint ? 5.7 : 4.2);
  body.velocity.x = THREE.MathUtils.lerp(
    body.velocity.x,
    move.x,
    1 - Math.exp(-dt * 12),
  );
  body.velocity.z = THREE.MathUtils.lerp(
    body.velocity.z,
    move.z,
    1 - Math.exp(-dt * 12),
  );
  if (input.jump && body.grounded) {
    body.velocity.y = 7.5;
    body.grounded = false;
    body.fallFrom = body.position.y;
  }
  for (const axis of ["x", "z"]) {
    const delta = body.velocity[axis] * dt;
    if (Math.abs(delta) < 1e-6) continue;
    const direction = new THREE.Vector3();
    direction[axis] = Math.sign(delta);
    let allowed = Math.abs(delta);
    for (const h of [step + 0.05, height * 0.65, height - 0.08]) {
      const origin = body.position.clone();
      origin.y += h;
      const hit = trace(origin, direction, allowed + radius);
      if (hit && Math.abs(hit.normal?.y || 0) < 0.65)
        allowed = Math.max(0, Math.min(allowed, hit.distance - radius - 0.015));
    }
    body.position[axis] += Math.sign(delta) * allowed;
    if (allowed < Math.abs(delta) * 0.5) body.velocity[axis] = 0;
  }
  const floorOrigin = body.position.clone();
  floorOrigin.y += step;
  const floor = trace(floorOrigin, DOWN, step + 0.1);
  if (
    body.grounded &&
    floor &&
    floor.normal?.y > 0.45 &&
    floor.point.y > body.position.y &&
    floor.point.y - body.position.y <= step
  )
    body.position.y = floor.point.y + 0.015;
  body.velocity.y -= 22 * dt;
  const vertical = body.velocity.y * dt;
  let landed = 0;
  if (vertical <= 0) {
    const origin = body.position.clone();
    origin.y += step;
    const ground = trace(origin, DOWN, step - vertical + 0.05);
    if (
      ground &&
      ground.normal?.y > 0.4 &&
      ground.point.y >= body.position.y + vertical - 0.025
    ) {
      if (!body.grounded)
        landed = Math.max(
          0,
          (body.fallFrom ?? body.position.y) - ground.point.y,
        );
      body.position.y = ground.point.y + 0.015;
      body.velocity.y = 0;
      body.grounded = true;
      body.fallFrom = body.position.y;
    } else {
      if (body.grounded) body.fallFrom = body.position.y;
      body.grounded = false;
      body.position.y += vertical;
    }
  } else {
    const origin = body.position.clone();
    origin.y += height;
    const ceiling = trace(origin, UP, vertical + 0.03);
    if (ceiling) {
      body.position.y += Math.max(0, ceiling.distance - 0.04);
      body.velocity.y = 0;
    } else body.position.y += vertical;
    body.grounded = false;
  }
  return {
    landed,
    distance: Math.hypot(body.velocity.x, body.velocity.z) * dt,
  };
}

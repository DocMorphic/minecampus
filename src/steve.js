import * as THREE from "three";
export function createSteve() {
  const root = new THREE.Group(),
    body = new THREE.Group();
  root.add(body);
  const mats = {
    skin: new THREE.MeshLambertMaterial({ color: 0xb58a6c }),
    shirt: new THREE.MeshLambertMaterial({ color: 0x25b7bd }),
    pants: new THREE.MeshLambertMaterial({ color: 0x464b9b }),
    shoe: new THREE.MeshLambertMaterial({ color: 0x4b495b }),
  };
  const box = (w, h, d, mat, x, y, z) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z);
    body.add(m);
    return m;
  };
  box(0.8, 1.1, 0.44, mats.shirt, 0, 1.55, 0);
  box(0.16, 0.25, 0.46, mats.skin, 0, 2.05, 0);
  const c = document.createElement("canvas");
  c.width = c.height = 8;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#b58a6c";
  ctx.fillRect(0, 0, 8, 8);
  ctx.fillStyle = "#3e2d20";
  ctx.fillRect(0, 0, 8, 2);
  ctx.fillRect(0, 2, 1, 2);
  ctx.fillRect(7, 2, 1, 2);
  ctx.fillStyle = "#e8e8e4";
  ctx.fillRect(1, 4, 2, 1);
  ctx.fillRect(5, 4, 2, 1);
  ctx.fillStyle = "#4d4a94";
  ctx.fillRect(2, 4, 1, 1);
  ctx.fillRect(5, 4, 1, 1);
  ctx.fillStyle = "#805238";
  ctx.fillRect(3, 5, 2, 1);
  ctx.fillStyle = "#4a3024";
  ctx.fillRect(2, 6, 4, 2);
  ctx.fillStyle = "#a37659";
  ctx.fillRect(3, 6, 2, 1);
  const tex = new THREE.CanvasTexture(c);
  tex.magFilter = tex.minFilter = THREE.NearestFilter;
  tex.colorSpace = THREE.SRGBColorSpace;
  const hair = new THREE.MeshLambertMaterial({ color: 0x402e21 }),
    face = new THREE.MeshLambertMaterial({ map: tex });
  box(0.79, 0.79, 0.79, [hair, hair, hair, mats.skin, face, hair], 0, 2.49, 0);
  const limbs = [];
  for (const side of [-1, 1]) {
    const arm = new THREE.Group();
    arm.position.set(side * 0.63, 1.95, 0);
    body.add(arm);
    const sleeve = new THREE.Mesh(
      new THREE.BoxGeometry(0.4, 0.38, 0.43),
      mats.shirt,
    );
    sleeve.position.y = -0.15;
    arm.add(sleeve);
    const hand = new THREE.Mesh(
      new THREE.BoxGeometry(0.38, 0.77, 0.4),
      mats.skin,
    );
    hand.position.y = -0.7;
    arm.add(hand);
    arm.rotation.z = side * 0.13;
    limbs.push(arm);
    const leg = new THREE.Group();
    leg.position.set(side * 0.205, 1, 0);
    body.add(leg);
    const pants = new THREE.Mesh(
      new THREE.BoxGeometry(0.39, 0.84, 0.43),
      mats.pants,
    );
    pants.position.y = -0.39;
    leg.add(pants);
    const shoe = new THREE.Mesh(
      new THREE.BoxGeometry(0.4, 0.2, 0.45),
      mats.shoe,
    );
    shoe.position.y = -0.9;
    leg.add(shoe);
    limbs.push(leg);
  }
  root.scale.setScalar(2);
  return {
    root,
    animate(t, moving) {
      body.position.y = Math.sin(t * 2) * 0.025;
      limbs[0].rotation.x = limbs[2].rotation.x = moving ? -1.3 : -0.15;
      limbs[1].rotation.x = moving ? 0.3 + Math.sin(t * 8) * 0.15 : 0;
      limbs[3].rotation.x = moving ? 0.3 - Math.sin(t * 8) * 0.15 : 0;
    },
  };
}

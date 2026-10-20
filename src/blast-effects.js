import * as THREE from "three";
function smokeTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d"),
    g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,.75)");
  g.addColorStop(0.45, "rgba(255,255,255,.4)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}
export class BlastEffects {
  constructor(scene) {
    this.scene = scene;
    this.smokeMap = smokeTexture();
    this.smoke = [];
    this.flashes = [];
    this.flashGeometry = new THREE.SphereGeometry(1, 16, 12);
  }
  burst(position) {
    const flash = new THREE.Mesh(
      this.flashGeometry,
      new THREE.MeshBasicMaterial({
        color: 0xffc46a,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    flash.position.copy(position);
    this.scene.add(flash);
    this.flashes.push({ mesh: flash, life: 0.28 });
    for (let i = 0; i < 22 && this.smoke.length < 180; i++) {
      const material = new THREE.SpriteMaterial({
        map: this.smokeMap,
        color: i % 3 === 0 ? 0x8d7960 : 0x393d39,
        transparent: true,
        opacity: 0.6,
        depthWrite: false,
        rotation: Math.random() * Math.PI,
      });
      const sprite = new THREE.Sprite(material);
      sprite.position
        .copy(position)
        .add(
          new THREE.Vector3(
            (Math.random() - 0.5) * 7,
            Math.random() * 4,
            (Math.random() - 0.5) * 7,
          ),
        );
      sprite.scale.setScalar(5 + Math.random() * 5);
      this.scene.add(sprite);
      this.smoke.push({
        mesh: sprite,
        velocity: new THREE.Vector3(
          (Math.random() - 0.35) * 5,
          3 + Math.random() * 5,
          (Math.random() - 0.5) * 5,
        ),
        life: 3 + Math.random() * 3,
        total: 6,
      });
    }
  }
  update(dt) {
    for (let i = this.flashes.length - 1; i >= 0; i--) {
      const f = this.flashes[i];
      f.life -= dt;
      f.mesh.scale.setScalar(1 + (1 - f.life / 0.28) * 13);
      f.mesh.material.opacity = Math.max(0, f.life / 0.28) * 0.65;
      if (f.life <= 0) {
        this.scene.remove(f.mesh);
        f.mesh.material.dispose();
        this.flashes.splice(i, 1);
      }
    }
    for (let i = this.smoke.length - 1; i >= 0; i--) {
      const s = this.smoke[i];
      s.life -= dt;
      s.mesh.position.addScaledVector(s.velocity, dt);
      s.mesh.scale.multiplyScalar(1 + dt * 0.28);
      s.mesh.material.opacity = Math.min(0.55, s.life / 4) * 0.75;
      if (s.life <= 0) {
        this.scene.remove(s.mesh);
        s.mesh.material.dispose();
        this.smoke.splice(i, 1);
      }
    }
  }
  clear() {
    for (const x of [...this.smoke, ...this.flashes]) {
      this.scene.remove(x.mesh);
      x.mesh.material.dispose();
    }
    this.smoke = [];
    this.flashes = [];
  }
}

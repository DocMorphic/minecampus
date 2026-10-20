import * as THREE from "three";
import { ITEMS } from "./items.js";
import { texture } from "./textures.js";
export class HeldItem {
  constructor(camera) {
    this.group = new THREE.Group();
    camera.add(this.group);
    this.hand = new THREE.Mesh(
      new THREE.BoxGeometry(0.14, 0.32, 0.16),
      new THREE.MeshBasicMaterial({ color: 0xc48d68 }),
    );
    this.hand.position.set(0.22, -0.24, -0.5);
    this.hand.rotation.set(-0.3, 0, -0.25);
    this.group.add(this.hand);
    this.item = null;
    this.id = null;
  }
  update(id, time, active, eating, visible) {
    this.group.visible = visible;
    if (id !== this.id) {
      if (this.item) {
        this.group.remove(this.item);
        this.item.geometry.dispose();
        this.item.material.dispose();
        if (!ITEMS[this.id]?.block) this.item.material.map?.dispose();
      }
      this.id = id;
      this.item = null;
      if (ITEMS[id]) {
        let geometry, material;
        if (ITEMS[id].block) {
          geometry =
            id === "torch"
              ? new THREE.BoxGeometry(0.045, 0.3, 0.045)
              : new THREE.BoxGeometry(0.2, 0.2, 0.2);
          material = new THREE.MeshBasicMaterial({ map: texture(id) });
        } else {
          const c = document.createElement("canvas");
          c.width = c.height = 128;
          const ctx = c.getContext("2d");
          ctx.font = "90px sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(ITEMS[id].icon, 64, 64);
          geometry = new THREE.PlaneGeometry(0.3, 0.3);
          material = new THREE.MeshBasicMaterial({
            map: new THREE.CanvasTexture(c),
            transparent: true,
            side: THREE.DoubleSide,
          });
        }
        this.item = new THREE.Mesh(geometry, material);
        this.group.add(this.item);
      }
    }
    const swing = active
      ? Math.sin(time * 18) * 0.06
      : Math.sin(time * 2) * 0.005;
    this.hand.position.y = -0.24 + swing;
    this.hand.rotation.x = -0.3 + (active ? Math.sin(time * 18) * 0.4 : 0);
    if (this.item) {
      this.item.position.set(
        eating ? 0.08 : 0.2,
        eating ? -0.06 + Math.sin(time * 25) * 0.025 : -0.15 + swing,
        -0.52,
      );
      this.item.rotation.set(
        0.2,
        ITEMS[id].block ? time * 0.15 : 0,
        active ? Math.sin(time * 18) * 0.3 : -0.2,
      );
    }
  }
}

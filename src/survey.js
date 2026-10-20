import * as THREE from "three";
import { MeshBVH, acceleratedRaycast } from "three-mesh-bvh";
import { decodeSurveyTile } from "./survey-format.js";
import { carveMesh } from "./mesh-damage.js";
import { texture } from "./textures.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
export class SurveyWorld {
  constructor(
    scene,
    manifest,
    edits = [],
    onProgress = () => {},
    onError = () => {},
  ) {
    this.group = new THREE.Group();
    scene.add(this.group);
    this.manifest = manifest;
    this.loaded = new Map();
    this.loading = new Set();
    this.failed = new Set();
    this.edits = edits.filter(
      (e) =>
        Array.isArray(e.position) &&
        e.position.length === 3 &&
        e.position.every(Number.isFinite) &&
        Number.isFinite(e.radius) &&
        e.radius > 0 &&
        e.radius <= 32,
    );
    this.onProgress = onProgress;
    this.onError = onError;
    this.disposed = false;
    this.textureLoader = new THREE.TextureLoader();
    this.pendingFragments = [];
    this.lastError = 0;
    this.craters = [];
    this.craterMaterial = new THREE.MeshBasicMaterial({
      map: texture("stone"),
      color: 0x777064,
      side: THREE.BackSide,
      vertexColors: true,
      toneMapped: false,
    });
    for (const e of this.edits) {
      const p = new THREE.Vector3(...e.position);
      this.cutCraters(p, e.radius);
      this.addCrater(p, e.radius);
    }
  }
  async load(meta) {
    this.loading.add(meta.id);
    try {
      const [response, map] = await Promise.all([
        fetch("/realworld/" + meta.geometry),
        this.textureLoader.loadAsync("/realworld/" + meta.texture),
      ]);
      if (!response.ok) throw Error("Mesh tile HTTP " + response.status);
      const buffer = await response.arrayBuffer();
      if (this.disposed) {
        map.dispose();
        return;
      }
      const { positions, uv, indices } = decodeSurveyTile(buffer, meta),
        g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
      g.setIndex(new THREE.BufferAttribute(indices, 1));
      g.computeBoundingBox();
      g.computeBoundingSphere();
      map.colorSpace = THREE.SRGBColorSpace;
      map.anisotropy = 4;
      map.flipY = false;
      const material = new THREE.MeshBasicMaterial({
          map,
          side: THREE.DoubleSide,
          fog: true,
          toneMapped: false,
        }),
        mesh = new THREE.Mesh(g, material);
      mesh.name = "Survey tile " + meta.id;
      mesh.raycast = acceleratedRaycast;
      mesh.userData.tile = meta;
      for (const e of this.edits) {
        const p = new THREE.Vector3(...e.position);
        if (g.boundingSphere.intersectsSphere(new THREE.Sphere(p, e.radius)))
          carveMesh(g, p, e.radius, { fragments: false });
      }
      g.boundsTree = new MeshBVH(g, { maxLeafSize: 12 });
      this.loaded.set(meta.id, mesh);
      this.group.add(mesh);
      this.onProgress(this.loaded.size, this.manifest.tiles.length);
    } catch (e) {
      this.failed.add(meta.id);
      this.onError(e);
    } finally {
      this.loading.delete(meta.id);
    }
  }
  update(position) {
    if (this.disposed || !this.group.visible) return;
    // Only fetch the actual campus subset; nearest tiles get priority, no remote services at runtime.
    const candidates = this.manifest.tiles
      .filter(
        (t) =>
          !this.loaded.has(t.id) &&
          !this.loading.has(t.id) &&
          !this.failed.has(t.id),
      )
      .sort(
        (a, b) =>
          Math.hypot(a.center[0] - position.x, a.center[2] - position.z) -
          Math.hypot(b.center[0] - position.x, b.center[2] - position.z),
      );
    while (this.loading.size < 4 && candidates.length)
      this.load(candidates.shift());
  }
  raycast(raycaster) {
    this.group.updateMatrixWorld(true);
    raycaster.firstHitOnly = true;
    const hits = raycaster.intersectObjects(
      [...this.loaded.values(), ...this.craters],
      false,
    );
    return hits[0];
  }
  explode(position, radius) {
    this.edits.push({ position: position.toArray(), radius });
    let removed = this.cutCraters(position, radius);
    const sphere = new THREE.Sphere(position, radius);
    for (const mesh of this.loaded.values()) {
      if (!mesh.geometry.boundingSphere.intersectsSphere(sphere)) continue;
      const result = carveMesh(mesh.geometry, position, radius);
      removed += result.removed;
      if (result.removed) {
        mesh.geometry.boundsTree = new MeshBVH(mesh.geometry, {
          maxLeafSize: 12,
        });
        this.pendingFragments.push(
          ...result.fragments.map((f) => ({ ...f, material: mesh.material })),
        );
      }
    }
    this.addCrater(position, radius);
    return removed;
  }
  // The survey contains exterior surfaces only. Give the cut a game-generated
  // inner shell so a roof/terrain hole reveals a dark cavity rather than the sky.
  addCrater(position, radius) {
    let g = new THREE.SphereGeometry(
      radius * 1.01,
      24,
      16,
      0,
      Math.PI * 2,
      Math.acos(-0.04),
      Math.PI - Math.acos(-0.04),
    );
    g.rotateY(0.12345);
    const cap = new THREE.CircleGeometry(radius * 0.13, 24);
    cap.rotateX(Math.PI / 2);
    cap.translate(0, -radius * 0.997, 0);
    const merged = mergeGeometries([g, cap]);
    g.dispose();
    cap.dispose();
    g = merged;
    g.translate(position.x, position.y, position.z);
    const colors = [];
    for (let i = 0; i < g.attributes.position.count; i++) {
      const h = (g.attributes.position.getY(i) - position.y) / radius;
      const light = 0.24 + 0.55 * (h + 1);
      colors.push(light, light, light);
    }
    g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    // Keep the interior non-indexed so generic cut operations retain its UVs.
    g.deleteAttribute("normal");
    g.computeBoundingSphere();
    g.boundsTree = new MeshBVH(g);
    const mesh = new THREE.Mesh(g, this.craterMaterial);
    mesh.raycast = acceleratedRaycast;
    mesh.userData.simulatedInterior = true;
    mesh.userData.blastPosition = position.clone();
    mesh.userData.blastRadius = radius;
    this.group.add(mesh);
    this.craters.push(mesh);
  }
  cutCraters(position, radius) {
    let removed = 0;
    for (const mesh of [...this.craters]) {
      const g = mesh.geometry;
      if (
        position.distanceTo(mesh.userData.blastPosition) +
          mesh.userData.blastRadius <=
        radius + 0.001
      ) {
        removed += g.index.count / 3;
        this.group.remove(mesh);
        g.dispose();
        if (mesh.material !== this.craterMaterial) mesh.material.dispose();
        this.craters.splice(this.craters.indexOf(mesh), 1);
        continue;
      }
      if (
        g.boundingSphere?.intersectsSphere(new THREE.Sphere(position, radius))
      ) {
        const r = carveMesh(g, position, radius, { fragments: false });
        removed += r.removed;
        if (r.removed) {
          if (g.index.count === 0) {
            this.group.remove(mesh);
            g.dispose();
            if (mesh.material !== this.craterMaterial) mesh.material.dispose();
            this.craters.splice(this.craters.indexOf(mesh), 1);
            continue;
          }
          g.deleteAttribute("color");
          mesh.material = this.craterMaterial.clone();
          mesh.material.vertexColors = false;
          g.boundsTree = new MeshBVH(g);
        }
      }
    }
    return removed;
  }
  takeFragments() {
    return this.pendingFragments.splice(0);
  }
  serialize() {
    return this.edits.map((e) => ({
      position: [...e.position],
      radius: e.radius,
    }));
  }
  reset() {
    this.edits = [];
    for (const mesh of this.loaded.values()) {
      mesh.geometry.dispose();
      mesh.material.map.dispose();
      mesh.material.dispose();
      this.group.remove(mesh);
    }
    for (const c of this.craters) {
      this.group.remove(c);
      c.geometry.dispose();
      if (c.material !== this.craterMaterial) c.material.dispose();
    }
    this.craters = [];
    this.loaded.clear();
    this.failed.clear();
  }
  retry() {
    this.failed.clear();
  }
  dispose() {
    this.disposed = true;
    this.reset();
    this.group.removeFromParent();
    this.craterMaterial.map.dispose();
    this.craterMaterial.dispose();
  }
}

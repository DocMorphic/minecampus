import * as THREE from "three";
import { BLOCK, project, insidePolygon, blockKey } from "./geo.js";
import { ITEMS } from "./items.js";
import { texture } from "./textures.js";
const cube = new THREE.BoxGeometry(BLOCK, BLOCK, BLOCK),
  dummy = new THREE.Object3D();
export class Campus {
  constructor(scene, data, saved = {}) {
    this.group = new THREE.Group();
    scene.add(this.group);
    this.blocks = new Map();
    this.batches = {};
    this.features = data.elements;
    this.removed = new Set(saved.removed || []);
    this.placed = new Map();
    this.initial = new Set();
    this.ground = [];
    const lists = {};
    const add = (x, y, z, type, name) => {
      const key = blockKey(x, y, z);
      this.initial.add(key);
      if (this.removed.has(key)) return;
      const b = { x, y, z, type, name, base: true, key };
      this.blocks.set(key, b);
    };
    for (const f of data.elements) {
      const p = f.geometry.map((g) => project(g.lat, g.lon)),
        t = f.tags;
      if (t.building && t.building !== "no") {
        const minX = Math.floor(Math.min(...p.map((a) => a[0])) / BLOCK),
          maxX = Math.ceil(Math.max(...p.map((a) => a[0])) / BLOCK);
        const minZ = Math.floor(Math.min(...p.map((a) => a[1])) / BLOCK),
          maxZ = Math.ceil(Math.max(...p.map((a) => a[1])) / BLOCK);
        const parsed = parseFloat((t.height || "").replace(",", "."));
        const height = Math.min(
            80,
            parsed || Number(t["building:levels"] || 3) * 3.5,
          ),
          levels = Math.max(1, Math.round(height / BLOCK));
        if ((maxX - minX) * (maxZ - minZ) > 100000) continue;
        const cells = new Set();
        for (let x = minX; x <= maxX; x++)
          for (let z = minZ; z <= maxZ; z++)
            if (insidePolygon((x + 0.5) * BLOCK, (z + 0.5) * BLOCK, p))
              cells.add(`${x},${z}`);
        for (const cell of cells) {
          const [x, z] = cell.split(",").map(Number);
          const edge =
            !cells.has(`${x + 1},${z}`) ||
            !cells.has(`${x - 1},${z}`) ||
            !cells.has(`${x},${z + 1}`) ||
            !cells.has(`${x},${z - 1}`);
          for (let y = 0; y < levels; y++)
            if (edge || y === levels - 1)
              add(
                x,
                y,
                z,
                y === levels - 1 ? "roof" : y % 3 === 1 ? "glass" : "concrete",
                t.name?.includes("Informatik")
                  ? "CIT · Informatik & Mathematik"
                  : t.name || "Campus building",
              );
        }
      } else if (
        (t.landuse || t.leisure || t.natural) &&
        p.length > 3 &&
        p[0][0] === p.at(-1)[0]
      ) {
        const type =
          t.natural === "water"
            ? "water"
            : t.landuse === "forest" || t.natural === "wood"
              ? "forest"
              : t.landuse === "grass" || t.leisure === "park"
                ? "grass"
                : null;
        if (type)
          this.polygon(
            p,
            type === "water"
              ? 0x699c9c
              : type === "forest"
                ? 0x698a55
                : 0x849f63,
            0.025,
          );
      }
    }
    // Path ribbons follow real OSM centre-lines, with width based on road class.
    const roadMats = {};
    for (const f of data.elements) {
      const t = f.tags;
      if (!t.highway || ["proposed", "construction"].includes(t.highway))
        continue;
      const p = f.geometry.map((g) => project(g.lat, g.lon));
      const wide = [
        "residential",
        "service",
        "unclassified",
        "tertiary",
        "secondary",
        "primary",
      ].includes(t.highway);
      const width = wide ? 5.8 : t.highway === "cycleway" ? 2.5 : 2;
      const color = wide ? 0x79857d : 0xbac2aa;
      roadMats[color] ??= new THREE.MeshLambertMaterial({ color });
      for (let i = 1; i < p.length; i++) {
        const a = p[i - 1],
          b = p[i],
          l = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (l > 250 || l < 0.1) continue;
        const m = new THREE.Mesh(
          new THREE.PlaneGeometry(width, l),
          roadMats[color],
        );
        m.rotation.x = -Math.PI / 2;
        m.rotation.z = -Math.atan2(b[0] - a[0], b[1] - a[1]);
        m.position.set((a[0] + b[0]) / 2, 0.06, (a[1] + b[1]) / 2);
        m.updateMatrix();
        this.ground.push(m);
      }
    }
    // Merge road ribbons to avoid thousands of draw calls.
    const byMaterial = new Map();
    for (const m of this.ground) {
      const g = m.geometry;
      g.applyMatrix4(m.matrix);
      let a = byMaterial.get(m.material);
      if (!a) byMaterial.set(m.material, (a = []));
      a.push(g);
    }
    for (const [mat, geos] of byMaterial) {
      const pos = [],
        uv = [];
      for (const g of geos) {
        const ng = g.toNonIndexed();
        pos.push(...ng.attributes.position.array);
        uv.push(...ng.attributes.uv.array);
        ng.dispose();
        g.dispose();
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
      g.computeVertexNormals();
      this.group.add(new THREE.Mesh(g, mat));
    }
    for (const b of this.blocks.values()) (lists[b.type] ??= []).push(b);
    for (const type of [
      "concrete",
      "glass",
      "roof",
      "tnt",
      "grass",
      "stone",
      "wood",
      "brick",
      ...Object.keys(ITEMS).filter(
        (id) =>
          ITEMS[id].block &&
          ![
            "concrete",
            "glass",
            "roof",
            "tnt",
            "grass",
            "stone",
            "wood",
            "brick",
          ].includes(id),
      ),
    ]) {
      const list = lists[type] || [],
        mesh = new THREE.InstancedMesh(
          type === "torch"
            ? new THREE.BoxGeometry(0.14, 0.8, 0.14)
            : type === "wheat_crop"
              ? new THREE.BoxGeometry(0.7, 0.7, 0.7)
              : cube,
          new THREE.MeshLambertMaterial({
            map: texture(type),
            ...(type === "torch"
              ? { emissive: 0xff871a, emissiveIntensity: 0.7 }
              : {}),
          }),
          list.length + 12000,
        );
      mesh.count = 0;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.frustumCulled = false;
      this.group.add(mesh);
      this.batches[type] = { mesh, list: [] };
      for (const b of list) this.insert(b);
    }
    for (const b of saved.placed || [])
      if (
        Number.isInteger(b.x) &&
        Number.isInteger(b.y) &&
        Number.isInteger(b.z) &&
        this.batches[b.type] &&
        !this.blocks.has(blockKey(b.x, b.y, b.z))
      )
        this.place(b.x, b.y, b.z, b.type);
    this.ground = [];
  }
  polygon(points, color, y) {
    const s = new THREE.Shape();
    points.forEach(([x, z], i) => (i ? s.lineTo(x, -z) : s.moveTo(x, -z)));
    const m = new THREE.Mesh(
      new THREE.ShapeGeometry(s),
      new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide }),
    );
    m.rotation.x = -Math.PI / 2;
    m.position.y = y;
    this.group.add(m);
  }
  insert(b) {
    const batch = this.batches[b.type];
    b.index = batch.list.length;
    batch.list.push(b);
    dummy.position.set(
      (b.x + 0.5) * BLOCK,
      (b.y + 0.5) * BLOCK,
      (b.z + 0.5) * BLOCK,
    );
    dummy.updateMatrix();
    batch.mesh.setMatrixAt(b.index, dummy.matrix);
    batch.mesh.count = batch.list.length;
    batch.mesh.instanceMatrix.needsUpdate = true;
  }
  get(x, y, z) {
    return this.blocks.get(blockKey(x, y, z));
  }
  place(x, y, z, type) {
    if (y < -30 || y > 150 || this.blocks.size > 1500000) return false;
    const key = blockKey(x, y, z);
    if (this.blocks.has(key)) return false;
    const batch = this.batches[type];
    if (!batch || batch.list.length >= batch.mesh.instanceMatrix.count)
      return false;
    const b = {
      x,
      y,
      z,
      type,
      key,
      name: ITEMS[type]?.name || type,
      base: false,
    };
    this.blocks.set(key, b);
    this.placed.set(key, b);
    this.insert(b);
    return b;
  }
  remove(b) {
    if (!this.blocks.has(b.key)) return;
    const batch = this.batches[b.type],
      last = batch.list.pop();
    if (last !== b) {
      last.index = b.index;
      batch.list[b.index] = last;
      const mat = new THREE.Matrix4();
      batch.mesh.getMatrixAt(batch.mesh.count - 1, mat);
      batch.mesh.setMatrixAt(b.index, mat);
    }
    batch.mesh.count--;
    batch.mesh.instanceMatrix.needsUpdate = true;
    this.blocks.delete(b.key);
    if (b.base) this.removed.add(b.key);
    else this.placed.delete(b.key);
  }
  explode(position, radius, protectedKeys = new Set()) {
    const removed = [];
    const [cx, cy, cz] = [position.x, position.y, position.z].map((v) =>
        Math.floor(v / BLOCK),
      ),
      n = Math.ceil(radius / BLOCK);
    for (let x = cx - n; x <= cx + n; x++)
      for (let y = Math.max(-30, cy - n); y <= cy + n; y++)
        for (let z = cz - n; z <= cz + n; z++) {
          const b = this.get(x, y, z);
          if (
            b &&
            !protectedKeys.has(b.key) &&
            Math.hypot(
              (x + 0.5) * BLOCK - position.x,
              (y + 0.5) * BLOCK - position.y,
              (z + 0.5) * BLOCK - position.z,
            ) < radius
          ) {
            removed.push(b);
            this.remove(b);
          }
        }
    return removed;
  }
  serialize() {
    return {
      version: 2,
      blockSize: BLOCK,
      removed: [...this.removed],
      placed: [...this.placed.values()].map(({ x, y, z, type }) => ({
        x,
        y,
        z,
        type,
      })),
    };
  }
  dispose() {
    this.group.removeFromParent();
    const geometries = new Set(),
      materials = new Set();
    this.group.traverse((o) => {
      if (o.geometry && o.geometry !== cube) geometries.add(o.geometry);
      for (const m of o.material
        ? Array.isArray(o.material)
          ? o.material
          : [o.material]
        : [])
        materials.add(m);
    });
    for (const g of geometries) g.dispose();
    for (const m of materials) {
      m.map?.dispose();
      m.dispose();
    }
  }
}

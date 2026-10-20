import * as THREE from "three";
import { TilesRenderer, WGS84_ELLIPSOID } from "3d-tiles-renderer/three";
import { GoogleCloudAuthPlugin } from "3d-tiles-renderer/core/plugins";
import { GLTFExtensionsPlugin } from "3d-tiles-renderer/three/plugins";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { ORIGIN } from "./geo.js";
export class PhotorealWorld {
  constructor(scene, renderer, camera, key, elevation, onError, onReady) {
    this.holes = Array.from(
      { length: 32 },
      () => new THREE.Vector4(0, -10000, 0, 0),
    );
    this.count = { value: 0 };
    this.scene = scene;
    this.renderer = renderer;
    this.camera = camera;
    this.disposed = false;
    const tiles = (this.tiles = new TilesRenderer());
    tiles.registerPlugin(
      new GoogleCloudAuthPlugin({ apiToken: key, autoRefreshToken: true }),
    );
    const draco = (this.draco = new DRACOLoader());
    draco.setDecoderPath("/draco/");
    tiles.registerPlugin(new GLTFExtensionsPlugin({ dracoLoader: draco }));
    tiles.errorTarget = 8;
    tiles.lruCache.maxSize = 600;
    tiles.setCamera(camera);
    scene.add(tiles.group);
    // ENU -> Three.js east/up/south, matching the local OSM projection.
    const frame = new THREE.Matrix4();
    WGS84_ELLIPSOID.getEastNorthUpFrame(
      (ORIGIN.lat * Math.PI) / 180,
      (ORIGIN.lon * Math.PI) / 180,
      elevation,
      frame,
    );
    const local = new THREE.Matrix4()
      .makeRotationX(-Math.PI / 2)
      .multiply(frame.invert());
    local.decompose(
      tiles.group.position,
      tiles.group.quaternion,
      tiles.group.scale,
    );
    tiles.group.updateMatrixWorld(true);
    let ready = false;
    tiles.addEventListener("load-model", ({ scene: model }) => {
      if (this.disposed) return;
      model.traverse((o) => {
        if (o.isMesh) {
          o.material = Array.isArray(o.material)
            ? o.material.map((m) => m.clone())
            : o.material.clone();
          for (const mat of Array.isArray(o.material)
            ? o.material
            : [o.material])
            this.cutMaterial(mat);
        }
      });
      if (!ready) {
        ready = true;
        onReady();
      }
    });
    tiles.addEventListener("load-error", () => {
      if (!this.disposed) onError();
    });
  }
  cutMaterial(mat) {
    const holes = this.holes,
      count = this.count;
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.blastHoles = { value: holes };
      shader.uniforms.blastCount = count;
      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          "#include <common>\nvarying vec3 blastWorldPosition;",
        )
        .replace(
          "#include <project_vertex>",
          "#include <project_vertex>\nblastWorldPosition = (modelMatrix * vec4(transformed, 1.0)).xyz;",
        );
      shader.fragmentShader = shader.fragmentShader
        .replace(
          "#include <common>",
          "#include <common>\nvarying vec3 blastWorldPosition;\nuniform vec4 blastHoles[32];\nuniform int blastCount;",
        )
        .replace(
          "#include <clipping_planes_fragment>",
          "#include <clipping_planes_fragment>\nfor (int i=0;i<32;i++){if(i>=blastCount)break;if(distance(blastWorldPosition,blastHoles[i].xyz)<blastHoles[i].w)discard;}",
        );
    };
    mat.customProgramCacheKey = () => "minecampus-blast-v1";
    mat.needsUpdate = true;
  }
  explode(p, r) {
    if (this.count.value >= 32) {
      this.holes.shift();
      this.holes.push(new THREE.Vector4());
    } else this.count.value++;
    this.holes[this.count.value - 1].set(p.x, p.y, p.z, r);
  }
  raycast(raycaster) {
    this.tiles.group.updateMatrixWorld(true);
    const hits = raycaster.intersectObject(this.tiles.group, true);
    return hits.find(
      (h) =>
        !this.holes
          .slice(0, this.count.value)
          .some(
            (s) => h.point.distanceTo(new THREE.Vector3(s.x, s.y, s.z)) < s.w,
          ),
    );
  }
  update() {
    if (this.disposed) return;
    this.tiles.setResolutionFromRenderer(this.camera, this.renderer);
    this.tiles.update();
  }
  attribution() {
    const a = [];
    this.tiles.getAttributions(a);
    return a
      .filter((a) => a.type === "string")
      .map((a) => a.value)
      .join(" · ");
  }
  dispose() {
    this.disposed = true;
    this.tiles.group.removeFromParent();
    this.tiles.dispose();
    this.draco.dispose();
  }
}

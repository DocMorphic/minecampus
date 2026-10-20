import * as THREE from "three";
export class Environment {
  constructor(scene, sun, hemi, state) {
    this.scene = scene;
    this.sun = sun;
    this.hemi = hemi;
    this.state = state;
    this.uniforms = {
      campDay: { value: 1 },
      campPlayer: { value: new THREE.Vector3() },
      campLamp: { value: 0 },
      campTorches: {
        value: Array.from({ length: 24 }, () => new THREE.Vector3(0, -1000, 0)),
      },
      campTorchCount: { value: 0 },
    };
    const p = [];
    let seed = 122;
    const rnd = () => {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      return seed / 4294967296;
    };
    for (let i = 0; i < 400; i++) {
      const a = rnd() * Math.PI * 2,
        h = rnd() * 0.85 + 0.1,
        r = Math.sqrt(1 - h * h) * 1800;
      p.push(Math.cos(a) * r, h * 1800, Math.sin(a) * r);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
    this.stars = new THREE.Points(
      g,
      new THREE.PointsMaterial({
        color: 0xcbdcff,
        size: 2,
        transparent: true,
        opacity: 0,
        fog: false,
        depthWrite: false,
      }),
    );
    scene.add(this.stars);
    this.moon = new THREE.Mesh(
      new THREE.SphereGeometry(18, 12, 8),
      new THREE.MeshBasicMaterial({ color: 0xe8e9cf, fog: false }),
    );
    scene.add(this.moon);
    this.lamp = new THREE.PointLight(0xffc477, 7, 14, 1.6);
    scene.add(this.lamp);
    this.torchLights = Array.from({ length: 10 }, () => {
      const light = new THREE.PointLight(0xffa33d, 3, 9, 1.5);
      scene.add(light);
      return light;
    });
    this.applied = new WeakSet();
    this.daylight = 1;
  }
  apply(material) {
    if (this.applied.has(material)) return;
    this.applied.add(material);
    const previous = material.onBeforeCompile;
    material.onBeforeCompile = (shader, ...args) => {
      previous?.call(material, shader, ...args);
      Object.assign(shader.uniforms, this.uniforms);
      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          "#include <common>\nvarying vec3 campWorld;",
        )
        .replace(
          "#include <project_vertex>",
          "#include <project_vertex>\ncampWorld=(modelMatrix*vec4(transformed,1.)).xyz;",
        );
      shader.fragmentShader = shader.fragmentShader
        .replace(
          "#include <common>",
          "#include <common>\nvarying vec3 campWorld;uniform float campDay;uniform vec3 campPlayer;uniform float campLamp;uniform vec3 campTorches[24];uniform int campTorchCount;",
        )
        .replace(
          "#include <color_fragment>",
          "#include <color_fragment>\nvec3 campLight=mix(vec3(.065,.085,.15),vec3(1.),campDay);float heldLight=(1.-smoothstep(1.,14.,distance(campWorld,campPlayer)))*campLamp;campLight+=vec3(1.,.65,.3)*heldLight;for(int ci=0;ci<24;ci++){if(ci>=campTorchCount)break;float glow=1.-smoothstep(1.,10.,distance(campWorld,campTorches[ci]));campLight+=vec3(1.,.53,.18)*glow;}diffuseColor.rgb*=clamp(campLight,vec3(0.),vec3(1.15));",
        );
    };
    material.customProgramCacheKey = () => "campus-night-v1";
    material.needsUpdate = true;
  }
  update(dt, position, torches = [], held = false) {
    if (this.state.cycle)
      this.state.time = (this.state.time + (dt * 24) / 600) % 24;
    const angle = ((this.state.time - 6) / 24) * Math.PI * 2,
      alt = Math.sin(angle);
    this.daylight = THREE.MathUtils.smoothstep(alt, -0.18, 0.3);
    this.uniforms.campDay.value = this.daylight;
    this.uniforms.campPlayer.value
      .copy(position)
      .add(new THREE.Vector3(0, 1, 0));
    this.uniforms.campLamp.value = held ? 1 : 0;
    const nearby = torches
      .sort(
        (a, b) => a.distanceToSquared(position) - b.distanceToSquared(position),
      )
      .slice(0, 24);
    this.uniforms.campTorchCount.value = nearby.length;
    nearby.forEach((p, i) => this.uniforms.campTorches.value[i].copy(p));
    this.scene.background
      .set("#050a1b")
      .lerp(new THREE.Color("#a6c7c9"), this.daylight);
    this.scene.fog.color.copy(this.scene.background);
    this.scene.fog.density = THREE.MathUtils.lerp(
      0.0025,
      0.0009,
      this.daylight,
    );
    this.sun.intensity = this.daylight * 3;
    this.sun.position.set(Math.cos(angle) * 500, alt * 650, 200);
    this.hemi.intensity = 0.17 + this.daylight * 2.3;
    this.stars.material.opacity = (1 - this.daylight) * 0.85;
    this.stars.position.set(position.x, 0, position.z);
    this.moon.position.set(
      position.x - Math.cos(angle) * 1500,
      Math.max(200, -alt * 1500),
      position.z - 500,
    );
    this.moon.visible = this.daylight < 0.5;
    this.lamp.position.copy(position).add(new THREE.Vector3(0, 1.5, 0));
    this.lamp.intensity = held ? 7 : 0;
    this.torchLights.forEach((l, i) => {
      l.intensity = nearby[i] ? 3 : 0;
      if (nearby[i])
        l.position.copy(nearby[i]).add(new THREE.Vector3(0, 0.4, 0));
    });
  }
  get night() {
    return this.state.time >= 19 || this.state.time < 5.5;
  }
  get label() {
    return `${this.night ? "☾" : "☀"} ${String(Math.floor(this.state.time)).padStart(2, "0")}:${String(Math.floor((this.state.time % 1) * 60)).padStart(2, "0")}`;
  }
  toggle() {
    this.state.time = this.night ? 8 : 22;
  }
}

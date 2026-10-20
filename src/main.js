import * as THREE from "three";
import "./style.css";
import { Campus } from "./campus.js";
import { PALETTE } from "./textures.js";
import { BLOCK, project, unproject, traceVoxels } from "./geo.js";
import { createSteve } from "./steve.js";
import { PhotorealWorld } from "./photoreal.js";
const $ = (id) => document.getElementById(id);
const canvas = $("world"),
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
const scene = new THREE.Scene();
scene.background = new THREE.Color("#a6c7c9");
scene.fog = new THREE.FogExp2("#b3cccc", 0.0009);
const camera = new THREE.PerspectiveCamera(
  62,
  innerWidth / innerHeight,
  0.15,
  5000,
);
scene.add(new THREE.HemisphereLight(0xe5f5ff, 0x546d38, 2.5));
const sun = new THREE.DirectionalLight(0xffedc6, 3);
sun.position.set(-400, 650, 250);
scene.add(sun);
const base = new THREE.Mesh(
  new THREE.PlaneGeometry(6000, 6000),
  new THREE.MeshLambertMaterial({ color: 0x8aa571 }),
);
base.rotation.x = -Math.PI / 2;
base.position.y = -0.1;
scene.add(base);
let saved = {};
try {
  saved = JSON.parse(localStorage.getItem("minecampus-world-v1") || "{}");
} catch {}
let data;
try {
  const response = await fetch("/data/garching-osm.json");
  if (!response.ok) throw Error();
  data = await response.json();
} catch {
  document.body.insertAdjacentHTML(
    "beforeend",
    '<div style="position:fixed;inset:25%;background:#14231c;padding:40px">Campus data could not load. Reload the page or check the dev server.</div>',
  );
  throw Error("Campus data unavailable");
}
const original = new Campus(scene, data, saved);
let campus = original,
  photo = null,
  mode = "campus";
const steve = createSteve();
scene.add(steve.root);
const player = {
  position: new THREE.Vector3(-180, 55, 380),
  yaw: 0,
  pitch: -0.45,
  velocity: new THREE.Vector3(),
};
let playing = false,
  selected = 0,
  firstPerson = false,
  lastTime = performance.now(),
  elapsed = 0,
  aim = null,
  aimTime = 0,
  saveTimer,
  toastTimer,
  blasts = 0,
  hasPointer = false,
  dragging = false,
  initialIntro = true;
const keys = new Set(),
  fuses = new Map(),
  particles = [],
  shockwaves = [];
const forward = new THREE.Vector3(),
  right = new THREE.Vector3(),
  desired = new THREE.Vector3(),
  raycaster = new THREE.Raycaster(),
  center = new THREE.Vector2(0, 0);
const selection = new THREE.Mesh(
  new THREE.BoxGeometry(BLOCK + 0.1, BLOCK + 0.1, BLOCK + 0.1),
  new THREE.MeshBasicMaterial({
    color: 0xe4f58f,
    wireframe: true,
    transparent: true,
    opacity: 0.75,
  }),
);
scene.add(selection);
selection.visible = false;
const hotbar = $("hotbar");
PALETTE.forEach((b, i) => {
  const btn = document.createElement("button");
  btn.innerHTML = `<small>${i + 1}</small><div class="block-icon ${b.id === "tnt" ? "tnt-icon" : ""}" style="--block:${b.color}">${b.id === "tnt" ? "TNT" : ""}</div>${b.name}`;
  btn.title = `${i + 1}: ${b.name}`;
  btn.setAttribute("aria-label", `Select ${b.name}`);
  btn.onclick = () => {
    selected = i;
    updateHotbar();
    if (playing) toast(`${b.name} selected`);
  };
  hotbar.append(btn);
});
function updateHotbar() {
  [...hotbar.children].forEach((b, i) => {
    b.classList.toggle("selected", i === selected);
    b.setAttribute("aria-pressed", String(i === selected));
  });
}
updateHotbar();
function toast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 3000);
}
function save() {
  if (mode !== "campus") return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      localStorage.setItem(
        "minecampus-world-v1",
        JSON.stringify(original.serialize()),
      );
    } catch {
      toast("Browser storage is full; this session still works.");
    }
  }, 400);
}
function spawn() {
  player.position.set(-180, 55, 380);
  player.yaw = 0;
  player.pitch = -0.45;
  player.velocity.setScalar(0);
  camera.position.copy(player.position).add(new THREE.Vector3(0, 8, 25));
  toast("Back above Garching. Creative privileges granted.");
}
async function enter() {
  if (initialIntro) spawn();
  playing = true;
  initialIntro = false;
  keys.clear();
  document.body.classList.add("playing");
  $("welcome").classList.add("hidden");
  $("flight-hud").classList.remove("hidden");
  try {
    await canvas.requestPointerLock();
  } catch {
    toast("Drag to look, or use arrow keys. Click to build.");
  }
  if (!hasPointer)
    toast(
      "Drag to look · click to place · right-click to mine · E ignites TNT",
    );
}
function pause() {
  playing = false;
  keys.clear();
  player.velocity.setScalar(0);
  document.exitPointerLock?.();
  document.body.classList.remove("playing");
  $("welcome").classList.remove("hidden");
  $("flight-hud").classList.add("hidden");
  $("play").innerHTML = "RESUME CREATIVE MODE <span>↗</span>";
  selection.visible = false;
}
$("play").onclick = enter;
$("pause").onclick = pause;
document.addEventListener("pointerlockchange", () => {
  const was = hasPointer;
  hasPointer = document.pointerLockElement === canvas;
  if (was && !hasPointer && playing) pause();
});
canvas.addEventListener("pointerdown", (e) => {
  if (!playing) return;
  if (!hasPointer && e.button === 0) {
    dragging = true;
    canvas.dataset.dragged = "false";
  } else if (hasPointer) {
    act(e.button === 2);
  }
});
window.addEventListener("pointerup", (e) => {
  if (dragging && e.button === 0) {
    if (canvas.dataset.dragged !== "true" && playing) act(false);
    dragging = false;
  }
});
canvas.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  if (playing && !hasPointer) act(true);
});
window.addEventListener("mousemove", (e) => {
  if (!playing || (!hasPointer && !dragging)) return;
  if (dragging && Math.abs(e.movementX) + Math.abs(e.movementY) > 1)
    canvas.dataset.dragged = "true";
  player.yaw -= e.movementX * 0.0025;
  player.pitch = THREE.MathUtils.clamp(
    player.pitch - e.movementY * 0.002,
    -1.4,
    1.3,
  );
});
window.addEventListener("keydown", (e) => {
  if ($("settings").open) return;
  if (
    ["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(
      e.code,
    )
  )
    e.preventDefault();
  if (e.code === "Escape") {
    if (playing) pause();
    return;
  }
  if (!playing) return;
  keys.add(e.code);
  if (e.repeat) return;
  if (/^Digit[1-6]$/.test(e.code)) {
    selected = Number(e.code.at(-1)) - 1;
    updateHotbar();
  }
  if (e.code === "KeyV") {
    firstPerson = !firstPerson;
    toast(firstPerson ? "First-person camera" : "Steve chase camera");
  }
  if (e.code === "KeyE") igniteNearby();
  if (e.code === "KeyR") spawn();
});
window.addEventListener("keyup", (e) => keys.delete(e.code));
window.addEventListener("blur", () => {
  keys.clear();
  if (playing) pause();
});
canvas.addEventListener(
  "wheel",
  (e) => {
    if (!playing) return;
    e.preventDefault();
    selected =
      (selected + (e.deltaY > 0 ? 1 : -1) + PALETTE.length) % PALETTE.length;
    updateHotbar();
  },
  { passive: false },
);
function aimAt() {
  camera.getWorldDirection(forward);
  const o = camera.position;
  const voxel = traceVoxels(o, forward, (x, y, z) => campus.get(x, y, z), 260);
  let hit = voxel
    ? {
        cell: voxel.cell,
        normal: new THREE.Vector3(...voxel.normal),
        point: new THREE.Vector3(...voxel.cell.map((v) => (v + 0.5) * BLOCK)),
        block: voxel.block,
        distance: voxel.distance,
      }
    : null;
  if (photo) {
    raycaster.setFromCamera(center, camera);
    raycaster.far = 260;
    const ph = photo.raycast(raycaster);
    if (ph && (!hit || ph.distance < hit.distance)) {
      const n =
        ph.face?.normal.clone().transformDirection(ph.object.matrixWorld) ||
        new THREE.Vector3(0, 1, 0);
      hit = { point: ph.point, normal: n, distance: ph.distance, photo: true };
    }
  }
  if (!hit && forward.y < -0.001) {
    const t = -o.y / forward.y;
    if (t > 0 && t < 300) {
      const p = o.clone().addScaledVector(forward, t);
      hit = { point: p, normal: new THREE.Vector3(0, 1, 0), ground: true };
    }
  }
  return hit;
}
function act(mine) {
  aim = aimAt();
  if (!aim) {
    toast("Aim at a roof, a block, or the ground.");
    return;
  }
  if (mine) {
    if (aim.block) {
      campus.remove(aim.block);
      fuses.delete(aim.block.key);
      save();
    } else if (photo && aim.photo) {
      photo.explode(aim.point, 2.5);
      debris(aim.point, 0x9fa18b, 10);
    }
    return;
  }
  const p = aim.point.clone();
  if (aim.block) {
    p.set(
      ...aim.cell.map((v, i) => (v + 0.5 + aim.normal.getComponent(i)) * BLOCK),
    );
  } else p.addScaledVector(aim.normal, BLOCK * 0.55);
  const cell = [p.x, p.y, p.z].map((v) => Math.floor(v / BLOCK));
  if (aim.ground) cell[1] = 0;
  const b = campus.place(...cell, PALETTE[selected].id);
  if (!b) {
    toast("That space is occupied or outside the build area.");
    return;
  }
  save();
  if (b.type === "tnt") toast("TNT placed. Press E to light the fuse.");
  else if (campus.placed.size === 1)
    toast("First block down. Make yourself at home.");
}
function igniteNearby() {
  let count = 0;
  for (const b of campus.placed.values())
    if (
      b.type === "tnt" &&
      !fuses.has(b.key) &&
      new THREE.Vector3(
        (b.x + 0.5) * BLOCK,
        (b.y + 0.5) * BLOCK,
        (b.z + 0.5) * BLOCK,
      ).distanceTo(player.position) < 220
    ) {
      fuses.set(b.key, { b, time: 2.5 + Math.random() * 0.4 });
      count++;
    }
  toast(
    count
      ? `${count} TNT primed. Stand back.`
      : "Place TNT first, then press E within 220 m.",
  );
}
let audio;
function boomSound() {
  try {
    audio ??= new AudioContext();
    audio.resume();
    const buffer = audio.createBuffer(
        1,
        audio.sampleRate * 0.8,
        audio.sampleRate,
      ),
      ch = buffer.getChannelData(0);
    for (let i = 0; i < ch.length; i++)
      ch[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / ch.length, 3);
    const s = audio.createBufferSource(),
      gain = audio.createGain(),
      filter = audio.createBiquadFilter();
    s.buffer = buffer;
    filter.type = "lowpass";
    filter.frequency.value = 200;
    gain.gain.value = 0.25;
    s.connect(filter).connect(gain).connect(audio.destination);
    s.start();
  } catch {}
}
const particleGeo = new THREE.BoxGeometry(1, 1, 1),
  particleMats = [0xc1c0aa, 0x727c6b, 0xf6b14f, 0xe96a35].map(
    (color) => new THREE.MeshLambertMaterial({ color }),
  );
function debris(p, color, count = 55) {
  for (let i = 0; i < count && particles.length < 450; i++) {
    const m = new THREE.Mesh(
      particleGeo,
      particleMats[i % particleMats.length],
    );
    m.position.copy(p);
    m.scale.setScalar(0.4 + Math.random() * 1.8);
    scene.add(m);
    particles.push({
      mesh: m,
      velocity: new THREE.Vector3(
        (Math.random() - 0.5) * 36,
        8 + Math.random() * 30,
        (Math.random() - 0.5) * 36,
      ),
      life: 1.5 + Math.random() * 1.4,
    });
  }
}
function explode(b) {
  fuses.delete(b.key);
  const p = new THREE.Vector3(
    (b.x + 0.5) * BLOCK,
    (b.y + 0.5) * BLOCK,
    (b.z + 0.5) * BLOCK,
  );
  const removed = campus.explode(p, 16);
  if (photo) photo.explode(p, 16);
  for (const other of removed)
    if (other.type === "tnt" && other.key !== b.key) {
      const chain = { ...other };
      fuses.set(chain.key, { b: chain, time: 0.15 + Math.random() * 0.35 });
    }
  debris(p, 0xddb877, 80);
  const ring = new THREE.Mesh(
    new THREE.SphereGeometry(1, 16, 10),
    new THREE.MeshBasicMaterial({
      color: 0xffb951,
      wireframe: true,
      transparent: true,
      opacity: 0.75,
      depthWrite: false,
    }),
  );
  ring.position.copy(p);
  scene.add(ring);
  shockwaves.push({ mesh: ring, life: 0.5 });
  blasts++;
  boomSound();
  save();
  toast(`BOOM. ${removed.length} blocks cleared.`);
}
function drawMap() {
  const ctx = $("minimap").getContext("2d"),
    w = 240,
    h = 210,
    scale = 0.15;
  ctx.fillStyle = "#1c3024";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#2b4030";
  ctx.lineWidth = 0.5;
  for (let i = 0; i < w; i += 24) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i, h);
    ctx.stroke();
  }
  for (let i = 0; i < h; i += 24) {
    ctx.beginPath();
    ctx.moveTo(0, i);
    ctx.lineTo(w, i);
    ctx.stroke();
  }
  for (const f of data.elements) {
    if (!f.tags.building && !f.tags.highway) continue;
    ctx.beginPath();
    f.geometry.forEach((g, i) => {
      const [x, z] = project(g.lat, g.lon);
      i
        ? ctx.lineTo(w / 2 + x * scale, h / 2 + z * scale)
        : ctx.moveTo(w / 2 + x * scale, h / 2 + z * scale);
    });
    if (f.tags.building) {
      ctx.fillStyle = "#71816a";
      ctx.fill();
    } else {
      ctx.strokeStyle = "#53664b";
      ctx.lineWidth = f.tags.highway === "service" ? 1.5 : 0.6;
      ctx.stroke();
    }
  }
  const x = w / 2 + player.position.x * scale,
    y = h / 2 + player.position.z * scale;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(-player.yaw);
  ctx.fillStyle = "#e4f58f";
  ctx.shadowBlur = 12;
  ctx.shadowColor = "#e4f58f";
  ctx.beginPath();
  ctx.moveTo(0, -7);
  ctx.lineTo(5, 6);
  ctx.lineTo(0, 3);
  ctx.lineTo(-5, 6);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}
function settingsOpen() {
  if (playing) pause();
  $("settings").showModal();
}
$("settings-button").onclick = settingsOpen;
$("api-key").value = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";
$("apply-settings").onclick = () => {
  const requested = $("world-mode").value;
  if (requested === "google" && !$("api-key").value.trim()) {
    toast("Enter a Google Maps key with Map Tiles API enabled.");
    return;
  }
  if (photo) {
    photo.dispose();
    photo = null;
  }
  if (campus !== original) campus.dispose();
  fuses.clear();
  mode = requested;
  if (mode === "google") {
    original.group.visible = false;
    base.visible = false;
    campus = new Campus(scene, { elements: [] });
    $("mode-label").textContent = "LOADING PHOTOREALISTIC TILES";
    photo = new PhotorealWorld(
      scene,
      renderer,
      camera,
      $("api-key").value.trim(),
      Number($("elevation").value) || 525,
      () => {
        toast(
          "3D tiles failed to load. Check key, billing, Map Tiles API, and coverage.",
        );
        $("mode-label").textContent = "3D TILES · LOAD ERROR";
      },
      () => {
        $("mode-label").textContent = "PHOTOREALISTIC WORLD";
        toast("Real-world 3D tiles connected.");
      },
    );
    $("credits").href = "https://www.google.com/intl/en/about/";
    $("credits").textContent = "Google Maps · loading attribution…";
    toast("Connecting to Google 3D Tiles…");
  } else {
    original.group.visible = true;
    base.visible = true;
    campus = original;
    $("mode-label").textContent = "OPEN MAP WORLD";
    $("credits").href = "https://www.openstreetmap.org/copyright";
    $("credits").textContent = "© OpenStreetMap contributors";
    toast("Open map campus restored.");
  }
  $("settings").close();
  spawn();
};
$("reset-world").onclick = () => {
  fuses.clear();
  if (mode === "campus") {
    for (const b of [...original.placed.values()]) original.remove(b);
    original.removed.clear(); // Rebuild the campus from its authoritative snapshot after a reset.
    localStorage.removeItem("minecampus-world-v1");
    location.reload();
  } else {
    for (const b of [...campus.placed.values()]) campus.remove(b);
    photo.holes.forEach((h) => h.set(0, -10000, 0, 0));
    photo.count.value = 0;
    toast("Photorealistic session reset.");
    $("settings").close();
  }
};
$("home").onclick = () => {
  spawn();
  $("settings").close();
};
window.addEventListener("resize", () => {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
});
let frame = 0;
function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min((now - lastTime) / 1000, 0.05);
  lastTime = now;
  elapsed += dt;
  frame++;
  if (playing) {
    if (keys.has("ArrowLeft")) player.yaw += dt * 1.3;
    if (keys.has("ArrowRight")) player.yaw -= dt * 1.3;
    if (keys.has("ArrowUp")) player.pitch = Math.min(1.3, player.pitch + dt);
    if (keys.has("ArrowDown")) player.pitch = Math.max(-1.4, player.pitch - dt);
    forward.set(-Math.sin(player.yaw), 0, -Math.cos(player.yaw));
    right.set(Math.cos(player.yaw), 0, -Math.sin(player.yaw));
    desired.setScalar(0);
    if (keys.has("KeyW")) desired.add(forward);
    if (keys.has("KeyS")) desired.sub(forward);
    if (keys.has("KeyD")) desired.add(right);
    if (keys.has("KeyA")) desired.sub(right);
    if (keys.has("Space")) desired.y++;
    if (keys.has("KeyC") || keys.has("ControlLeft")) desired.y--;
    desired
      .normalize()
      .multiplyScalar(
        keys.has("ShiftLeft") || keys.has("ShiftRight") ? 85 : 30,
      );
    player.velocity.lerp(desired, 1 - Math.exp(-dt * 5));
    player.position.addScaledVector(player.velocity, dt);
    player.position.y = THREE.MathUtils.clamp(player.position.y, 4, 450);
    player.position.x = THREE.MathUtils.clamp(player.position.x, -1400, 1400);
    player.position.z = THREE.MathUtils.clamp(player.position.z, -1400, 1400);
    const look = new THREE.Vector3(
      -Math.sin(player.yaw) * Math.cos(player.pitch),
      Math.sin(player.pitch),
      -Math.cos(player.yaw) * Math.cos(player.pitch),
    );
    if (firstPerson) {
      camera.position.copy(player.position).add(new THREE.Vector3(0, 4.8, 0));
      steve.root.visible = false;
    } else {
      const offset = look.clone().multiplyScalar(-17);
      offset.y += 6;
      offset.addScaledVector(right, 5);
      camera.position.copy(player.position).add(offset);
      steve.root.visible = true;
    }
    camera.lookAt(camera.position.clone().addScaledVector(look, 100));
    aimTime += dt;
    if (aimTime > 0.08) {
      aimTime = 0;
      aim = aimAt();
      selection.visible = !!aim;
      if (aim) {
        const p = aim.block
          ? new THREE.Vector3(...aim.cell.map((v) => (v + 0.5) * BLOCK))
          : aim.point.clone().addScaledVector(aim.normal, BLOCK * 0.5);
        selection.position.set(
          ...[p.x, p.y, p.z].map((v) => (Math.floor(v / BLOCK) + 0.5) * BLOCK),
        );
        $("target-label").textContent = aim.block?.name || "Click to build";
      } else $("target-label").textContent = "";
    }
  } else if (initialIntro) {
    const t = elapsed * 0.025;
    camera.position.set(220 + Math.sin(t) * 40, 185, 370 + Math.cos(t) * 35);
    camera.lookAt(-35, 5, -20);
    steve.root.visible = true;
    player.position.set(
      155 + Math.sin(elapsed * 0.4) * 5,
      80 + Math.sin(elapsed) * 2,
      195,
    );
  }
  steve.root.position.copy(player.position);
  if (initialIntro) {
    const view = new THREE.Vector3();
    camera.getWorldDirection(view);
    const side = new THREE.Vector3().crossVectors(view, camera.up).normalize();
    steve.root.position
      .copy(camera.position)
      .addScaledVector(view, 43)
      .addScaledVector(side, 14);
    steve.root.position.y -= 9;
    steve.root.rotation.y = -0.3;
  } else steve.root.rotation.y = player.yaw + Math.PI;
  steve.animate(elapsed, player.velocity.length() > 3 || !playing);
  // Fuse timers advance only in active play; pausing does not destroy your work.
  if (playing) {
    for (const [key, f] of [...fuses]) {
      f.time -= dt;
      if (f.time <= 0) explode(f.b);
    }
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.life -= dt;
      p.velocity.y -= 30 * dt;
      p.mesh.position.addScaledVector(p.velocity, dt);
      p.mesh.rotation.x += dt * 3;
      p.mesh.rotation.z += dt * 2;
      if (p.life < 0.4) p.mesh.scale.multiplyScalar(Math.exp(-dt * 5));
      if (p.life <= 0) {
        scene.remove(p.mesh);
        particles.splice(i, 1);
      }
    }
    for (let i = shockwaves.length - 1; i >= 0; i--) {
      const s = shockwaves[i];
      s.life -= dt;
      s.mesh.scale.setScalar(1 + (1 - s.life / 0.5) * 24);
      s.mesh.material.opacity = Math.max(0, s.life * 1.4);
      if (s.life <= 0) {
        scene.remove(s.mesh);
        s.mesh.geometry.dispose();
        s.mesh.material.dispose();
        shockwaves.splice(i, 1);
      }
    }
  }
  if (photo) {
    photo.update();
    if (frame % 60 === 0) {
      $("credits").textContent =
        `Google Maps · ${photo.attribution() || "Photorealistic 3D Tiles"}`;
    }
  }
  if (frame % 12 === 0) {
    drawMap();
    const g = unproject(player.position.x, player.position.z);
    $("coords").textContent = `${g.lat.toFixed(4)} N / ${g.lon.toFixed(4)} E`;
    $("altitude").innerHTML = `${Math.round(player.position.y)}<span> m</span>`;
    $("speed").textContent = `${Math.round(player.velocity.length())} M/S`;
    $("stats").textContent =
      `${campus.placed.size} BLOCKS PLACED / ${blasts} BLASTS`;
  }
  renderer.render(scene, camera);
}
spawn();
requestAnimationFrame(animate);

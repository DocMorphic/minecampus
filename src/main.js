import * as THREE from "three";
import "./style.css";
import { Campus } from "./campus.js";
import { PALETTE, texture } from "./textures.js";
import { BLOCK, project, unproject, traceVoxels } from "./geo.js";
import { createSteve } from "./steve.js";
import { PhotorealWorld } from "./photoreal.js";
import { SurveyWorld } from "./survey.js";
import { campusLandmarks, nearestLandmark } from "./landmarks.js";
import { AirTNT } from "./air-tnt.js";
import { BlastEffects } from "./blast-effects.js";
import { exportPhoto } from "./photo.js";
import { Survival, migrateWorldSave } from "./survival.js";
import { ITEMS, makeStack } from "./items.js";
import { miningTime, canHarvest } from "./items.js";
import { InventoryUI } from "./survival-ui.js";
import { stepWalker } from "./physics.js";
import { Environment } from "./environment.js";
import { HeldItem } from "./held-item.js";
import { Life } from "./life.js";
import { GameAudio, materialSound } from "./game-audio.js";
import { Multiplayer } from "./multiplayer.js";
import { Projectiles, bowShot, shieldDamage } from "./projectiles.js";
import { addStack } from "./items.js";
import { createRoomAuthority } from "./room-actions.js";
const audioFX = new GameAudio();
let publishTimer = 0,
  profileTimer = 0;
let networkSession = false,
  network = null,
  projectiles = null,
  bowCharge = null,
  rightHeld = false,
  stepDistance = 0,
  networkTimer = 0,
  shotTimer = 0;
const stationLocks = new Map();
function emitSound(name, position = null) {
  audioFX.play(name, position);
  if (network?.connected && position)
    network.send({ type: "sound", sound: name, position: position.toArray() });
}
function takeDamage(amount, from = null) {
  const blocked = shieldDamage(
    survival,
    amount,
    from,
    player.position,
    player.yaw,
  );
  const actual = survival.damage(blocked);
  if (actual) {
    emitSound(blocked < amount ? "shield" : "hurt", player.position);
    if (from) {
      const push = player.position.clone().sub(from);
      push.y = 0;
      if (push.length()) player.velocity.addScaledVector(push.normalize(), 3);
    }
    updateHotbar();
  }
  return actual;
}
function gamePlayers() {
  if (!network?.connected)
    return [
      {
        id: "solo",
        local: true,
        active: playing && !photoMode,
        health: survival.health,
        position: player.position.clone(),
      },
    ];
  return [...network.players.values()].map((p) => ({
    ...p,
    local: p.id === network.id,
    position:
      p.id === network.id
        ? player.position.clone()
        : new THREE.Vector3(...p.position),
    health: p.id === network.id ? survival.health : p.health,
    active:
      p.id === network.id
        ? !initialIntro && !pendingSpawn && survival.health > 0
        : p.active,
  }));
}

let resetting = false;
let playerSaved = {};
try {
  playerSaved = JSON.parse(
    localStorage.getItem("minecampus-player-v1") || "{}",
  );
} catch {}
const survival = new Survival(playerSaved);
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
const hemi = new THREE.HemisphereLight(0xe5f5ff, 0x546d38, 2.5);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xffedc6, 3);
sun.position.set(-400, 650, 250);
scene.add(sun);
scene.add(camera);
const heldView = new HeldItem(camera);
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
saved = migrateWorldSave(saved);
let original = null;
base.visible = false;
let surveySaved = {};
try {
  surveySaved = JSON.parse(
    localStorage.getItem("minecampus-survey-v1") || "{}",
  );
} catch {}
const manifestResponse = await fetch("/realworld/manifest.json");
if (!manifestResponse.ok)
  throw Error(
    "Real campus assets are missing. Run the survey preparation script.",
  );
const surveyManifest = await manifestResponse.json();
surveySaved = migrateWorldSave(surveySaved);
let campus = new Campus(scene, { elements: [] }, surveySaved),
  photo = null,
  mode = "survey";
let real = new SurveyWorld(
  scene,
  surveyManifest,
  surveySaved.blasts || [],
  (loaded, total) => {
    if (mode === "survey") {
      $("mode-label").textContent = `REAL CAMPUS · ${loaded} TILES`;
      $("play").disabled = loaded < 12;
      $("asset-status").textContent =
        `${loaded} / ${total} real aerial survey tiles loaded`;
    }
  },
  () => {
    if (mode === "survey") {
      $("asset-status").textContent =
        "Some campus tiles failed. Use Retry assets in settings.";
    }
  },
);
const environment = new Environment(scene, sun, hemi, survival);
real.environment = environment;
environment.apply(real.craterMaterial);
$("play").disabled = true;
$("mode-label").textContent = "LOADING REAL CAMPUS";
const steve = createSteve();
scene.add(steve.root);
const player = {
  position: new THREE.Vector3(-180, 55, 380),
  yaw: 0,
  pitch: -0.45,
  velocity: new THREE.Vector3(),
  grounded: false,
  height: 1.8,
  radius: 0.3,
  fallFrom: 0,
};
let playing = false,
  selected = survival.selected,
  firstPerson = true,
  lastTime = performance.now(),
  elapsed = 0,
  aim = null,
  aimTime = 0,
  saveTimer,
  toastTimer,
  blasts = 0,
  hasPointer = false,
  dragging = false,
  initialIntro = true,
  photoMode = false,
  previousFov = 62,
  captureBusy = false,
  photoResult = null,
  cameraShake = 0;
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
const landmarks = campusLandmarks(data.elements);
const effects = new BlastEffects(scene);
const airTNT = new AirTNT(
  scene,
  new THREE.MeshLambertMaterial({ map: texture("tnt") }),
  terrainSegment,
  (position) => detonateAt(position),
);
const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;
$("camera-shake").checked = !reducedMotion;
for (const place of landmarks) {
  const button = document.createElement("button");
  button.className = "landmark-card";
  button.innerHTML = `<span class="landmark-letter">${place.marker}</span><span><strong>${place.name}</strong><small>${place.detail}</small></span><span class="travel-arrow">↗</span>`;
  button.setAttribute("aria-label", `Fly to ${place.name}`);
  button.onclick = () => teleport(place);
  $("landmark-list").append(button);
}
function updatePlayerCamera() {
  const look = new THREE.Vector3(
    -Math.sin(player.yaw) * Math.cos(player.pitch),
    Math.sin(player.pitch),
    -Math.cos(player.yaw) * Math.cos(player.pitch),
  );
  const side = new THREE.Vector3(
    Math.cos(player.yaw),
    0,
    -Math.sin(player.yaw),
  );
  if (firstPerson) {
    camera.position.copy(player.position).add(new THREE.Vector3(0, 1.62, 0));
    steve.root.visible = false;
  } else {
    camera.position
      .copy(player.position)
      .addScaledVector(look, -6)
      .addScaledVector(side, 1.5);
    camera.position.y += 2.5;
    steve.root.visible = true;
  }
  camera.lookAt(camera.position.clone().addScaledVector(look, 100));
  if (!photoMode && $("camera-shake").checked && cameraShake > 0.005) {
    camera.position.x += Math.sin(elapsed * 91) * cameraShake;
    camera.position.y += Math.cos(elapsed * 73) * cameraShake * 0.7;
    camera.rotateZ(Math.sin(elapsed * 53) * cameraShake * 0.005);
  }
}
function exploreCampus() {
  if (playing) pause();
  $("explore").showModal();
}
function teleport(place) {
  $("explore").close();
  initialIntro = false;
  player.position.set(...place.spawn);
  if (survival.mode === "survival") pendingSpawn = true;
  player.yaw = place.yaw;
  player.pitch = place.pitch;
  player.velocity.setScalar(0);
  cameraShake = 0;
  updatePlayerCamera();
  enter();
  toast(`Now above ${place.short}. Have a look around.`);
}
function setPhotoMode(enabled, quiet = false) {
  if (enabled === photoMode) return;
  photoMode = enabled;
  keys.clear();
  player.velocity.setScalar(0);
  document.body.classList.toggle("photo-mode", enabled);
  $("photo-tools").classList.toggle("hidden", !enabled);
  selection.visible = false;
  if (enabled) {
    previousFov = camera.fov;
    $("photo-credit").textContent = $("credits").textContent;
    $("photo-credit").href = $("credits").href;
    $("photo-fov").value = camera.fov;
    $("photo-fov-value").value = `${Math.round(camera.fov)}°`;
    document.exitPointerLock?.();
  } else {
    camera.fov = previousFov;
    camera.updateProjectionMatrix();
    if (!quiet) toast("Back to creative mode.");
  }
}
async function startPhoto() {
  if (network?.connected) {
    toast("Photo mode is available in solo play.");
    return;
  }
  if (!playing) await enter();
  setPhotoMode(true);
}
async function capturePhoto() {
  if (!photoMode || captureBusy) return;
  if (mode === "google") {
    toast("PNG export is available in the bundled campus modes.");
    return;
  }
  captureBusy = true;
  $("take-photo").disabled = true;
  try {
    const result = await exportPhoto(renderer, scene, camera, {
      coordinates: unproject(player.position.x, player.position.z),
      credit:
        mode === "survey"
          ? "Bayerische Vermessungsverwaltung – www.geodaten.bayern.de · CC BY 4.0 · adapted"
          : "© OpenStreetMap contributors · ODbL · adapted",
    });
    if (photoResult) URL.revokeObjectURL(photoResult.url);
    photoResult = result;
    $("photo-preview").src = result.url;
    $("download-photo").href = result.url;
    $("download-photo").download = result.filename;
    $("photo-review").showModal();
    toast("Photo ready. Preview it, then download the PNG.");
  } catch {
    toast("Photo could not be saved. Try again in this browser.");
  } finally {
    captureBusy = false;
    $("take-photo").disabled = false;
  }
}
$("explore-button").onclick = exploreCampus;
$("photo-button").onclick = startPhoto;
$("exit-photo").onclick = () => setPhotoMode(false);
$("take-photo").onclick = capturePhoto;
$("photo-fov").oninput = () => {
  camera.fov = Number($("photo-fov").value);
  camera.updateProjectionMatrix();
  $("photo-fov-value").value = `${camera.fov}°`;
};
$("minimap").onclick = (event) => {
  const rect = $("minimap").getBoundingClientRect(),
    x = ((event.clientX - rect.left) / rect.width) * 240,
    z = ((event.clientY - rect.top) / rect.height) * 210;
  const nearest = nearestLandmark(
    landmarks,
    (x - 120) / 0.15,
    (z - 105) / 0.15,
  );
  if (nearest && nearest.distance < 75) teleport(nearest.place);
  else exploreCampus();
};
function terrainSegment(origin, direction, length) {
  let hit = null;
  const voxel = traceVoxels(
    origin,
    direction,
    (x, y, z) => campus.get(x, y, z),
    length,
  );
  if (voxel)
    hit = {
      distance: voxel.distance,
      point: origin.clone().addScaledVector(direction, voxel.distance),
      normal: new THREE.Vector3(...voxel.normal),
    };
  const surface = mode === "survey" ? real : photo;
  if (surface) {
    const ray = new THREE.Raycaster(origin, direction, 0, length);
    const h = surface.raycast(ray);
    if (h && (!hit || h.distance < hit.distance)) {
      const normal =
        h.face?.normal.clone().transformDirection(h.object.matrixWorld) ||
        new THREE.Vector3(0, 1, 0);
      if (normal.dot(direction) > 0) normal.negate();
      hit = { point: h.point, distance: h.distance, normal };
    }
  } else if (direction.y < 0) {
    const distance = -origin.y / direction.y;
    if (
      distance >= 0 &&
      distance <= length &&
      (!hit || distance < hit.distance)
    )
      hit = {
        distance,
        point: origin.clone().addScaledVector(direction, distance),
        normal: new THREE.Vector3(0, 1, 0),
      };
  }
  return hit;
}
function dropTNT() {
  if (network?.connected && !network.isHost) {
    toast("Use placed TNT and flint and steel in co-op.");
    return;
  }
  if (!playing || photoMode) return;
  const direction = new THREE.Vector3(
    -Math.sin(player.yaw),
    0,
    -Math.cos(player.yaw),
  );
  const position = player.position.clone().addScaledVector(direction, 5);
  position.y += 1;
  if (
    airTNT.drop(
      position,
      player.velocity.clone().addScaledVector(direction, 12),
    )
  ) {
    primeAudio();
    toast("TNT away. Impact lights the fuse.");
  } else toast("Give the last charge a moment.");
}
const inventoryUI = new InventoryUI(survival, {
  changed: () => {
    emitSound("craft", player.position);
    syncStation();
    updateHotbar();
    savePlayer();
  },
  select: (i) => {
    selected = i;
    survival.selected = i;
    updateHotbar();
  },
  drop: (stack) => dropItem(stack, player.position),
  toast,
});
const life = new Life(
  scene,
  survival,
  {
    trace: terrainSegment,
    player: () => player.position,
    night: () => environment.night,
    damage: (n, from, id) => {
      if (id === "solo" || id === network?.id) takeDamage(n, from);
      else network?.target(id, "damage", { amount: n, from: from?.toArray() });
    },
    players: gamePlayers,
    sound: emitSound,
    resourceChanged: save,
    remotePickup: (id, stack) => network.target(id, "loot", { stack }),
    shoot: (mob, target) => {
      const origin = mob.position.clone().add(new THREE.Vector3(0, 1.45, 0));
      const direction = target.position
        .clone()
        .add(new THREE.Vector3(0, 1.1, 0))
        .sub(origin);
      direction.y += direction.length() * 0.055;
      projectiles.fire(
        origin,
        direction.normalize().multiplyScalar(24),
        `mob-${mob.id}`,
        4,
      );
    },
    explosion: (p, r) => detonateAt(p, null, r),
    pickup: () => {
      emitSound("pickup", player.position);
      updateHotbar();
      savePlayer();
    },
  },
  playerSaved.life,
);
let pendingSpawn = false,
  mining = false,
  mineWork = null,
  autoSave = 0;
function updateHotbar() {
  survival.selected = selected;
  inventoryUI.renderHotbar();
}
function savePlayer() {
  if (networkSession) {
    if (network?.connected)
      network.send({ type: "profile", profile: profileState() });
    return;
  }
  try {
    localStorage.setItem(
      "minecampus-player-v1",
      JSON.stringify({ ...survival.serialize(), life: life.serialize() }),
    );
  } catch {}
}
async function openInventory(station) {
  if (networkSession && !network?.connected) {
    toast("Disconnected. Leave the room to return to solo.");
    return;
  }
  if (
    network?.connected &&
    station &&
    ["chest", "furnace"].includes(station.type)
  ) {
    try {
      const result = await requestAction({ kind: "station_open", ...station });
      const map =
        station.type === "chest" ? survival.chests : survival.furnaces;
      map[station.key] = result.value;
    } catch (e) {
      toast(e.message);
      return;
    }
  }
  if (playing) pause();
  emitSound(
    station?.type === "chest"
      ? "chest"
      : station?.type === "furnace"
        ? "furnace"
        : "craft",
    player.position,
  );
  inventoryUI.open(station);
}
function syncStation() {
  const st = inventoryUI?.station;
  if (
    network?.connected &&
    $("inventory").open &&
    st &&
    ["chest", "furnace"].includes(st.type)
  ) {
    const value = (st.type === "chest" ? survival.chests : survival.furnaces)[
      st.key
    ];
    requestAction({
      kind: "station_write",
      ...st,
      value: structuredClone(value),
    }).catch((e) => toast(e.message));
  }
}
function closeInventory() {
  syncStation();
  const st = inventoryUI.station;
  inventoryUI.close();
  if (network?.connected && st && ["chest", "furnace"].includes(st.type))
    requestAction({ kind: "station_close", ...st }).catch((e) =>
      toast(e.message),
    );
  enter();
}
$("inventory-button").onclick = () => openInventory();
$("close-inventory").onclick = closeInventory;
$("inventory").addEventListener("cancel", (e) => {
  e.preventDefault();
  closeInventory();
});
$("night-button").onclick = () => {
  if (network?.connected && !network.isHost) {
    toast("The host controls the shared clock.");
    return;
  }
  environment.toggle();
  toast(
    environment.night ? "Nightfall: keep a torch close." : "Morning on campus.",
  );
  savePlayer();
};
$("game-mode").value = survival.mode;
$("game-mode").onchange = () => {
  if (network?.connected && !network.isHost) {
    $("game-mode").value = survival.mode;
    toast("The host chooses the room play mode.");
    return;
  }
  survival.mode = $("game-mode").value;
  spawn();
  savePlayer();
};
$("day-cycle").checked = survival.cycle;
$("day-cycle").onchange = () => {
  if (network?.connected && !network.isHost) {
    $("day-cycle").checked = survival.cycle;
    toast("The host controls the clock.");
    return;
  }
  survival.cycle = $("day-cycle").checked;
  savePlayer();
};
$("respawn").onclick = () => {
  survival.health = 20;
  survival.hunger = 20;
  survival.saturation = 5;
  $("death").close();
  spawn();
  enter();
  savePlayer();
};
window.addEventListener("beforeunload", () => {
  if (!resetting) savePlayer();
});
function toast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 3000);
}
function save() {
  if (networkSession) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      if (mode === "campus")
        localStorage.setItem(
          "minecampus-world-v1",
          JSON.stringify(original.serialize()),
        );
      if (mode === "survey")
        localStorage.setItem(
          "minecampus-survey-v1",
          JSON.stringify({ ...campus.serialize(), blasts: real.serialize() }),
        );
    } catch {
      toast("Browser storage is full; this session still works.");
    }
  }, 400);
}
function spawn() {
  player.velocity.setScalar(0);
  player.grounded = false;
  player.yaw = -1.3;
  player.pitch = -0.05;
  if (survival.mode === "survival") {
    player.position.set(...(survival.respawn || [-100, 30, 350]));
    pendingSpawn = true;
    survival.invulnerable = 3;
  } else {
    player.position.set(-180, 55, 380);
    pendingSpawn = false;
  }
  updatePlayerCamera();
}
async function enter() {
  if (networkSession && !network?.connected) {
    toast("Leave the disconnected room to return to solo.");
    return;
  }
  audioFX.unlock();
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
      "Drag to look · hold left to mine · right to use / place · E inventory",
    );
}
function pause() {
  if (photoMode) setPhotoMode(false, true);
  playing = false;
  mining = false;
  bowCharge = null;
  survival.blocking = false;
  rightHeld = false;
  mineWork = null;
  keys.clear();
  player.velocity.setScalar(0);
  document.exitPointerLock?.();
  document.body.classList.remove("playing");
  $("welcome").classList.remove("hidden");
  $("flight-hud").classList.add("hidden");
  $("play").innerHTML = "RESUME CAMPUS <span>↗</span>";
  selection.visible = false;
}
$("play").onclick = enter;
$("pause").onclick = pause;
document.addEventListener("pointerlockchange", () => {
  const was = hasPointer;
  hasPointer = document.pointerLockElement === canvas;
  if (was && !hasPointer && playing && !photoMode && !$("inventory").open)
    pause();
});
canvas.addEventListener("pointerdown", (e) => {
  if (!playing || (networkSession && !network?.connected)) return;
  audioFX.unlock();
  if (e.button === 2) {
    rightHeld = true;
    act();
    return;
  }
  if (e.button !== 0) return;
  if (!hasPointer) {
    dragging = true;
    canvas.dataset.dragged = "false";
  }
  if (!photoMode) mining = true;
});
window.addEventListener("pointerup", (e) => {
  if (e.button === 2) {
    rightHeld = false;
    survival.blocking = false;
    if (bowCharge !== null) releaseBow();
  }
  if (e.button === 0) {
    mining = false;
    mineWork = null;
    dragging = false;
  }
});
canvas.addEventListener("contextmenu", (e) => e.preventDefault());
window.addEventListener("mousemove", (e) => {
  if (!playing || (!hasPointer && !dragging)) return;
  if (dragging && Math.abs(e.movementX) + Math.abs(e.movementY) > 1) {
    canvas.dataset.dragged = "true";
    mining = false;
    mineWork = null;
  }
  player.yaw -= e.movementX * 0.0025;
  player.pitch = THREE.MathUtils.clamp(
    player.pitch - e.movementY * 0.002,
    -1.4,
    1.3,
  );
});
window.addEventListener("keydown", (e) => {
  if ($("inventory").open) {
    if (e.code === "KeyE" && !e.repeat) closeInventory();
    return;
  }
  if (
    $("settings").open ||
    $("explore").open ||
    $("photo-review").open ||
    $("multiplayer").open ||
    $("death").open
  )
    return;
  if (e.code === "KeyM" && !e.repeat) {
    exploreCampus();
    return;
  }
  if (e.code === "KeyP" && !e.repeat) {
    if (photoMode) setPhotoMode(false);
    else startPhoto();
    return;
  }
  if (photoMode && e.code === "Enter") {
    e.preventDefault();
    if (!e.repeat) capturePhoto();
    return;
  }
  if (
    photoMode &&
    e.target === $("photo-fov") &&
    ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.code)
  )
    return;
  if (
    ["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(
      e.code,
    )
  )
    e.preventDefault();
  if (e.code === "Escape") {
    if (photoMode) setPhotoMode(false);
    else if (playing) pause();
    return;
  }
  if (!playing) return;
  keys.add(e.code);
  if (e.repeat) return;
  if (/^Digit[1-9]$/.test(e.code)) {
    selected = Number(e.code.at(-1)) - 1;
    updateHotbar();
  }
  if (e.code === "KeyV") {
    firstPerson = !firstPerson;
    toast(firstPerson ? "First-person camera" : "Steve chase camera");
  }
  if (e.code === "KeyE" && !photoMode) openInventory();
  if (e.code === "KeyF") {
    if (survival.held?.id === "bow") {
      bowCharge = 0;
      emitSound("bow", player.position);
    } else if (survival.beginEating()) emitSound("eat", player.position);
  }
  if (e.code === "KeyN") $("night-button").click();
  if (e.code === "KeyG" && survival.mode === "creative") igniteNearby();
  if (e.code === "KeyB" && survival.mode === "creative") dropTNT();
  if (e.code === "KeyQ" && survival.held) {
    dropItem(
      { ...survival.held, count: 1 },
      player.position.clone().addScaledVector(forward, 2.5),
    );
    survival.consume();
    updateHotbar();
    savePlayer();
  }
  if (e.code === "KeyR") spawn();
});
window.addEventListener("keyup", (e) => {
  keys.delete(e.code);
  if (e.code === "KeyF" && bowCharge !== null) releaseBow();
});
window.addEventListener("blur", () => {
  keys.clear();
  if (playing) pause();
});
canvas.addEventListener(
  "wheel",
  (e) => {
    if (!playing) return;
    e.preventDefault();
    if (photoMode) {
      camera.fov = THREE.MathUtils.clamp(
        camera.fov + (e.deltaY > 0 ? 2 : -2),
        35,
        90,
      );
      camera.updateProjectionMatrix();
      $("photo-fov").value = camera.fov;
      $("photo-fov-value").value = `${camera.fov}°`;
      return;
    }
    selected = (selected + (e.deltaY > 0 ? 1 : -1) + 9) % 9;
    updateHotbar();
  },
  { passive: false },
);
function aimAt() {
  camera.getWorldDirection(forward);
  const o = camera.position;
  const reach = survival.mode === "survival" ? 5 : 260;
  const voxel = traceVoxels(
    o,
    forward,
    (x, y, z) => campus.get(x, y, z),
    reach,
  );
  let hit = voxel
    ? {
        cell: voxel.cell,
        normal: new THREE.Vector3(...voxel.normal),
        point: new THREE.Vector3(...voxel.cell.map((v) => (v + 0.5) * BLOCK)),
        block: voxel.block,
        distance: voxel.distance,
      }
    : null;
  const surface = mode === "survey" ? real : photo;
  if (surface) {
    raycaster.setFromCamera(center, camera);
    raycaster.far = reach;
    const ph = surface.raycast(raycaster);
    if (ph && (!hit || ph.distance < hit.distance)) {
      const n =
        ph.face?.normal.clone().transformDirection(ph.object.matrixWorld) ||
        new THREE.Vector3(0, 1, 0);
      if (n.dot(forward) > 0) n.negate();
      hit = {
        point: ph.point,
        normal: n,
        distance: ph.distance,
        photo: true,
        simulated: ph.object.userData.simulatedInterior,
      };
    }
  }
  if (!hit && mode === "campus" && forward.y < -0.001) {
    const t = -o.y / forward.y;
    if (t > 0 && t < 300) {
      const p = o.clone().addScaledVector(forward, t);
      hit = { point: p, normal: new THREE.Vector3(0, 1, 0), ground: true };
    }
  }
  return hit;
}
function mineTick(dt) {
  if (photoMode || pendingSpawn) return;
  aim = aimAt();
  camera.getWorldDirection(forward);
  const ray = new THREE.Ray(camera.position, forward),
    mob = life.target(ray, survival.mode === "survival" ? 5 : 260);
  if (survival.held?.id === "bow" || survival.blocking) return;
  if (mob && (!aim || mob.distance < aim.distance)) {
    if (survival.attackCooldown <= 0) {
      if (network?.connected)
        requestAction({ kind: "attack", id: mob.mob.id }).catch((e) =>
          toast(e.message),
        );
      else
        life.hit(
          mob.mob,
          ITEMS[survival.held?.id]?.damage || 1,
          player.position,
        );
      emitSound("swing", player.position);
      survival.attackCooldown = 0.5;
      survival.wear();
      survival.exhaustion += 0.1;
      updateHotbar();
    }
    return;
  }
  if (!aim) return;
  const id = aim.block?.type || (aim.normal.y > 0.65 ? "dirt" : "stone");
  const key = aim.block?.key || aim.point.toArray().map(Math.floor).join(",");
  if (mineWork?.key !== key) mineWork = { key, progress: 0 };
  const total =
    survival.mode === "creative" ? 0.05 : miningTime(id, survival.held);
  mineWork.progress += dt / total;
  if (Math.floor(mineWork.progress * 5) !== mineWork.sound) {
    mineWork.sound = Math.floor(mineWork.progress * 5);
    emitSound("mine_" + materialSound(id), aim.point);
  }
  $("mine-progress").style.display = "block";
  $("mine-progress").value = mineWork.progress;
  if (mineWork.progress < 1) return;
  mineWork = null;
  if (network?.connected) {
    const toolStack = survival.held;
    requestAction({
      kind: "mine",
      key: aim.block?.key,
      point: aim.point.toArray(),
      normal: aim.normal.toArray(),
    })
      .then(() => {
        survival.wearStack(toolStack);
        survival.exhaustion += 0.05;
        updateHotbar();
        savePlayer();
      })
      .catch((e) => toast(e.message));
    return;
  }
  emitSound("break", aim.point);
  if (aim.block) {
    const b = aim.block;
    campus.remove(b);
    fuses.delete(b.key);
    if (survival.mode === "survival" && canHarvest(id, survival.held)) {
      if (id === "wheat_crop") {
        life.drop(makeStack("seeds", 2), aim.point);
        if ((survival.crops[b.key] || 0) >= 90)
          life.drop(makeStack("wheat"), aim.point);
        delete survival.crops[b.key];
      } else life.drop(makeStack(ITEMS[id]?.drop || id), aim.point);
      if (id === "leaves" && Math.random() < 0.4)
        life.drop(makeStack("apple"), aim.point);
    }
    for (const container of [survival.chests, survival.furnaces]) {
      const c = container[b.key];
      if (c) {
        for (const stack of c.slots || c)
          if (stack) life.drop(stack, aim.point);
        delete container[b.key];
      }
    }
  } else if (aim.photo) {
    (mode === "survey" ? real : photo).explode(aim.point, 0.7);
    if (survival.mode === "survival" && canHarvest(id, survival.held))
      life.drop(makeStack(id), aim.point);
    if (id === "stone" && Math.random() < 0.12)
      life.drop(makeStack("flint"), aim.point);
  }
  survival.wear();
  survival.exhaustion += 0.05;
  updateHotbar();
  save();
  savePlayer();
}
function act() {
  aim = aimAt();
  const held = survival.held,
    def = ITEMS[held?.id];
  if (held?.id === "bow") {
    if (bowCharge === null) {
      bowCharge = 0;
      emitSound("bow", player.position);
    }
    return;
  }
  if (
    held?.id === "shield" ||
    (survival.armor.offhand?.id === "shield" &&
      !def?.block &&
      !def?.food &&
      held?.id !== "seeds")
  ) {
    survival.blocking = true;
    return;
  }

  if (def?.food) {
    if (!survival.beginEating()) toast("Your hunger bar is full.");
    else emitSound("eat", player.position);
    return;
  }
  if (!aim) return;
  if (aim.block && !keys.has("KeyC")) {
    const b = aim.block;
    if (["crafting_table", "furnace", "chest"].includes(b.type)) {
      openInventory({ type: b.type, key: b.key });
      return;
    }
    if (b.type === "bed") {
      if (network?.connected) {
        requestAction({ kind: "sleep", key: b.key })
          .then(() => {
            survival.respawn = [b.x + 2, b.y + 1, b.z];
            savePlayer();
            toast("Respawn point set.");
          })
          .catch((e) => toast(e.message));
        return;
      }
      survival.respawn = [b.x + 2, b.y + 1, b.z];
      if (environment.night) survival.time = 8;
      toast("Respawn point set.");
      savePlayer();
      return;
    }
    if (b.type === "tnt" && held?.id === "flint_steel") {
      if (network?.connected) {
        const flint = survival.held;
        requestAction({ kind: "ignite", key: b.key })
          .then(() => {
            survival.wearStack(flint);
            updateHotbar();
          })
          .catch((e) => toast(e.message));
        return;
      }
      fuses.set(b.key, { b, time: 2.5 });
      emitSound("fuse", aim.point);
      survival.wear();
      updateHotbar();
      return;
    }
  }
  if (def?.part) {
    const old = survival.armor[def.part];
    survival.armor[def.part] = held;
    survival.inventory[selected] = old;
    updateHotbar();
    savePlayer();
    return;
  }
  if (!def?.block && held?.id !== "seeds") return;
  const p = aim.point.clone();
  if (aim.block)
    p.set(
      ...aim.cell.map((v, i) => (v + 0.5 + aim.normal.getComponent(i)) * BLOCK),
    );
  else p.addScaledVector(aim.normal, 0.55);
  const cell = p.toArray().map(Math.floor);
  if (
    Math.abs(cell[0] + 0.5 - player.position.x) < 0.8 &&
    Math.abs(cell[2] + 0.5 - player.position.z) < 0.8 &&
    cell[1] < player.position.y + 1.8 &&
    cell[1] + 1 > player.position.y
  )
    return;
  if (network?.connected) {
    const index = selected,
      item = held.id;
    const finite = survival.mode !== "creative";
    survival.consume(index);
    updateHotbar();
    requestAction({
      kind: "place",
      cell,
      type: item === "seeds" ? "wheat_crop" : item,
    })
      .then(() => savePlayer())
      .catch((e) => {
        if (finite) survival.add(item);
        updateHotbar();
        toast(e.message);
      });
    return;
  }
  const b = campus.place(...cell, held.id === "seeds" ? "wheat_crop" : held.id);
  if (!b) return;
  emitSound("place_" + materialSound(b.type), new THREE.Vector3(...cell));
  if (held.id === "seeds") survival.crops[b.key] = 0;
  survival.consume();
  updateHotbar();
  save();
  savePlayer();
}
function igniteNearby() {
  if (network?.connected && !network.isHost) {
    toast("Use flint and steel on a TNT block.");
    return;
  }
  primeAudio();
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
function primeAudio() {
  audioFX.unlock();
}
function boomSound(position) {
  emitSound("explosion", position);
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
function addRealFragments() {
  for (const f of real.takeFragments().slice(0, 50)) {
    const g = new THREE.BufferGeometry();
    g.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(f.positions, 3),
    );
    g.setAttribute("uv", new THREE.Float32BufferAttribute(f.uv, 2));
    const mesh = new THREE.Mesh(g, f.material);
    mesh.position.copy(f.center);
    scene.add(mesh);
    particles.push({
      mesh,
      velocity: f.center
        .clone()
        .sub(player.position)
        .normalize()
        .multiplyScalar(10)
        .add(
          new THREE.Vector3(
            (Math.random() - 0.5) * 25,
            12 + Math.random() * 22,
            (Math.random() - 0.5) * 25,
          ),
        ),
      life: 3 + Math.random() * 2,
      fragment: true,
    });
  }
}
function explode(b) {
  fuses.delete(b.key);
  detonateAt(
    new THREE.Vector3(
      (b.x + 0.5) * BLOCK,
      (b.y + 0.5) * BLOCK,
      (b.z + 0.5) * BLOCK,
    ),
    b.key,
  );
}
function detonateAt(
  p,
  sourceKey = null,
  radius = survival.mode === "survival" ? 6 : 16,
) {
  life.blast(p, radius);
  for (const target of gamePlayers()) {
    const damage =
      Math.max(0, 1 - target.position.distanceTo(p) / (radius * 1.5)) * 18;
    if (target.local || target.id === "solo") takeDamage(damage, p);
    else if (network?.isHost)
      network.target(target.id, "damage", {
        amount: damage,
        from: p.toArray(),
      });
  }
  if (networkSession && real.edits.length >= 2048) {
    toast("This room has reached its terrain edit limit.");
    return;
  }
  airTNT.primeNearby(p, radius);
  effects.burst(p);
  cameraShake = Math.min(
    1.2,
    cameraShake + Math.max(0, 1 - player.position.distanceTo(p) / 180) * 0.8,
  );
  const removed = campus.explode(p, radius, stationLocks);
  if (mode === "survey") {
    real.explode(p, radius);
    addRealFragments();
  } else if (photo) photo.explode(p, radius);
  for (const other of removed)
    if (other.type === "tnt" && other.key !== sourceKey) {
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
  boomSound(p);
  save();
  toast(
    mode === "survey"
      ? "BOOM. Campus reshaped."
      : `BOOM. ${removed.length} blocks cleared.`,
  );
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
  for (const place of landmarks) {
    const x = w / 2 + place.x * scale,
      y = h / 2 + place.z * scale;
    ctx.fillStyle = "#e4f58f";
    ctx.beginPath();
    ctx.arc(x, y, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#17291c";
    ctx.font = "bold 5px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(place.marker, x, y);
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
function saveCurrentImmediately() {
  if (mode === "survey")
    localStorage.setItem(
      "minecampus-survey-v1",
      JSON.stringify({ ...campus.serialize(), blasts: real.serialize() }),
    );
  if (mode === "campus")
    localStorage.setItem(
      "minecampus-world-v1",
      JSON.stringify(original.serialize()),
    );
}
$("apply-settings").onclick = () => {
  if (networkSession) {
    toast("Leave the multiplayer room before changing world rendering.");
    return;
  }
  const requested = $("world-mode").value;
  if (requested === "google" && !$("api-key").value.trim()) {
    toast("Enter a Google Maps key with Map Tiles API enabled.");
    return;
  }
  try {
    saveCurrentImmediately();
  } catch {}
  if (photo) {
    photo.dispose();
    photo = null;
  }
  if (campus !== original) campus.dispose();
  fuses.clear();
  airTNT.clear();
  effects.clear();
  cameraShake = 0;
  mode = requested;
  real.group.visible = mode === "survey";
  if (original) original.group.visible = mode === "campus";
  base.visible = mode === "campus";
  $("play").disabled = false;
  if (mode === "survey") {
    let state = {};
    try {
      state = JSON.parse(localStorage.getItem("minecampus-survey-v1") || "{}");
    } catch {}
    campus = new Campus(scene, { elements: [] }, state);
    $("mode-label").textContent = `REAL CAMPUS · ${real.loaded.size} TILES`;
    setSurveyCredits();
    toast("Actual aerial survey mesh restored.");
  } else if (mode === "google") {
    campus = new Campus(scene, { elements: [] });
    $("mode-label").textContent = "LOADING GOOGLE TILES";
    photo = new PhotorealWorld(
      scene,
      renderer,
      camera,
      $("api-key").value.trim(),
      Number($("elevation").value) || 525,
      () => {
        toast("Google tiles failed. Check key, billing, API, and coverage.");
        $("mode-label").textContent = "GOOGLE TILES · ERROR";
      },
      () => {
        $("mode-label").textContent = "GOOGLE PHOTOREALISTIC";
        toast("Google tiles connected.");
      },
    );
    $("credits").href = "https://www.google.com/intl/en/about/";
    $("credits").textContent = "Google Maps · loading attribution…";
  } else {
    original ??= new Campus(scene, data, saved);
    original.group.visible = true;
    campus = original;
    $("mode-label").textContent = "STYLIZED MAP WORLD";
    $("credits").href = "https://www.openstreetmap.org/copyright";
    $("credits").textContent = "© OpenStreetMap contributors";
  }
  $("settings").close();
  spawn();
};
function setSurveyCredits() {
  $("credits").href =
    "https://www.geodaten.bayern.de/odd/m/3/html/nutzungsbedingungen.html";
  $("credits").textContent =
    "Bayerische Vermessungsverwaltung · CC BY 4.0 · adapted";
}
setSurveyCredits();
$("reset-world").onclick = () => {
  if (networkSession) {
    toast("Leave the room to reset your solo world.");
    return;
  }
  if (mode !== "google") {
    resetting = true;
    localStorage.removeItem("minecampus-player-v1");
  }
  fuses.clear();
  if (mode === "survey") {
    localStorage.removeItem("minecampus-survey-v1");
    location.reload();
  } else if (mode === "campus") {
    localStorage.removeItem("minecampus-world-v1");
    location.reload();
  } else {
    for (const b of [...campus.placed.values()]) campus.remove(b);
    photo.holes.forEach((h) => h.set(0, -10000, 0, 0));
    photo.count.value = 0;
    toast("Google session reset.");
    $("settings").close();
  }
};
$("retry-assets").onclick = () => {
  real.retry();
  toast("Retrying campus assets.");
  $("settings").close();
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
function profileState() {
  const s = survival.serialize();
  for (const key of [
    "furnaces",
    "chests",
    "crops",
    "resourceAreas",
    "time",
    "cycle",
  ])
    delete s[key];
  return s;
}
function currentPose() {
  return {
    position: player.position.toArray(),
    yaw: player.yaw,
    pitch: player.pitch,
    health: survival.health,
    held: survival.held?.id || null,
    mode: survival.mode,
    blocking: !!survival.blocking,
    active: !initialIntro && !pendingSpawn && survival.health > 0,
  };
}
function requestAction(action) {
  network.pose(currentPose());
  return network.request(action);
}
function dropItem(stack, position) {
  if (!stack) return;
  if (network?.connected) {
    requestAction({
      kind: "drop",
      stack: { ...stack },
      point: position.toArray(),
    }).catch((e) => {
      addStack(survival.inventory, stack);
      updateHotbar();
      toast(e.message);
    });
  } else if (!networkSession) life.drop(stack, position);
}
function tickPlayer(dt, move = {}) {
  const eating = !!survival.eating;
  const furnaces = survival.furnaces,
    crops = survival.crops;
  if (network?.connected && !network.isHost) {
    survival.furnaces = {};
    survival.crops = {};
  }
  survival.tick(dt, move);
  if (network?.connected && !network.isHost) {
    survival.furnaces = furnaces;
    survival.crops = crops;
  }
  if (eating && !survival.eating) {
    emitSound("burp", player.position);
    updateHotbar();
    savePlayer();
  }
}
function releaseBow() {
  const charge = bowCharge;
  bowCharge = null;
  if (charge === null || charge < 0.12 || survival.held?.id !== "bow") return;
  const ammo = survival.inventory.findIndex((s) => s?.id === "arrow");
  if (survival.mode !== "creative" && ammo < 0) {
    toast("You need arrows.");
    return;
  }
  const bow = survival.held;
  const shot = bowShot(charge),
    direction = new THREE.Vector3();
  camera.getWorldDirection(direction);
  const origin = player.position
    .clone()
    .add(new THREE.Vector3(0, 1.5, 0))
    .addScaledVector(direction, 0.7);
  if (survival.mode !== "creative") survival.consume(ammo);
  const fire = network?.connected
    ? requestAction({ kind: "shoot", charge, direction: direction.toArray() })
    : Promise.resolve(
        projectiles.fire(
          origin,
          direction.multiplyScalar(shot.speed),
          "solo",
          shot.damage,
        ),
      );
  fire
    .then(() => {
      survival.wearStack(bow);
      if ($("inventory").open) inventoryUI.render();
      emitSound("bow", player.position);
      updateHotbar();
      savePlayer();
    })
    .catch((e) => {
      if (survival.mode !== "creative") survival.add("arrow");
      toast(e.message);
      updateHotbar();
    });
}
function worldSnapshot() {
  return {
    version: ++shotTimer,
    placed: campus.serialize().placed,
    blasts: real.serialize(),
    life: life.serialize(),
    arrows: projectiles.serialize(),
    fuses: [...fuses.values()].map((f) => ({ key: f.b.key, time: f.time })),
    air: airTNT.charges.map((c) => ({
      position: c.position.toArray(),
      velocity: c.velocity.toArray(),
      age: c.age,
      fuse: c.fuse,
      settled: c.settled,
    })),
    time: survival.time,
    cycle: survival.cycle,
    mode: survival.mode,
    shared: {
      chests: survival.chests,
      furnaces: survival.furnaces,
      crops: survival.crops,
      resourceAreas: survival.resourceAreas,
    },
  };
}
function receiveSnapshot(snapshot, initial = false) {
  if (!snapshot) return;
  if (initial) {
    campus.dispose();
    campus = new Campus(
      scene,
      { elements: [] },
      { blockSize: 1, placed: snapshot.placed },
    );
    const old = real;
    real = new SurveyWorld(
      scene,
      surveyManifest,
      snapshot.blasts,
      old.onProgress,
      old.onError,
    );
    real.environment = environment;
    environment.apply(real.craterMaterial);
    old.dispose();
    fuses.clear();
    airTNT.clear();
    effects.clear();
  } else {
    const desired = new Map(
      snapshot.placed.map((b) => [`${b.x},${b.y},${b.z}`, b]),
    );
    for (const b of [...campus.placed.values()])
      if (desired.get(b.key)?.type !== b.type) campus.remove(b);
    for (const [key, b] of desired)
      if (!campus.get(b.x, b.y, b.z)) campus.place(b.x, b.y, b.z, b.type);
    const previous = real.edits.length;
    for (let i = previous; i < snapshot.blasts.length; i++) {
      const b = snapshot.blasts[i],
        p = new THREE.Vector3(...b.position);
      real.explode(p, b.radius);
      if (b.radius > 2) {
        effects.burst(p);
        cameraShake = Math.min(
          0.5,
          20 / Math.max(20, player.position.distanceTo(p)),
        );
      }
    }
    real.takeFragments?.();
  }
  blasts = snapshot.blasts.filter((b) => b.radius > 2).length;
  survival.time = snapshot.time;
  survival.cycle = snapshot.cycle;
  survival.mode = snapshot.mode || "survival";
  $("game-mode").value = survival.mode;
  $("day-cycle").checked = survival.cycle;
  const ownStation = $("inventory").open ? inventoryUI.station : null;
  for (const name of ["chests", "furnaces", "crops"]) {
    const preserved =
      ownStation &&
      ((name === "chests" && ownStation.type === "chest") ||
        (name === "furnaces" && ownStation.type === "furnace"))
        ? survival[name][ownStation.key]
        : null;
    survival[name] = structuredClone(snapshot.shared?.[name] || {});
    if (preserved) survival[name][ownStation.key] = preserved;
  }
  survival.resourceAreas = snapshot.shared?.resourceAreas || [];
  life.applySnapshot(snapshot.life);
  projectiles.applySnapshot(snapshot.arrows || []);
  fuses.clear();
  for (const f of snapshot.fuses || []) {
    const b = campus.blocks.get(f.key);
    if (b?.type === "tnt") fuses.set(f.key, { b, time: f.time });
  }
  const charges = snapshot.air || [];
  while (airTNT.charges.length > charges.length)
    airTNT.remove(airTNT.charges.at(-1));
  charges.forEach((r, i) => {
    if (!airTNT.charges[i]) {
      airTNT.cooldown = 0;
      airTNT.drop(new THREE.Vector3(...r.position), new THREE.Vector3());
    }
    const c = airTNT.charges[i];
    if (c) {
      c.position.set(...r.position);
      c.velocity.set(...r.velocity);
      c.age = r.age;
      c.fuse = r.fuse;
      c.settled = r.settled;
      c.mesh.position.copy(c.position);
    }
  });
}
function setupOnline() {
  const hostAction = createRoomAuthority({
    context: () => ({
      survival,
      campus,
      real,
      life,
      projectiles,
      stationLocks,
      fuses,
    }),
    localId: () => network?.id,
    localPosition: () => player.position,
    gamePlayers,
    emitSound,
    terrainSegment,
  });
  projectiles = new Projectiles(scene, {
    trace: terrainSegment,
    mobs: () => life.mobs,
    players: gamePlayers,
    hitMob: (m, n, p) => life.hit(m, n, p),
    hitPlayer: (id, n, p) => {
      if (id === "solo" || id === network?.id) takeDamage(n, p);
      else network?.target(id, "damage", { amount: n, from: p.toArray() });
    },
    sound: emitSound,
  });
  network = new Multiplayer(scene, {
    welcome: (m) => {
      networkSession = true;
      const roomUrl = new URL(location.href);
      roomUrl.searchParams.set("room", m.code);
      history.replaceState(null, "", roomUrl);
      clearTimeout(saveTimer);
      if (m.profile) {
        Object.assign(survival, new Survival(m.profile));
        selected = survival.selected;
      } else if (m.snapshot) {
        Object.assign(survival, new Survival());
        selected = survival.selected;
      }
      if (m.snapshot) receiveSnapshot(m.snapshot, true);
      else for (const f of Object.values(survival.furnaces)) f.paused = false;
      stationLocks.clear();
      if (network.isHost) network.publish(worldSnapshot());
      $("multiplayer").close();
      $("room-status").textContent = `Room ${m.code} is ready.`;
      initialIntro = false;
      spawn();
      enter();
      updateHotbar();
    },
    snapshot: (s) => receiveSnapshot(s),
    action: hostAction,
    target: (event, data) => {
      if (event === "damage")
        takeDamage(
          data.amount,
          data.from ? new THREE.Vector3(...data.from) : null,
        );
      if (event === "loot") {
        const left = addStack(survival.inventory, data.stack);
        emitSound("pickup", player.position);
        if (left)
          dropItem(
            { ...data.stack, count: left },
            player.position.clone().add(new THREE.Vector3(3, 0, 0)),
          );
        updateHotbar();
        savePlayer();
      }
    },
    sound: (name, p) => audioFX.play(name, new THREE.Vector3(...p)),
    status: (message) => {
      const online = network.connected;
      $("online-count").textContent = online
        ? `${network.players.size}/8`
        : "Solo";
      $("room-connected").classList.toggle("hidden", !online);
      $("create-room").disabled = online;
      $("join-room").disabled = online;
      if (message) $("room-status").textContent = message;
      else if (online)
        $("room-status").textContent =
          `Room ${network.code} · ${network.players.size} player${network.players.size === 1 ? "" : "s"} · ${network.isHost ? "You are hosting" : "Co-op connected"}`;
      if (online) {
        const invite = new URL(location.href);
        invite.searchParams.set("room", network.code);
        $("invite-url").value = invite.href;
        $("room-players").replaceChildren(
          ...[...network.players.values()].map((p) => {
            const div = document.createElement("div");
            div.textContent = `${p.id === network.host ? "♛ " : ""}${p.name}${p.id === network.id ? " (you)" : ""}`;
            return div;
          }),
        );
      } else if (networkSession) {
        pause();
        toast(message || "Disconnected from the room.");
      }
    },
    departed: (id) => {
      for (const [key, owner] of stationLocks)
        if (owner === id) {
          stationLocks.delete(key);
          if (survival.furnaces[key]) survival.furnaces[key].paused = false;
        }
    },
    authority: (s) => {
      if (s) receiveSnapshot(s);
      stationLocks.clear();
      for (const f of Object.values(survival.furnaces)) f.paused = false;
      toast("The previous host left. You are now hosting.");
    },
  });
  $("player-name").value =
    sessionStorage.getItem("minecampus-name") ||
    localStorage.getItem("minecampus-name") ||
    `Steve-${Math.floor(Math.random() * 90 + 10)}`;
  const invite = new URL(location.href).searchParams.get("room");
  if (invite) $("room-code").value = invite.toUpperCase();
  $("multiplayer-button").onclick = () => {
    if (playing) pause();
    $("multiplayer").showModal();
  };
  async function connect(create) {
    if (mode !== "survey") {
      toast("Switch to the real campus before joining co-op.");
      return;
    }
    const name = $("player-name").value.trim() || "Steve";
    localStorage.setItem("minecampus-name", name);
    sessionStorage.setItem("minecampus-name", name);
    $("create-room").disabled = $("join-room").disabled = true;
    $("room-status").textContent = create
      ? "Starting your campus room…"
      : "Connecting to campus…";
    audioFX.unlock();
    try {
      await network.connect({
        create,
        code: $("room-code").value.trim().toUpperCase(),
        name,
      });
    } catch (e) {
      $("room-status").textContent = e.message;
      $("create-room").disabled = $("join-room").disabled = false;
    }
  }
  $("create-room").onclick = () => connect(true);
  $("join-room").onclick = () => connect(false);
  $("copy-invite").onclick = async () => {
    try {
      await navigator.clipboard.writeText($("invite-url").value);
      $("room-status").textContent = "Invite link copied.";
    } catch {
      $("invite-url").select();
      $("room-status").textContent = "Select and copy the invite link.";
    }
  };
  $("leave-room").onclick = () => {
    savePlayer();
    network.socket?.close();
    location.href = location.pathname;
  };
  for (const [id, key] of [
    ["sound-volume", "volume"],
    ["mob-volume", "mobs"],
    ["step-volume", "steps"],
  ]) {
    $(id).value = audioFX.settings[key] * 100;
    $(id).oninput = () => {
      audioFX.settings[key] = Number($(id).value) / 100;
      audioFX.save();
    };
  }
  $("sound-muted").checked = audioFX.settings.muted;
  $("sound-muted").onchange = () => {
    audioFX.settings.muted = $("sound-muted").checked;
    audioFX.save();
  };
  $("sound-test").onclick = () => {
    audioFX.unlock();
    audioFX.context?.resume().then(() => {
      audioFX.play("explosion");
      $("sound-status").textContent =
        `Audio ${audioFX.context.state} · ${audioFX.context.sampleRate} Hz · original spatial effects`;
    });
  };
  if (invite) $("multiplayer").showModal();
}
function tickNetwork(dt) {
  if (!network) return;
  if (networkSession && !network.connected) {
    for (const a of network.avatars.values()) a.root.visible = false;
    return;
  }
  if (!network.connected) return;
  network.update(dt, elapsed);
  if (!network.isHost) {
    life.interpolate(dt);
  }
  publishTimer += dt;
  profileTimer += dt;
  networkTimer += dt;
  if (networkTimer < 0.1) return;
  networkTimer = 0;
  network.pose(currentPose());
  if (network.isHost && publishTimer >= 0.2) {
    publishTimer = 0;
    network.publish(worldSnapshot());
  }
  if (profileTimer >= 2) {
    profileTimer = 0;
    savePlayer();
  }
}

let frame = 0;
function animate(now, manual = false) {
  if (!manual) requestAnimationFrame(animate);
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
    if (survival.mode === "survival" && !photoMode) {
      if (pendingSpawn) {
        const h = terrainSegment(
          new THREE.Vector3(player.position.x, 120, player.position.z),
          new THREE.Vector3(0, -1, 0),
          200,
        );
        if (h) {
          player.position.y = h.point.y + 0.02;
          player.fallFrom = player.position.y;
          pendingSpawn = false;
          if (!networkSession || network?.isHost) life.seedResources(campus);
          save();
        }
      } else {
        const sprint = keys.has("ShiftLeft") && survival.hunger > 6;
        const wasGrounded = player.grounded;
        const motion = stepWalker(
          player,
          dt,
          { move: desired, sprint, jump: keys.has("Space") },
          terrainSegment,
        );
        if (
          (wasGrounded && !player.grounded && keys.has("Space")) ||
          (!wasGrounded && player.grounded)
        )
          emitSound("step_stone", player.position);
        if (motion.landed > 3) takeDamage(motion.landed - 3);
        if (player.grounded) {
          stepDistance += motion.distance;
          if (stepDistance > (sprint ? 1.65 : 1.9)) {
            stepDistance = 0;
            const surface = terrainSegment(
              player.position.clone().add(new THREE.Vector3(0, 0.2, 0)),
              new THREE.Vector3(0, -1, 0),
              0.6,
            );
            emitSound(
              "step_" + materialSound(surface?.block?.type || "stone"),
              player.position,
            );
          }
        }
        tickPlayer(dt, { distance: motion.distance, sprint });
        if (player.position.y < -40) survival.health = 0;
      }
    } else {
      if (keys.has("Space")) desired.y++;
      if (keys.has("KeyC")) desired.y--;
      desired.normalize().multiplyScalar(keys.has("ShiftLeft") ? 85 : 15);
      player.velocity.lerp(desired, 1 - Math.exp(-dt * 5));
      player.position.addScaledVector(player.velocity, dt);
      if (!photoMode) tickPlayer(dt);
    }
    player.position.x = THREE.MathUtils.clamp(player.position.x, -700, 700);
    player.position.z = THREE.MathUtils.clamp(player.position.z, -750, 750);
    updatePlayerCamera();
    aimTime += dt;
    if (aimTime > 0.08) {
      aimTime = 0;
      aim = aimAt();
      selection.visible = !!aim && !photoMode;
      if (aim) {
        const p = aim.block
          ? new THREE.Vector3(...aim.cell.map((v) => (v + 0.5) * BLOCK))
          : aim.point.clone().addScaledVector(aim.normal, BLOCK * 0.5);
        selection.position.set(
          ...[p.x, p.y, p.z].map((v) => (Math.floor(v / BLOCK) + 0.5) * BLOCK),
        );
        $("target-label").textContent =
          aim.block?.name ||
          (mode === "survey"
            ? aim.simulated
              ? "Blast cavity · game-generated interior"
              : "Real campus · hold left to mine · right to place"
            : "Click to build");
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
  // Photo mode freezes charges and effects while the camera remains free to fly.
  if (network?.connected && !playing) tickPlayer(dt);
  if ((playing && !photoMode) || network?.connected) {
    if (!pendingSpawn && (!networkSession || network?.isHost)) {
      life.update(dt, campus);
      projectiles.update(dt);
    }

    if (mining) mineTick(dt);
    else $("mine-progress").style.display = "none";
    if (survival.health <= 0 && !$("death").open) {
      if ($("inventory").open) {
        syncStation();
        const st = inventoryUI.station;
        inventoryUI.close();
        if (network?.connected && st)
          requestAction({ kind: "station_close", ...st }).catch(() => {});
      }
      emitSound("death", player.position);
      for (let i = 0; i < 36; i++) {
        if (survival.inventory[i])
          dropItem(survival.inventory[i], player.position);
        survival.inventory[i] = null;
      }
      for (const part of Object.keys(survival.armor)) {
        if (survival.armor[part])
          dropItem(survival.armor[part], player.position);
        survival.armor[part] = null;
      }
      pause();
      $("death").showModal();
      savePlayer();
      updateHotbar();
    }
    autoSave += dt;
    if (autoSave > 2) {
      autoSave = 0;
      savePlayer();
      updateHotbar();
    }
    cameraShake *= Math.exp(-dt * 6);
    if (!networkSession || network?.isHost) airTNT.update(dt);
    effects.update(dt);
    for (const [key, f] of !networkSession || network?.isHost
      ? [...fuses]
      : []) {
      f.time -= dt;
      if (Math.floor(f.time * 2) !== f.beat) {
        f.beat = Math.floor(f.time * 2);
        emitSound(
          "fuse",
          new THREE.Vector3(f.b.x + 0.5, f.b.y + 0.5, f.b.z + 0.5),
        );
      }
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
        if (p.fragment) p.mesh.geometry.dispose();
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
  if (mode === "survey")
    real.update(
      playing
        ? player.position
        : new THREE.Vector3(
            real.loaded.size < 12 ? -180 : 0,
            0,
            real.loaded.size < 12 ? 300 : 0,
          ),
    );
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
    const nearby = nearestLandmark(
      landmarks,
      player.position.x,
      player.position.z,
    );
    $("nearby-place").textContent = nearby
      ? `${nearby.place.short} · ${Math.round(nearby.distance)} m`
      : "";
    $("stats").textContent =
      `${campus.placed.size} BLOCKS / ${blasts} BLASTS / ${airTNT.charges.length} AIRBORNE`;
  }
  environment.update(
    (!networkSession ? playing && !photoMode : network?.isHost) ? dt : 0,
    player.position,
    [...campus.placed.values()]
      .filter((b) => b.type === "torch")
      .map((b) => new THREE.Vector3(b.x + 0.5, b.y + 0.8, b.z + 0.5)),
    survival.held?.id === "torch",
  );
  if (frame % 12 === 0) {
    $("health").textContent = `♥ ${Math.ceil(survival.health)} / 20`;
    $("hunger").textContent =
      `🍗 ${Math.ceil(survival.hunger)} / 20${survival.eating ? " · Eating…" : ""}`;
    $("world-clock").textContent =
      `${environment.label} · ${life.mobs.length} mobs`;
    $("game-mode-label").textContent = survival.mode.toUpperCase();
  }
  tickNetwork(dt);
  if (bowCharge !== null) {
    if (!playing || survival.held?.id !== "bow") bowCharge = null;
    else bowCharge = Math.min(1, bowCharge + dt);
  }
  $("combat-status").textContent =
    bowCharge !== null
      ? `BOW · ${Math.round(bowCharge * 100)}%`
      : survival.blocking
        ? "SHIELD RAISED"
        : "";
  audioFX.listener = player.position;
  audioFX.yaw = player.yaw;
  heldView.update(
    survival.held?.id,
    elapsed,
    mining || survival.attackCooldown > 0.25,
    !!survival.eating,
    playing && firstPerson && !photoMode,
  );
  if (!manual) renderer.render(scene, camera);
}
spawn();
setupOnline();
// Keep room simulation moving when the browser reduces background animation frames.
setInterval(() => {
  if (network?.isHost && performance.now() - lastTime > 250) {
    const steps = Math.min(20, Math.floor((performance.now() - lastTime) / 50));
    for (let i = 0; i < steps; i++) animate(lastTime + 50, true);
  }
}, 250);
requestAnimationFrame(animate);

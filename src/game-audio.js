// Original synthesized effects. No Minecraft audio files are redistributed.
const SETTINGS = "minecampus-audio-v1";
export const SOUND_NAMES = [
  "step_stone",
  "step_grass",
  "step_wood",
  "place_stone",
  "place_wood",
  "place_grass",
  "mine_stone",
  "mine_wood",
  "mine_grass",
  "break",
  "fuse",
  "explosion",
  "swing",
  "hit",
  "hurt",
  "eat",
  "burp",
  "pickup",
  "craft",
  "chest",
  "furnace",
  "bow",
  "arrow_hit",
  "shield",
  "death",
  "zombie",
  "creeper",
  "skeleton",
  "spider",
  "pig",
  "cow",
  "sheep",
  "chicken",
];
const duration = (name) =>
  name === "explosion"
    ? 1.65
    : name === "fuse"
      ? 0.7
      : ["zombie", "cow", "sheep"].includes(name)
        ? 0.7
        : name === "death"
          ? 0.65
          : 0.2;
export function synthSound(name, sampleRate = 44100, seed = 1) {
  const length = Math.ceil(duration(name) * sampleRate),
    samples = new Float32Array(length);
  let last = 0,
    phase = 0;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return (seed / 4294967296) * 2 - 1;
  };
  for (let i = 0; i < length; i++) {
    const t = i / sampleRate,
      u = i / length,
      n = rnd();
    last = 0.94 * last + 0.06 * n;
    let v = 0;
    const fall = Math.exp(-u * 8);
    if (name === "explosion")
      v =
        (last * 6 + Math.sin(2 * Math.PI * (55 * t - 10 * t * t)) * 0.5) *
        Math.exp(-t * 3.8) *
        (1 - Math.exp(-t * 220));
    else if (name === "fuse" || name === "creeper")
      v = n * 0.21 * (0.6 + 0.4 * Math.sin(t * 85));
    else if (
      name.startsWith("step") ||
      name.startsWith("place") ||
      name.startsWith("mine") ||
      name === "break"
    ) {
      const wood = name.endsWith("wood"),
        grass = name.endsWith("grass");
      v =
        (n * (grass ? 0.45 : 0.18) +
          last * (wood ? 2 : 1.8) +
          Math.sin(2 * Math.PI * (wood ? 170 : 90) * t) * 0.22) *
        fall;
      if (name.startsWith("mine")) v *= 0.55;
    } else if (name === "bow")
      v =
        (n * 0.12 + Math.sin(2 * Math.PI * (800 * t - 1400 * t * t)) * 0.4) *
        fall;
    else if (name === "arrow_hit")
      v = (n * 0.3 + Math.sin(t * 2 * Math.PI * 1200) * 0.2) * fall;
    else if (name === "shield")
      v =
        (Math.sin(t * 2 * Math.PI * 290) +
          Math.sin(t * 2 * Math.PI * 713) * 0.4 +
          n * 0.1) *
        fall *
        0.45;
    else if (["pickup", "craft", "burp"].includes(name)) {
      const hz = name === "burp" ? 95 : name === "craft" ? 660 : 1100;
      v = Math.sin(t * 2 * Math.PI * hz * (u < 0.5 ? 1 : 1.5)) * fall * 0.35;
    } else if (
      [
        "zombie",
        "cow",
        "sheep",
        "pig",
        "chicken",
        "skeleton",
        "spider",
      ].includes(name)
    ) {
      const hz = {
        zombie: 80,
        cow: 105,
        sheep: 240,
        pig: 370,
        chicken: 650,
        skeleton: 1000,
        spider: 160,
      }[name];
      phase += (2 * Math.PI * (hz + Math.sin(t * 20) * hz * 0.18)) / sampleRate;
      v =
        (Math.sin(phase) +
          0.3 * Math.sin(phase * 2) +
          n * (name === "skeleton" ? 0.9 : 0.12)) *
        Math.sin(Math.PI * u) *
        0.22;
      if (name === "skeleton") v *= Math.exp(-((u * 4) % 1) * 8);
    } else if (name === "eat")
      v =
        (n * 0.32 + Math.sin(t * 2 * Math.PI * 150) * 0.2) *
        Math.exp(-((u * 3) % 1) * 5);
    else if (name === "hurt" || name === "death")
      v =
        (Math.sin(2 * Math.PI * (160 * t - 65 * t * t)) + n * 0.3) *
        Math.sin(Math.PI * u) *
        0.3;
    else if (name === "swing") v = n * 0.3 * Math.sin(Math.PI * u) ** 2;
    else v = (n * 0.4 + last * 2) * fall;
    samples[i] = Math.tanh(v) * 0.8;
  }
  return samples;
}
export class GameAudio {
  constructor() {
    this.context = null;
    this.listener = { x: 0, y: 0, z: 0 };
    this.yaw = 0;
    this.seed = 1;
    this.cache = new Map();
    this.last = new Map();
    this.settings = { volume: 0.65, mobs: 0.6, steps: 0.5, muted: false };
    try {
      Object.assign(
        this.settings,
        JSON.parse(localStorage.getItem(SETTINGS) || "{}"),
      );
    } catch {}
    this.played = 0;
  }
  unlock() {
    try {
      this.context ??= new AudioContext();
      this.context.resume().catch(() => {});
      return true;
    } catch {
      return false;
    }
  }
  save() {
    try {
      localStorage.setItem(SETTINGS, JSON.stringify(this.settings));
    } catch {}
  }
  play(name, position = null) {
    if (
      !SOUND_NAMES.includes(name) ||
      this.settings.muted ||
      !this.context ||
      this.context.state !== "running"
    )
      return false;
    const now = this.context.currentTime;
    if (now - (this.last.get(name) || -100) < (name === "fuse" ? 0.4 : 0.035))
      return false;
    this.last.set(name, now);
    const category = name.startsWith("step")
      ? this.settings.steps
      : [
            "zombie",
            "skeleton",
            "spider",
            "cow",
            "sheep",
            "pig",
            "chicken",
            "creeper",
          ].includes(name)
        ? this.settings.mobs
        : 1;
    let gain = this.settings.volume * category,
      pan = 0;
    if (position) {
      const dx = position.x - this.listener.x,
        dz = position.z - this.listener.z,
        dy = position.y - this.listener.y;
      const distance = Math.hypot(dx, dy, dz),
        range = name === "explosion" ? 180 : 35;
      gain *= Math.max(0, 1 - distance / range) ** 2;
      pan = Math.max(
        -1,
        Math.min(
          1,
          (dx * Math.cos(this.yaw) - dz * Math.sin(this.yaw)) /
            Math.max(3, distance),
        ),
      );
    }
    if (gain < 0.001) return false;
    const key = name + "-" + (++this.seed % 4);
    let buffer = this.cache.get(key);
    if (!buffer) {
      const samples = synthSound(name, this.context.sampleRate, this.seed),
        b = this.context.createBuffer(
          1,
          samples.length,
          this.context.sampleRate,
        );
      b.copyToChannel(samples, 0);
      buffer = b;
      this.cache.set(key, b);
    }
    const source = this.context.createBufferSource(),
      volume = this.context.createGain(),
      stereo = this.context.createStereoPanner();
    source.buffer = buffer;
    source.playbackRate.value = 0.96 + (this.seed % 7) * 0.013;
    volume.gain.value = gain;
    stereo.pan.value = pan;
    source.connect(volume).connect(stereo).connect(this.context.destination);
    source.start();
    source.onended = () => {
      source.disconnect();
      volume.disconnect();
      stereo.disconnect();
    };
    this.played++;
    return true;
  }
}
export const materialSound = (id) =>
  ["wood", "planks", "chest", "crafting_table", "bed"].includes(id)
    ? "wood"
    : ["grass", "dirt", "leaves", "wheat_crop", "sand"].includes(id)
      ? "grass"
      : "stone";

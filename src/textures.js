import * as THREE from "three";
export function texture(kind) {
  const c = document.createElement("canvas");
  c.width = c.height = 32;
  const ctx = c.getContext("2d");
  const palettes = {
    concrete: ["#c6c8b6", "#b3b5a6", "#d4d5c5"],
    glass: ["#648f99", "#86abb1", "#537a85"],
    roof: ["#9caba4", "#87948e", "#acb9ad"],
    grass: ["#759650", "#668a44", "#88a858"],
    stone: ["#969e96", "#858f87", "#acb4a8"],
    wood: ["#ad8b55", "#9a7644", "#c6a36a"],
    brick: ["#b77f63", "#ce9877", "#a56c51"],
    planks: ["#b49a60", "#917846", "#c5ae76"],
    dirt: ["#836247", "#71513c", "#a47b55"],
    sand: ["#d7c990", "#c7b880", "#eadca8"],
    leaves: ["#4e843e", "#36682c", "#70a554"],
    coal_ore: ["#858b84", "#252a26", "#454b43"],
    iron_ore: ["#8e9289", "#bc9270", "#d4b398"],
    crafting_table: ["#9e7447", "#553f2b", "#c19a63"],
    furnace: ["#787f78", "#3a423d", "#a1a69c"],
    chest: ["#ad803e", "#6b512a", "#c69b51"],
    bed: ["#bb4439", "#dfded0", "#90372f"],
    torch: ["#bc8a48", "#ffd36c", "#ff9b2c"],
    wheat_crop: ["#b6a846", "#7c9134", "#d5c968"],
    tnt: ["#c95036", "#e26545", "#b13f2d"],
  };
  const colors = palettes[kind] || palettes.concrete;
  ctx.fillStyle = colors[0];
  ctx.fillRect(0, 0, 32, 32);
  let seed = 42;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  for (let i = 0; i < 100; i++) {
    ctx.fillStyle = colors[1 + (i % 2)];
    ctx.globalAlpha = 0.4;
    ctx.fillRect(
      Math.floor(rand() * 16) * 2,
      Math.floor(rand() * 16) * 2,
      2,
      2,
    );
  }
  ctx.globalAlpha = 1;
  if (kind === "glass") {
    ctx.fillStyle = "#c6d9d0";
    ctx.fillRect(0, 0, 32, 2);
    ctx.fillRect(0, 0, 2, 32);
    ctx.fillStyle = "#9dc0c3";
    ctx.globalAlpha = 0.25;
    ctx.fillRect(6, 3, 3, 24);
    ctx.globalAlpha = 1;
  }
  if (kind === "brick") {
    ctx.fillStyle = "#d7c7a4";
    for (let y = 0; y < 32; y += 8) {
      ctx.fillRect(0, y, 32, 1);
      for (let x = y % 16 ? 8 : 0; x < 32; x += 16) ctx.fillRect(x, y, 1, 8);
    }
  }
  if (["wood", "planks", "crafting_table", "chest"].includes(kind)) {
    ctx.fillStyle = "#735735";
    for (let y = 7; y < 32; y += 8) ctx.fillRect(0, y, 32, 1);
  }
  if (kind === "tnt") {
    ctx.fillStyle = "#efe7cd";
    ctx.fillRect(0, 10, 32, 13);
    ctx.fillStyle = "#302b23";
    ctx.font = "bold 12px monospace";
    ctx.fillText("TNT", 4, 21);
    ctx.fillStyle = "#f2b481";
    ctx.fillRect(0, 0, 32, 3);
  }
  if (["crafting_table", "furnace", "chest"].includes(kind)) {
    ctx.strokeStyle = "#382f24";
    ctx.lineWidth = 2;
    ctx.strokeRect?.(2, 2, 28, 28);
    ctx.fillStyle = kind === "furnace" ? "#252c28" : "#d3b77a";
    ctx.fillRect(
      kind === "furnace" ? 7 : 14,
      kind === "furnace" ? 13 : 12,
      kind === "furnace" ? 18 : 4,
      kind === "furnace" ? 12 : 8,
    );
  }
  const t = new THREE.CanvasTexture(c);
  t.magFilter = THREE.NearestFilter;
  t.minFilter = THREE.NearestMipmapLinearFilter;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
export const PALETTE = [
  { id: "tnt", name: "TNT", color: "#d65b3d" },
  { id: "grass", name: "Grass", color: "#7b9a55" },
  { id: "stone", name: "Stone", color: "#9ba39a" },
  { id: "wood", name: "Oak", color: "#b68f55" },
  { id: "brick", name: "Brick", color: "#bc8061" },
  { id: "glass", name: "Glass", color: "#80adb7" },
];

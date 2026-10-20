export const ITEMS = {
  wood: {
    name: "Oak log",
    icon: "🪵",
    block: "wood",
    hardness: 1.5,
    tool: "axe",
  },
  planks: {
    name: "Oak planks",
    icon: "▤",
    block: "planks",
    hardness: 1,
    tool: "axe",
  },
  dirt: {
    name: "Dirt",
    icon: "🟫",
    block: "dirt",
    hardness: 0.65,
    tool: "shovel",
  },
  grass: {
    name: "Grass block",
    icon: "🌿",
    block: "grass",
    hardness: 0.7,
    tool: "shovel",
    drop: "dirt",
  },
  stone: {
    name: "Cobblestone",
    icon: "🪨",
    block: "stone",
    hardness: 2,
    tool: "pickaxe",
    tier: 1,
  },
  sand: {
    name: "Sand",
    icon: "🟨",
    block: "sand",
    hardness: 0.6,
    tool: "shovel",
  },
  glass: { name: "Glass", icon: "◇", block: "glass", hardness: 0.5 },
  brick: {
    name: "Bricks",
    icon: "🧱",
    block: "brick",
    hardness: 2,
    tool: "pickaxe",
    tier: 1,
  },
  leaves: { name: "Leaves", icon: "🍃", block: "leaves", hardness: 0.35 },
  coal_ore: {
    name: "Coal ore",
    icon: "⬛",
    block: "coal_ore",
    hardness: 2.5,
    tool: "pickaxe",
    tier: 1,
    drop: "coal",
  },
  iron_ore: {
    name: "Iron ore",
    icon: "◩",
    block: "iron_ore",
    hardness: 3,
    tool: "pickaxe",
    tier: 2,
  },
  crafting_table: {
    name: "Crafting table",
    icon: "▦",
    block: "crafting_table",
    hardness: 1.5,
    tool: "axe",
  },
  furnace: {
    name: "Furnace",
    icon: "▣",
    block: "furnace",
    hardness: 3,
    tool: "pickaxe",
    tier: 1,
  },
  chest: {
    name: "Chest",
    icon: "📦",
    block: "chest",
    hardness: 1.5,
    tool: "axe",
  },
  bed: { name: "Bed", icon: "🛏", block: "bed", hardness: 0.5 },
  torch: { name: "Torch", icon: "🔥", block: "torch", hardness: 0.1 },
  tnt: { name: "TNT", icon: "🧨", block: "tnt", hardness: 0.3 },
  wheat_crop: {
    name: "Wheat crop",
    icon: "🌾",
    block: "wheat_crop",
    hardness: 0.2,
  },
  stick: { name: "Stick", icon: "╱" },
  coal: { name: "Coal", icon: "◆" },
  iron: { name: "Iron ingot", icon: "▬" },
  gunpowder: { name: "Gunpowder", icon: "✦" },
  flint: { name: "Flint", icon: "◢" },
  wool: { name: "Wool", icon: "☁" },
  leather: { name: "Leather", icon: "▱" },
  seeds: { name: "Wheat seeds", icon: "🌱" },
  wheat: { name: "Wheat", icon: "🌾" },
  apple: { name: "Apple", icon: "🍎", food: 4, saturation: 2.4 },
  bread: { name: "Bread", icon: "🍞", food: 5, saturation: 6 },
  raw_beef: { name: "Raw beef", icon: "🥩", food: 3, saturation: 1.8 },
  cooked_beef: { name: "Cooked steak", icon: "🍖", food: 8, saturation: 12.8 },
  raw_pork: { name: "Raw pork", icon: "🥓", food: 3, saturation: 1.8 },
  cooked_pork: { name: "Cooked pork", icon: "🍗", food: 8, saturation: 12.8 },
};
Object.assign(ITEMS, {
  bow: { name: "Bow", icon: "🏹", stack: 1, durability: 192 },
  arrow: { name: "Arrow", icon: "➶" },
  shield: {
    name: "Shield",
    icon: "🛡",
    stack: 1,
    durability: 240,
    part: "offhand",
  },
  string: { name: "String", icon: "〰" },
  bone: { name: "Bone", icon: "🦴" },
  feather: { name: "Feather", icon: "🪶" },
  raw_chicken: { name: "Raw chicken", icon: "🍗", food: 2, saturation: 1 },
  cooked_chicken: {
    name: "Cooked chicken",
    icon: "🍗",
    food: 6,
    saturation: 7.2,
  },
});
for (const [material, tier, durability, speed, damage] of [
  ["wooden", 1, 59, 2, 4],
  ["stone", 2, 131, 4, 5],
  ["iron", 3, 250, 6, 6],
])
  for (const tool of ["pickaxe", "axe", "shovel", "sword"])
    ITEMS[material + "_" + tool] = {
      name: material[0].toUpperCase() + material.slice(1) + " " + tool,
      icon:
        tool === "sword"
          ? "⚔"
          : tool === "axe"
            ? "🪓"
            : tool === "pickaxe"
              ? "⛏"
              : "♠",
      stack: 1,
      tool,
      tier,
      durability,
      speed,
      damage: tool === "sword" ? damage : tool === "axe" ? damage + 1 : 2,
    };
ITEMS.flint_steel = {
  name: "Flint and steel",
  icon: "✧",
  stack: 1,
  durability: 64,
};
for (const [part, armor] of [
  ["helmet", 2],
  ["chestplate", 6],
  ["leggings", 5],
  ["boots", 2],
])
  ITEMS["iron_" + part] = {
    name: "Iron " + part,
    icon: "🛡",
    stack: 1,
    durability: 180,
    armor,
    part,
  };
ITEMS.rotten_flesh = {
  name: "Rotten flesh",
  icon: "🥀",
  food: 4,
  saturation: 0.8,
};
export const stackLimit = (id) => ITEMS[id]?.stack || 64;
export const makeStack = (id, count = 1) =>
  ITEMS[id]
    ? {
        id,
        count: Math.min(count, stackLimit(id)),
        ...(ITEMS[id].durability ? { durability: ITEMS[id].durability } : {}),
      }
    : null;
export const sameStack = (a, b) =>
  a?.id === b?.id && a?.durability === b?.durability;
export function addStack(slots, stack) {
  let left = stack.count;
  for (const s of slots)
    if (s && sameStack(s, stack)) {
      const n = Math.min(left, stackLimit(s.id) - s.count);
      s.count += n;
      left -= n;
      if (!left) return 0;
    }
  for (let i = 0; i < slots.length; i++)
    if (!slots[i]) {
      const n = Math.min(left, stackLimit(stack.id));
      slots[i] = { ...stack, count: n };
      left -= n;
      if (!left) return 0;
    }
  return left;
}
export function takeItems(slots, needs) {
  for (const [id, n] of Object.entries(needs))
    if (slots.reduce((s, x) => s + (x?.id === id ? x.count : 0), 0) < n)
      return false;
  for (const [id, n] of Object.entries(needs)) {
    let left = n;
    for (let i = 0; i < slots.length && left; i++)
      if (slots[i]?.id === id) {
        const amount = Math.min(left, slots[i].count);
        slots[i].count -= amount;
        left -= amount;
        if (!slots[i].count) slots[i] = null;
      }
  }
  return true;
}
export function clickSlot(slots, index, cursor, button = 0) {
  const target = slots[index];
  if (button === 2) {
    if (!cursor && target) {
      const n = Math.ceil(target.count / 2);
      cursor = { ...target, count: n };
      target.count -= n;
      if (!target.count) slots[index] = null;
    } else if (
      cursor &&
      (!target || sameStack(target, cursor)) &&
      (target?.count || 0) < stackLimit(cursor.id)
    ) {
      if (!target) slots[index] = { ...cursor, count: 1 };
      else target.count++;
      cursor.count--;
      if (!cursor.count) cursor = null;
    }
  } else if (!cursor) {
    cursor = target;
    slots[index] = null;
  } else if (!target) {
    slots[index] = cursor;
    cursor = null;
  } else if (sameStack(target, cursor)) {
    const n = Math.min(cursor.count, stackLimit(target.id) - target.count);
    target.count += n;
    cursor.count -= n;
    if (!cursor.count) cursor = null;
  } else {
    slots[index] = cursor;
    cursor = target;
  }
  return cursor;
}
export function miningTime(id, tool) {
  const def = ITEMS[id] || ITEMS.stone,
    held = ITEMS[tool?.id];
  let time = def.hardness || 1;
  if (held?.tool === def.tool) time /= held.speed || 1;
  else if (def.tool === "pickaxe") time *= 2.3;
  return Math.max(0.12, time);
}
export function canHarvest(id, tool) {
  const d = ITEMS[id] || ITEMS.stone;
  return (
    !d.tier ||
    (ITEMS[tool?.id]?.tool === "pickaxe" && ITEMS[tool.id].tier >= d.tier)
  );
}

import { ITEMS, makeStack, stackLimit, addStack, takeItems } from "./items.js";
export const RECIPES = [];
function recipe(id, pattern, keys, result, count = 1) {
  RECIPES.push({ id, pattern, keys, result, count, name: ITEMS[result].name });
}
recipe("planks", ["L"], { L: "wood" }, "planks", 4);
recipe("sticks", ["P", "P"], { P: "planks" }, "stick", 4);
recipe("table", ["PP", "PP"], { P: "planks" }, "crafting_table");
recipe("torch", ["C", "S"], { C: "coal", S: "stick" }, "torch", 4);
recipe("bread", ["WWW"], { W: "wheat" }, "bread");
recipe("furnace", ["CCC", "C C", "CCC"], { C: "stone" }, "furnace");
recipe("chest", ["PPP", "P P", "PPP"], { P: "planks" }, "chest");
recipe("bed", ["WWW", "PPP"], { W: "wool", P: "planks" }, "bed");
recipe("tnt", ["GSG", "SGS", "GSG"], { G: "gunpowder", S: "sand" }, "tnt");
recipe("flint_steel", ["I ", " F"], { I: "iron", F: "flint" }, "flint_steel");
recipe("bricks", ["SS", "SS"], { S: "stone" }, "brick", 4);
for (const [material, ingredient] of [
  ["wooden", "planks"],
  ["stone", "stone"],
  ["iron", "iron"],
]) {
  const k = { M: ingredient, S: "stick" };
  recipe(
    material + "_pickaxe",
    ["MMM", " S ", " S "],
    k,
    material + "_pickaxe",
  );
  recipe(material + "_axe", ["MM", "MS", " S"], k, material + "_axe");
  recipe(material + "_shovel", ["M", "S", "S"], k, material + "_shovel");
  recipe(material + "_sword", ["M", "M", "S"], k, material + "_sword");
}
recipe("helmet", ["III", "I I"], { I: "iron" }, "iron_helmet");
recipe("chestplate", ["I I", "III", "III"], { I: "iron" }, "iron_chestplate");
recipe("leggings", ["III", "I I", "I I"], { I: "iron" }, "iron_leggings");
recipe("boots", ["I I", "I I"], { I: "iron" }, "iron_boots");
recipe("bow", [" ST", "S T", " ST"], { S: "stick", T: "string" }, "bow");
recipe(
  "arrows",
  ["F", "S", "W"],
  { F: "flint", S: "stick", W: "feather" },
  "arrow",
  4,
);
recipe("shield", ["PIP", "PPP", " P "], { P: "planks", I: "iron" }, "shield");
function trim(grid, size) {
  let minX = size,
    minY = size,
    maxX = -1,
    maxY = -1;
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++)
      if (grid[y * size + x]) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
  if (maxX < 0) return [];
  return Array.from({ length: maxY - minY + 1 }, (_, y) =>
    Array.from(
      { length: maxX - minX + 1 },
      (_, x) => grid[(y + minY) * size + x + minX]?.id || null,
    ),
  );
}
export function matchRecipe(grid, size) {
  const shape = trim(grid, size);
  for (const r of RECIPES) {
    if (
      shape.length !== r.pattern.length ||
      shape[0]?.length !== r.pattern[0].length
    )
      continue;
    for (const mirror of [false, true])
      if (
        shape.every((row, y) =>
          row.every(
            (id, x) =>
              id ===
              (r.keys[r.pattern[y][mirror ? row.length - 1 - x : x]] || null),
          ),
        )
      )
        return r;
  }
  return null;
}
export function craftOutput(grid, size, cursor) {
  const r = matchRecipe(grid, size);
  if (!r) return { ok: false, cursor };
  const item = makeStack(r.result, r.count);
  if (
    cursor &&
    (!(cursor.id === item.id && cursor.durability === item.durability) ||
      cursor.count + item.count > stackLimit(item.id))
  )
    return { ok: false, cursor };
  for (let i = 0; i < size * size; i++)
    if (grid[i] && !--grid[i].count) grid[i] = null;
  return {
    ok: true,
    cursor: cursor ? { ...cursor, count: cursor.count + item.count } : item,
    recipe: r,
  };
}
export function fillRecipe(slots, grid, size, recipe) {
  if (recipe.pattern.length > size || recipe.pattern[0].length > size)
    return false;
  const next = slots.map((s) => (s ? { ...s } : null));
  for (const s of grid) if (s && addStack(next, s)) return false;
  const needs = {};
  for (const row of recipe.pattern)
    for (const key of row) {
      const id = recipe.keys[key];
      if (id) needs[id] = (needs[id] || 0) + 1;
    }
  if (!takeItems(next, needs)) return false;
  slots.splice(0, slots.length, ...next);
  grid.fill(null);
  recipe.pattern.forEach((row, y) =>
    [...row].forEach((key, x) => {
      if (recipe.keys[key]) grid[y * size + x] = makeStack(recipe.keys[key]);
    }),
  );
  return true;
}
export const SMELTING = {
  raw_beef: "cooked_beef",
  raw_pork: "cooked_pork",
  raw_chicken: "cooked_chicken",
  sand: "glass",
  iron_ore: "iron",
};
export const FUELS = { coal: 80, wood: 15, planks: 15, stick: 5 };
export function tickFurnace(f, dt) {
  if (f.paused) return;
  f.burn = Math.max(0, (f.burn || 0) - dt);
  const input = f.slots[0],
    result = SMELTING[input?.id],
    output = f.slots[2];
  const valid =
    !!result && (!output || (output.id === result && output.count < 64));
  if (!valid) {
    f.cook = 0;
    return;
  }
  if (!f.burn && FUELS[f.slots[1]?.id]) {
    f.burn = FUELS[f.slots[1].id];
    f.fuelTotal = f.burn;
    if (!--f.slots[1].count) f.slots[1] = null;
  }
  if (f.burn > 0) {
    f.cook = (f.cook || 0) + dt;
    if (f.cook >= 8) {
      f.cook -= 8;
      if (!--input.count) f.slots[0] = null;
      if (output) output.count++;
      else f.slots[2] = makeStack(result);
    }
  }
}

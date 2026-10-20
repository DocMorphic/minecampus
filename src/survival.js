import { ITEMS, makeStack, addStack } from "./items.js";
import { tickFurnace } from "./crafting.js";
function validStack(s) {
  return s && ITEMS[s.id] && Number.isInteger(s.count) && s.count > 0
    ? {
        ...makeStack(s.id, s.count),
        ...(ITEMS[s.id].durability
          ? {
              durability: Math.max(
                1,
                Math.min(
                  s.durability || ITEMS[s.id].durability,
                  ITEMS[s.id].durability,
                ),
              ),
            }
          : {}),
      }
    : null;
}
export class Survival {
  constructor(saved = {}) {
    this.mode = saved.mode === "creative" ? "creative" : "survival";
    this.inventory = Array.from({ length: 36 }, (_, i) =>
      validStack(saved.inventory?.[i]),
    );
    if (!saved.inventory) {
      [
        "wood",
        "wooden_pickaxe",
        "wooden_sword",
        "apple",
        "torch",
        "crafting_table",
        "dirt",
        "wheat",
        "flint_steel",
        "tnt",
        "sand",
        "stone",
        "coal",
        "bow",
        "arrow",
        "shield",
      ].forEach(
        (id, i) =>
          (this.inventory[i] = makeStack(
            id,
            {
              wood: 8,
              apple: 5,
              torch: 12,
              dirt: 16,
              wheat: 6,
              tnt: 3,
              sand: 8,
              stone: 8,
              coal: 4,
              arrow: 16,
            }[id] || 1,
          )),
      );
    }
    if (saved.inventory && (saved.version || 1) < 2) {
      this.add("bow");
      this.add("arrow", 16);
      this.add("shield");
    }
    this.health = Math.max(
      0,
      Math.min(20, Number.isFinite(saved.health) ? saved.health : 20),
    );
    this.hunger = Math.max(
      0,
      Math.min(20, Number.isFinite(saved.hunger) ? saved.hunger : 20),
    );
    this.saturation = Math.max(0, Math.min(20, saved.saturation ?? 5));
    this.exhaustion = 0;
    this.selected = Math.max(0, Math.min(8, saved.selected || 0));
    this.armor = {};
    for (const part of ["helmet", "chestplate", "leggings", "boots", "offhand"])
      this.armor[part] = validStack(saved.armor?.[part]);
    this.cursor = validStack(saved.cursor);
    this.grid = Array.from({ length: 9 }, (_, i) =>
      validStack(saved.grid?.[i]),
    );
    this.furnaces = saved.furnaces || {};
    this.chests = saved.chests || {};
    this.crops = saved.crops || {};
    this.respawn = saved.respawn || null;
    this.resourceAreas = saved.resourceAreas || [];
    this.time = Number.isFinite(saved.time) ? saved.time : 8;
    this.cycle = saved.cycle !== false;
    this.regen = 0;
    this.starve = 0;
    this.invulnerable = 0;
    this.attackCooldown = 0;
    this.xp = saved.xp || 0;
    this.eating = null;
  }
  get held() {
    return this.inventory[this.selected];
  }
  add(id, count = 1) {
    return addStack(this.inventory, { ...makeStack(id), count });
  }
  consume(index = this.selected, n = 1) {
    if (this.mode === "creative") return true;
    const s = this.inventory[index];
    if (!s || s.count < n) return false;
    s.count -= n;
    if (!s.count) this.inventory[index] = null;
    return true;
  }
  wear(index = this.selected) {
    return this.wearStack(this.inventory[index]);
  }
  wearStack(stack) {
    if (this.mode === "creative" || !stack || !ITEMS[stack.id].durability)
      return false;
    const index = this.inventory.indexOf(stack);
    if (index < 0) return false;
    if (--stack.durability <= 0) {
      this.inventory[index] = null;
      return true;
    }
    return false;
  }
  damage(amount) {
    if (
      amount <= 0 ||
      this.mode === "creative" ||
      this.health <= 0 ||
      this.invulnerable > 0
    )
      return 0;
    const armor = Object.values(this.armor).reduce(
      (n, s) => n + (ITEMS[s?.id]?.armor || 0),
      0,
    );
    const damage = Math.max(0.5, amount * (1 - Math.min(20, armor) * 0.04));
    this.health = Math.max(0, this.health - damage);
    this.invulnerable = 0.65;
    this.exhaustion += 0.3;
    for (const part of Object.keys(this.armor))
      if (this.armor[part] && --this.armor[part].durability <= 0)
        this.armor[part] = null;
    return damage;
  }
  beginEating() {
    if (this.eating || this.hunger >= 20 || !ITEMS[this.held?.id]?.food)
      return false;
    this.eating = { index: this.selected, id: this.held.id, time: 1.2 };
    return true;
  }
  tick(dt, { distance = 0, sprint = false } = {}) {
    this.invulnerable = Math.max(0, this.invulnerable - dt);
    this.attackCooldown = Math.max(0, this.attackCooldown - dt);
    for (const f of Object.values(this.furnaces)) tickFurnace(f, dt);
    for (const key of Object.keys(this.crops))
      this.crops[key] = Math.min(90, this.crops[key] + dt);
    if (this.mode === "creative" || this.health <= 0) return;
    this.exhaustion += dt * 0.004 + distance * (sprint ? 0.1 : 0.015);
    while (this.exhaustion >= 4) {
      this.exhaustion -= 4;
      if (this.saturation > 0)
        this.saturation = Math.max(0, this.saturation - 1);
      else this.hunger = Math.max(0, this.hunger - 1);
    }
    if (this.hunger >= 18 && this.health < 20) {
      this.regen += dt;
      if (this.regen >= 4) {
        this.health = Math.min(20, this.health + 1);
        this.exhaustion += 6;
        this.regen = 0;
      }
    } else this.regen = 0;
    if (this.hunger === 0 && this.health > 1) {
      this.starve += dt;
      if (this.starve >= 4) {
        this.health = Math.max(1, this.health - 1);
        this.starve = 0;
      }
    } else this.starve = 0;
    if (this.eating) {
      if (
        this.selected !== this.eating.index ||
        this.held?.id !== this.eating.id
      )
        this.eating = null;
      else if ((this.eating.time -= dt) <= 0) {
        const food = ITEMS[this.held.id];
        this.consume();
        this.hunger = Math.min(20, this.hunger + food.food);
        this.saturation = Math.min(
          this.hunger,
          this.saturation + food.saturation,
        );
        this.eating = null;
      }
    }
  }
  serialize() {
    return {
      version: 2,
      mode: this.mode,
      inventory: this.inventory,
      health: this.health,
      hunger: this.hunger,
      saturation: this.saturation,
      selected: this.selected,
      armor: this.armor,
      cursor: this.cursor,
      grid: this.grid,
      furnaces: this.furnaces,
      chests: this.chests,
      crops: this.crops,
      respawn: this.respawn,
      resourceAreas: this.resourceAreas,
      time: this.time,
      cycle: this.cycle,
      xp: this.xp,
    };
  }
}
export function migrateWorldSave(saved) {
  if (saved.blockSize === 1) return saved;
  const old = saved.blockSize || 3;
  if (old === 1) return saved;
  const placed = (saved.placed || []).map((b) => ({
    ...b,
    x: Math.floor((b.x + 0.5) * old),
    y: Math.floor((b.y + 0.5) * old),
    z: Math.floor((b.z + 0.5) * old),
  }));
  const removed = [];
  for (const key of saved.removed || []) {
    const [x, y, z] = key.split(",").map(Number);
    for (let a = 0; a < old; a++)
      for (let b = 0; b < old; b++)
        for (let c = 0; c < old; c++)
          removed.push(`${x * old + a},${y * old + b},${z * old + c}`);
  }
  return { ...saved, blockSize: 1, placed, removed };
}

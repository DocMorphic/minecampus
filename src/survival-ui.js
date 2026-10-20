import { ITEMS, makeStack, stackLimit, addStack, clickSlot } from "./items.js";
import { RECIPES, matchRecipe, craftOutput, fillRecipe } from "./crafting.js";
const $ = (id) => document.getElementById(id);
export function itemMarkup(stack) {
  if (!stack) return "";
  const d = ITEMS[stack.id];
  return `<span class="item-glyph">${d.icon}</span><span class="stack-count">${stack.count > 1 ? stack.count : ""}</span>${d.durability ? `<span class="durability" style="--durability:${Math.max(0, stack.durability / d.durability) * 100}%"></span>` : ""}`;
}
export class InventoryUI {
  constructor(state, { changed, select, drop, toast }) {
    this.state = state;
    this.changed = changed;
    this.select = select;
    this.drop = drop;
    this.toast = toast;
    this.size = 2;
    this.station = null;
    this.filter = "";
    this.lastSignature = "";
    this.renderHotbar();
    $("craft-result").onclick = () => {
      const result = craftOutput(state.grid, this.size, state.cursor);
      if (result.ok) {
        state.cursor = result.cursor;
        changed();
        this.render();
      }
    };
    $("recipe-search").oninput = () => {
      this.filter = $("recipe-search").value;
      this.renderRecipes();
    };
    document.addEventListener("pointermove", (e) => {
      $("carried-item").style.left = `${e.clientX + 12}px`;
      $("carried-item").style.top = `${e.clientY + 12}px`;
    });
  }
  slotButton(slots, index, label, outputOnly = false) {
    const s = slots[index],
      button = document.createElement("button");
    button.className = "inventory-slot";
    button.innerHTML = itemMarkup(s);
    button.title = s
      ? `${ITEMS[s.id].name} × ${s.count}${ITEMS[s.id].durability ? ` · ${s.durability} durability` : ""}`
      : label;
    button.setAttribute(
      "aria-label",
      s ? `${label}: ${ITEMS[s.id].name}, ${s.count}` : `${label}: empty`,
    );
    button.draggable = !!s && !outputOnly;
    const act = (e) => {
      e.preventDefault();
      if (outputOnly && this.state.cursor) return;
      if (e.shiftKey && slots === this.state.inventory && s) {
        const dest =
          index < 9
            ? this.state.inventory.slice(9)
            : this.state.inventory.slice(0, 9);
        const left = addStack(dest, { ...s });
        if (index < 9) this.state.inventory.splice(9, 27, ...dest);
        else this.state.inventory.splice(0, 9, ...dest);
        s.count = left;
        if (!left) slots[index] = null;
      } else
        this.state.cursor = clickSlot(
          slots,
          index,
          this.state.cursor,
          e.button,
        );
      this.changed();
      this.render();
    };
    button.onclick = act;
    button.oncontextmenu = act;
    button.ondragstart = (e) => {
      this.dragSource = { slots, index };
      e.dataTransfer.setData("text/plain", String(index));
    };
    button.ondragover = (e) => e.preventDefault();
    button.ondrop = (e) => {
      e.preventDefault();
      if (outputOnly) return;
      const source = this.dragSource;
      if (!source || (source.slots === slots && source.index === index)) return;
      const from = source.slots[source.index];
      if (!from) return;
      const old = slots[index];
      if (!old) {
        slots[index] = from;
        source.slots[source.index] = null;
      } else if (old.id === from.id && old.durability === from.durability) {
        const n = Math.min(from.count, stackLimit(old.id) - old.count);
        old.count += n;
        from.count -= n;
        if (!from.count) source.slots[source.index] = null;
      } else {
        slots[index] = from;
        source.slots[source.index] = old;
      }
      this.dragSource = null;
      this.changed();
      this.render();
    };
    return button;
  }
  renderHotbar() {
    const bar = $("hotbar");
    bar.replaceChildren();
    for (let i = 0; i < 9; i++) {
      const s = this.state.inventory[i],
        b = document.createElement("button");
      b.className =
        "inventory-slot" + (i === this.state.selected ? " selected" : "");
      b.innerHTML = `<small>${i + 1}</small>${itemMarkup(s)}`;
      b.setAttribute(
        "aria-label",
        s
          ? `Hotbar ${i + 1}: ${ITEMS[s.id].name}, ${s.count}`
          : `Hotbar ${i + 1}: empty`,
      );
      b.title = s ? ITEMS[s.id].name : "Empty";
      b.onclick = () => this.select(i);
      bar.append(b);
    }
    const held = this.state.held;
    $("held-name").textContent = held
      ? `${ITEMS[held.id].name}${this.state.mode === "creative" && ITEMS[held.id].block ? " · ∞" : ""}`
      : "Empty hand";
  }
  open(station) {
    this.station = station;
    this.size = station?.type === "crafting_table" ? 3 : 2;
    $("craft-size").textContent =
      station?.type === "crafting_table"
        ? "CRAFTING TABLE · 3 × 3"
        : "CRAFTING · 2 × 2";
    this.render();
    $("inventory").showModal();
    this.renderCursor();
  }
  render() {
    const state = this.state;
    $("inventory-title").textContent =
      this.station?.type === "chest"
        ? "Chest"
        : this.station?.type === "furnace"
          ? "Furnace"
          : "Inventory";
    $("player-slots").replaceChildren(
      ...state.inventory.map((_, i) =>
        this.slotButton(
          state.inventory,
          i,
          `${i < 9 ? "Hotbar" : "Backpack"} ${i < 9 ? i + 1 : i - 8}`,
        ),
      ),
    );
    const crafting =
      this.station?.type !== "chest" && this.station?.type !== "furnace";
    $("craft-panel").classList.toggle("hidden", !crafting);
    $("station-panel").classList.toggle("hidden", crafting);
    $("craft-grid").style.gridTemplateColumns = `repeat(${this.size},46px)`;
    $("craft-grid").replaceChildren(
      ...state.grid
        .slice(0, this.size * this.size)
        .map((_, i) =>
          this.slotButton(state.grid, i, `Crafting slot ${i + 1}`),
        ),
    );
    const r = matchRecipe(state.grid, this.size);
    $("craft-result").innerHTML = r
      ? itemMarkup(makeStack(r.result, r.count))
      : "→";
    $("craft-result").title = r
      ? `Craft ${r.count} ${r.name}`
      : "Arrange ingredients to craft";
    $("craft-result").disabled = !r;
    if (this.station?.type === "chest") {
      const slots = (state.chests[this.station.key] ??= Array(27).fill(null));
      $("station-slots").className = "chest-grid";
      $("station-slots").replaceChildren(
        ...slots.map((_, i) =>
          this.slotButton(slots, i, `Chest slot ${i + 1}`),
        ),
      );
      $("furnace-progress").classList.add("hidden");
    }
    if (this.station?.type === "furnace") {
      const f = (state.furnaces[this.station.key] ??= {
        slots: [null, null, null],
        burn: 0,
        cook: 0,
      });
      $("station-slots").className = "furnace-grid";
      $("station-slots").replaceChildren(
        ...f.slots.map((_, i) =>
          this.slotButton(
            f.slots,
            i,
            ["Smelting input", "Fuel", "Smelted output"][i],
            i === 2,
          ),
        ),
      );
      $("furnace-progress").classList.remove("hidden");
      $("furnace-progress").value = (f.cook || 0) / 8;
      $("furnace-note").textContent =
        "Input · Fuel · Output. Cooking takes 8 seconds while playing.";
    }
    $("armor-slots").replaceChildren(
      ...["helmet", "chestplate", "leggings", "boots", "offhand"].map(
        (part) => {
          const b = document.createElement("button");
          b.className = "inventory-slot";
          b.innerHTML = itemMarkup(state.armor[part]) || "🛡";
          b.title = part;
          b.setAttribute(
            "aria-label",
            `Armor ${part}: ${state.armor[part] ? ITEMS[state.armor[part].id].name : "empty"}`,
          );
          b.onclick = () => {
            const old = state.armor[part];
            if (state.cursor && ITEMS[state.cursor.id].part !== part) return;
            state.armor[part] = state.cursor;
            state.cursor = old;
            this.changed();
            this.render();
          };
          return b;
        },
      ),
    );
    this.renderRecipes();
    this.renderCursor();
    this.renderHotbar();
  }
  renderCursor() {
    const node = $("carried-item");
    node.innerHTML = itemMarkup(this.state.cursor);
    node.classList.toggle("hidden", !this.state.cursor || !$("inventory").open);
  }
  renderRecipes() {
    const area = $("recipe-list");
    area.replaceChildren();
    const creative = this.state.mode === "creative";
    $("recipe-heading").textContent = creative
      ? "CREATIVE CATALOG"
      : "RECIPE BOOK";
    const list = creative
      ? Object.keys(ITEMS)
          .filter((id) => id !== "wheat_crop")
          .map((id) => ({ result: id, name: ITEMS[id].name }))
      : RECIPES;
    for (const recipe of list) {
      if (!recipe.name.toLowerCase().includes(this.filter.toLowerCase()))
        continue;
      const b = document.createElement("button");
      b.className = "recipe-button";
      b.innerHTML = `<span>${ITEMS[recipe.result].icon}</span>${recipe.name}`;
      if (
        !creative &&
        (recipe.pattern.length > this.size ||
          recipe.pattern[0].length > this.size)
      ) {
        b.disabled = true;
        b.title = "Place and use a crafting table for a 3 × 3 grid";
      }
      b.onclick = () => {
        if (creative) {
          const left = this.state.add(recipe.result, stackLimit(recipe.result));
          if (left) this.toast("Inventory full.");
        } else if (
          !fillRecipe(this.state.inventory, this.state.grid, this.size, recipe)
        )
          this.toast("Missing ingredients or not enough inventory space.");
        this.changed();
        this.render();
      };
      area.append(b);
    }
  }
  close() {
    for (let i = 0; i < this.state.grid.length; i++) {
      const s = this.state.grid[i];
      if (s) {
        const left = addStack(this.state.inventory, s);
        if (left) this.drop({ ...s, count: left });
        this.state.grid[i] = null;
      }
    }
    if (this.state.cursor) {
      const left = addStack(this.state.inventory, this.state.cursor);
      if (left) this.drop({ ...this.state.cursor, count: left });
      this.state.cursor = null;
    }
    this.changed();
    $("carried-item").classList.add("hidden");
    $("inventory").close();
    this.renderHotbar();
  }
}

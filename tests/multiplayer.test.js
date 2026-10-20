import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import WebSocket from "ws";
import { attachRooms, validSnapshot } from "../server/rooms.js";
const snapshot = (version = 1) => ({
  version,
  placed: [],
  blasts: [],
  life: { mobs: [], drops: [] },
  time: 8,
  cycle: true,
  mode: "survival",
  shared: { chests: {}, furnaces: {}, crops: {}, resourceAreas: [] },
});
async function start(t, dataDir = null) {
  const server = http.createServer(),
    rooms = attachRooms(server, { dataDir });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const clients = [];
  const close = async () => {
    for (const c of clients) c.ws.terminate();
    await rooms.close();
    await new Promise((resolve) => server.close(resolve));
  };
  t.after(close);
  async function client() {
    const ws = new WebSocket(
        `ws://127.0.0.1:${server.address().port}/multiplayer`,
      ),
      queue = [],
      waiters = [];
    ws.on("message", (raw) => {
      const m = JSON.parse(raw);
      const i = waiters.findIndex((w) => w.type === m.type && w.match(m));
      if (i >= 0) {
        const w = waiters.splice(i, 1)[0];
        clearTimeout(w.timer);
        w.resolve(m);
      } else queue.push(m);
    });
    await once(ws, "open");
    const c = {
      ws,
      send: (m) => ws.send(JSON.stringify(m)),
      get: (type, match = () => true) =>
        new Promise((resolve, reject) => {
          const i = queue.findIndex((m) => m.type === type && match(m));
          if (i >= 0) {
            resolve(queue.splice(i, 1)[0]);
            return;
          }
          const timer = setTimeout(
            () => reject(Error(`Timed out waiting for ${type}`)),
            3000,
          );
          waiters.push({ type, match, resolve, timer });
        }),
    };
    clients.push(c);
    return c;
  }
  return { rooms, client, close };
}
async function host(h) {
  h.send({ type: "join", create: true, name: "Host" });
  const w = await h.get("welcome");
  h.send({ type: "snapshot", snapshot: snapshot() });
  return w;
}
test("two players share snapshots, movement, routed actions and targeted damage", async (t) => {
  const app = await start(t),
    h = await app.client(),
    hw = await host(h),
    g = await app.client();
  g.send({ type: "join", code: hw.code, name: "Guest" });
  const gw = await g.get("welcome");
  assert.equal(gw.snapshot.version, 1);
  await h.get("roster", (r) => r.players.length === 2);
  g.send({
    type: "pose",
    position: [-100, 0, 350],
    yaw: 1,
    health: 20,
    held: "wooden_sword",
    active: true,
  });
  const pose = await h.get("pose");
  assert.equal(pose.player.id, gw.id);
  assert.equal(pose.player.held, "wooden_sword");
  g.send({
    type: "action",
    request: "mine-1",
    action: { kind: "mine", key: "1,0,0" },
  });
  const action = await h.get("action");
  assert.equal(action.actor.id, gw.id);
  assert.equal(action.actor.held, "wooden_sword");
  h.send({
    type: "reply",
    request: action.request,
    ok: true,
    result: { removed: true },
  });
  assert.equal((await g.get("reply")).result.removed, true);
  h.send({
    type: "target",
    to: gw.id,
    event: "damage",
    data: { amount: 3, from: [0, 0, 0] },
  });
  assert.equal((await g.get("target")).data.amount, 3);
  h.send({
    type: "snapshot",
    snapshot: {
      ...snapshot(2),
      placed: [{ x: 1, y: 0, z: 0, type: "tnt" }],
      blasts: [{ position: [2, 0, 0], radius: 6 }],
    },
  });
  const received = await g.get("snapshot");
  assert.equal(received.snapshot.placed[0].type, "tnt");
  assert.equal(received.snapshot.blasts[0].radius, 6);
});
test("late joins receive destruction and host disconnection promotes a survivor", async (t) => {
  const app = await start(t),
    h = await app.client(),
    hw = await host(h),
    g = await app.client();
  h.send({
    type: "snapshot",
    snapshot: {
      ...snapshot(4),
      blasts: [{ position: [0, 0, 0], radius: 6 }],
      life: {
        mobs: [
          {
            id: "skeleton-1",
            kind: "skeleton",
            position: [2, 0, 0],
            health: 20,
          },
        ],
        drops: [],
      },
    },
  });
  g.send({ type: "join", code: hw.code, name: "Guest" });
  const gw = await g.get("welcome");
  assert.equal(gw.snapshot.version, 4);
  assert.equal(gw.snapshot.life.mobs[0].kind, "skeleton");
  h.ws.close();
  const authority = await g.get("authority");
  assert.equal(authority.snapshot.version, 4);
  const roster = await g.get("roster", (r) => r.players.length === 1);
  assert.equal(roster.host, gw.id);
  g.send({ type: "snapshot", snapshot: snapshot(5) });
  const late = await app.client();
  late.send({ type: "join", code: hw.code, name: "Late" });
  assert.equal((await late.get("welcome")).snapshot.version, 5);
});
test("rooms are isolated and guests cannot replace authoritative world state", async (t) => {
  const app = await start(t),
    h = await app.client(),
    hw = await host(h),
    other = await app.client(),
    ow = await host(other);
  assert.notEqual(hw.code, ow.code);
  const g = await app.client();
  g.send({ type: "join", code: hw.code, name: "Guest" });
  await g.get("welcome");
  g.send({ type: "snapshot", snapshot: snapshot(99) });
  const late = await app.client();
  late.send({ type: "join", code: hw.code, name: "Late" });
  assert.equal((await late.get("welcome")).snapshot.version, 1);
  assert.equal(app.rooms.rooms.get(ow.code).players.size, 1);
});
test("unknown rooms and duplicate player identities return useful errors", async (t) => {
  const app = await start(t),
    h = await app.client(),
    hw = await host(h),
    g = await app.client();
  g.send({ type: "join", code: "ZZZZZZZZ", name: "Nope" });
  assert.match((await g.get("error")).error, /not found/);
  g.send({ type: "join", code: hw.code, name: "Clone", token: hw.token });
  assert.match((await g.get("error")).error, /already connected/);
});
test("room state and individual inventory profiles persist to disk", async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "minecampus-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const app = await start(t, dir),
    h = await app.client(),
    hw = await host(h);
  h.send({
    type: "profile",
    profile: {
      version: 2,
      inventory: [{ id: "arrow", count: 12 }],
      health: 17,
    },
  });
  await h.get("profile_saved");
  h.ws.close();
  await once(h.ws, "close");
  await app.rooms.rooms.get(hw.code).persistence;
  const newApp = await start(t, dir),
    g = await newApp.client();
  g.send({ type: "join", code: hw.code, name: "Back", token: hw.token });
  const welcome = await g.get("welcome");
  assert.equal(welcome.profile.inventory[0].count, 12);
  assert.equal(welcome.profile.health, 17);
  assert.equal(welcome.snapshot.time, 8);
});
test("invalid geometry and malformed messages cannot poison snapshots or crash rooms", async (t) => {
  assert.equal(
    validSnapshot({
      ...snapshot(),
      placed: [{ x: NaN, y: 0, z: 0, type: "tnt" }],
    }),
    false,
  );
  assert.equal(
    validSnapshot({
      ...snapshot(),
      blasts: [{ position: [0, 0, 0], radius: 9000 }],
    }),
    false,
  );
  const app = await start(t),
    h = await app.client(),
    hw = await host(h);
  h.ws.send("this is not JSON");
  h.send({ type: "snapshot", snapshot: { ...snapshot(90), time: NaN } });
  const g = await app.client();
  g.send({ type: "join", code: hw.code, name: "Still works" });
  assert.equal((await g.get("welcome")).snapshot.version, 1);
});

import { randomBytes, randomUUID } from "node:crypto";
import { WebSocketServer, WebSocket } from "ws";
import { mkdir, readFile, writeFile, rename } from "node:fs/promises";
import { ITEMS } from "../src/items.js";
export const ROOM_CODE = /^[A-Z0-9]{8}$/;
const vec = (v) =>
  Array.isArray(v) &&
  v.length === 3 &&
  v.every((n) => Number.isFinite(n) && Math.abs(n) < 5000);
export function validSnapshot(s) {
  return (
    !!s &&
    Array.isArray(s.placed) &&
    s.placed.length <= 12000 &&
    s.placed.every(
      (b) =>
        b &&
        [b.x, b.y, b.z].every(Number.isInteger) &&
        Math.abs(b.x) < 1000 &&
        Math.abs(b.z) < 1000 &&
        b.y >= -30 &&
        b.y <= 150 &&
        ITEMS[b.type]?.block,
    ) &&
    Array.isArray(s.blasts) &&
    s.blasts.length <= 2048 &&
    s.blasts.every(
      (b) =>
        vec(b.position) &&
        Number.isFinite(b.radius) &&
        b.radius > 0 &&
        b.radius <= 32,
    ) &&
    s.life &&
    Array.isArray(s.life.mobs) &&
    s.life.mobs.length <= 64 &&
    Array.isArray(s.life.drops) &&
    s.life.drops.length <= 512 &&
    Number.isFinite(s.time) &&
    s.time >= 0 &&
    s.time < 24
  );
}
export function attachRooms(server, { dataDir = null, maxRooms = 100 } = {}) {
  const wss = new WebSocketServer({
      noServer: true,
      maxPayload: 2 * 1024 * 1024,
    }),
    rooms = new Map();
  const send = (ws, msg) => {
    if (ws.readyState === WebSocket.OPEN && ws.bufferedAmount < 3 * 1024 * 1024)
      ws.send(JSON.stringify(msg));
  };
  const publicPlayer = (p) => ({ id: p.id, name: p.name, ...p.pose });
  const broadcast = (room, msg, except) => {
    for (const p of room.players.values()) if (p.id !== except) send(p.ws, msg);
  };
  const roster = (room) =>
    broadcast(room, {
      type: "roster",
      host: room.host,
      players: [...room.players.values()].map(publicPlayer),
    });
  const persist = (room) => {
    if (!dataDir || !room.snapshot) return Promise.resolve();
    const contents = JSON.stringify({
      snapshot: room.snapshot,
      profiles: [...room.profiles],
    });
    room.persistence = (room.persistence || Promise.resolve()).then(
      async () => {
        try {
          await mkdir(dataDir, { recursive: true });
          const dest = `${dataDir}/${room.code}.json`;
          await writeFile(dest + ".tmp", contents);
          await rename(dest + ".tmp", dest);
        } catch (e) {
          console.error("Room save failed:", e.message);
        }
      },
    );
    return room.persistence;
  };
  const leave = (ws) => {
    const room = ws.room,
      p = ws.player;
    if (!room || !p) return;
    room.players.delete(p.id);
    for (const [id, r] of room.pending)
      if (r.actor === p.id || r.host === p.id) {
        const target = room.players.get(r.actor);
        if (target)
          send(target.ws, {
            type: "reply",
            request: id,
            ok: false,
            error: "Player disconnected. Try again.",
          });
        room.pending.delete(id);
      }
    broadcast(room, { type: "departed", id: p.id });
    if (room.host === p.id) {
      room.host = room.players.keys().next().value || null;
      const next = room.players.get(room.host);
      if (next) send(next.ws, { type: "authority", snapshot: room.snapshot });
    }
    roster(room);
    persist(room);
    ws.room = null;
    ws.player = null;
    if (!room.players.size) room.emptySince = Date.now();
  };
  server.on("upgrade", (req, socket, head) => {
    if (new URL(req.url, "http://localhost").pathname !== "/multiplayer")
      return;
    const origin = req.headers.origin;
    if (origin) {
      try {
        if (new URL(origin).host !== req.headers.host) {
          socket.destroy();
          return;
        }
      } catch {
        socket.destroy();
        return;
      }
    }
    wss.handleUpgrade(req, socket, head, (ws) =>
      wss.emit("connection", ws, req),
    );
  });
  wss.on("connection", (ws) => {
    ws.alive = true;
    ws.on("pong", () => (ws.alive = true));
    ws.count = 0;
    ws.window = Date.now();
    const joinTimeout = setTimeout(() => {
      if (!ws.room) ws.close(1008, "Join a room first");
    }, 10000);
    joinTimeout.unref();
    ws.on("message", async (raw) => {
      try {
        if (Date.now() - ws.window > 1000) {
          ws.window = Date.now();
          ws.count = 0;
        }
        if (++ws.count > (ws.player?.id === ws.room?.host ? 300 : 80)) {
          ws.close(1008, "Too many messages");
          return;
        }
        const m = JSON.parse(raw.toString());
        if (!m || typeof m.type !== "string") return;
        if (m.type === "join") {
          if (ws.room) return;
          const code = m.create
            ? randomBytes(6).toString("hex").slice(0, 8).toUpperCase()
            : String(m.code || "").toUpperCase();
          if (!ROOM_CODE.test(code)) {
            send(ws, {
              type: "error",
              error: "Use the eight-character room code.",
            });
            return;
          }
          let room = rooms.get(code);
          if (!room && dataDir && !m.create) {
            try {
              const saved = JSON.parse(
                await readFile(`${dataDir}/${code}.json`, "utf8"),
              );
              if (validSnapshot(saved.snapshot))
                room = {
                  code,
                  players: new Map(),
                  host: null,
                  snapshot: saved.snapshot,
                  profiles: new Map(saved.profiles || []),
                  pending: new Map(),
                };
            } catch {}
          }
          if (!room && !m.create) {
            send(ws, {
              type: "error",
              error: "Room not found. Check the code and server address.",
            });
            return;
          }
          if (!room) {
            if (rooms.size >= maxRooms) {
              send(ws, { type: "error", error: "Server room limit reached." });
              return;
            }
            room = {
              code,
              players: new Map(),
              host: null,
              snapshot: null,
              profiles: new Map(),
              pending: new Map(),
            };
          }
          if (room.players.size >= 8) {
            send(ws, {
              type: "error",
              error: "This room already has eight players.",
            });
            return;
          }
          if (ws.readyState !== WebSocket.OPEN) return;
          room = rooms.get(code) || room;
          rooms.set(code, room);
          const token = /^[a-f0-9-]{36}$/.test(m.token || "")
            ? m.token
            : randomUUID();
          const existing = [...room.players.values()].find(
            (p) => p.token === token,
          );
          if (existing) {
            send(ws, {
              type: "error",
              error:
                "This player is already connected. Use a different browser profile.",
            });
            return;
          }
          const p = {
            id: randomUUID(),
            token,
            name:
              String(m.name || "Steve")
                .replace(/[\u0000-\u001f<>]/g, "")
                .trim()
                .slice(0, 20) || "Steve",
            ws,
            pose: {
              position: [-100, 30, 350],
              yaw: -1.3,
              pitch: 0,
              health: 20,
              mode: "survival",
              held: null,
              active: false,
            },
          };
          ws.player = p;
          ws.room = room;
          room.players.set(p.id, p);
          room.host ??= p.id;
          send(ws, {
            type: "welcome",
            id: p.id,
            token,
            code,
            host: room.host,
            snapshot: room.snapshot,
            profile: room.profiles.get(token) || null,
          });
          roster(room);
          return;
        }
        const room = ws.room,
          p = ws.player;
        if (!room || !p) return;
        if (m.type === "pose" && vec(m.position) && Number.isFinite(m.yaw)) {
          p.pose = {
            position: m.position,
            yaw: m.yaw,
            pitch: Number.isFinite(m.pitch) ? m.pitch : 0,
            health: Math.max(0, Math.min(20, Number(m.health) || 0)),
            held: ITEMS[m.held] ? m.held : null,
            mode: m.mode === "creative" ? "creative" : "survival",
            active: m.active === true,
            blocking: m.blocking === true,
          };
          broadcast(room, { type: "pose", player: publicPlayer(p) }, p.id);
        } else if (
          m.type === "snapshot" &&
          room.host === p.id &&
          validSnapshot(m.snapshot)
        ) {
          room.snapshot = m.snapshot;
          broadcast(room, { type: "snapshot", snapshot: m.snapshot }, p.id);
          if (!room.savedAt || Date.now() - room.savedAt > 5000) {
            room.savedAt = Date.now();
            persist(room);
          }
        } else if (
          m.type === "action" &&
          typeof m.request === "string" &&
          m.request.length < 70 &&
          m.action &&
          JSON.stringify(m.action).length < 16000
        ) {
          const host = room.players.get(room.host);
          if (!host || !room.snapshot) {
            send(ws, {
              type: "reply",
              request: m.request,
              ok: false,
              error: "Host is preparing the world.",
            });
            return;
          }
          if (room.pending.size > 250) return;
          room.pending.set(m.request, {
            actor: p.id,
            host: host.id,
            time: Date.now(),
          });
          send(host.ws, {
            type: "action",
            request: m.request,
            actor: publicPlayer(p),
            action: m.action,
          });
        } else if (m.type === "reply" && p.id === room.host) {
          const pending = room.pending.get(m.request);
          if (!pending || pending.host !== p.id) return;
          room.pending.delete(m.request);
          const actor = room.players.get(pending.actor);
          if (actor)
            send(actor.ws, {
              type: "reply",
              request: m.request,
              ok: m.ok === true,
              result: m.result,
              error: String(m.error || "").slice(0, 160),
            });
        } else if (
          m.type === "target" &&
          p.id === room.host &&
          ["damage", "loot", "sound"].includes(m.event)
        ) {
          const to = room.players.get(m.to);
          if (to) send(to.ws, { type: "target", event: m.event, data: m.data });
        } else if (
          m.type === "sound" &&
          typeof m.sound === "string" &&
          m.sound.length < 40 &&
          vec(m.position)
        )
          broadcast(
            room,
            { type: "sound", sound: m.sound, position: m.position },
            p.id,
          );
        else if (
          m.type === "profile" &&
          m.profile &&
          JSON.stringify(m.profile).length < 60000
        ) {
          room.profiles.set(p.token, m.profile);
          await persist(room);
          send(ws, { type: "profile_saved" });
        }
      } catch {
        /* Malformed messages cannot crash the room server. */
      }
    });
    ws.on("close", () => {
      clearTimeout(joinTimeout);
      leave(ws);
    });
    ws.on("error", () => {});
  });
  const heartbeat = setInterval(() => {
    for (const ws of wss.clients) {
      if (!ws.alive) {
        ws.terminate();
        continue;
      }
      ws.alive = false;
      ws.ping();
    }
    for (const [code, room] of rooms) {
      for (const [id, pending] of room.pending)
        if (Date.now() - pending.time > 8000) {
          const p = room.players.get(pending.actor);
          if (p)
            send(p.ws, {
              type: "reply",
              request: id,
              ok: false,
              error: "Host did not respond. Try again.",
            });
          room.pending.delete(id);
        }
      if (!room.players.size && Date.now() - room.emptySince > 30 * 60000)
        rooms.delete(code);
    }
  }, 10000);
  heartbeat.unref();
  return {
    rooms,
    wss,
    async close() {
      clearInterval(heartbeat);
      await Promise.all([...rooms.values()].map(persist));
      for (const ws of wss.clients) ws.terminate();
      await new Promise((resolve) => wss.close(resolve));
    },
  };
}

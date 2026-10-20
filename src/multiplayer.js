import { newId } from "./id.js";
import * as THREE from "three";
import { createSteve } from "./steve.js";
export class Multiplayer {
  constructor(
    scene,
    { welcome, snapshot, action, target, sound, status, departed, authority },
  ) {
    this.scene = scene;
    Object.assign(this, {
      onWelcome: welcome,
      onSnapshot: snapshot,
      onAction: action,
      onTarget: target,
      onSound: sound,
      onStatus: status,
      onDeparted: departed,
      onAuthority: authority,
    });
    this.socket = null;
    this.id = null;
    this.host = null;
    this.code = null;
    this.players = new Map();
    this.avatars = new Map();
    this.pending = new Map();
    this.connected = false;
    this.timer = 0;
    this.version = 0;
  }
  get isHost() {
    return this.connected && this.host === this.id;
  }
  connect({ create = false, code = "", name = "Steve" }) {
    if (this.socket) this.socket.close();
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/multiplayer`,
      );
      this.socket = ws;
      let settled = false;
      const timer = setTimeout(() => {
        if (!settled) {
          settled = true;
          reject(
            Error(
              "Could not reach the multiplayer server. Start with npm run dev or npm start.",
            ),
          );
          ws.close();
        }
      }, 10000);
      const storageKey = `minecampus-token-${code}-${name}`;
      ws.onopen = () =>
        ws.send(
          JSON.stringify({
            type: "join",
            create,
            code,
            name,
            token: localStorage.getItem(storageKey),
          }),
        );
      ws.onmessage = (event) => {
        let m;
        try {
          m = JSON.parse(event.data);
        } catch {
          return;
        }
        if (m.type === "error") {
          if (!settled) {
            settled = true;
            clearTimeout(timer);
            reject(Error(m.error));
            ws.close();
          } else this.onStatus(m.error);
          return;
        }
        if (m.type === "welcome") {
          settled = true;
          clearTimeout(timer);
          this.connected = true;
          this.id = m.id;
          this.host = m.host;
          this.code = m.code;
          localStorage.setItem(`minecampus-token-${m.code}-${name}`, m.token);
          this.onWelcome(m);
          resolve(m);
        } else if (m.type === "roster") {
          this.host = m.host;
          const ids = new Set();
          for (const p of m.players) {
            this.players.set(p.id, p);
            ids.add(p.id);
          }
          for (const id of this.players.keys())
            if (!ids.has(id)) this.removePlayer(id);
          this.onStatus();
        } else if (m.type === "pose") {
          this.players.set(m.player.id, m.player);
        } else if (m.type === "snapshot" && !this.isHost) {
          this.onSnapshot(m.snapshot);
        } else if (m.type === "action" && this.isHost) {
          Promise.resolve()
            .then(() => this.onAction(m.action, m.actor))
            .then((result) =>
              this.send({
                type: "reply",
                request: m.request,
                ok: true,
                result,
              }),
            )
            .catch((e) =>
              this.send({
                type: "reply",
                request: m.request,
                ok: false,
                error: e.message,
              }),
            );
        } else if (m.type === "reply") {
          const p = this.pending.get(m.request);
          if (p) {
            clearTimeout(p.timer);
            this.pending.delete(m.request);
            m.ok
              ? p.resolve(m.result)
              : p.reject(Error(m.error || "Action rejected."));
          }
        } else if (m.type === "target") this.onTarget(m.event, m.data);
        else if (m.type === "sound") this.onSound(m.sound, m.position);
        else if (m.type === "departed") {
          this.removePlayer(m.id);
          this.onDeparted(m.id);
        } else if (m.type === "authority") {
          this.host = this.id;
          this.onAuthority(m.snapshot);
          this.onStatus();
        }
      };
      ws.onerror = () => {};
      ws.onclose = () => {
        clearTimeout(timer);
        this.connected = false;
        for (const p of this.pending.values()) {
          clearTimeout(p.timer);
          p.reject(Error("Disconnected."));
        }
        this.pending.clear();
        if (!settled) {
          settled = true;
          reject(
            Error(
              "Multiplayer server unavailable. Start with npm run dev or npm start.",
            ),
          );
        } else
          this.onStatus(
            "Disconnected. Your solo world is safe; leave the room to return to it.",
          );
      };
    });
  }
  send(m) {
    if (this.socket?.readyState === WebSocket.OPEN)
      this.socket.send(JSON.stringify(m));
  }
  request(action) {
    if (this.isHost)
      return Promise.resolve().then(() =>
        this.onAction(action, { id: this.id, ...this.players.get(this.id) }),
      );
    return new Promise((resolve, reject) => {
      if (!this.connected) {
        reject(Error("Not connected."));
        return;
      }
      const request = newId(),
        timer = setTimeout(() => {
          this.pending.delete(request);
          reject(Error("The host did not respond."));
        }, 8000);
      this.pending.set(request, { resolve, reject, timer });
      this.send({ type: "action", request, action });
    });
  }
  target(to, event, data) {
    if (to === this.id) this.onTarget(event, data);
    else this.send({ type: "target", to, event, data });
  }
  publish(snapshot) {
    this.send({ type: "snapshot", snapshot });
  }
  pose(p) {
    this.players.set(this.id, {
      id: this.id,
      name: this.players.get(this.id)?.name || "Steve",
      ...p,
    });
    this.send({ type: "pose", ...p });
  }
  removePlayer(id) {
    this.players.delete(id);
    const a = this.avatars.get(id);
    if (a) {
      this.scene.remove(a.root);
      a.root.traverse((o) => {
        o.geometry?.dispose();
        if (o.material)
          for (const m of Array.isArray(o.material)
            ? o.material
            : [o.material]) {
            m.map?.dispose();
            m.dispose();
          }
      });
      this.avatars.delete(id);
    }
  }
  update(dt, time) {
    for (const p of this.players.values()) {
      if (p.id === this.id || !p.position) continue;
      let avatar = this.avatars.get(p.id);
      if (!avatar) {
        avatar = createSteve();
        const c = document.createElement("canvas");
        c.width = 256;
        c.height = 64;
        const x = c.getContext("2d");
        x.fillStyle = "#102219cc";
        x.fillRect(0, 0, 256, 64);
        x.font = "bold 25px sans-serif";
        x.fillStyle = "#e4f58f";
        x.textAlign = "center";
        x.fillText(p.name, 128, 41);
        const label = new THREE.Sprite(
          new THREE.SpriteMaterial({
            map: new THREE.CanvasTexture(c),
            depthTest: false,
          }),
        );
        label.position.y = 3.45;
        label.scale.set(3.7, 0.9, 1);
        avatar.root.add(label);
        avatar.root.position.set(...p.position);
        this.scene.add(avatar.root);
        this.avatars.set(p.id, avatar);
      }
      avatar.root.visible = p.active && p.health > 0;
      const target = new THREE.Vector3(...p.position),
        moving = avatar.root.position.distanceTo(target) > 0.03;
      avatar.root.position.lerp(target, 1 - Math.exp(-dt * 15));
      avatar.root.rotation.y = p.yaw + Math.PI;
      avatar.animate(time, moving);
    }
  }
  leave() {
    this.send({ type: "profile", profile: null });
    this.socket?.close();
  }
}

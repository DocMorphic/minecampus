import http from "node:http";
import { networkInterfaces } from "node:os";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { attachRooms } from "./rooms.js";
const root = fileURLToPath(new URL("../", import.meta.url)),
  production = process.argv.includes("--production");
let vite;
const types = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".webp": "image/webp",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".bin": "application/octet-stream",
};
const server = http.createServer(async (req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true, rooms: rooms.rooms.size }));
    return;
  }
  if (vite) {
    vite.middlewares(req, res);
    return;
  }
  try {
    const base = resolve(root, "dist"),
      url = new URL(req.url, "http://localhost"),
      path = resolve(
        base,
        "." +
          decodeURIComponent(
            url.pathname === "/" ? "/index.html" : url.pathname,
          ),
      );
    if (!path.startsWith(base + sep)) {
      res.writeHead(403);
      res.end();
      return;
    }
    const meta = await stat(path);
    if (!meta.isFile()) throw Error();
    res.writeHead(200, {
      "content-type": types[extname(path)] || "application/octet-stream",
      "content-length": meta.size,
      "x-content-type-options": "nosniff",
      "cache-control": url.pathname.startsWith("/realworld/")
        ? "public,max-age=86400"
        : "no-cache",
    });
    createReadStream(path).pipe(res);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
});
const rooms = attachRooms(server, {
  dataDir: resolve(root, ".minecampus/rooms"),
});
if (!production) {
  const { createServer } = await import("vite");
  vite = await createServer({
    root,
    server: { middlewareMode: true, hmr: { server } },
  });
}
const host = process.env.HOST || (production ? "0.0.0.0" : "127.0.0.1"),
  port = Number(process.env.PORT || 5173);
server.listen(port, host, () => {
  const actual = server.address().port;
  console.log(
    `Minecampus ${production ? "production" : "development"} + multiplayer: http://127.0.0.1:${actual}`,
  );
  if (host === "0.0.0.0")
    for (const [name, addresses] of Object.entries(networkInterfaces()))
      for (const address of addresses || [])
        if (address.family === "IPv4" && !address.internal)
          console.log(`LAN (${name}): http://${address.address}:${actual}`);
});

async function close() {
  await rooms.close();
  await vite?.close();
  server.close(() => process.exit(0));
}
process.on("SIGTERM", close);
process.on("SIGINT", close);

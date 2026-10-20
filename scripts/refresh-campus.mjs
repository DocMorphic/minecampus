import { writeFile } from "node:fs/promises";
const bbox = "48.257,11.659,48.273,11.682";
const query = `[out:json][timeout:90];(way["building"](${bbox});way["highway"](${bbox});way["landuse"](${bbox});way["natural"="water"](${bbox}););out geom;`;
const endpoint =
  process.argv[2] || "https://overpass.kumi.systems/api/interpreter";
const url = new URL(endpoint);
url.searchParams.set("data", query);
const response = await fetch(url, { signal: AbortSignal.timeout(120000) });
if (!response.ok) throw Error(`Overpass returned ${response.status}`);
const data = await response.json();
if (!data.elements?.length)
  throw Error("Overpass returned no features; preserving existing data.");
data.source = "OpenStreetMap contributors";
data.license = "ODbL-1.0";
data.bbox = [11.659, 48.257, 11.682, 48.273];
data.retrieved = new Date().toISOString().slice(0, 10);
await writeFile(
  new URL("../public/data/garching-osm.json", import.meta.url),
  JSON.stringify(data),
);
console.log(`Saved ${data.elements.length} real campus features.`);

import { project } from "./geo.js";
const DEFINITIONS = [
  {
    id: "cit",
    way: 27917482,
    marker: "A",
    name: "Informatik & Mathematik",
    short: "CIT",
    detail: "Solar roofs, courtyards, and a familiar place to start.",
    altitude: 60,
    targetHeight: 16,
    offset: 115,
  },
  {
    id: "studitum",
    way: 476929995,
    marker: "B",
    name: "StudiTUM",
    short: "StudiTUM",
    detail: "The student house at the heart of campus.",
    altitude: 48,
    targetHeight: 15,
    offset: 95,
  },
  {
    id: "u6",
    way: 370169707,
    marker: "C",
    name: "Garching-Forschungszentrum",
    short: "U6",
    detail: "Drop in above the campus U-Bahn stop.",
    altitude: 42,
    targetHeight: 3,
    offset: 95,
  },
  {
    id: "ias",
    way: 308082263,
    marker: "D",
    name: "Institute for Advanced Study",
    short: "IAS",
    detail: "A new angle on the northern campus.",
    altitude: 52,
    targetHeight: 20,
    offset: 100,
  },
  {
    id: "tower",
    way: 117881300,
    marker: "E",
    name: "Oskar von Miller tower",
    short: "TUrM",
    detail: "A high perch on the western edge of campus.",
    altitude: 105,
    targetHeight: 48,
    offset: 125,
  },
];
export function campusLandmarks(features) {
  return DEFINITIONS.flatMap((def) => {
    const f = features.find((f) => f.id === def.way);
    if (!f?.geometry?.length) return [];
    const lat = f.geometry.reduce((n, p) => n + p.lat, 0) / f.geometry.length,
      lon = f.geometry.reduce((n, p) => n + p.lon, 0) / f.geometry.length;
    const [x, z] = project(lat, lon),
      spawn = [x, def.altitude, z + def.offset];
    return [
      {
        ...def,
        lat,
        lon,
        x,
        z,
        spawn,
        yaw: 0,
        pitch: Math.atan2(def.targetHeight - def.altitude, def.offset),
      },
    ];
  });
}
export function nearestLandmark(landmarks, x, z) {
  let nearest = null,
    distance = Infinity;
  for (const place of landmarks) {
    const d = Math.hypot(place.x - x, place.z - z);
    if (d < distance) {
      nearest = place;
      distance = d;
    }
  }
  return nearest ? { place: nearest, distance } : null;
}

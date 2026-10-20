export async function exportPhoto(
  renderer,
  scene,
  camera,
  { coordinates, credit, filename = `minecampus-${Date.now()}.png` },
) {
  renderer.render(scene, camera);
  const output = document.createElement("canvas");
  output.width = renderer.domElement.width;
  output.height = renderer.domElement.height;
  const ctx = output.getContext("2d");
  ctx.drawImage(renderer.domElement, 0, 0);
  const unit = Math.max(1, output.width / 1600),
    height = Math.round(76 * unit);
  ctx.fillStyle = "rgba(10,25,18,.82)";
  ctx.fillRect(0, output.height - height, output.width, height);
  ctx.fillStyle = "#e4f58f";
  ctx.font = `bold ${Math.round(18 * unit)}px monospace`;
  ctx.fillText("MINECAMPUS", 24 * unit, output.height - 43 * unit);
  ctx.fillStyle = "#e5e9da";
  ctx.font = `${Math.round(12 * unit)}px monospace`;
  ctx.fillText(
    `${coordinates.lat.toFixed(5)}° N / ${coordinates.lon.toFixed(5)}° E`,
    24 * unit,
    output.height - 20 * unit,
  );
  ctx.textAlign = "right";
  ctx.font = `${Math.round(10 * unit)}px sans-serif`;
  ctx.fillText(
    credit,
    output.width - 24 * unit,
    output.height - 20 * unit,
    output.width * 0.52,
  );
  const blob = await new Promise((resolve, reject) =>
    output.toBlob(
      (b) => (b ? resolve(b) : reject(Error("Photo export failed"))),
      "image/png",
    ),
  );
  const url = URL.createObjectURL(blob);
  return { filename, url, blob };
}

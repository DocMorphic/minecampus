// MCM1: 16-byte header, uint16 XYZUV attributes, alignment, uint32 indices.
export function decodeSurveyTile(buffer, meta) {
  const header = new DataView(buffer);
  if (header.byteLength < 16 || header.getUint32(0, true) !== 0x314d434d)
    throw Error("Invalid campus mesh tile");
  const vertices = header.getUint32(4, true),
    count = header.getUint32(8, true),
    indexOffset = 16 + Math.ceil((vertices * 10) / 4) * 4;
  if (
    vertices > 2000000 ||
    count > 6000000 ||
    indexOffset + count * 4 !== buffer.byteLength
  )
    throw Error("Truncated campus mesh tile");
  const packed = new Uint16Array(buffer, 16, vertices * 5),
    positions = new Float32Array(vertices * 3),
    uv = new Float32Array(vertices * 2);
  for (let i = 0; i < vertices; i++) {
    for (let j = 0; j < 3; j++)
      positions[i * 3 + j] =
        meta.min[j] + (packed[i * 5 + j] / 65535) * meta.scale[j];
    uv[i * 2] = packed[i * 5 + 3] / 65535;
    uv[i * 2 + 1] = packed[i * 5 + 4] / 65535;
  }
  const indices = new Uint32Array(buffer, indexOffset, count);
  for (const i of indices)
    if (i >= vertices) throw Error("Campus mesh index out of range");
  return { positions, uv, indices };
}

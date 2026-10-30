// Stand-ins for the surroundings that the browser fetches, for the offline headless test of
// examples/sixty5_geo.py: OpenStreetMap's tiles and the one tile of the 3D BAG that
// e2e/offline-pdok/sitecustomize.py puts at the Sixty5 site. Both are made here, so the test
// needs neither tile.openstreetmap.org nor api.pdok.nl.
import { deflateSync, crc32 } from "node:zlib";

/** The tile sitecustomize.py's tileset points at */
export const TILE_URL = "https://tiles.e2e.test/boxes.glb";

/**
 * The boxes of the tile, in the east-north-up frame of the Sixty5 site origin (metres): the
 * first stands on the stand-in BAG pand under the model's middle, so hide_within leaves it
 * out; the others stand 120 m east and 105 m south of it. Each box is one feature.
 */
export const BOXES = [
  { min: [27.9, 2.1, 0], max: [35.9, 10.1, 20] },
  { min: [146, 2.1, 0], max: [154, 10.1, 12] },
  { min: [27.9, -104, 0], max: [35.9, -96, 9] },
];

const CORS = { "Access-Control-Allow-Origin": "*" };

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

/** A 256 x 256 PNG in one colour with a darker edge, so that the map shows its tiles */
export function tilePng([r, g, b]) {
  const size = 256;
  const rows = [];
  for (let y = 0; y < size; y++) {
    const row = Buffer.alloc(1 + 3 * size); // filter byte 0: none
    for (let x = 0; x < size; x++) {
      const edge = x < 2 || y < 2 ? 0.8 : 1;
      row.set([r * edge, g * edge, b * edge], 1 + 3 * x);
    }
    rows.push(row);
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header.set([8, 2, 0, 0, 0], 8); // 8 bits, RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(Buffer.concat(rows))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

/**
 * A binary glTF of boxes, each a feature of its own (_FEATURE_ID_0, as EXT_mesh_features
 * names it in PDOK's tiles). The boxes are z-up; glTF is y-up, which 3D Tiles turns back.
 */
export function boxesGlb(boxes) {
  const positions = [];
  const features = [];
  const indices = [];
  // The faces of a box over its corners, numbered x + 2 y + 4 z
  const faces = [
    [0, 2, 3, 1],
    [4, 5, 7, 6],
    [0, 1, 5, 4],
    [2, 6, 7, 3],
    [0, 4, 6, 2],
    [1, 3, 7, 5],
  ];
  boxes.forEach(({ min, max }, feature) => {
    const first = positions.length / 3;
    for (let corner = 0; corner < 8; corner++) {
      const [x, y, z] = [0, 1, 2].map((axis) => ((corner >> axis) & 1 ? max : min)[axis]);
      positions.push(x, z, -y);
      features.push(feature);
    }
    for (const [a, b, c, d] of faces) {
      indices.push(first + a, first + b, first + c, first + a, first + c, first + d);
    }
  });
  const binaries = [
    Buffer.from(new Float32Array(positions).buffer),
    Buffer.from(new Float32Array(features).buffer),
    Buffer.from(new Uint16Array(indices).buffer),
  ];
  const offsets = [];
  let offset = 0;
  for (const binary of binaries) {
    offsets.push(offset);
    offset += Math.ceil(binary.length / 4) * 4;
  }
  const bin = Buffer.alloc(offset);
  binaries.forEach((binary, i) => binary.copy(bin, offsets[i]));
  const axis = (pick, i) => pick(...positions.filter((_, j) => j % 3 === i));
  const json = {
    asset: { version: "2.0", generator: "specklewidgets e2e" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0 }],
    meshes: [
      { primitives: [{ attributes: { POSITION: 0, _FEATURE_ID_0: 1 }, indices: 2, mode: 4 }] },
    ],
    accessors: [
      {
        bufferView: 0,
        componentType: 5126,
        count: positions.length / 3,
        type: "VEC3",
        min: [0, 1, 2].map((i) => axis(Math.min, i)),
        max: [0, 1, 2].map((i) => axis(Math.max, i)),
      },
      { bufferView: 1, componentType: 5126, count: features.length, type: "SCALAR" },
      { bufferView: 2, componentType: 5123, count: indices.length, type: "SCALAR" },
    ],
    bufferViews: binaries.map((binary, i) => ({
      buffer: 0,
      byteOffset: offsets[i],
      byteLength: binary.length,
      ...(i < 2 ? { target: 34962 } : { target: 34963 }),
    })),
    buffers: [{ byteLength: bin.length }],
  };
  let text = Buffer.from(JSON.stringify(json));
  text = Buffer.concat([text, Buffer.alloc((4 - (text.length % 4)) % 4, 0x20)]);
  const header = Buffer.alloc(12);
  header.write("glTF", 0, "ascii");
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + text.length + 8 + bin.length, 8);
  const textHeader = Buffer.alloc(8);
  textHeader.writeUInt32LE(text.length, 0);
  textHeader.write("JSON", 4, "ascii");
  const binHeader = Buffer.alloc(8);
  binHeader.writeUInt32LE(bin.length, 0);
  binHeader.write("BIN\0", 4, "ascii");
  return Buffer.concat([header, textHeader, text, binHeader, bin]);
}

/**
 * Serves the stand-ins to a Playwright page or context: a tile of the map in one of two
 * colours by z/x/y, and the 3D BAG's tile of BOXES.
 *
 * @returns the URLs it served, for the test to look at
 */
export async function routeSurroundings(target) {
  const served = [];
  const colours = [
    [236, 232, 220],
    [214, 226, 206],
  ];
  const tiles = new Map(colours.map((colour, i) => [i, tilePng(colour)]));
  await target.route("https://tile.openstreetmap.org/**", async (route) => {
    const url = route.request().url();
    served.push(url);
    const [x, y] = url
      .match(/(\d+)\/(\d+)\.png$/)
      .slice(1)
      .map(Number);
    await route.fulfill({ body: tiles.get((x + y) % 2), contentType: "image/png", headers: CORS });
  });
  const glb = boxesGlb(BOXES);
  await target.route(TILE_URL, async (route) => {
    served.push(route.request().url());
    await route.fulfill({ body: glb, contentType: "model/gltf-binary", headers: CORS });
  });
  return served;
}

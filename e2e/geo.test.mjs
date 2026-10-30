// Opens examples/sixty5_geo.py in headless Chromium: Sixty5's structural model from read_ifc,
// placed with its derived Engineering CRS, in a GeoSpeckleViewer on an OpenStreetMap ground
// map among PDOK's 3D BAG, without the BAG pand the model stands on. The test reads what the
// viewer reports: the elements it draws, the scene's bounding box, and its surroundings (the
// map's plane, the tiles in, the buildings left out).
//
//   npm run build && npm run e2e
//
// It runs twice. Offline, PDOK's APIs answer from e2e/offline-pdok/sitecustomize.py and the
// browser's map and 3D BAG tiles from e2e/surroundings.mjs, so it runs where api.pdok.nl and
// tile.openstreetmap.org are out of reach (the cloud containers). Live, it reads them; it
// skips where they are out of reach. The notebook reads the bimpolars test data (set
// BIMPOLARS_DATA_DIR to a local copy, or let bimpolars download it).
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { after, before, describe, test } from "node:test";
import { canvasContent, MINUTE, OUT, openNotebook } from "./marimo.mjs";
import { routeSurroundings, TILE_URL } from "./surroundings.mjs";

const NOTEBOOK = "examples/sixty5_geo.py";

// What tests/test_geo.py and bimpolars reach without the viewer: the rows with a mesh less
// the 1284 openings, and their bbox in metres
const DRAWN_ROWS = 1363;
const FRAME_BBOX = [-2.24, -0.001, -30.4, 33.585, 55.69, 56.64];
const BBOX_TOLERANCE = 1e-4;

// What tests/test_geo.py reaches with PDOK: the BAG pand under the slabs and footings
const SIXTY5_PANDEN = ["0772100001025175"];
// How far the bottom of the 3D BAG's building under the model may lie from the map, at z = 0
// (the site origin: AHN4's ground there), in metres. Without the NSGI grids it lies 44 m off
const GROUND_TOLERANCE = 3;

const PDOK = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items?f=json&limit=1";
const OSM = "https://tile.openstreetmap.org/0/0/0.png";

async function reachable(url) {
  try {
    return (await fetch(url, { signal: AbortSignal.timeout(15_000) })).ok;
  } catch {
    return false;
  }
}

function assertBbox(actual, expected, what) {
  assert.equal(actual.length, 6, `${what} has six numbers`);
  actual.forEach((value, i) =>
    assert.ok(
      Math.abs(value - expected[i]) < BBOX_TOLERANCE,
      `${what}[${i}] = ${value}, expected ${expected[i]}`,
    ),
  );
}

/** Whether two plan boxes [xmin, ymin, xmax, ymax] overlap */
function overlaps([ax0, ay0, ax1, ay1], [bx0, by0, bx1, by1]) {
  return ax0 < bx1 && bx0 < ax1 && ay0 < by1 && by0 < ay1;
}

/**
 * The report once the model, the map and the tiles are in, and at least `hiddenFeatures` of
 * the tiles' features left out
 */
async function report(page, hiddenFeatures, timeout) {
  const handle = await page.waitForFunction(
    (hiddenFeatures) => {
      const element = document.querySelector("#geo-report");
      if (!element || element.dataset.objectCount === "0") {
        return null;
      }
      const seen = Object.fromEntries(
        Object.entries(element.dataset).map(([key, value]) => [key, JSON.parse(value)]),
      );
      const { ground_map, tiles, hidden_features } = seen.surroundings;
      return ground_map.length && tiles > 0 && hidden_features >= hiddenFeatures ? seen : null;
    },
    hiddenFeatures,
    { timeout, polling: 1000 },
  );
  return handle.jsonValue();
}

/** The checks both runs share; returns the report for theirs */
async function checkSixty5InItsSurroundings({ page, errors, waitFor }, name) {
  // Fails with what the page logged when the viewer never reports
  await waitFor(page.locator("#geo-report:not([data-object-count='0'])"), 8 * MINUTE);
  let seen = await report(page, 0, 5 * MINUTE);
  // The tiles come in one by one, and the one with the model's building may come last
  seen = await report(page, 1, 3 * MINUTE).catch(() => seen);
  console.log(`Sixty5 ${name}:`, JSON.stringify({ ...seen, frameBbox: undefined }));
  assert.equal(seen.drawnRows, DRAWN_ROWS, "rows with a mesh, less the openings");
  assert.equal(seen.objectCount, DRAWN_ROWS, "elements drawn");
  assertBbox(seen.frameBbox, FRAME_BBOX, "frame bbox");
  assertBbox(seen.sceneBbox, seen.frameBbox, "scene_bbox");

  // The map lies under the whole model, and the BAG panden under the site under the model
  const [xmin, ymin, , xmax, ymax] = seen.sceneBbox;
  const [mx0, my0, mx1, my1] = seen.surroundings.ground_map;
  assert.ok(mx0 < xmin && my0 < ymin && mx1 > xmax && my1 > ymax, "the map covers the model");
  assert.ok(seen.panden.length >= 1, "a BAG pand under the model");
  assert.ok(
    overlaps(seen.pandenBbox, [xmin, ymin, xmax, ymax]),
    `the BAG panden ${JSON.stringify(seen.pandenBbox)} overlap the scene ${JSON.stringify(seen.sceneBbox)}`,
  );
  assert.ok(seen.surroundings.hidden_features >= 1, "the 3D BAG's Sixty5 is left out");
  // ... and stood on the map, as the model does
  const [bottom] = seen.surroundings.hidden_heights;
  assert.ok(
    Math.abs(bottom) < GROUND_TOLERANCE,
    `the 3D BAG's Sixty5 stands at z = ${bottom} m, the map and the model at 0`,
  );

  // SwiftShader takes its time to draw the model, the map and the tiles
  await mkdir(OUT, { recursive: true });
  const png = await page
    .locator("canvas")
    .first()
    .screenshot({ timeout: 5 * MINUTE });
  await writeFile(path.join(OUT, `${name}.png`), png);
  const { drawn, colours } = await canvasContent(page, png);
  assert.ok(drawn > 0.2, `only ${(drawn * 100).toFixed(2)} % of the canvas is drawn`);
  assert.ok(colours > 16, `the canvas has only ${colours} colours`);
  assert.deepEqual(errors, []);
  return seen;
}

describe("offline: generated map tiles, 3D BAG and BAG", () => {
  let notebook;
  let served;

  before(async () => {
    notebook = await openNotebook(NOTEBOOK, {
      env: { PYTHONPATH: path.join(import.meta.dirname, "offline-pdok") },
      route: async (context) => {
        served = await routeSurroundings(context);
      },
    });
  });

  after(async () => {
    await notebook?.close();
  });

  test("Sixty5 stands on its own pand, among the boxes", { timeout: 15 * MINUTE }, async () => {
    const seen = await checkSixty5InItsSurroundings(notebook, "offline");
    // The stand-in BAG has one pand under the model; its tile three boxes, one on the pand
    assert.deepEqual(seen.panden, ["0772100000e2e000"]);
    assert.equal(seen.leaves, 1);
    assert.deepEqual(seen.surroundings, { ...seen.surroundings, tiles: 1, hidden_features: 1 });
    // The box on the pand stands from 0 to 20 m (BOXES), at the site origin's ellipsoidal height
    seen.surroundings.hidden_heights.forEach((z, i) =>
      assert.ok(Math.abs(z - [0, 20][i]) < 0.1, `the box on the pand spans ${z} m`),
    );
    assert.ok(served.includes(TILE_URL));
    assert.ok(served.filter((url) => url.includes("openstreetmap")).length > 4);
  });
});

const live = (await reachable(PDOK)) && (await reachable(OSM));

describe(
  "live: OpenStreetMap and PDOK",
  { skip: !live && "api.pdok.nl or tile.openstreetmap.org is out of reach" },
  () => {
    let notebook;

    before(async () => {
      notebook = await openNotebook(NOTEBOOK);
    });

    after(async () => {
      await notebook?.close();
    });

    test("Sixty5 stands on its BAG pand, in the 3D BAG", { timeout: 15 * MINUTE }, async () => {
      const seen = await checkSixty5InItsSurroundings(notebook, "live");
      assert.deepEqual(seen.panden, SIXTY5_PANDEN);
    });
  },
);

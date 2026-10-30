// Opens examples/rvt_arch_bimdataframe.py in headless Chromium: the Revit Advanced Sample's
// architectural model read by read_speckle and by read_ifc, each BimDataFrame in its own
// SpeckleViewer (the first by its materials, the second by class). Each viewer must draw one
// element per row with a mesh and span the BimDataFrame's bbox.
//
//   just build && just e2e
//
// The notebook reads the bimpolars test data (set BIMPOLARS_DATA_DIR to a local copy, or let
// bimpolars download it) and spends 45 s in read_ifc. A request to esm.sh fails the test, as
// in notebook.test.mjs (see marimo.mjs).
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { after, before, test } from "node:test";
import { canvasContent, MINUTE, OUT, openNotebook } from "./marimo.mjs";

const NOTEBOOK = "examples/rvt_arch_bimdataframe.py";

// What tests/test_rvt_arch_bimdataframe.py reaches without the viewer: the rows with a mesh
// (openings left out) and their bbox in metres
const MODELS = {
  speckle: { rows: 5568, bbox: [-116.6763, -76.0339, -1.8288, 202.3891, 75.7287, 12.5745] },
  ifc: { rows: 5512, bbox: [-107.4743, -53.3989, -1.8288, 211.5911, 98.3638, 12.4854] },
};
// The viewer's float32 vertices, 200 m from the origin
const BBOX_TOLERANCE = 1e-4;

let notebook;
let page;
let errors;
let waitFor;

before(async () => {
  notebook = await openNotebook(NOTEBOOK);
  ({ page, errors, waitFor } = notebook);
});

after(async () => {
  await notebook?.close();
});

function assertBbox(actual, expected, what) {
  assert.equal(actual.length, 6, `${what} has six numbers`);
  actual.forEach((value, i) =>
    assert.ok(
      Math.abs(value - expected[i]) < BBOX_TOLERANCE,
      `${what}[${i}] = ${value}, expected ${expected[i]}`,
    ),
  );
}

test(
  "both BimDataFrames render, one element per row with a mesh",
  { timeout: 12 * MINUTE },
  async () => {
    for (const [key, expected] of Object.entries(MODELS)) {
      // The report reruns when the viewer reports; 0 until the model is in
      const report = page.locator(`#${key}-report:not([data-object-count='0'])`);
      await waitFor(report, 8 * MINUTE);

      const rows = Number(await report.getAttribute("data-drawn-rows"));
      assert.equal(rows, expected.rows, `${key}: rows with a mesh`);
      assert.equal(Number(await report.getAttribute("data-object-count")), rows, `${key}: drawn`);

      const frameBbox = JSON.parse(await report.getAttribute("data-frame-bbox"));
      assertBbox(frameBbox, expected.bbox, `${key} frame bbox`);
      const sceneBbox = JSON.parse(await report.getAttribute("data-scene-bbox"));
      assertBbox(sceneBbox, frameBbox, `${key} scene_bbox`);
    }

    // SwiftShader takes its time to draw a frame of a quarter to half a million triangles
    await mkdir(OUT, { recursive: true });
    const canvases = page.locator("canvas");
    assert.equal(await canvases.count(), 2);
    for (const [index, key] of Object.keys(MODELS).entries()) {
      const png = await canvases.nth(index).screenshot({ timeout: 5 * MINUTE });
      await writeFile(path.join(OUT, `${key}.png`), png);
      const { drawn, colours } = await canvasContent(page, png);
      assert.ok(drawn > 0.01, `${key}: only ${(drawn * 100).toFixed(2)} % of the canvas is drawn`);
      assert.ok(colours > 16, `${key}: the canvas has only ${colours} colours`);
    }

    assert.deepEqual(errors, []);
  },
);

test("a click selects a row of the BimDataFrame", { timeout: 5 * MINUTE }, async () => {
  const canvas = page.locator("canvas").nth(1);
  await waitFor(canvas, MINUTE);
  const { width, height } = await canvas.boundingBox();
  const selected = page.locator("#ifc-selected");
  // The model fills the middle of the view; try a few points there until one hits
  for (const [x, y] of [
    [0.5, 0.5],
    [0.45, 0.5],
    [0.55, 0.5],
    [0.5, 0.45],
    [0.5, 0.55],
  ]) {
    await canvas.click({ position: { x: x * width, y: y * height }, timeout: 2 * MINUTE });
    try {
      await selected.waitFor({ timeout: 30_000 });
      break;
    } catch {
      // nothing under this point
    }
  }
  const ids = JSON.parse(await selected.getAttribute("data-ids"));
  assert.equal(ids.length, 1);
  // The row the notebook shows for it: an IFC GlobalId, 22 characters
  assert.match(ids[0], /^[0-9A-Za-z_$]{22}$/);
  assert.deepEqual(errors, []);
});

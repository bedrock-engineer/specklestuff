// Opens the example notebook in headless Chromium, with no person in the loop: marimo serves
// examples/rvt_advanced_sample.py, the three Revit Advanced Sample models load into one
// SpeckleViewer, and the test reads what the viewer reports back through its traits.
//
//   npm run build && npm run e2e
//
// The notebook reads the bimpolars test data (set BIMPOLARS_DATA_DIR to a local copy, or let
// bimpolars download it). esm.sh is served from node_modules (see esm-mirror.mjs), unless
// E2E_ESM_SH=network: then the browser loads the real esm.sh, as a user's does (CI sets it).
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { after, before, test } from "node:test";
import { canvasContent, MINUTE, OUT, openNotebook } from "./marimo.mjs";

const NOTEBOOK = "examples/rvt_advanced_sample.py";

// The numbers tests/test_rvt_advanced_sample.py reaches without the viewer: the elements a
// click can select (arch 5686, str 918, mep 6942) and the scene's bounding box in metres
const OBJECT_COUNT = 5686 + 918 + 6942;
const SCENE_BBOX = [-116.6763, -121.7323, -7.2, 202.3891, 75.7287, 15.2066];
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

test("the three models render in one viewer", { timeout: 10 * MINUTE }, async () => {
  // The report cell reruns when the viewer reports; 0 until the models are in
  const report = page.locator("#viewer-report:not([data-object-count='0'])");
  await waitFor(report, 8 * MINUTE);

  assert.equal(Number(await report.getAttribute("data-object-count")), OBJECT_COUNT);
  const bbox = JSON.parse(await report.getAttribute("data-scene-bbox"));
  assert.equal(bbox.length, 6);
  bbox.forEach((value, i) =>
    assert.ok(
      Math.abs(value - SCENE_BBOX[i]) < BBOX_TOLERANCE,
      `scene_bbox[${i}] = ${value}, expected ${SCENE_BBOX[i]}`,
    ),
  );

  // SwiftShader takes its time to draw a frame of three quarters of a million triangles
  const png = await page
    .locator("canvas")
    .first()
    .screenshot({ timeout: 5 * MINUTE });
  await mkdir(OUT, { recursive: true });
  await writeFile(path.join(OUT, "canvas.png"), png);
  const { drawn, colours } = await canvasContent(page, png);
  assert.ok(drawn > 0.01, `only ${(drawn * 100).toFixed(2)} % of the canvas is drawn`);
  assert.ok(colours > 16, `the canvas has only ${colours} colours`);

  assert.deepEqual(errors, []);
});

test("a click selects an element", { timeout: 5 * MINUTE }, async () => {
  const canvas = page.locator("canvas").first();
  await waitFor(canvas, MINUTE);
  const { width, height } = await canvas.boundingBox();
  const selected = page.locator("#viewer-selected");
  // The models fill the middle of the view; try a few points there until one hits
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
  const elements = JSON.parse(await selected.getAttribute("data-selected"));
  assert.equal(elements.length, 1);
  assert.ok(elements[0].applicationId, "the selected element has an applicationId");
  assert.ok(!("displayValue" in elements[0]), "the selection leaves geometry out");
  assert.deepEqual(errors, []);
});

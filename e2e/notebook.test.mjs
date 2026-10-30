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
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import path from "node:path";
import { after, before, test } from "node:test";
import { chromium } from "playwright";
import { buildMirror, routeEsmSh } from "./esm-mirror.mjs";

const ROOT = path.join(import.meta.dirname, "..");
// Whether the browser loads the real esm.sh instead of the mirror
const ESM_SH_NETWORK = process.env.E2E_ESM_SH === "network";
// The canvas as the test saw it, for a look when it fails (gitignored)
const OUT = path.join(import.meta.dirname, ".out");
const NOTEBOOK = "examples/rvt_advanced_sample.py";

// The numbers tests/test_rvt_advanced_sample.py reaches without the viewer: the elements a
// click can select (arch 5686, str 918, mep 6942) and the scene's bounding box in metres
const OBJECT_COUNT = 5686 + 918 + 6942;
const SCENE_BBOX = [-116.6763, -121.7323, -7.2, 202.3891, 75.7287, 15.2066];
// The viewer's float32 vertices, 200 m from the origin
const BBOX_TOLERANCE = 1e-4;

const MINUTE = 60_000;

async function freePort() {
  const server = createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function waitForServer(url, timeout) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url)).ok) {
        return;
      }
    } catch {
      // not listening yet
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`${url} did not answer within ${timeout / 1000} s`);
}

/** Pixels that differ from the canvas's most common colour, as a fraction, and colours */
async function canvasContent(page, png) {
  return page.evaluate(async (base64) => {
    const blob = await (await fetch(`data:image/png;base64,${base64}`)).blob();
    const image = await createImageBitmap(blob);
    const canvas = new OffscreenCanvas(image.width, image.height);
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0);
    const { data } = context.getImageData(0, 0, image.width, image.height);
    const counts = new Map();
    for (let i = 0; i < data.length; i += 4) {
      const colour = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
      counts.set(colour, (counts.get(colour) ?? 0) + 1);
    }
    const pixels = data.length / 4;
    const background = Math.max(...counts.values());
    return { drawn: (pixels - background) / pixels, colours: counts.size };
  }, png.toString("base64"));
}

let marimo;
let browser;
let page;
const errors = [];
// Everything the page logs and every request that fails, for the message of a test that
// times out before it gets to the errors
const log = [];

/** Waits for a locator, and on timeout fails with what the page logged */
async function waitFor(locator, timeout) {
  try {
    await locator.waitFor({ timeout });
  } catch (error) {
    await mkdir(OUT, { recursive: true });
    await page.screenshot({ path: path.join(OUT, "page.png"), fullPage: true }).catch(() => {});
    assert.fail(`${error.message}\n\nThe page logged:\n${log.slice(-40).join("\n")}`);
  }
}

before(async () => {
  if (!ESM_SH_NETWORK) {
    await buildMirror();
  }
  const port = await freePort();
  marimo = spawn(
    "uv",
    [
      "run",
      "marimo",
      "run",
      NOTEBOOK,
      "--headless",
      "--no-token",
      "--no-sandbox",
      "--port",
      `${port}`,
    ],
    { cwd: ROOT, stdio: ["ignore", "inherit", "inherit"] },
  );
  const url = `http://127.0.0.1:${port}/`;
  await waitForServer(url, 2 * MINUTE);

  // SwiftShader: WebGL without a GPU
  browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  if (!ESM_SH_NETWORK) {
    await routeEsmSh(context);
  }
  page = await context.newPage();
  page.on("console", (message) => {
    log.push(`${message.type()}: ${message.text()}`);
    // A second three.js (esm.sh resolving the viewer's three to another module than ours) only
    // warns, and most of the scene still draws
    if (
      message.type() === "error" ||
      message.text().includes("Multiple instances of Three.js being imported")
    ) {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(`${error.name}: ${error.message}`);
    log.push(`pageerror: ${error.name}: ${error.message}`);
  });
  page.on("requestfailed", (request) =>
    log.push(`requestfailed: ${request.url()} (${request.failure()?.errorText})`),
  );
  page.on("response", (response) => {
    if (response.status() >= 400) {
      log.push(`HTTP ${response.status()}: ${response.url()}`);
    }
  });
  await page.goto(url);
});

after(async () => {
  await browser?.close();
  marimo?.kill();
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

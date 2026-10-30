// Opens the demo page (site/) in headless Chromium: Sixty5 in a GeoSpeckleViewer beside a
// MapLibre map, a click in the viewer showing the element's footprint on the map, the
// separator between them resizing both, and on a phone a strip that scrolls the page while the
// panes keep their touches. The test
// writes the page's data with site/sixty5.py and builds the page into OUT, then serves it as
// GitHub Pages does: static files, the gzipped model as it is.
//
//   just e2e
//
// It runs offline: PDOK's APIs answer site/sixty5.py from e2e/offline-pdok/sitecustomize.py,
// and the browser's map tiles and 3D BAG tile come from e2e/surroundings.mjs, so it runs where
// api.pdok.nl, service.pdok.nl and tile.openstreetmap.org are out of reach (the cloud
// containers). The data script reads the bimpolars test data (set BIMPOLARS_DATA_DIR to a
// local copy, or let bimpolars download it).
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { after, before, test } from "node:test";
import { build } from "vite";
import { MINUTE, OUT, openPage } from "./marimo.mjs";
import { routeSurroundings, tilePng } from "./surroundings.mjs";

const ROOT = path.join(import.meta.dirname, "..");
const DIST = path.join(OUT, "site");
const DATA = path.join(OUT, "site-data");

// What tests/test_geo.py and the notebook reach: the rows with a mesh less the 1284 openings,
// each with a footprint
const DRAWN_ROWS = 1363;

const TYPES = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".geojson": "application/geo+json",
  // GitHub Pages serves a .gz file as it is, without a Content-Encoding
  ".gz": "application/gzip",
};

function run(command, args, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: ROOT,
      stdio: ["ignore", "inherit", "inherit"],
      env: { ...process.env, ...env },
    });
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`${command} ${args.join(" ")} exited ${code}`)),
    );
  });
}

/** Serves the built page, its data folder from the data the test wrote */
async function serve() {
  const server = createServer(async (request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const file = pathname.startsWith("/data/")
      ? path.join(DATA, pathname.slice("/data/".length))
      : path.join(DIST, pathname.endsWith("/") ? `${pathname}index.html` : pathname);
    try {
      const body = await readFile(file);
      response.writeHead(200, {
        "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream",
      });
      response.end(body);
    } catch {
      response.writeHead(404);
      response.end();
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return server;
}

let server;
let opened;
let served;
const basemapTiles = [];
const pdok = tilePng([200, 210, 190]);

/** The stand-ins for OSM's and PDOK's tiles; what routeSurroundings served */
async function routeTiles(context) {
  const tiles = await routeSurroundings(context);
  await context.route("https://service.pdok.nl/**", async (route) => {
    basemapTiles.push(route.request().url());
    await route.fulfill({
      body: pdok,
      contentType: "image/png",
      headers: { "Access-Control-Allow-Origin": "*" },
    });
  });
  return tiles;
}

function url() {
  return `http://127.0.0.1:${server.address().port}/`;
}

before(async () => {
  await mkdir(OUT, { recursive: true });
  await run("uv", ["run", "python", "site/sixty5.py", DATA], {
    PYTHONPATH: path.join(ROOT, "e2e", "offline-pdok"),
  });
  await build({
    configFile: path.join(ROOT, "site", "vite.config.js"),
    logLevel: "warn",
    // Only what the page imports: the data comes from DATA
    publicDir: false,
    build: { outDir: DIST, emptyOutDir: true },
  });
  server = await serve();
  opened = await openPage(url(), {
    name: "site",
    viewport: { width: 1440, height: 900 },
    async route(context) {
      served = await routeTiles(context);
    },
  });
});

after(async () => {
  await opened?.close();
  server?.close();
});

test("the viewer draws Sixty5 among the 3D BAG", { timeout: 10 * MINUTE }, async () => {
  const { page, errors, waitFor } = opened;
  await waitFor(page.locator("#viewer-pane[data-object-count]"), 5 * MINUTE);
  const pane = page.locator("#viewer-pane");
  assert.equal(Number(await pane.getAttribute("data-object-count")), DRAWN_ROWS);
  assert.ok(await page.locator("#loading").isHidden(), "the loading message is gone");
  // The 3D BAG's tile comes in after the model
  await page.waitForFunction(
    () => JSON.parse(document.getElementById("viewer-pane").dataset.surroundings ?? "{}").tiles > 0,
    undefined,
    { timeout: 3 * MINUTE },
  );
  const surroundings = JSON.parse(await pane.getAttribute("data-surroundings"));
  assert.equal(surroundings.ground_map.length, 4, "the ground map lies under the model");
  assert.ok(
    served.some((url) => url.startsWith("https://tile.openstreetmap.org/")),
    "the ground map's tiles",
  );
  assert.ok(basemapTiles.length > 0, "the footprint map's tiles");
  assert.ok(
    basemapTiles.every((url) => url.includes("/brt/achtergrondkaart/")),
    "the topographic map by default",
  );
  // The h1 of site/intro/<SITE>.html, which vite.config.js puts into the page
  const title = await page.title();
  assert.doesNotMatch(title, /%/);
  assert.equal(await page.locator("h1").textContent(), title);
  assert.deepEqual(errors, []);
});

test("a click shows the element's footprint on the map", { timeout: 10 * MINUTE }, async () => {
  const { page, errors, waitFor } = opened;
  const canvas = page.locator("#viewer canvas").first();
  await waitFor(canvas, MINUTE);
  const { width, height } = await canvas.boundingBox();
  const selected = page.locator('#selection:not([data-ids="[]"])');
  // The tower fills the middle of the view; try a few points there until one hits
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
  const card = page.locator("#selection");
  const ids = JSON.parse(await card.getAttribute("data-ids"));
  assert.equal(ids.length, 1, "one element selected");
  // The map draws the footprint once it has flown there
  await waitFor(page.locator('#selection:not([data-drawn="[]"])'), MINUTE);
  assert.deepEqual(JSON.parse(await card.getAttribute("data-drawn")), ids);
  const footprints = JSON.parse(await readFile(path.join(DATA, "footprints.geojson"), "utf8"));
  const { properties } = footprints.features.find((feature) => feature.properties.id === ids[0]);
  assert.equal(await card.locator(".class").textContent(), properties.class);
  assert.match(await card.locator(".storey").textContent(), new RegExp(`^${properties.storey}`));
  await page.screenshot({ path: path.join(OUT, "site.png"), timeout: 5 * MINUTE });
  assert.deepEqual(errors, []);
});

/** Waits until the canvas in a pane is as wide as the pane: the pane's content follows it */
async function canvasFills(page, pane, canvas) {
  await page.waitForFunction(
    ([pane, canvas]) =>
      Math.abs(
        document.querySelector(canvas).getBoundingClientRect().width -
          document.querySelector(pane).getBoundingClientRect().width,
      ) < 2,
    [pane, canvas],
    { timeout: MINUTE },
  );
}

test("the separator resizes the viewer and the map", { timeout: 5 * MINUTE }, async () => {
  const { page, errors } = opened;
  const separator = page.locator("#splitter");
  assert.equal(await separator.getAttribute("aria-valuenow"), "60");
  const panes = await page.locator(".panes").boundingBox();
  const handle = await separator.boundingBox();
  const y = handle.y + handle.height / 2;
  await page.mouse.move(handle.x + handle.width / 2, y);
  await page.mouse.down();
  await page.mouse.move(panes.x + 0.4 * panes.width, y, { steps: 5 });
  await page.mouse.up();
  await page.waitForFunction(
    () => document.getElementById("splitter").getAttribute("aria-valuenow") === "40",
    undefined,
    { timeout: MINUTE },
  );
  const viewer = await page.locator("#viewer-pane").boundingBox();
  const map = await page.locator("#map-pane").boundingBox();
  assert.ok(Math.abs(viewer.width / (viewer.width + map.width) - 0.4) < 0.01, "40 % to the viewer");
  await canvasFills(page, "#viewer-pane", "#viewer canvas");
  await canvasFills(page, "#map-pane", "#map canvas.maplibregl-canvas");
  // The keys move it too
  await separator.focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await separator.getAttribute("aria-valuenow"), "42");
  await page.keyboard.press("Home");
  assert.equal(await separator.getAttribute("aria-valuenow"), "20");
  await separator.dblclick();
  assert.equal(await separator.getAttribute("aria-valuenow"), "60");
  await canvasFills(page, "#viewer-pane", "#viewer canvas");
  assert.deepEqual(errors, []);
});

test(
  "on a phone, a strip scrolls the page and the panes keep their touches",
  {
    timeout: 5 * MINUTE,
  },
  async () => {
    const phone = await openPage(url(), {
      name: "site-phone",
      viewport: { width: 390, height: 844 },
      device: { hasTouch: true, isMobile: true, deviceScaleFactor: 2 },
      route: routeTiles,
    });
    try {
      const { page, errors, waitFor } = phone;
      // The viewer's element comes before its model
      await waitFor(page.locator("#viewer > div"), MINUTE);
      assert.equal(
        await page
          .locator("#viewer > div")
          .evaluate((element) => getComputedStyle(element).touchAction),
        "none",
        "the widget takes the touches on its viewer, whatever the page around it",
      );
      assert.ok(await page.locator(".how-click").isHidden(), "the strip has the instructions");
      const rail = await page.locator(".rail").boundingBox();
      const viewer = await page.locator("#viewer-pane").boundingBox();
      const map = await page.locator("#map-pane").boundingBox();
      assert.equal(Math.round(rail.x + rail.width), 390, "the strip is on the right");
      assert.ok(
        Math.abs(rail.y - viewer.y) < 1 && Math.abs(rail.y + rail.height - map.y - map.height) < 1,
        "the strip runs beside both panes",
      );
      // A finger's swipe up from the top of the page, through the browser's touch input (CDP's
      // synthesized scroll gestures scroll nothing in headless Chromium)
      const cdp = await page.context().newCDPSession(page);
      async function swipe(x, y) {
        await page.evaluate(() => window.scrollTo(0, 0));
        const touch = (type, dy) =>
          cdp.send("Input.dispatchTouchEvent", {
            type,
            touchPoints: type === "touchEnd" ? [] : [{ x: Math.round(x), y: Math.round(y - dy) }],
          });
        await touch("touchStart", 0);
        for (let dy = 30; dy <= 300; dy += 30) {
          await touch("touchMove", dy);
        }
        await touch("touchEnd", 300);
        await page.waitForTimeout(300);
        return page.evaluate(() => window.scrollY);
      }
      assert.ok((await swipe(rail.x + rail.width / 2, 600)) > 100, "a swipe on the strip scrolls");
      assert.equal(await swipe(viewer.x + viewer.width / 2, viewer.y + viewer.height / 2), 0);
      // Clear of the map's buttons, in the part of the map above the fold
      assert.equal(await swipe(map.x + 80, map.y + 60), 0);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(OUT, "site-phone.png"), fullPage: true });
      assert.deepEqual(errors, []);
    } finally {
      await phone.close();
    }
  },
);

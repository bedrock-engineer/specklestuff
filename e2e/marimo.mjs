// What the headless tests share: headless Chromium on a page, a marimo server for an example
// notebook, and a look at a canvas. The widget bundles the viewer and three.js, so the page loads
// nothing from a CDN; a request to esm.sh counts as an error.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { createServer } from "node:net";
import path from "node:path";
import { chromium } from "playwright";

const ROOT = path.join(import.meta.dirname, "..");
// What a test saw, for a look when it fails (gitignored; CI uploads it)
export const OUT = path.join(import.meta.dirname, ".out");

export const MINUTE = 60_000;

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

/**
 * Opens a page in headless Chromium (WebGL by SwiftShader), logging what goes wrong.
 *
 * @param {string} url
 * @param {object} [options]
 * @param {(context: import("playwright").BrowserContext) => Promise<void>} [options.route]
 *   routes the browser's requests before it opens the page, as the stand-ins for PDOK and
 *   OSM do
 * @param {string} [options.name] the name of the screenshot a failed wait leaves in OUT
 * @param {{ width: number, height: number }} [options.viewport]
 * @param {import("playwright").BrowserContextOptions} [options.device] more of the browser
 *   context's options, a phone's touch screen for one
 * @returns {Promise<{
 *   page: import("playwright").Page,
 *   errors: string[],
 *   waitFor: (locator: import("playwright").Locator, timeout: number) => Promise<void>,
 *   close: () => Promise<void>,
 * }>} the page; the console errors, page errors, a second three.js and any request to esm.sh
 *   it logs; a wait for a locator that on timeout fails with what the page logged (and saves a
 *   screenshot of the page in OUT); and what closes the browser
 */
export async function openPage(
  url,
  { route, name = "page", viewport = { width: 1280, height: 1000 }, device = {} } = {},
) {
  const browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader"] });
  try {
    const context = await browser.newContext({ viewport, ...device });
    const errors = [];
    // The bundle is self-contained: the CDN it used to import from must not be asked
    await context.route("https://esm.sh/**", async (route) => {
      errors.push(`request to esm.sh: ${route.request().url()}`);
      await route.abort();
    });
    await route?.(context);
    const page = await context.newPage();
    // Everything the page logs and every request that fails, for the message of a test that
    // times out before it gets to the errors
    const log = [];
    page.on("console", (message) => {
      log.push(`${message.type()}: ${message.text()}`);
      // A second three.js (a dependency of the viewer bundling its own copy) only warns, and
      // most of the scene still draws
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
    async function waitFor(locator, timeout) {
      try {
        await locator.waitFor({ timeout });
      } catch (error) {
        await mkdir(OUT, { recursive: true });
        const screenshot = path.join(OUT, `${name}.png`);
        await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {});
        assert.fail(`${error.message}\n\nThe page logged:\n${log.slice(-40).join("\n")}`);
      }
    }
    await page.goto(url);
    return { page, errors, waitFor, close: () => browser.close() };
  } catch (error) {
    await browser.close();
    throw error;
  }
}

/**
 * Serves a notebook with `marimo run` and opens it with openPage.
 *
 * @param {string} notebook the notebook's path from the repository root
 * @param {object} [options]
 * @param {Record<string, string>} [options.env] more environment for marimo and its kernel
 * @param {(context: import("playwright").BrowserContext) => Promise<void>} [options.route]
 *   as for openPage
 * @returns what openPage returns, its close stopping marimo as well
 */
export async function openNotebook(notebook, { env = {}, route } = {}) {
  const port = await freePort();
  const marimo = spawn(
    "uv",
    [
      "run",
      "marimo",
      "run",
      notebook,
      "--headless",
      "--no-token",
      "--no-sandbox",
      "--port",
      `${port}`,
    ],
    { cwd: ROOT, stdio: ["ignore", "inherit", "inherit"], env: { ...process.env, ...env } },
  );
  try {
    const url = `http://127.0.0.1:${port}/`;
    await waitForServer(url, 2 * MINUTE);
    const opened = await openPage(url, { route, name: path.basename(notebook, ".py") });
    return {
      ...opened,
      async close() {
        await opened.close();
        marimo.kill();
      },
    };
  } catch (error) {
    marimo.kill();
    throw error;
  }
}

/** Pixels that differ from the canvas's most common colour, as a fraction, and colours */
export async function canvasContent(page, png) {
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

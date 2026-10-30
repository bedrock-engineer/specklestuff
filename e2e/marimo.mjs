// What the headless tests share: a marimo server for an example notebook, headless Chromium
// on it with esm.sh served from node_modules (see esm-mirror.mjs), and a look at a canvas.
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import path from "node:path";
import { chromium } from "playwright";
import { buildMirror, routeEsmSh } from "./esm-mirror.mjs";

const ROOT = path.join(import.meta.dirname, "..");

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
 * Serves a notebook with `marimo run` and opens it in headless Chromium (WebGL by SwiftShader).
 *
 * @param {string} notebook the notebook's path from the repository root
 * @param {object} [options]
 * @param {Record<string, string>} [options.env] more environment for marimo and its kernel
 * @param {(context: import("playwright").BrowserContext) => Promise<void>} [options.route]
 *   routes the browser's requests before it opens the notebook, as esm.sh's are
 * @returns {Promise<{page: import("playwright").Page, errors: string[], close: () => Promise<void>}>}
 *   the page, the console errors and page errors it logs, and what stops both
 */
export async function openNotebook(notebook, { env = {}, route } = {}) {
  await buildMirror();
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
  let browser;
  async function close() {
    await browser?.close();
    marimo.kill();
  }
  try {
    const url = `http://127.0.0.1:${port}/`;
    await waitForServer(url, 2 * MINUTE);
    browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader"] });
    const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
    await routeEsmSh(context);
    await route?.(context);
    const page = await context.newPage();
    const errors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        errors.push(message.text());
      }
    });
    page.on("pageerror", (error) => errors.push(`${error.name}: ${error.message}`));
    await page.goto(url);
    return { page, errors, close };
  } catch (error) {
    await close();
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

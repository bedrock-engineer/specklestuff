// esm.sh, the CDN the widget loads @speckle/viewer and three.js from, is out of reach in some
// environments (the cloud containers block it). The mirror bundles the same packages from
// node_modules into ES modules, split so that the viewer and the widget share one three.js
// module as they do on esm.sh, and a Playwright route serves them for the esm.sh URLs.
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { build } from "esbuild";
import { ESM_SH } from "../vite.config.js";

const MIRROR = path.join(import.meta.dirname, ".mirror");

/** The mirror's entry file of each external, by the URL the widget imports it from */
function entries() {
  return Object.fromEntries(
    Object.entries(ESM_SH).map(([name, url]) => [url, `${name.replaceAll(/[@/]/g, "_")}.js`]),
  );
}

/** Bundles the externals into the mirror folder */
export async function buildMirror() {
  await mkdir(MIRROR, { recursive: true });
  await build({
    entryPoints: Object.fromEntries(
      Object.keys(ESM_SH).map((name) => [name.replaceAll(/[@/]/g, "_"), name]),
    ),
    bundle: true,
    splitting: true,
    format: "esm",
    platform: "browser",
    target: "es2022",
    outdir: MIRROR,
    chunkNames: "chunk-[hash]",
    logLevel: "warning",
    define: { "process.env.NODE_ENV": '"production"' },
  });
  // The entries sit at different depths of esm.sh (@speckle/viewer@..., three@...), so a
  // relative chunk import would give one chunk two URLs, and the browser two module
  // instances of it: two three.js copies. Every chunk gets one absolute URL instead.
  for (const file of await readdir(MIRROR)) {
    const code = await readFile(path.join(MIRROR, file), "utf8");
    await writeFile(
      path.join(MIRROR, file),
      code.replaceAll('"./chunk-', '"https://esm.sh/chunk-'),
    );
  }
}

/** Serves the mirror for every esm.sh request of a Playwright page or context */
export async function routeEsmSh(target) {
  const files = entries();
  await target.route("https://esm.sh/**", async (route) => {
    const url = route.request().url();
    // An entry by its exact URL; a chunk by its file name
    const file = files[url] ?? path.basename(new URL(url).pathname);
    try {
      const body = await readFile(path.join(MIRROR, file));
      await route.fulfill({ body, contentType: "application/javascript" });
    } catch {
      await route.fulfill({ status: 404, body: `${url} is not in the esm.sh mirror` });
    }
  });
}

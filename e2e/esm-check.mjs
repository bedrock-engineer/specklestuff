// Crawls the module graph esm.sh serves for the widget's externals, the URLs a user's browser
// loads, and fails with esm.sh's own error when a module does not answer 200, or when the
// graph holds more than one build of an external (two three.js modules: the viewer's objects
// and ours would not mix). Seconds, where the e2e takes minutes to tell the same.
//
//   node e2e/esm-check.mjs [url ...]   (default: the widget's externals, vite.config.js ESM_SH)
import { ESM_SH } from "../vite.config.js";

// esm.sh picks what it serves by user agent where a URL has no target; ask as a browser does
const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
};
// Static and dynamic imports and re-exports, as esm.sh writes them, of esm.sh modules
const IMPORT = /(?:\bfrom|\bimport)\s*\(?\s*["']((?:\/|https:\/\/esm\.sh\/)[^"']+)["']/g;

/** Every module reachable from the start URLs, with its status and, on failure, the body */
async function crawl(starts) {
  const modules = new Map();
  let pending = starts.map((url) => new URL(url).href);
  while (pending.length > 0) {
    const batch = pending.filter((url) => !modules.has(url));
    pending = [];
    for (const url of batch) {
      modules.set(url, null);
    }
    await Promise.all(
      batch.map(async (url) => {
        try {
          const response = await fetch(url, { headers: HEADERS });
          const body = await response.text();
          modules.set(url, { status: response.status, body: response.ok ? "" : body });
          if (response.ok) {
            const base = response.url;
            for (const [, specifier] of body.matchAll(IMPORT)) {
              pending.push(new URL(specifier, base).href);
            }
          }
        } catch (error) {
          modules.set(url, { status: 0, body: `${error.cause ?? error}` });
        }
      }),
    );
  }
  return modules;
}

/** The distinct builds of each external in the graph: its <name>.mjs module paths */
function builds(modules) {
  const found = {};
  for (const name of Object.keys(ESM_SH)) {
    const file = `/${name.split("/").pop()}.mjs`;
    found[name] = [...modules.keys()]
      .map((url) => new URL(url).pathname)
      .filter((pathname) => pathname.startsWith(`/${name}@`) && pathname.endsWith(file));
  }
  return found;
}

const starts = process.argv.length > 2 ? process.argv.slice(2) : Object.values(ESM_SH);
const modules = await crawl(starts);
const failed = [...modules].filter(([, result]) => result.status !== 200);
const duplicated = Object.entries(builds(modules)).filter(([, paths]) => paths.length > 1);

console.log(`${starts.join("\n")}\n${modules.size} modules`);
for (const [url, { status, body }] of failed) {
  console.log(`\nHTTP ${status}: ${url}\n${body.slice(0, 2000)}`);
}
for (const [name, paths] of duplicated) {
  console.log(`\n${paths.length} builds of ${name}:\n${paths.join("\n")}`);
}
process.exitCode = failed.length > 0 || duplicated.length > 0 ? 1 : 0;

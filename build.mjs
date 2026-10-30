// Builds every widget entry into src/specklewidgets/static/, one vite build each (see
// vite.config.js). A node script rather than a shell line so that `npm run build` works in
// cmd.exe as well: no rm -rf, no ENTRY=... prefix.
//
//   node build.mjs           clean build of all entries
//   node build.mjs --watch   rebuilds on change, without cleaning
import { rmSync } from "node:fs";
import { build } from "vite";
import { ENTRIES, OUT_DIR, widgetConfig } from "./vite.config.js";

const watch = process.argv.includes("--watch");
if (!watch) {
  rmSync(OUT_DIR, { recursive: true, force: true });
}
for (const entry of ENTRIES) {
  await build({ configFile: false, ...widgetConfig(entry, { watch }) });
}

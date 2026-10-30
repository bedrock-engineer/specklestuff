import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import anywidget from "@anywidget/vite";

// @speckle/viewer and three.js stay out of the bundle: the widget imports them from esm.sh, at
// the exact versions package.json pins. ?target=es2022 on every URL makes esm.sh serve the
// viewer's own three.js import and ours from one module, so the markers we add are the
// viewer's three.js objects.
const { dependencies } = JSON.parse(readFileSync(new URL("package.json", import.meta.url)));
export const ESM_SH = Object.fromEntries(
  Object.entries(dependencies).map(([name, version]) => [
    name,
    `https://esm.sh/${name}@${version}?target=es2022`,
  ]),
);

// anywidget loads each _esm file as a self-contained module (relative imports don't resolve
// from a blob URL), so every widget entry gets its own vite invocation: a single multi-entry
// build would split shared lib code into chunks the entries import relatively. npm run build
// loops over the entries via ENTRY.
export default defineConfig({
  build: {
    outDir: "src/specklewidgets/static",
    emptyOutDir: false,
    // the bundles are committed and read in diffs, keep them readable
    minify: false,
    lib: {
      entry: [process.env.ENTRY ?? "js/speckle-viewer.ts"],
      formats: ["es"],
    },
    rollupOptions: {
      external: Object.keys(ESM_SH),
      output: { paths: ESM_SH },
    },
  },
  plugins: [anywidget()],
  // e2e/ holds node:test files that run against a browser, through npm run e2e
  test: { include: ["js/**/*.test.ts"] },
});

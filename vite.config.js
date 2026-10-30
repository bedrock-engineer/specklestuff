import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import anywidget from "@anywidget/vite";

// @speckle/viewer, three.js and 3d-tiles-renderer stay out of the bundles: the widgets import
// them from esm.sh, at the exact versions package.json pins. ?target=es2022 on every URL makes
// esm.sh serve the viewer's own three.js import and ours from one module, so the markers we
// add are the viewer's three.js objects. A package that has three as a peer dependency
// (3d-tiles-renderer) would get esm.sh's latest three.js unless &deps pins the viewer's.
const { dependencies } = JSON.parse(readFileSync(new URL("package.json", import.meta.url)));
const THREE_PEERS = new Set(["3d-tiles-renderer"]);
// Modules of the dependencies that the widgets import by path
const SUBPATHS = [
  "three/examples/jsm/loaders/GLTFLoader.js",
  "three/examples/jsm/libs/meshopt_decoder.module.js",
];

function esmShUrl(specifier) {
  const name = Object.keys(dependencies).find(
    (dependency) => specifier === dependency || specifier.startsWith(`${dependency}/`),
  );
  const path = specifier.slice(name.length);
  const deps = THREE_PEERS.has(name) ? `&deps=three@${dependencies.three}` : "";
  return `https://esm.sh/${name}@${dependencies[name]}${path}?target=es2022${deps}`;
}

export const ESM_SH = Object.fromEntries(
  [...Object.keys(dependencies), ...SUBPATHS].map((specifier) => [specifier, esmShUrl(specifier)]),
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

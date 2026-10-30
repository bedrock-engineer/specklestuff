import { readFileSync } from "node:fs";
import { defineConfig } from "vite";

// The npm package's build: src/index.ts into dist/index.js, ES module, with the dependencies
// left as imports, so an app that uses three.js itself bundles one copy of it. The widget
// bundles in the wheel are another build (the root vite.config.js), with everything in.
const { dependencies } = JSON.parse(readFileSync(new URL("package.json", import.meta.url)));
const external = Object.keys(dependencies);

export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
    minify: false,
    lib: { entry: "src/index.ts", formats: ["es"], fileName: () => "index.js" },
    rollupOptions: {
      // three/examples/jsm/... as well as three
      external: (id) => external.some((name) => id === name || id.startsWith(`${name}/`)),
    },
  },
});

import { defineConfig } from "vite";
import anywidget from "@anywidget/vite";
import license from "rollup-plugin-license";

// One entry per widget. anywidget loads each _esm file as a self-contained module (relative
// imports don't resolve from a blob URL), so every entry gets its own vite build: a single
// multi-entry build would split shared code into chunks the entries import relatively.
// build.mjs loops over the entries.
export const ENTRIES = ["js/speckle-viewer.ts", "js/geo-speckle-viewer.ts"];
export const OUT_DIR = "src/specklewidgets/static";

// Packages that ship no license file get a pointer instead of the text. The Apache-2.0 text,
// for the @speckle packages, is the package's own LICENSE.
function licenseReport(dependencies) {
  const header =
    "Third-party software bundled into this widget, with the license each package ships.\n" +
    "The Apache License 2.0 is in this package's LICENSE file.\n\n";
  return (
    header +
    dependencies
      .map((dependency) =>
        dependency.licenseText
          ? dependency.text()
          : `${dependency.text()}\nLicense Text: none in the npm package; ${dependency.license}, ` +
            `see ${dependency.repository?.url ?? dependency.homepage}`,
      )
      .join("\n\n---\n\n")
  );
}

/**
 * The build of one widget entry. @speckle/viewer, @speckle/objectloader2 and three.js are
 * bundled in, so the widget loads from the wheel alone, and npm's single copy of three.js is
 * the one the viewer, its three-mesh-bvh and troika dependencies, and our markers all use.
 * Each bundle's third-party licenses go next to it as <name>.LICENSES.txt.
 */
export function widgetConfig(entry, { watch = false } = {}) {
  const name = entry.replace(/^.*\//, "").replace(/\.ts$/, "");
  return {
    build: {
      outDir: OUT_DIR,
      emptyOutDir: false,
      // Unminified: stack traces in the browser console stay readable, and our own code
      // stays readable in diffs. Minifying would save 0.5 MB of 2.7, 50 kB gzipped in the wheel.
      minify: false,
      lib: { entry: [entry], formats: ["es"], fileName: () => `${name}.js` },
      watch: watch ? {} : null,
    },
    // Library mode leaves process.env.NODE_ENV to the consumer; the viewer's dependencies read
    // it, and anywidget runs the bundle as it is
    define: { "process.env.NODE_ENV": JSON.stringify("production") },
    plugins: [
      anywidget(),
      license({
        thirdParty: {
          output: { file: `${OUT_DIR}/${name}.LICENSES.txt`, template: licenseReport },
        },
      }),
    ],
  };
}

export default defineConfig({
  ...widgetConfig(process.env.ENTRY ?? ENTRIES[0]),
  // e2e/ holds node:test files that run against a browser, through npm run e2e
  test: { include: ["js/**/*.test.ts", "site/**/*.test.ts"] },
});

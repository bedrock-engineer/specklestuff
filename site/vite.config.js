import { defineConfig } from "vite";

// The demo page for GitHub Pages: site/index.html and what it imports, the widget's js/
// among it, into site/dist. site/sixty5.py writes the data into site/public/data first.
export default defineConfig({
  root: import.meta.dirname,
  // Relative URLs, so the page works under any repository's Pages path
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // The viewer, three.js and MapLibre: one page, loaded once
    chunkSizeWarningLimit: 5000,
  },
});

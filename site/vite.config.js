import { readFileSync } from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";

// Whose page this is: specklestuff's, or bimpolars' (its Pages workflow sets SITE=bimpolars).
// site/intro/<SITE>.html is the header: its h1 the title, the rest the intro.
const site = process.env.SITE || "specklestuff";

// The demo page for GitHub Pages: site/index.html and what it imports, the npm package
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
  plugins: [
    {
      name: "site-intro",
      transformIndexHtml(html) {
        const intro = readFileSync(path.join(import.meta.dirname, "intro", `${site}.html`), "utf8");
        const [, h1, rest] = intro.match(/<h1>(.*?)<\/h1>(.*)/s);
        const title = h1.replace(/<[^>]*>/g, "").trim();
        return html.replaceAll("<!-- title -->", title).replace("<!-- intro -->", rest.trim());
      },
    },
  ],
});

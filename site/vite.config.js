import { readFileSync } from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";

// Whose page this is: specklestuff's, or bimpolars' (its Pages workflow sets SITE=bimpolars).
// site/intro/<SITE>.html is the header: its h1 the title, the rest the intro, and its
// <meta name="description"> the link preview's text.
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
        const text = (fragment) =>
          fragment
            .replace(/<[^>]*>/g, "")
            .replace(/\s+/g, " ")
            .trim();
        // The link preview's text, written for it rather than taken from the intro, which points
        // at the viewer below. Its paragraphs are rewrapped and rejoined with a blank line: apps
        // that keep line breaks in a preview show them, the others a space. It stays escaped as
        // the attribute value it was.
        const meta = intro.match(/<meta\s+name="description"\s+content="([^"]*)"\s*\/?>/);
        if (!meta) {
          throw new Error(`site/intro/${site}.html has no <meta name="description" content="...">`);
        }
        const description = meta[1]
          .split(/\n\s*\n/)
          .map(text)
          .filter(Boolean)
          .join("\n\n");
        return html
          .replaceAll("<!-- title -->", text(h1))
          .replaceAll("<!-- description -->", description)
          .replace("<!-- url -->", `https://bedrock-engineer.github.io/${site}/`)
          .replace("<!-- intro -->", rest.trim());
      },
    },
  ],
});

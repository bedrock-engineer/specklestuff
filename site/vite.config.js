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
        const text = (fragment) =>
          fragment
            .replace(/<[^>]*>/g, "")
            .replace(/\s+/g, " ")
            .trim();
        // The intro's paragraphs as sentences, the arrow that points at the viewer below left out
        const paragraphs = rest.split("</p>").map(text).filter(Boolean);
        const description = paragraphs
          .map((paragraph, i) => {
            let sentence = paragraph.replace(/^↓\s*/, "");
            if (sentence !== paragraph && !paragraphs[i - 1]?.endsWith(":")) {
              sentence = sentence[0].toUpperCase() + sentence.slice(1);
            }
            return /[.:!?]$/.test(sentence) ? sentence : `${sentence}.`;
          })
          .join(" ")
          .replaceAll('"', "&quot;");
        return html
          .replaceAll("<!-- title -->", text(h1))
          .replaceAll("<!-- description -->", description)
          .replace("<!-- url -->", `https://bedrock-engineer.github.io/${site}/`)
          .replace("<!-- intro -->", rest.trim());
      },
    },
  ],
});

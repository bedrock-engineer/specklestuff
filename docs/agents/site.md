# The demo page

`site/` is the demo page for GitHub Pages (`.github/workflows/pages.yml`, on every push to main;
bimpolars' own Pages workflow builds the same page from this repository's main): Sixty5 in a
GeoSpeckleViewer beside a map of the clicked element's footprint, the layout side by side
(stacked below 900 px), as joost chose. `just site-data`, `just site` and `just site-dev` build
and serve it.

## How it is built

- `sixty5.py` writes its data into `site/public/data/` (gitignored): GeoSpeckleViewer's traits
  (`viewer.json`, the model as `objects.json.gz`) and the drawn rows' `geog` footprints in 2D
  (`footprints.geojson`, with id, class, name, storey and the storey's elevation in metres;
  `outline.geojson` their union).
- `main.ts` calls the widget's own `render` with a `StaticModel` (`static-model.ts`: an AnyModel
  without a kernel, firing `change:<trait>` on `set`), sets `height` to the pane's, and follows
  `selected` with `footprint-map.ts` (MapLibre on PDOK's luchtfoto, or BRT).
- `e2e/site.test.mjs` writes the data offline, builds the page into `e2e/.out/site` and serves
  it as Pages does.

## Rules

- The demo page is the widget, not a copy: it imports `js/geo-speckle-viewer.ts` and calls its
  `render` with only `model` and `el`, so a widget's `render` reads nothing else.
- Pages runs no Python, so whatever the page needs from Python is computed by `site/sixty5.py`
  at build time.
- maplibre-gl is a devDependency (the page's, never in a widget bundle); MapLibre 6 loads its
  worker from its own folder, which the bundle is not, so `footprint-map.ts` passes it
  `maplibre-gl/dist/maplibre-gl-worker.mjs?url`, and a server must send `.mjs` as JavaScript
  (GitHub Pages does).
- The model goes out as `objects.json.gz`, served as it is (Pages sends no Content-Encoding for
  it), and the page gunzips it as the widget does a Bytes trait.
- URLs are relative (`base: "./"`), so the page works under any repository's path.

## Known numbers

The demo page (`site/`, `e2e/site.test.mjs`, 80 s in the cloud): `site/sixty5.py` takes 25 s and
writes 1363 footprints (every drawn row has one), `footprints.geojson` 1.6 MB and
`objects.json.gz` 1.2 MB; the page's bundle is 3.0 MB (1.0 MB gzipped) and MapLibre's worker
0.5 MB.

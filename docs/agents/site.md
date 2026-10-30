# The demo page

`site/` is the demo page for GitHub Pages (`.github/workflows/pages.yml`, on every push to main;
bimpolars' own Pages workflow builds the same page from this repository's main): Sixty5 in a
GeoSpeckleViewer beside a map of the clicked element's footprint, the layout side by side with a
draggable separator, as joost chose. The instructions are a strip over the panes that reads as
one sentence ("Click a BIM element to see its footprint on the map"), split on two grid columns
at the word space over the separator's middle so that it moves with it; the separator stops under
the strip (joost: "should really read as a single sentence"). Below 900 px the panes stack, without a separator, beside a
strip on the right (`.rail`) that holds the instructions written vertically and is the only place
on the panes where a swipe scrolls the page: the panes are `touch-action: none`, so their touches
always move the camera or the map (joost, on his phone). There the header's intro is a `<details>`
collapsed to the title, which a tap opens; an inline script in `index.html` opens it side by side
before the first paint. `just site-data`,
`just site` and `just site-dev` build and serve it.

## How it is built

- `sixty5.py` writes its data into `site/public/data/` (gitignored): GeoSpeckleViewer's traits
  (`viewer.json`, the model as `objects.json.gz`) and the drawn rows' `geog` footprints in 2D
  (`footprints.geojson`, with id, class, name, storey and the storey's elevation in metres;
  `outline.geojson` their union).
- `main.ts` runs the widget with `mountGeoSpeckleViewer` from `@bedrock-engineer/geospeckle-viewer`
  (a `StaticModel`: an AnyModel without a kernel, firing `change:<trait>` on `set`), sets
  `height` to the pane's, and follows
  `selected` with `footprint-map.ts` (MapLibre on PDOK's BRT, or its luchtfoto; the building's
  outline dotted red). `splitter.ts` sets the panes' `--viewer-share` and `--map-share`; the
  viewer and the map follow their panes' sizes with ResizeObservers of their own.
- The header's title and intro are `site/intro/<SITE>.html`, which `vite.config.js` puts into
  `index.html`, the h1 as the `<title>` too: `SITE` is unset (specklestuff) or `bimpolars`, which
  bimpolars' Pages workflow sets (`SITE=bimpolars just site` builds that one here). The header's two-row hint says how to select; the card
  on the map stays empty, and out of sight, until something is selected.
- `e2e/site.test.mjs` writes the data offline, builds the page into `e2e/.out/site` and serves
  it as Pages does.

## Rules

- The demo page is the widget, not a copy: `site/` is a workspace package (`site/package.json`)
  that imports `@bedrock-engineer/geospeckle-viewer` by name, as any other web app would, and
  `mountGeoSpeckleViewer` calls the widget's `render` with only `model` and `el`, so a widget's
  `render` reads nothing else. Add the model's handlers before awaiting `loaded`.
- Pages runs no Python, so whatever the page needs from Python is computed by `site/sixty5.py`
  at build time.
- maplibre-gl is a dependency of `site/` only, never in a widget bundle; MapLibre 6 loads its
  worker from its own folder, which the bundle is not, so `footprint-map.ts` passes it
  `maplibre-gl/dist/maplibre-gl-worker.mjs?url`, and a server must send `.mjs` as JavaScript
  (GitHub Pages does).
- The model goes out as `objects.json.gz`, served as it is (Pages sends no Content-Encoding for
  it), and the page gunzips it as the widget does a Bytes trait.
- URLs are relative (`base: "./"`), so the page works under any repository's path.

## Known numbers

The demo page (`site/`, `e2e/site.test.mjs`, 4 minutes in the cloud, 1.5 of them the separator's
test, as SwiftShader redraws the model at each width, and 1.5 the phone's, whose touches wait on
the model loading): `site/sixty5.py` takes 25 s
and writes 1363 footprints (every drawn row has one), `footprints.geojson` 1.6 MB and
`objects.json.gz` 1.2 MB; the page's bundle is 3.0 MB (1.0 MB gzipped) and MapLibre's worker
0.5 MB.

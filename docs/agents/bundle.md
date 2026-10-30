# The JS bundles

`js/` holds one entry per widget (`speckle-viewer.ts`, `geo-speckle-viewer.ts`), each composing
`js/lib/` modules: `viewer.ts` mounts the SpeckleViewer both entries share (models, selection,
markers, the report) and hands back the viewer for the geo entry to add the ground map and the
3D Tiles ([geo.md](geo.md)). Pure logic (selection, the element count, gunzip, the map's tiles,
hiding features) is in `js/lib` with colocated `*.test.ts` (vitest); `js/types/` declares what
@types/three 0.140 leaves out (the meshopt decoder).

## Builds

- `just build` writes the bundles into `src/specklewidgets/static/`, which is committed,
  unminified (`minify: false`), so that the wheel and `git+` installs need no node. Each bundle
  comes with its `<name>.LICENSES.txt`, the third-party licenses rollup-plugin-license
  collects. CI's `just check-bundle` fails when the committed bundle is not the build of the
  committed `js/`.
- One vite build per widget entry (`vite.config.js` `ENTRIES`, looped by `build.mjs`):
  anywidget loads each `_esm` as one self-contained module, so entries must not share chunks
  or load relative assets. Each bundle carries its own viewer and three.js, so a notebook with
  both widgets loads three.js twice (three warns; the widgets share no objects).

## Dependencies

- `@speckle/viewer`, `@speckle/objectloader2`, `three` and `3d-tiles-renderer` are bundled in,
  at the exact versions in package.json's `dependencies`. The widgets load nothing from a CDN.
- npm dedupes three to one copy, which the viewer's three-mesh-bvh and troika dependencies and
  3d-tiles-renderer (three is its peer) resolve to as well, so the viewer, the tiles and our
  markers share one three.js. (esm.sh resolved those peer ranges to 0.172.0 and 0.186.1, and
  its builds failed for hours on 2026-10-30, which is why the widgets no longer load from it.)
- Bump the viewer, objectloader2 and three together, and check that `npm ls three --all` shows
  one version (it exits 1 on the peer ranges of 3d-tiles-renderer's unused dependencies, which
  want three >= 0.144).
- 3d-tiles-renderer 0.3.46 is the last for three.js 0.140; its npm dependencies (react,
  postprocessing, @takram) are for its r3f and plugin entries, which we do not import, and
  stay out of the bundle.

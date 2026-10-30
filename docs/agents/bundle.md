# The JS: the npm package and the widget bundles

The JS is a pnpm workspace (`pnpm-workspace.yaml`): `packages/geospeckle-viewer`, the npm
package `@bedrock-engineer/geospeckle-viewer` (joost, 2026-10-30: always the `@bedrock-engineer`
scope, spelled "geospeckle", and only this one package on npm, as `@speckle/viewer` is the
viewer), and `site/`, the demo page that uses it ([site.md](site.md)). The root package.json
is private and holds the tools.

`packages/geospeckle-viewer/src` holds one anywidget entry per widget (`speckle-viewer.ts`,
`geospeckle-viewer.ts`), each composing `lib/` modules: `viewer.ts` mounts the SpeckleViewer
both entries share (models, selection, markers, the report) and hands back the viewer for the
geo entry to add the ground map and the 3D Tiles ([geo.md](geo.md)). Pure logic (selection,
the element count, gunzip, the map's tiles, hiding features) is in `lib/` with colocated
`*.test.ts` (vitest, run from the root); `types/` declares what @types/three 0.140 leaves out
(the meshopt decoder). `index.ts` is the package's API for web pages: `mountGeoSpeckleViewer`
runs the geo entry's `render` on a `StaticModel` (`static-model.ts`, an AnyModel without a
kernel) with specklewidgets' defaults for the traits left out.

## Builds

- `just build` writes the widget bundles into `src/specklewidgets/static/`, which is
  committed, unminified (`minify: false`), so that the wheel and `git+` installs need no node.
  Each bundle comes with its `<name>.LICENSES.txt`, the third-party licenses
  rollup-plugin-license collects (the package itself is left out of it). CI's
  `just check-bundle` fails when the committed bundle is not the build of the committed source.
- One vite build per widget entry (the root `vite.config.js` `ENTRIES`, looped by
  `build.mjs`): anywidget loads each `_esm` as one self-contained module, so entries must not
  share chunks or load relative assets. Each bundle carries its own viewer and three.js, so a
  notebook with both widgets loads three.js twice (three warns; the widgets share no objects).
- `just build-npm` builds the npm package into `packages/geospeckle-viewer/dist` (not
  committed; CI builds it): `index.js` with the dependencies left as imports
  (`packages/geospeckle-viewer/vite.config.js`), and the declarations in `dist/types` (tsc with
  the package's `tsconfig.json`). In the workspace, `exports` points at `src/index.ts`, so the
  site and the tests need no build; `publishConfig.exports` points a published package at
  `dist/`. Publishing, to npm and PyPI from one release tag, is issue #15; release-it already
  bumps the package's version with pyproject's.

## Dependencies

- `@speckle/viewer`, `@speckle/objectloader2`, `three` and `3d-tiles-renderer` are the
  package's `dependencies`, at exact versions. The widget bundles carry them; the npm package
  imports them. The widgets load nothing from a CDN.
- pnpm resolves three to one copy, 0.140.2, which the viewer's three-mesh-bvh and troika
  dependencies and 3d-tiles-renderer (three is its peer) take as well, so the viewer, the
  tiles and our markers share one three.js. (esm.sh resolved those peer ranges to 0.172.0 and
  0.186.1, and its builds failed for hours on 2026-10-30, which is why the widgets no longer
  load from it.)
- Bump the viewer, objectloader2 and three together, and check that `pnpm why -r three` shows
  one version. `pnpm install` warns about unmet peers: those are 3d-tiles-renderer's unused
  dependencies, which want three >= 0.144.
- 3d-tiles-renderer 0.3.46 is the last for three.js 0.140; its npm dependencies (react,
  postprocessing, @takram) are for its r3f and plugin entries, which we do not import, and
  stay out of the bundle.
- pnpm runs no install scripts unless `pnpm-workspace.yaml` lists them; esbuild and
  msgpackr-extract (for bull, a server-side peer of @speckle/shared) are skipped on purpose.

# specklewidgets

anywidgets around Speckle's web viewer (`@speckle/viewer`), fed with Speckle v3 objects from
Python instead of a Speckle server. Laid out like `bedrock-engineer/cpt-anywidget`. The words
model, element, definition, member and placement are defined in [CONTEXT.md](CONTEXT.md).

## Layout

- `src/specklewidgets/`: the Python package, the single source of truth for the Python API;
  `static/` holds the built bundles, committed.
- `packages/geospeckle-viewer/`: the npm package `@bedrock-engineer/geospeckle-viewer`, the
  only JS package (not published yet, issue #15): one widget entry per widget in `src/`,
  composing `src/lib/` modules, and `src/index.ts`, the API for web pages.
- `examples/`: marimo notebooks, each with an e2e test in `e2e/`.
- `site/`: the demo page for GitHub Pages, a pnpm workspace package that uses the npm package.
- `sandbox/oauth/`: the old OAuth widget, not packaged, not linted.

## Commands

just is the task runner (the repo has two toolchains, pnpm and uv): `just` lists the recipes,
and CI runs the same ones.

- `just build` after every change in `packages/geospeckle-viewer/src`, and commit
  `src/specklewidgets/static/`.
- `just check` (`check-js` and `check-py`: typecheck, vitest, oxlint, oxfmt, ruff, mypy,
  pytest) passes on every commit; `just e2e` runs the example notebooks in headless Chromium.
- Recipes run in sh (Git Bash on Windows). package.json scripts stay single commands, with no
  `rm -rf` and no `VAR=x` prefixes, because pnpm runs them in cmd.exe on Windows (`build.mjs`
  cleans and loops in node for that reason).

## Rules

- Python: typed (`mypy --strict`), Google-style docstrings (ruff `D`), `uv` + hatchling,
  Python >= 3.12.
- Trait names stay the JSON wire format; facades only translate arguments.
  `packages/geospeckle-viewer/src/lib/types.ts` is the TS mirror of the trait comments, and
  `src/index.ts`'s defaults mirror the traits' defaults: change them together.
- The Python core depends on anywidget and traitlets only and imports nothing else. Each
  module with more lives behind an extra: `specklewidgets.bim` (`[bim]`: specklepy, plus the
  bimpolars, numpy and polars any BimDataFrame brings; bimpolars stays a dev dependency, as it
  is not on PyPI), `specklewidgets.geo` (`[geo]`) and `specklewidgets.server` (`[server]`).
  `test_the_core_imports_neither_bimpolars_nor_specklepy` (test_facade.py) and
  `test_a_bimdataframe_without_specklepy_names_the_extra` (test_bim.py) run in a subprocess with
  `sys.modules[...] = None` to keep it that way.

## Docs

Read the doc of an area before you change its code or write its tests:

- [The JS](docs/agents/bundle.md): the pnpm workspace, the npm package, the widget bundles,
  the dependencies, bumping the viewer and three.js.
- [SpeckleViewer](docs/agents/viewer.md): `@speckle/viewer`'s quirks, `models_gz`,
  `object_count` and `scene_bbox`.
- [The BimDataFrame intake](docs/agents/bim.md): `specklewidgets.bim`, and what a round trip
  keeps.
- [The surroundings](docs/agents/geo.md): GeoSpeckleViewer and `specklewidgets.geo`, the ground
  map, the 3D BAG, heights and the NSGI grids.
- [Speckle server](docs/agents/server.md): `specklewidgets.server`, tokens, the fake server and
  the live tests.
- [The demo page](docs/agents/site.md): `site/`, its build-time data and the Pages workflow.
- [Test data and the e2e tests](docs/agents/testing.md): the bucket, the e2e tests, and running
  them in a cloud container.

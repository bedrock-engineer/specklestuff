# specklewidgets

anywidgets around Speckle's web viewer (`@speckle/viewer`), fed with Speckle v3 objects from
Python instead of a Speckle server. Laid out like `bedrock-engineer/cpt-anywidget`. The words
model, element, definition, member and placement are defined in [CONTEXT.md](CONTEXT.md).

## Layout

- `src/specklewidgets/`: the Python package, the single source of truth for the Python API;
  `static/` holds the built bundles, committed.
- `js/`: one entry per widget, composing `js/lib/` modules.
- `examples/`: marimo notebooks, each with an e2e test in `e2e/`.
- `sandbox/oauth/`: the old OAuth widget, not packaged, not linted.

## Commands

just is the task runner (the repo has two toolchains, npm and uv): `just` lists the recipes,
and CI runs the same ones.

- `just build` after every change in `js/`, and commit `src/specklewidgets/static/`.
- `just check` (`check-js` and `check-py`: typecheck, vitest, oxlint, oxfmt, ruff, mypy,
  pytest) passes on every commit; `just e2e` runs the example notebooks in headless Chromium.
- Recipes run in sh (Git Bash on Windows). package.json scripts stay single commands, with no
  `rm -rf` and no `VAR=x` prefixes, because npm runs them in cmd.exe on Windows (`build.mjs`
  cleans and loops in node for that reason).

## Rules

- Python: typed (`mypy --strict`), Google-style docstrings (ruff `D`), `uv` + hatchling,
  Python >= 3.12.
- Trait names stay the JSON wire format; facades only translate arguments. `js/lib/types.ts` is
  the TS mirror of the trait comments: change them together.
- The Python core depends on anywidget and traitlets only and imports nothing else. Each
  module with more lives behind an extra: `specklewidgets.bim` (`[bim]`: specklepy, plus the
  bimpolars, numpy and polars any BimDataFrame brings; bimpolars stays a dev dependency, as it
  is not on PyPI), `specklewidgets.geo` (`[geo]`) and `specklewidgets.server` (`[server]`).
  `test_the_core_imports_neither_bimpolars_nor_specklepy` (test_facade.py) and
  `test_a_bimdataframe_without_specklepy_names_the_extra` (test_bim.py) run in a subprocess with
  `sys.modules[...] = None` to keep it that way.

## Docs

Read the doc of an area before you change its code or write its tests:

- [The JS bundles](docs/agents/bundle.md): the vite builds, the bundled dependencies, bumping
  the viewer and three.js.
- [SpeckleViewer](docs/agents/viewer.md): `@speckle/viewer`'s quirks, `models_gz`,
  `object_count` and `scene_bbox`.
- [The BimDataFrame intake](docs/agents/bim.md): `specklewidgets.bim`, and what a round trip
  keeps.
- [The surroundings](docs/agents/geo.md): GeoSpeckleViewer and `specklewidgets.geo`, the ground
  map, the 3D BAG, heights and the NSGI grids.
- [Speckle server](docs/agents/server.md): `specklewidgets.server`, tokens, the fake server and
  the live tests.
- [Test data and the e2e tests](docs/agents/testing.md): the bucket, the e2e tests, and running
  them in a cloud container.

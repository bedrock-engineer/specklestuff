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
- `examples/`: marimo notebooks; `e2e/` opens them and the demo page in headless Chromium.
- `site/`: the demo page for GitHub Pages, a pnpm workspace package that uses the npm package.
- `sandbox/oauth/`: the old OAuth widget, not packaged, not linted.

## Commands

just is the task runner (the repo has two toolchains, pnpm and uv): `just` lists the recipes,
and CI runs the same ones. CI on a PR is `check-js`, `check-bundle`, `build-npm` and `check-py`,
a few minutes; the e2e workflow runs only when started by hand.

- `just build` after every change in `packages/geospeckle-viewer/src`, and commit
  `src/specklewidgets/static/`.
- `just check` (`check-js` and `check-py`: typecheck, vitest, oxlint, oxfmt, ruff, mypy,
  pytest) passes on every commit. `just e2e` (15 to 20 minutes) runs the example notebooks and
  the demo page in headless Chromium: run it, or the e2e workflow, after changing how the
  widgets load or draw, and before a release.
- Recipes run in sh (Git Bash on Windows). package.json scripts stay single commands, with no
  `rm -rf` and no `VAR=x` prefixes, because pnpm runs them in cmd.exe on Windows (`build.mjs`
  cleans and loops in node for that reason).

## Rules

- specklestuff is pre-release and changes fast (joost, 2026-10-30): check a change you can see
  by looking at it, a Playwright screenshot of the notebook or the page that you attach to your
  reply or PR, not by adding an e2e test. Add no e2e tests for layout or styling; keep unit
  tests for logic. When a change of yours breaks an existing e2e test for a detail that changed
  on purpose, update or drop that test and say so.
- Python: typed (`mypy --strict`), `uv` + hatchling, Python >= 3.12, Google-style docstrings
  in the shape marimo's documentation panel renders: read
  [docstrings.md](docs/agents/docstrings.md) before writing one. ruff `D` and
  `tests/test_docstrings.py` check it.
- Trait names stay the JSON wire format; facades only translate arguments.
  `packages/geospeckle-viewer/src/lib/types.ts` is the TS mirror of the trait comments, and
  `src/index.ts`'s defaults mirror the traits' defaults: change them together.
- The Python package depends on anywidget, traitlets and specklepy, and has no extras. The
  viewers import neither specklepy nor bimpolars: `specklewidgets.bim` (specklepy's serializer
  and bimpolars) is imported only for a BimDataFrame, and `specklewidgets.geo` (bimpolars and
  its pyproj) and `specklewidgets.server` (`bimpolars[speckle]`) only when used. bimpolars
  stays a dev dependency, as it is not on PyPI: any BimDataFrame brings it.
  `test_the_core_imports_neither_bimpolars_nor_specklepy` (test_facade.py) runs in a
  subprocess with `sys.modules[...] = None` to keep it that way.

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

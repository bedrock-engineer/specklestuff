# specklewidgets

anywidgets around Speckle's web viewer (`@speckle/viewer`), fed with Speckle v3 objects from
Python instead of a Speckle server. Laid out like `bedrock-engineer/cpt-anywidget`.

## Files

- `src/specklewidgets/`: the Python package, the single source of truth for the Python API.
  `speckle_viewer.py` (`SpeckleViewer`: traits + constructor facade; `Marker`), `models.py`
  (`models_gz`: packs models and adjusts what trips the viewer), `bim.py` (`bim_objects`,
  `bim_collection`: a BimDataFrame as v3 objects, the `[bim]` extra), `static/` the built
  bundles (committed, `minify: false`, so the wheel and `git+` installs need no node) and each
  bundle's `<name>.LICENSES.txt`, the third-party licenses rollup-plugin-license collects.
- `js/`: one entry per widget (`speckle-viewer.ts`) composing `js/lib/` modules;
  `js/lib/types.ts` is the TS mirror of the trait comments, change them together. Pure logic
  (selection, the element count, gunzip) is in `js/lib` with colocated `*.test.ts` (vitest).
- `examples/rvt_advanced_sample.py`: the marimo notebook with the three Revit Advanced Sample
  models; `e2e/notebook.test.mjs` opens it in headless Chromium.
  `examples/rvt_arch_bimdataframe.py`: the architectural model as BimDataFrames from
  `read_speckle` and `read_ifc`, two viewers; `e2e/bimdataframe.test.mjs` opens it.
  `e2e/marimo.mjs` serves a notebook and opens it for both.
- `sandbox/oauth/`: the old OAuth widget, not packaged, not linted.
- `CONTEXT.md`: the glossary (model, element, definition, member, placement).

## Rules

- just is the task runner (the repo has two toolchains, npm and uv): `just` lists the
  recipes and CI runs the same ones. `just build` after every change in `js/` and commit
  `src/specklewidgets/static/`; `just check` (`check-js` and `check-py`: typecheck, vitest,
  oxlint, oxfmt, ruff, mypy, pytest) must pass. Recipes run in sh (Git Bash on Windows);
  package.json scripts stay single commands without `rm -rf` or `VAR=x` prefixes, because npm
  runs them in cmd.exe on Windows (`build.mjs` cleans and loops in node for that reason).
- One vite build per widget entry (`vite.config.js` `ENTRIES`, looped by `build.mjs`):
  anywidget loads each `_esm` as one self-contained module, so entries must not share chunks
  or load relative assets.
- `@speckle/viewer`, `@speckle/objectloader2` and `three` are bundled in, at the exact versions
  in package.json's `dependencies`. npm dedupes three to one copy, which the viewer's
  three-mesh-bvh and troika dependencies resolve to as well, so the viewer and our markers
  share one three.js (esm.sh resolved those peer ranges to 0.172.0 and 0.186.1, and its builds
  failed for hours on 2026-10-30, which is why the widget no longer loads from it). Bump the
  three together, and check `npm ls three` shows one version.
- The Python core depends on anywidget and traitlets only and imports nothing else.
  `specklewidgets.bim` (the BimDataFrame intake) needs the extra `[bim]` (specklepy) and
  bimpolars, numpy and polars, which any BimDataFrame brings; bimpolars stays a dev dependency
  (it is not on PyPI). `SpeckleViewer` recognises a BimDataFrame by the class in
  `sys.modules["bimpolars.frame"]` and imports `specklewidgets.bim` only then.
  `tests/test_bim.py` and the data tests skip without bimpolars or specklepy.
  `test_the_core_imports_neither_bimpolars_nor_specklepy` (test_facade.py) and
  `test_a_bimdataframe_without_specklepy_names_the_extra` (test_bim.py) run in a subprocess
  with `sys.modules[...] = None` to keep it that way.
- The intake draws the rows with a mesh except `bimpolars.gltf.EXCLUDED_CLASSES` (openings),
  one DataObject per row (`applicationId` = `id`, so `object_count` = those rows), and writes
  each property set at the path its name gives, the inverse of `bimpolars.read_speckle`'s
  `_flatten`, so that `read_speckle` reads back the drawn rows' ids, classes, names, meshes
  and property sets (a test pins that). The other columns are plain fields, so they come back
  inside the `object` set, not as columns: `container` reads back null, and the spatial rows
  it points at have no mesh and are not drawn. Unstyled faces get no RenderMaterial, so they
  read back unstyled. Colours for `color` are the dataviz reference palette's light
  categorical slots and blue ramp (steps 250 to 700).
- Python: typed (`mypy --strict`), Google-style docstrings (ruff `D`), `uv` + hatchling,
  Python >= 3.12. Trait names stay the JSON wire format; facades only translate arguments.
- The viewer works in metres: `scene_bbox` and `markers` are in metres whatever the models'
  units.
- `object_count` is the number of elements the viewer draws, as a click selects them (nearest
  atomic node, then `elementOf`); `tests/test_rvt_advanced_sample.py` reaches the same numbers
  by a Python traversal, and the scene bbox from `bimpolars.read_speckle`. Change both sides
  together.

## Viewer facts (2.31.14)

- `SpeckleOfflineLoader` ignores the objects it is given; `MemoryLoader` (a `SpeckleLoader`
  over `ObjectLoader2Factory.createFromObjects`) loads each model into its own subtree,
  resource `memory/<root id>`.
- Its converter finds instance definition members by counting down nodes with a member
  applicationId and stops at zero, so two objects with one member id (specklepy's
  `def-geo-<n>` DataObject and its Mesh) end the search early ("Consumable applicationId ...
  could not be found"); and it removes only one tree copy of a member, so a member listed
  twice stays drawn at the definition's origin and its instances are never batched
  (`findId(baseId)` returns the non-instanced copy). `models_gz` fixes both in the data.
- It batches an instance's geometry as instanced only from 10,000 vertices up; smaller
  instances are drawn as ordinary meshes under their InstanceProxy node, and a definition
  placed once is drawn as its own objects, hence `singlePlacements` for selection.
- Headless Chromium needs `--enable-unsafe-swiftshader` for WebGL; a frame of the three RVT
  models takes tens of seconds in SwiftShader, so screenshots need long timeouts.

## Test data

The example and `tests/test_rvt_advanced_sample.py` read `rvt-advanced-sample/
speckle-v3-objects.parquet` through `bimpolars.data.fetch`: set `BIMPOLARS_DATA_DIR` to a local
copy of the bimpolars bucket, or let it download (16 MB). Known numbers (bucket file of
2026-10-29): arch 13,194 objects, str 5355, mep 16,173; drawn elements arch 5686, str 918,
mep 6942 (13,546 together); scene bbox x -116.6763..202.3891, y -121.7323..75.7287,
z -7.2..15.2066 m; `models_gz` of the three: 53 MB of JSON, 6.0 MB gzipped, 2 s.

The architectural model as BimDataFrames (`tests/test_rvt_arch_bimdataframe.py`, read_ifc
takes 45 s): `read_speckle` with the bundle draws 5568 rows (every row with a mesh), bbox x
-116.6763..202.3891, y -76.0339..75.7287, z -1.8288..12.5745 m; `read_ifc` of
`rvt-advanced-sample-arch.ifc` draws 5512 (5647 with a mesh less 135 openings), bbox x
-107.4743..211.5911, y -53.3989..98.3638, z -1.8288..12.4854 m. `bim_objects` takes 4 to 6 s
on either (specklepy hashes 17,600 objects, 36 to 45 MB of JSON).

The widget loads nothing from a CDN, so `just e2e` runs in the cloud containers as it does in
CI. The tests fail on any request to esm.sh and on three's "Multiple instances of Three.js"
warning. The two e2e files run one after the other (`--test-concurrency=1`): each starts
marimo and a SwiftShader Chromium through `openNotebook` in `e2e/marimo.mjs`.

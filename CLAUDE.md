# specklewidgets

anywidgets around Speckle's web viewer (`@speckle/viewer`), fed with Speckle v3 objects from
Python instead of a Speckle server. Laid out like `bedrock-engineer/cpt-anywidget`.

## Files

- `src/specklewidgets/`: the Python package, the single source of truth for the Python API.
  `speckle_viewer.py` (`SpeckleViewer`: traits + constructor facade; `Marker`), `models.py`
  (`models_gz`: packs models and adjusts what trips the viewer), `bim.py` (`bim_objects`,
  `bim_collection`: a BimDataFrame as v3 objects, the `[bim]` extra), `server.py`
  (`local_client`, `token_client`, `receive`, `send`, `ReceivedVersion`: a Speckle server, the
  `[server]` extra), `static/` the built bundles (committed, `minify: false`, so the wheel and
  `git+` installs need no node).
- `js/`: one entry per widget (`speckle-viewer.ts`) composing `js/lib/` modules;
  `js/lib/types.ts` is the TS mirror of the trait comments, change them together. Pure logic
  (selection, the element count, gunzip) is in `js/lib` with colocated `*.test.ts` (vitest).
- `examples/rvt_advanced_sample.py`: the marimo notebook with the three Revit Advanced Sample
  models; `e2e/notebook.test.mjs` opens it in headless Chromium.
  `examples/rvt_arch_bimdataframe.py`: the architectural model as BimDataFrames from
  `read_speckle` and `read_ifc`, two viewers; `e2e/bimdataframe.test.mjs` opens it.
  `e2e/marimo.mjs` serves a notebook and opens it for both.
  `examples/speckle_receive_send.py`: sign in, receive a version, compare it with the bucket's
  frame, send it back; no e2e test (it needs a server).
- `sandbox/oauth/`: the old OAuth widget, not packaged, not linted.
- `CONTEXT.md`: the glossary (model, element, definition, member, placement).

## Rules

- `npm run build` after every change in `js/` and commit `src/specklewidgets/static/`.
  `npm run typecheck`, `npm run test`, `npm run lint`, `npm run fmt:check`, `uv run pytest`,
  `uv run mypy src`, `uv run ruff check` and `uv run ruff format --check` must pass.
- One vite invocation per widget entry (`ENTRY=...`): anywidget loads each `_esm` as one
  self-contained module, so entries must not share chunks.
- `@speckle/viewer`, `@speckle/objectloader2` and `three` are externals on esm.sh at the exact
  versions in package.json's `dependencies`, every URL with `?target=es2022` (vite.config.js
  `ESM_SH`), so that esm.sh serves the viewer's three.js and ours as one module. Bump the three
  together: three must be the version the viewer's own range resolves to on esm.sh.
- The Python core depends on anywidget and traitlets only and imports nothing else.
  `specklewidgets.bim` (the BimDataFrame intake) needs the extra `[bim]` (specklepy) and
  bimpolars, numpy and polars, which any BimDataFrame brings; bimpolars stays a dev dependency
  (it is not on PyPI). `SpeckleViewer` recognises a BimDataFrame by the class in
  `sys.modules["bimpolars.frame"]` and imports `specklewidgets.bim` only then.
  `tests/test_bim.py` and the data tests skip without bimpolars or specklepy.
- `specklewidgets.server` needs the extra `[server]` (`specklepy[bundle]`: its bundle download
  imports pyarrow) and `bimpolars[speckle]` (`bimpolars.bundle.bundle_objects`, the
  projection of a bundle-only version with the two fixes specklepy's `to_base` lacks; never
  specklepy's own `operations.receive` of a bundle reference, which is the plain `to_base`).
  It uses specklepy's deprecated v3 pipeline on purpose (issue #4: until Speckle opens its
  bundle code; no upstream bug reports) and silences only those DeprecationWarnings, by
  message (`server._DEPRECATIONS`); a test in `tests/test_server.py` runs a send and a
  receive with DeprecationWarnings as errors.
- A token is never written to disk: `token_client` keeps it in the client, `send` passes
  `use_default_cache=False` (no SQLite object cache), and the example takes it from an
  `EnvConfig` field. `local_client` passes over an account whose token the server refuses
  (401, 403 or a GraphQL error) and lets other failures (an unreachable server) raise.
- `receive` downloads with `specklepy.bundle.download.download_bundle` (not
  `bundle.receive`, whose `Model` deletes its temporary folder on close and which raises
  instead of answering "no bundle"), into `<directory>/<model id>/<version id>/`, the bucket's
  `speckle-bundle` layout, and does not mark the version received.
- Server tests: `tests/test_server.py` runs everything against `tests/fake_speckle_server.py`,
  a localhost server for the requests specklepy makes (GraphQL by query text, ServerTransport's
  REST routes, the `/api/v2` artifact listing). When `server.py` starts using another
  specklepy call, teach the fake its request. `tests/test_server_live.py` (marker `live`,
  deselected by `addopts`; `uv run pytest -m live`) repeats them on app.speckle.systems and
  skips without a local account; `tests/round_trip.py` holds the checks both share.
- The intake draws the rows with a mesh except `bimpolars.gltf.EXCLUDED_CLASSES` (openings),
  one DataObject per row (`applicationId` = `id`, so `object_count` = those rows), and writes
  each property set at the path its name gives, the inverse of `bimpolars.read_speckle`'s
  `_flatten`, so that `read_speckle` reads the drawn rows back (a test pins that). Unstyled
  faces get no RenderMaterial, so they read back unstyled. Colours for `color` are the
  dataviz reference palette's light categorical slots and blue ramp (steps 250 to 700).
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

The server tests (`tests/test_server.py`, 35 s): receiving the bundle-only arch version from
the fake server gives the bucket's frame (`BimDataFrame.equals`), and its non-root objects
the bucket's ids; sending the arch frame (5568 drawn rows) and receiving it back keeps every
drawn row's id, class, triangles (corner by corner) and styles (name, face count, colour to
1/255), in 16 s. The live round trip sends the str frame (918 drawn rows) instead, to keep
the upload to joost's account small. The cloud containers cannot reach app.speckle.systems,
so the live tests have not run there (they skip); the fake covers the same calls offline.

esm.sh is blocked from the cloud containers: `npm run e2e` serves it from a mirror bundled out
of `node_modules` (`e2e/esm-mirror.mjs`), so it runs there as well. The two e2e files run one
after the other (`--test-concurrency=1`): each starts marimo and a SwiftShader Chromium.

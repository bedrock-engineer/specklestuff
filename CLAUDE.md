# specklewidgets

anywidgets around Speckle's web viewer (`@speckle/viewer`), fed with Speckle v3 objects from
Python instead of a Speckle server. Laid out like `bedrock-engineer/cpt-anywidget`.

## Files

- `src/specklewidgets/`: the Python package, the single source of truth for the Python API.
  `speckle_viewer.py` (`SpeckleViewer`: traits + constructor facade; `Marker`), `models.py`
  (`models_gz`: packs models and adjusts what trips the viewer), `bim.py` (`bim_objects`,
  `bim_collection`: a BimDataFrame as v3 objects, the `[bim]` extra),
  `geo_speckle_viewer.py` (`GeoSpeckleViewer`, a `SpeckleViewer` subclass with its own
  `_esm`; the `GroundMap` and `Tileset` TypedDicts of its traits), `geo.py` (the surroundings
  of a georeferenced BimDataFrame: `osm_ground_map`, `pdok_3d_buildings`, `site_3d_tiles`,
  `bag_panden_under`; the `[geo]` extra), `server.py` (`local_client`, `token_client`,
  `receive`, `send`, `ReceivedVersion`: a Speckle server, the `[server]` extra), `static/` the
  built bundles (committed, `minify: false`, so the wheel and `git+` installs need no node)
  and each bundle's `<name>.LICENSES.txt`, the third-party licenses rollup-plugin-license
  collects.
- `js/`: one entry per widget (`speckle-viewer.ts`, `geo-speckle-viewer.ts`) composing
  `js/lib/` modules: `viewer.ts` mounts the SpeckleViewer both entries share (models,
  selection, markers, the report) and hands back the viewer for the geo entry to add the
  ground map (`ground-map.ts`, `map-tiles.ts`) and the 3D Tiles (`context-tiles.ts`,
  `hide-features.ts`). `js/lib/types.ts` is the TS mirror of the trait comments, change them
  together. Pure logic (selection, the element count, gunzip, the map's tiles, hiding
  features) is in `js/lib` with colocated `*.test.ts` (vitest); `js/types/` declares what
  @types/three 0.140 leaves out (the meshopt decoder).
- `examples/rvt_advanced_sample.py`: the marimo notebook with the three Revit Advanced Sample
  models; `e2e/notebook.test.mjs` opens it in headless Chromium.
  `examples/rvt_arch_bimdataframe.py`: the architectural model as BimDataFrames from
  `read_speckle` and `read_ifc`, two viewers; `e2e/bimdataframe.test.mjs` opens it.
  `examples/sixty5_geo.py`: Sixty5's structural model in a GeoSpeckleViewer at Strijp-S;
  `e2e/geo.test.mjs` opens it offline (`e2e/offline-pdok/sitecustomize.py` answers PDOK's
  APIs in the kernel, `e2e/surroundings.mjs` serves the map's tiles and the 3D BAG's tile of
  boxes in the browser) and live where PDOK and OSM answer.
  `e2e/marimo.mjs` serves a notebook and opens it for all three (`openPage` opens any page:
  the demo page's test uses it).
  `examples/speckle_receive_send.py`: sign in, receive a version, compare it with the bucket's
  frame, send it back; no e2e test (it needs a server).
- `site/`: the demo page for GitHub Pages (`.github/workflows/pages.yml`, on every push to
  main; bimpolars' own Pages workflow builds the same page from this repository's main), the
  layout side by side (stacked below 900 px), as joost chose. `sixty5.py` writes its data into
  `site/public/data/` (gitignored): GeoSpeckleViewer's traits (`viewer.json`, the model as
  `objects.json.gz`) and the drawn rows' `geog` footprints in 2D (`footprints.geojson`, with
  id, class, name, storey and the storey's elevation in metres; `outline.geojson` their
  union). `main.ts` calls the widget's own `render` with a `StaticModel`
  (`static-model.ts`: an AnyModel without a kernel, firing `change:<trait>` on `set`), sets
  `height` to the pane's, and follows `selected` with `footprint-map.ts` (MapLibre on PDOK's
  luchtfoto, or BRT). `e2e/site.test.mjs` writes the data offline, builds the page into
  `e2e/.out/site` and serves it as Pages does.
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
  or load relative assets. Each bundle carries its own viewer and three.js, so a notebook
  with both widgets loads three.js twice (three warns; the widgets share no objects).
- `@speckle/viewer`, `@speckle/objectloader2`, `three` and `3d-tiles-renderer` are bundled in,
  at the exact versions in package.json's `dependencies`. npm dedupes three to one copy, which
  the viewer's three-mesh-bvh and troika dependencies and 3d-tiles-renderer (three is its peer)
  resolve to as well, so the viewer, the tiles and our markers share one three.js (esm.sh
  resolved those peer ranges to 0.172.0 and 0.186.1, and its builds failed for hours on
  2026-10-30, which is why the widgets no longer load from it). Bump the viewer, objectloader2
  and three together, and check that `npm ls three --all` shows one version (it exits 1 on
  the peer ranges of 3d-tiles-renderer's unused dependencies, which want three >= 0.144).
  3d-tiles-renderer 0.3.46 is the last for three.js 0.140; its npm dependencies (react,
  postprocessing, @takram) are for its r3f and plugin entries, which we do not import, and
  stay out of the bundle.
- The Python core depends on anywidget and traitlets only and imports nothing else.
  `specklewidgets.bim` (the BimDataFrame intake) needs the extra `[bim]` (specklepy) and
  bimpolars, numpy and polars, which any BimDataFrame brings; bimpolars stays a dev dependency
  (it is not on PyPI). `specklewidgets.geo` needs the extra `[geo]`: pyproj, what
  `bimpolars[geobim]` adds, listed as such until bimpolars is on PyPI. `SpeckleViewer`
  recognises a BimDataFrame by the class in `sys.modules["bimpolars.frame"]` and imports
  `specklewidgets.bim` only then.
  `tests/test_bim.py` and the data tests skip without bimpolars or specklepy.
  `test_the_core_imports_neither_bimpolars_nor_specklepy` (test_facade.py) and
  `test_a_bimdataframe_without_specklepy_names_the_extra` (test_bim.py) run in a subprocess
  with `sys.modules[...] = None` to keep it that way.
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
  `EnvConfig` field whose validator signs in once and keeps the client
  (`test_no_file_holds_the_token` sends and receives with every home and cache folder
  redirected and searches them). A token goes only where it was meant to: `local_client`
  signs each account in at the URL stored with it, scheme included, never the caller's URL
  (it only selects the accounts by host); `token_client` warns on plain http to a host other
  than loopback; bundle files come from presigned URLs without the token
  (`test_bundle_downloads_carry_no_token`). `local_client` passes over an account whose
  token the server refuses (HTTP 401 or 403, or a GraphQL error whose `extensions.code` is in
  `server._REFUSED_CODES`) and lets other failures (an unreachable server, any other GraphQL
  error) raise. It filters `get_local_accounts()` by host rather than calling
  `get_accounts_for_server`, which keeps one account per user in `os.listdir` order and so
  may drop the user's working account.
- `receive` downloads with `specklepy.bundle.download.download_bundle` (not
  `bundle.receive`, whose `Model` deletes its temporary folder on close and which raises
  instead of answering "no bundle"), into `<directory>/<model id>/<version id>/`, the bucket's
  `speckle-bundle` layout, and does not mark the version received. A temporary folder of
  its own is removed again when the receive fails or the version has no bundle.
- Server tests: `tests/test_server.py` runs everything against `tests/fake_speckle_server.py`,
  a localhost server for the requests specklepy makes (GraphQL by query text, ServerTransport's
  REST routes, the `/api/v2` artifact listing). When `server.py` starts using another
  specklepy call, teach the fake its request. `tests/test_server_live.py` (marker `live`,
  deselected by `addopts`; `just live`, which is `uv run pytest -m live`) repeats them on
  app.speckle.systems and skips without a local account; `tests/round_trip.py` holds the
  checks both share. The live round trip deletes a scratch project it made, and the objects
  with it; in `SPECKLEWIDGETS_TEST_PROJECT` it deletes only the model and the sent objects
  stay. A delete answered with False warns with the id instead of failing.
- A round trip through `send` and `receive` keeps the drawn rows' ids, classes, meshes and
  styles, not `container` (it comes back as the field
  `properties.object.container`: `read_speckle` sets the column from a bundle only) nor the
  levels (no mesh, not drawn); `simple_features` then lays each footprint at its own lowest z.
  Left so on purpose (bimpolars#21); `test_a_sent_bimdataframe_comes_back` pins it.
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
- The demo page is the widget, not a copy: it imports `js/geo-speckle-viewer.ts` and calls
  its `render` with only `model` and `el`, so a widget's `render` reads nothing else. Pages
  runs no Python, so whatever the page needs from Python is computed by `site/sixty5.py` at
  build time. maplibre-gl is a devDependency (the page's, never in a widget bundle); MapLibre
  6 loads its worker from its own folder, which the bundle is not, so `footprint-map.ts`
  passes it `maplibre-gl/dist/maplibre-gl-worker.mjs?url`, and a server must send `.mjs` as
  JavaScript (GitHub Pages does). The model goes out as `objects.json.gz`, served as it is
  (Pages sends no Content-Encoding for it), and the page gunzips it as the widget does a
  Bytes trait. URLs are relative (`base: "./"`), so the page works under any repository's
  path.
- `object_count` is the number of elements the viewer draws, as a click selects them (nearest
  atomic node, then `elementOf`); `tests/test_rvt_advanced_sample.py` reaches the same numbers
  by a Python traversal, and the scene bbox from `bimpolars.read_speckle`. Change both sides
  together.

## The surroundings (GeoSpeckleViewer, specklewidgets.geo)

- The viewer's world is the models' coordinates in metres. `specklewidgets.geo` goes from it
  to ECEF and back through one matrix, `bimpolars.geobim.linearized_site_to_ecef` of the
  BimDataFrame's CRS (`_World`), and between ECEF and longitude/latitude with pyproj's
  EPSG:4978/4979 conversion: the ground map, the 3D BAG (`ecef_to_world` is its inverse) and
  the BAG panden line up with each other exactly, and with PROJ's own transformation (by way
  of the Engineering CRS's base, as `with_geog` goes) to under a centimetre over Sixty5
  (`test_the_viewers_world_is_proj_to_a_centimetre`). A model must sit near its CRS's origin:
  a frame in EPSG:7415 would be linearized at RD's origin, off the map.
- `osm_ground_map`'s affine from longitude and latitude to the world is good to 11 mm at the
  corners of Sixty5's 500 m map: the meridians converge. The front end draws OSM's raster tiles
  into a canvas itself (`map-tiles.ts`: the zoom whose tiles come closest to the image's
  resolution, up to 19), where geospeckle rendered a MapLibre map off-screen: no MapLibre and
  no second WebGL context.
- The map and the tiles are on the PROPS layer and added to the scene directly, as the
  markers are, so `object_count` and `scene_bbox` leave them out. `GroundInView` pushes the
  camera's far plane out to the map's farthest corner every frame; `ContextTiles` updates the
  tiles for the camera every frame and hides the features of each tile as it arrives
  (`hideFeaturesWithin`: more than half of a feature's vertices in a polygon; three.js 0.140
  returns quantized positions as stored, so they are scaled first). `surroundings` reports
  the map's plane, the tile contents loaded, the features hidden in them and the heights those
  span in the world, 250 ms after the last change.
- PDOK's 3D BAG is a tree of external tilesets; `site_3d_tiles` walks it along the tiles that
  overlap the area (3d-tiles-renderer 0.3.46 would fetch every child of a tile without content,
  half the country's tilesets) and gives a one-level tileset of the finest tiles there (and
  of the content of the tiles that refine by `ADD` on the way).
- `bag_panden_under` keeps a pand with more than half of its area under the footprint;
  `pdok_3d_buildings` grows the `hide_within` polygons by `hide_margin` (0.5 m) so that a
  building's vertices on its pand's outline count as within.
- PDOK's 3D Tiles are at ellipsoidal heights, and the world's z = 0 is the site origin's NAP
  height, so the 3D BAG stands on the ground map only with the NSGI grids. Without them PROJ
  passes NAP off as ellipsoidal heights (bimpolars warns): the model sits within about a metre
  of PDOK's data in plan, and the 3D BAG floats 44 m above it. The example turns PROJ's
  network on (`pyproj.network.set_network_enabled(True)`, as bimpolars' Sixty5 notebook
  does), so PROJ fetches the grids; CI's pytest sets `PROJ_NETWORK=ON`, so that the tests of
  the `grids` fixture run, and the offline stand-in's tile stands at the true height. The
  tiles' `region` heights say nothing about it: both of PDOK's leaves at Sixty5 (zoom 9,
  2026-10-30) start at 23.91 m, where the ground is at 62.5 m ellipsoidal (18.6 m NAP). What
  does is `surroundings.hidden_heights`, the world heights of the 3D BAG's Sixty5 as drawn:
  the geo e2e wants its bottom within 3 m of the map (z = 0, AHN4 at the site origin).

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

Sixty5's structural model (`tests/test_geo.py`, `e2e/geo.test.mjs`): read_ifc takes 14 s; its
BAG pand (under the slabs and footings) is `0772100001025175`, and the 3D BAG over the map two
zoom-9 tiles (PDOK, 2026-10-30); 1363 rows drawn (with a mesh, less 1284 openings), bbox x
-2.24..33.585, y -0.001..55.69, z -30.4..56.64 m in the site grid; the plan extent of all rows'
`bbox` turned by -50.36 degrees gives `osm_ground_map` bounds 5.457095..5.464129 E,
51.444345..51.448716 N with the 150 m margin, a 2048 x 2042 image (without the grids). The site
origin is at 5.4601517 E, 51.4464756 N, ellipsoidal height 62.544 m (NAP 18.625 m and
NLGEO2018's 43.919 m) with the NSGI grids, and at 5.460153 E, 51.446476 N, 18.625 m without
them. The live e2e (CI, 2026-10-30) draws the 3D BAG's Sixty5 from 0.04 to 57.28 m: PDOK's
heights are ellipsoidal, and with the grids the 3D BAG stands on the map.

The demo page (`site/`, `e2e/site.test.mjs`, 80 s in the cloud): `site/sixty5.py` takes 25 s
and writes 1363 footprints (every drawn row has one), `footprints.geojson` 1.6 MB and
`objects.json.gz` 1.2 MB; the page's bundle is 3.0 MB (1.0 MB gzipped) and MapLibre's worker
0.5 MB.

The server tests (`tests/test_server.py`, 31 tests, 38 s): receiving the bundle-only arch
version from the fake server gives the bucket's frame (`BimDataFrame.equals`), and its non-root
objects the bucket's ids; sending the arch frame (5568 drawn rows) and receiving it back keeps every
drawn row's id, class, triangles (corner by corner) and styles (name, face count, colour to
1/255), in 16 s. The live round trip sends the str frame (918 drawn rows) instead, to keep
the upload to joost's account small. The cloud containers cannot reach app.speckle.systems,
so the live tests have not run there (they skip); the fake covers the same calls offline.

The widgets load nothing from a CDN, so `just e2e` runs in the cloud containers as it does in
CI. The tests fail on any request to esm.sh and on three's "Multiple instances of Three.js"
warning. api.pdok.nl, tile.openstreetmap.org and cdn.proj.org are blocked from the cloud
containers. With the PROJ network on and no grids, bimpolars fails to transform there ("did not
transform"), so before the geo e2e put `nl_nsgi_nlgeo2018.tif` and `nl_nsgi_rdtrans2018.tif`
from https://raw.githubusercontent.com/OSGeo/PROJ-data/master/nl_nsgi/ (GitHub answers) into
`pyproj.datadir.get_user_data_dir()` (`~/.local/share/proj`). The geo test's offline run answers
PDOK and OSM itself (`e2e/offline-pdok/` goes on the kernel's PYTHONPATH: its
`sitecustomize.py` patches `urllib.request.urlopen` for api.pdok.nl), so it runs there as well;
the live run and `tests/test_geo.py`'s `pdok` tests skip there and run on GitHub Actions. The
e2e files run one after the other (`--test-concurrency=1`): each starts marimo and a
SwiftShader Chromium through `openNotebook` in `e2e/marimo.mjs`.

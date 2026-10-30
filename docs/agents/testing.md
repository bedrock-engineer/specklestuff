# Test data and the e2e tests

## Test data

The examples and the data tests read the bimpolars bucket through `bimpolars.data.fetch`: set
`BIMPOLARS_DATA_DIR` to a local copy of the bucket, or let it download (16 MB, and 45 MB for
the IFC). `tests/test_bim.py` and the data tests skip without bimpolars or specklepy. Each
area's known numbers sit in its doc: [viewer.md](viewer.md) (the three RVT models),
[bim.md](bim.md) (the architectural model as BimDataFrames), [geo.md](geo.md) (Sixty5),
[server.md](server.md) (the server tests).

## The e2e tests

Each example notebook has an e2e test that opens it in headless Chromium:

- `examples/rvt_advanced_sample.py` (the three Revit Advanced Sample models):
  `e2e/notebook.test.mjs`.
- `examples/rvt_arch_bimdataframe.py` (the architectural model as BimDataFrames from
  `read_speckle` and `read_ifc`, two viewers): `e2e/bimdataframe.test.mjs`.
- `examples/sixty5_geo.py` (Sixty5's structural model in a GeoSpeckleViewer at Strijp-S):
  `e2e/geo.test.mjs`, offline (`e2e/offline-pdok/sitecustomize.py` answers PDOK's APIs in the
  kernel, `e2e/surroundings.mjs` serves the map's tiles and the 3D BAG's tile of boxes in the
  browser) and live where PDOK and OSM answer.

`e2e/marimo.mjs` serves a notebook and opens it for all three (`openNotebook`: marimo and a
SwiftShader Chromium). The e2e files run one after the other (`--test-concurrency=1`). The
tests fail on any request to esm.sh and on three's "Multiple instances of Three.js" warning.

## In a cloud container

The widgets load nothing from a CDN, so `just e2e` runs in the cloud containers as it does in
CI. api.pdok.nl, tile.openstreetmap.org and cdn.proj.org are blocked from the cloud
containers:

- With the PROJ network on and no grids, bimpolars fails to transform there ("did not
  transform"), so before the geo e2e put `nl_nsgi_nlgeo2018.tif` and `nl_nsgi_rdtrans2018.tif`
  from https://raw.githubusercontent.com/OSGeo/PROJ-data/master/nl_nsgi/ (GitHub answers) into
  `pyproj.datadir.get_user_data_dir()` (`~/.local/share/proj`).
- The geo test's offline run answers PDOK and OSM itself (`e2e/offline-pdok/` goes on the
  kernel's PYTHONPATH: its `sitecustomize.py` patches `urllib.request.urlopen` for
  api.pdok.nl), so it runs there as well; the live run and `tests/test_geo.py`'s `pdok` tests
  skip there and run on GitHub Actions.
- app.speckle.systems is out of reach too ([server.md](server.md)).

# specklewidgets

Speckle's web viewer in a notebook, fed with Speckle objects or BimDataFrames instead of a
server.

`SpeckleViewer` is an [anywidget](https://anywidget.dev) that runs
[`@speckle/viewer`](https://www.npmjs.com/package/@speckle/viewer), the viewer behind the Speckle
web app, in marimo or Jupyter. It takes the v3 objects of one or more Speckle models from Python,
as [bimpolars](https://github.com/bedrock-engineer/bimpolars) reads them from a local copy, or a
bimpolars `BimDataFrame` read from an IFC file or a Speckle version, and draws them side by side:
no Speckle server, no token, no upload.

```python
import marimo as mo
from bimpolars import data
from bimpolars.speckle import version_objects
from specklewidgets import Marker, SpeckleViewer

objects = data.fetch(data.RVT_SPECKLE_V3_OBJECTS)
models = [
    version_objects(objects, version.version_id)
    for version in (data.RVT_SPECKLE_ARCH, data.RVT_SPECKLE_STR, data.RVT_SPECKLE_MEP)
]
viewer = mo.ui.anywidget(
    SpeckleViewer(models, height=600, markers=[Marker("project base point", (0, 0, 0))])
)
viewer

# in another cell, once the models are in
viewer.widget.object_count  # 13546: the elements a click can select
viewer.widget.scene_bbox  # [xmin, ymin, zmin, xmax, ymax, zmax] in metres
viewer.widget.selected  # the clicked elements' own data
```

`examples/rvt_advanced_sample.py` is that notebook: `uv run marimo edit
examples/rvt_advanced_sample.py`.

A BimDataFrame draws one element per row with a mesh, in its own materials or coloured by a
column; a click reports the row's `id`:

```python
import polars as pl
from bimpolars import data, read_ifc

bdf = read_ifc(data.fetch("rvt-advanced-sample-arch.ifc"))
viewer = mo.ui.anywidget(SpeckleViewer(bdf, color="class", height=600))
viewer

# in another cell: the clicked elements' rows
ids = [element["applicationId"] for element in viewer.widget.selected]
bdf.frame.filter(pl.col("id").is_in(ids))
```

`examples/rvt_arch_bimdataframe.py` shows the Revit Advanced Sample's architectural model read
both ways, `read_speckle` and `read_ifc`, side by side.

`GeoSpeckleViewer` adds the model's surroundings: an OpenStreetMap ground map under it and 3D
Tiles around it, such as the buildings of PDOK's 3D Basisvoorziening (the 3D BAG), without the
buildings the model takes the place of. `specklewidgets.geo` builds them for a BimDataFrame
that bimpolars has placed on earth:

```python
import pyproj
from bimpolars import simple_features
from bimpolars.crs import linear_unit
from bimpolars.geobim import derived_engineering_crs, set_crs
from specklewidgets import GeoSpeckleViewer
from specklewidgets.geo import bag_panden_under, osm_ground_map, pdok_3d_buildings

# PDOK's 3D Tiles are at ellipsoidal heights, which take the NSGI grids: PROJ fetches them
pyproj.network.set_network_enabled(True)
bdf = read_ifc(data.fetch("sixty5_O-S1-CON-structural-engineering.ifc"))
crs = derived_engineering_crs(
    "EPSG:7415", 160_071.5, 384_156.5, 18.625, -50.36, unit=linear_unit(bdf.crs), name="Sixty5"
)
site = set_crs(bdf, crs)  # Sixty5 at Strijp-S, Eindhoven
panden = bag_panden_under(simple_features(site))  # the BAG panden under the model
ground_map = osm_ground_map(site)  # 150 m of map around the model
tilesets = [pdok_3d_buildings(site, ground_map["bounds"], hide_within=panden.values())]
viewer = mo.ui.anywidget(GeoSpeckleViewer(site, ground_map=ground_map, tilesets=tilesets))
viewer

# in another cell, once the surroundings are in
viewer.widget.surroundings  # {"ground_map": [...], "tiles": 2, "hidden_features": 1, ...}
```

`examples/sixty5_geo.py` is that notebook, with the Sixty5 structural model.

`specklewidgets.server` receives a version from a Speckle server, as its bundle and its v3
objects, and sends a BimDataFrame as a new version, signed in with this machine's Speckle
account or a personal access token:

```python
from specklewidgets.server import local_client, receive, send

client = local_client("https://app.speckle.systems")  # None without a local account
version = receive(client, "461cc2a20f", "363cae173a", "d5e5bacdde")  # the arch version
viewer = mo.ui.anywidget(SpeckleViewer(version.objects))
bdf = version.bimdataframe()  # read_speckle(version.objects, version.bundle)

version_id = send(client, bdf, "<project id>", "<model id>", message="from a notebook")
```

`examples/speckle_receive_send.py` is that notebook, with a token field (wigglystuff's
`EnvConfig`) for a machine without a Speckle account.

## Demo page

`site/` is a static page with the GeoSpeckleViewer of `examples/sixty5_geo.py` beside a
[MapLibre](https://maplibre.org) map that shows the footprint of the element you click, on
PDOK's topographic map: [bedrock-engineer.github.io/specklestuff](https://bedrock-engineer.github.io/specklestuff/),
and the same page under bimpolars' title at [bedrock-engineer.github.io/bimpolars](https://bedrock-engineer.github.io/bimpolars/).
GitHub Pages runs no Python, so `site/sixty5.py` computes what the notebook computes at build
time: the widget's traits (`viewer.json`, and the model as `objects.json.gz`) and the drawn
rows' footprints in longitude and latitude (`footprints.geojson`, bimpolars' `geog` column).
The page runs the widget with `mountGeoSpeckleViewer` from the npm package (below), on a
`StaticModel`, an anywidget model without a kernel, and follows its `selected` trait.
`just site` builds it into `site/dist`; `just site-data` and then `just site-dev` serve it with
hot reload.

## In a web page

The widgets' front end is the npm package
[`@bedrock-engineer/geospeckle-viewer`](packages/geospeckle-viewer) (not published yet), which
runs GeoSpeckleViewer on any web page, without Python. Without a ground map and 3D Tiles it is
SpeckleViewer:

```ts
import { mountGeoSpeckleViewer } from "@bedrock-engineer/geospeckle-viewer";

const { model, loaded } = mountGeoSpeckleViewer(document.getElementById("viewer")!, {
  objects_gz: await (await fetch("objects.json.gz")).arrayBuffer(),
  height: 600,
});
model.on("change:selected", () => console.log(model.get("selected")));
await loaded;
```

## Install

```sh
uv add "specklewidgets @ git+https://github.com/bedrock-engineer/specklestuff"
```

The package depends on anywidget and traitlets only. The built widgets are in the wheel, with
`@speckle/viewer` and three.js bundled in (2.7 MB, 0.8 MB of the wheel), so the notebook needs
no network access; their licenses are in `specklewidgets/static/speckle-viewer.LICENSES.txt`.
GeoSpeckleViewer's bundle adds 3d-tiles-renderer (2.9 MB, 0.8 MB of the wheel; licenses in
`geospeckle-viewer.LICENSES.txt`). A BimDataFrame needs the extra `specklewidgets[bim]`
(specklepy, which turns its rows into Speckle objects) and bimpolars, which any BimDataFrame
comes with. `specklewidgets.geo` needs the extra `specklewidgets[geo]`: pyproj, which is what
`bimpolars[geobim]` adds to bimpolars. The ground map's tiles come from tile.openstreetmap.org
and the 3D BAG from api.pdok.nl, so the browser needs to reach both, and the notebook's Python
api.pdok.nl. Receiving and sending need the extra `specklewidgets[server]` (specklepy with its
bundle reader) and `bimpolars[speckle]`, which projects a bundle-only version to v3 objects.

## API

- `SpeckleViewer(models=None, *, color=None, markers=None, **traits)`: the widget. `models` is
  one model or a sequence of models; a model is a Speckle version's v3 objects, its root first,
  parsed (as `bimpolars.speckle.version_objects` gives them) or as JSON array text, or a
  `BimDataFrame`, which `bim_objects` turns into v3 objects. `color` colours the elements of the
  BimDataFrames by a column or a polars expression instead of by their materials. Clicking an
  element selects it, shift-click adds to the selection and a click on nothing clears it; a
  click on an instance selects its InstanceProxy, whose applicationId is the element's, with
  `-instance-<n>` appended when the element has several placements or geometry of its own
  (`read_speckle` strips it to key its rows), and whose `definitionId` has the model's root id
  in front (`<root id>/def-12`, see `models_gz`); a click on a BimDataFrame's element reports
  its row's `id` as `applicationId`. Its traits:
  - `objects_gz`: the packed models (`models_gz`); set it to load other models.
  - `height` (pixels; `None`, the default, follows the width by `aspect_ratio`, 16:9).
  - `markers`: axes with a label, `[{"name", "position": [x, y, z], "size"}]` in metres.
  - `selected`: the selected elements' data, without their geometry and children.
  - `object_count` and `scene_bbox`, set by the viewer after each load: the number of
    elements it draws (what a click can select: an element with several meshes counts once,
    an instance once per placement) and the scene's bounding box,
    `[xmin, ymin, zmin, xmax, ymax, zmax]`, in metres (the viewer scales every model to
    metres), `[]` when empty.
- `Marker(name, position, size=5.0)`: a marker, `position` in metres.
- `models_gz(*models, compresslevel=6)`: packs models for `objects_gz` as gzipped JSON. It
  adjusts three things in raw models that trip the viewer (2.31.14): it prefixes the ids of
  each model's instance definitions and their members with the model's root id, so that the
  `def-1` of one model does not select the instances of another; it keeps a member id on the
  mesh only when the mesh's DataObject carries it too (as specklepy's projection of a bundle
  writes `def-geo-<n>`), where the viewer would stop looking for members halfway; and it lists
  each object once in a collection, where the viewer would leave a member's extra copies at
  the definition's origin and draw none of its instances. Ids are otherwise left alone.
- `GeoSpeckleViewer(models=None, *, ground_map=None, tilesets=None, **kwargs)`: a
  `SpeckleViewer` (`color` and `markers` included) with the model's surroundings, in the
  viewer's world (the models' coordinates in metres). The map and the tiles are not elements:
  `object_count` and `scene_bbox` leave them out, and a click does not select them. Its
  traits, besides `SpeckleViewer`'s:
  - `ground_map` (a `GroundMap`, `{}` for none): OpenStreetMap's tiles over `bounds`
    (`[west, south, east, north]` in degrees), drawn into a `width` x `height` image north up
    and laid on a plane at height `z` with `opacity`; its corners go to the world through
    `lnglat_to_world`, an affine `[a, b, c, d, e, f]` with `x = a lon + b lat + c` and
    `y = d lon + e lat + f`.
  - `tilesets` (a list of `Tileset`): 3D Tiles, each a dict with `tileset` (the tileset JSON
    with absolute content URLs), `ecef_to_world` (a column-major 4x4 from ECEF to the
    world), `attribution` (a credit line) and `hide_within` (polygons as rings of `[x, y]`).
    A feature of the tiles (an `EXT_mesh_features` id: a building of the 3D BAG) with more
    than half of its vertices inside one of the `hide_within` polygons is left out. Tiles in
    glTF need `EXT_meshopt_compression` at most; the viewer runs 3d-tiles-renderer 0.3.46,
    the last for its three.js.
  - `surroundings`, set by the viewer: a dict with `ground_map` (`[xmin, ymin, xmax, ymax]`
    of the map's plane in metres, `[]` until it is drawn), `tiles` (the tile contents
    loaded), `hidden_features` (the features of those tiles that `hide_within` leaves out)
    and `hidden_heights` (`[zmin, zmax]` of those features in metres, `[]` for none: the
    building the model takes the place of should stand where the model does).
- `specklewidgets.geo` (the `[geo]` extra), for a BimDataFrame in a georeferenced CRS such as
  the Engineering CRS of `bimpolars.geobim.derived_engineering_crs`. The viewer's world goes to
  ECEF and back through one 4x4, `bimpolars.geobim.linearized_site_to_ecef`, for the map, the
  tiles and the panden alike, so they line up with each other exactly and with PROJ's own
  transformation to a centimetre around a site, and to its own accuracy. In the Netherlands
  that takes the NSGI grids, which PROJ fetches from cdn.proj.org with its network on
  (`pyproj.network.set_network_enabled(True)` or `PROJ_NETWORK=ON`). Without them PROJ falls
  back to a Helmert transformation, good to about a metre in plan, that passes NAP heights
  off as ellipsoidal ones (bimpolars warns): PDOK's 3D BAG, at ellipsoidal heights, then
  floats some 44 m above the map and the model.
  - `osm_ground_map(bdf, *, margin=150.0, width=2048, z=0.0, opacity=0.85)`: the `ground_map`
    over the model's plan extent (its `bbox` column) and `margin` metres around it; `z` is the
    map's height in metres in the model's CRS (0: the site origin's).
  - `pdok_3d_buildings(bdf, bounds=None, *, margin=150.0, hide_within=(), hide_margin=0.5)`: a
    `tilesets` entry with the 3D BAG's buildings (LoD 2.2) over `bounds` (degrees, such as the
    ground map's; by default the area `osm_ground_map` covers), without those within the
    `hide_within` polygons in the model's coordinates, grown by `hide_margin` metres.
  - `bag_panden_under(bdf, footprint=None)`: the BAG panden with more than half of their area
    under `footprint` (in the model's coordinates; by default the union of the frame's
    `footprint` column, from `bimpolars.simple_features`), by `identificatie`, as polygons in
    the model's coordinates.
  - `site_3d_tiles(tileset_url, bounds)`: a one-level tileset of the finest tiles of a 3D Tiles
    tileset (with region bounding volumes) that overlap `bounds`, fetching only the external
    tilesets on the way: 3d-tiles-renderer 0.3.46 would fetch every child of a tile without
    content.
- `specklewidgets.bim` (the `[bim]` extra):
  - `bim_objects(bdf, *, color=None, name=None)`: a BimDataFrame as the v3 objects of one
    Speckle model, root first, serialized with specklepy. One DataObject per row with a mesh
    (an `IfcOpeningElement`'s mesh, the void it cuts, is left out, as in bimpolars' glTF):
    `applicationId` the row's `id`, `name`, `category` the `class`, its property sets at the
    paths their names give (`properties.Parameters.Dimensions` in `properties`, an IFC
    `Pset_WallCommon` as a field of that name, as `bimpolars.read_speckle` names them) and its
    other columns as fields, without nulls; its mesh as one Mesh per style. Each style becomes
    a RenderMaterial of its meshes. With `color`, a numeric column colours the elements in ten
    blues from its minimum to its maximum, any other in eight colours by how many rows have the
    value, the rest and nulls grey; each material is named after what it shows
    (`class: IfcWall`, `Volume: 1.2 to 2.4`). `bimpolars.read_speckle` reads back the drawn
    rows' ids, classes, names, meshes and property sets; the other columns come back inside
    its `object` set.
  - `bim_collection(bdf, *, color=None, name=None)`: the same as a specklepy `Collection`,
    one sub-collection per class, for specklepy to send.
- `specklewidgets.server` (the `[server]` extra and `bimpolars[speckle]`), through specklepy's
  v3 pipeline (`ServerTransport`, `operations.send`, `version.create`), which specklepy
  deprecates since 2026.9; its DeprecationWarnings are silenced:
  - `local_client(server="https://app.speckle.systems")`: a `SpeckleClient` signed in with
    this machine's Speckle account for the server (Speckle Manager's or a connector's, as
    specklepy's `get_local_accounts` finds them; the default account first, each signed in
    at the URL it was stored with, so a token stored for https never goes over http; a
    refused token passed over), or None.
  - `token_client(token, server="https://app.speckle.systems")`: a client signed in with a
    personal access token, kept in memory only; `ValueError` if the server refuses it, and a
    `UserWarning` when the server is plain http on another machine. A notebook takes the
    token from a password field, such as wigglystuff's `EnvConfig`.
  - `receive(client, project_id, model_id, version_id=None, *, directory=None)`: a version
    (the model's latest by default) as a `ReceivedVersion`: `objects`, its v3 objects root
    first, and `bundle`, the folder its bundle is downloaded into,
    `<directory>/<model id>/<version id>/` (a temporary folder by default, removed again
    when the receive fails; None when the server has no bundle for it). A bundle-only
    version's objects are projected from its bundle by `bimpolars.bundle.bundle_objects`
    (`v3_route` `"projected"`, else `"server"`). `ReceivedVersion.bimdataframe()` reads it
    with `bimpolars.read_speckle`, objects and bundle; for the Revit Advanced Sample's
    architectural version that is the bimpolars bucket's frame.
  - `send(client, bdf, project_id, model_id, *, message=None, color=None, name=None)`: sends
    a BimDataFrame's `bim_collection` as a new version of a model and returns its id;
    `receive` and `read_speckle` give back its drawn rows' ids, classes and meshes. Not the
    `container` column, which comes back as the field `properties.object.container`
    (`read_speckle` sets `container` from a bundle only), nor the levels, which have no mesh
    and are not drawn; `simple_features` then lays each footprint at its own lowest z.

## Development

The repo has two toolchains, [pnpm](https://pnpm.io) for the JS (a workspace of
`packages/geospeckle-viewer` and `site/`) and uv for the Python, and
[just](https://just.systems) runs both (`scoop install just`, `brew install just`, or
`uv tool install rust-just`; on Windows it needs Git Bash's `sh`):

```sh
just                # lists the recipes
just setup          # pnpm install --frozen-lockfile + uv sync --locked
just build          # tsc + vite: packages/geospeckle-viewer → src/specklewidgets/static/ (committed)
just build-npm      # the npm package's dist/, as it would be published
just dev            # rebuilds on change; ANYWIDGET_HMR=1 hot-reloads the notebook
just check          # typecheck, vitest, oxlint, oxfmt, ruff, mypy, pytest
just e2e            # the example notebooks in headless Chromium (see below)
just live           # receive and send on a real Speckle server (see below)
```

`tests/test_server.py` receives and sends through a fake Speckle server on localhost
(`tests/fake_speckle_server.py`, the requests specklepy makes), which serves the architectural
version from the bimpolars bucket. `just live` (`uv run pytest -m live`) runs the same checks
against app.speckle.systems with this machine's Speckle account, and skips without one (CI has
none and gets no token): it receives the architectural version and compares it with the
bucket's frame, and sends the structural model into a new model of
`SPECKLEWIDGETS_TEST_PROJECT`, or of a new private project, on `SPECKLEWIDGETS_TEST_SERVER`
(app.speckle.systems by default). It deletes a project it made, and with it the objects it
sent; in `SPECKLEWIDGETS_TEST_PROJECT` it deletes only the model, and the sent objects stay in
that project.

`just e2e` serves the example notebooks with marimo, opens them in headless Chromium (WebGL
by SwiftShader) and asserts that the three Revit Advanced Sample models load with no console
errors, that the canvas is drawn on and that the viewer reports the element count and bounding
box that `tests/test_rvt_advanced_sample.py` reaches without the viewer; that each BimDataFrame
of the architectural model draws one element per row with a mesh and spans the frame's `bbox`
(`tests/test_rvt_arch_bimdataframe.py` has the numbers); that Sixty5 in
`examples/sixty5_geo.py` stands on its BAG pand, on the ground map and among the 3D BAG with
its own building left out; and that the page asks no CDN for anything. The Sixty5 test runs
twice: offline, with PDOK's APIs answered by `e2e/offline-pdok/sitecustomize.py` and the map
and 3D BAG tiles made by `e2e/surroundings.mjs`, and live, where api.pdok.nl and
tile.openstreetmap.org answer. The models come through `bimpolars.data.fetch`: set
`BIMPOLARS_DATA_DIR` to a local copy of the bimpolars bucket, or let it download (16 MB, and
45 MB for the IFC).

`sandbox/oauth/` holds the earlier OAuth widget, which is not packaged.

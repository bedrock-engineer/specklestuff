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
from bimpolars import simple_features
from bimpolars.crs import linear_unit
from bimpolars.geobim import derived_engineering_crs, set_crs
from specklewidgets import GeoSpeckleViewer
from specklewidgets.geo import bag_panden_under, osm_ground_map, pdok_3d_buildings

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
viewer.widget.surroundings  # {"ground_map": [xmin, ymin, xmax, ymax], "tiles": ..., "hidden_features": ...}
```

`examples/sixty5_geo.py` is that notebook, with the Sixty5 structural model.

## Install

```sh
uv add "specklewidgets @ git+https://github.com/bedrock-engineer/specklestuff"
```

The package depends on anywidget and traitlets only; the built widget is in the wheel. The
browser loads `@speckle/viewer` and three.js from [esm.sh](https://esm.sh), so the notebook needs
to reach it. A BimDataFrame needs the extra `specklewidgets[bim]` (specklepy, which turns its
rows into Speckle objects) and bimpolars, which any BimDataFrame comes with.
`specklewidgets.geo` needs the extra `specklewidgets[geo]`: pyproj, which is what
`bimpolars[geobim]` adds to bimpolars. The ground map's tiles come from
tile.openstreetmap.org and the 3D BAG from api.pdok.nl, so the browser needs to reach both, and
the notebook's Python api.pdok.nl.

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
- `GeoSpeckleViewer(models=None, *, color=None, markers=None, ground_map=None, tilesets=None,
  **traits)`: `SpeckleViewer` with the model's surroundings, in the viewer's world (the models'
  coordinates in metres). The map and the tiles are not elements: `object_count` and
  `scene_bbox` leave them out, and a click does not select them. Its traits, besides
  `SpeckleViewer`'s:
  - `ground_map` (a `GroundMap`, `{}` for none): OpenStreetMap's tiles over `bounds` (`[west,
    south, east, north]` in degrees), drawn into a `width` x `height` image north up and laid
    on a plane at height `z` with `opacity`; its corners go to the world through
    `lnglat_to_world`, an affine `[a, b, c, d, e, f]` with `x = a lon + b lat + c` and `y = d
    lon + e lat + f`.
  - `tilesets` (a list of `Tileset`): 3D Tiles, each `{"tileset": tileset JSON with absolute
    content URLs, "ecef_to_world": column-major 4x4 from ECEF to the world, "attribution":
    credit line, "hide_within": polygons as rings of [x, y]}`. A feature of the tiles (an
    `EXT_mesh_features` id: a building of the 3D BAG) with more than half of its vertices
    inside one of the `hide_within` polygons is left out. Tiles in glTF need
    `EXT_meshopt_compression` at most; the viewer runs 3d-tiles-renderer 0.3.46, the last for
    its three.js.
  - `surroundings`, set by the viewer: `{"ground_map": [xmin, ymin, xmax, ymax] of the map's
    plane in metres ([] until it is drawn), "tiles": tile contents loaded, "hidden_features":
    features of those tiles left out by hide_within}`.
- `specklewidgets.geo` (the `[geo]` extra), for a BimDataFrame in a georeferenced CRS such as
  the Engineering CRS of `bimpolars.geobim.derived_engineering_crs`. The viewer's world goes to
  ECEF and back through one 4x4, `bimpolars.geobim.linearized_site_to_ecef`, for the map, the
  tiles and the panden alike, so they line up with each other exactly and with PROJ's own
  transformation to a centimetre around a site (and to its own accuracy: without the NSGI
  grids, a Helmert transformation that is good to about a metre):
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
    (`class: IfcWall`, `Volume: 1.2 to 2.4`). `bimpolars.read_speckle` reads the objects back
    into the drawn rows, ids, classes, meshes and property sets included.
  - `bim_collection(bdf, *, color=None, name=None)`: the same as a specklepy `Collection`,
    one sub-collection per class, for specklepy to send.

## Development

```sh
npm install && uv sync
npm run build       # tsc + vite: js/ → src/specklewidgets/static/ (committed)
npm run dev         # rebuilds on change; ANYWIDGET_HMR=1 hot-reloads the notebook
ENTRY=js/geo-speckle-viewer.ts npm run dev  # the same for GeoSpeckleViewer
npm run typecheck && npm run test && npm run lint && npm run fmt:check
uv run pytest && uv run mypy src && uv run ruff check && uv run ruff format --check
npm run e2e         # the example notebooks in headless Chromium (see below)
```

`npm run e2e` serves the example notebooks with marimo, opens them in headless Chromium (WebGL
by SwiftShader) and asserts that the three Revit Advanced Sample models load with no console
errors, that the canvas is drawn on and that the viewer reports the element count and bounding
box that `tests/test_rvt_advanced_sample.py` reaches without the viewer; and that each
BimDataFrame of the architectural model draws one element per row with a mesh and spans the
frame's `bbox` (`tests/test_rvt_arch_bimdataframe.py` has the numbers); and that Sixty5 in
`examples/sixty5_geo.py` stands on its BAG pand, on the ground map and among the 3D BAG with
its own building left out. That last one runs twice: offline, with PDOK's APIs answered by
`e2e/offline-pdok/sitecustomize.py` and the map and 3D BAG tiles made by `e2e/surroundings.mjs`,
and live, where api.pdok.nl and tile.openstreetmap.org answer. It serves esm.sh from a mirror
it bundles out of `node_modules`, so it runs where esm.sh is out of reach;
`E2E_ESM_SH=network npm run e2e` loads the real esm.sh instead, as CI does. The models come
through `bimpolars.data.fetch`: set `BIMPOLARS_DATA_DIR` to a local copy of the bimpolars
bucket, or let it download (16 MB).

`sandbox/oauth/` holds the earlier OAuth widget, which is not packaged.

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

## Install

```sh
uv add "specklewidgets @ git+https://github.com/bedrock-engineer/specklestuff"
```

The package depends on anywidget and traitlets only. The built widget is in the wheel, with
`@speckle/viewer` and three.js bundled in (2.7 MB, 0.8 MB of the wheel), so the notebook needs
no network access; their licenses are in `specklewidgets/static/speckle-viewer.LICENSES.txt`.
A BimDataFrame needs the extra `specklewidgets[bim]` (specklepy, which turns its rows into
Speckle objects) and bimpolars, which any BimDataFrame comes with.

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

## Development

The repo has two toolchains, npm for `js/` and uv for the Python, and
[just](https://just.systems) runs both (`scoop install just`, `brew install just`, or
`uv tool install rust-just`; on Windows it needs Git Bash's `sh`):

```sh
just                # lists the recipes
just setup          # npm ci + uv sync --locked
just build          # tsc + vite: js/ → src/specklewidgets/static/ (committed)
just dev            # rebuilds on change; ANYWIDGET_HMR=1 hot-reloads the notebook
just check          # typecheck, vitest, oxlint, oxfmt, ruff, mypy, pytest
just e2e            # the example notebook in headless Chromium (see below)
```

`just e2e` serves the example notebooks with marimo, opens them in headless Chromium (WebGL
by SwiftShader) and asserts that the three Revit Advanced Sample models load with no console
errors, that the canvas is drawn on and that the viewer reports the element count and bounding
box that `tests/test_rvt_advanced_sample.py` reaches without the viewer; that each BimDataFrame
of the architectural model draws one element per row with a mesh and spans the frame's `bbox`
(`tests/test_rvt_arch_bimdataframe.py` has the numbers); and that the page asks no CDN for
anything. The models come through `bimpolars.data.fetch`: set `BIMPOLARS_DATA_DIR` to a local
copy of the bimpolars bucket, or let it download (16 MB, and 45 MB for the IFC).

`sandbox/oauth/` holds the earlier OAuth widget, which is not packaged.

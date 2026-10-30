# specklewidgets

Speckle's web viewer in a notebook, fed with Speckle objects instead of a server.

`SpeckleViewer` is an [anywidget](https://anywidget.dev) that runs
[`@speckle/viewer`](https://www.npmjs.com/package/@speckle/viewer), the viewer behind the Speckle
web app, in marimo or Jupyter. It takes the v3 objects of one or more Speckle models from Python,
as [bimpolars](https://github.com/bedrock-engineer/bimpolars) reads them from a local copy, and
draws them side by side: no Speckle server, no token, no upload.

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

## Install

```sh
uv add "specklewidgets @ git+https://github.com/bedrock-engineer/specklestuff"
```

The package depends on anywidget and traitlets only; the built widget is in the wheel. The
browser loads `@speckle/viewer` and three.js from [esm.sh](https://esm.sh), so the notebook needs
to reach it.

## API

- `SpeckleViewer(models=None, *, markers=None, **traits)`: the widget. `models` is one model
  or a sequence of models; a model is a Speckle version's v3 objects, its root first, parsed (as
  `bimpolars.speckle.version_objects` gives them) or as JSON array text. Clicking an element
  selects it, shift-click adds to the selection and a click on nothing clears it; a click on an
  instance selects its InstanceProxy, whose applicationId is the element's, with
  `-instance-<n>` appended when the element has several placements or geometry of its own
  (`read_speckle` strips it to key its rows), and whose `definitionId` has the model's root id
  in front (`<root id>/def-12`, see `models_gz`). Its traits:
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

## Development

```sh
npm install && uv sync
npm run build       # tsc + vite: js/ → src/specklewidgets/static/ (committed)
npm run dev         # rebuilds on change; ANYWIDGET_HMR=1 hot-reloads the notebook
npm run typecheck && npm run test && npm run lint && npm run fmt:check
uv run pytest && uv run mypy src && uv run ruff check && uv run ruff format --check
npm run e2e         # the example notebook in headless Chromium (see below)
```

`npm run e2e` serves the example notebook with marimo, opens it in headless Chromium (WebGL by
SwiftShader) and asserts that the three Revit Advanced Sample models load with no console
errors, that the canvas is drawn on and that the viewer reports the element count and bounding
box that `tests/test_rvt_advanced_sample.py` reaches without the viewer. It serves esm.sh from a
mirror it bundles out of `node_modules`, so it runs where esm.sh is out of reach;
`E2E_ESM_SH=network npm run e2e` loads the real esm.sh instead, as CI does. The models
come through `bimpolars.data.fetch`: set `BIMPOLARS_DATA_DIR` to a local copy of the bimpolars
bucket, or let it download (16 MB).

`sandbox/oauth/` holds the earlier OAuth widget, which is not packaged.

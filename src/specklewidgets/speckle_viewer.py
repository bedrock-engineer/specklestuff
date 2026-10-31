"""Speckle's web viewer in a notebook, fed with Speckle models or BimDataFrames.

The widget runs Speckle's own viewer (``@speckle/viewer``, the npm package behind the Speckle
web app, bundled with three.js into the widget) without a Speckle server. The v3 objects of one or
more models go to the browser as gzipped JSON (``models_gz``), and a
``SpeckleLoader`` subclass hands each model to ``ObjectLoader2Factory.createFromObjects``,
the in-memory object loader. A ``bimpolars.BimDataFrame`` becomes v3 objects first,
through ``specklewidgets.bim.bim_objects``.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anywidget
import traitlets

from specklewidgets.models import Model, models_gz

if TYPE_CHECKING:
    import polars as pl
    from bimpolars import BimDataFrame
    from typing_extensions import TypeIs  # typing's from Python 3.13

type ViewerModel = Model | BimDataFrame
"""A model as ``SpeckleViewer`` takes it: a Speckle version's v3 objects, root first
(parsed or as JSON array text), or a BimDataFrame."""

_STATIC = Path(__file__).parent / "static"


@dataclass(frozen=True)
class Marker:
    """Axes (x red, y green, z blue) and a label at a named point.

    Attributes:
        name (str): The label.
        position (tuple[float, float, float]): ``(x, y, z)`` in the viewer's world, which is in
            metres whatever the models' units.
        size (float): The length of the axes in metres.
    """

    name: str
    position: tuple[float, float, float]
    size: float = 5.0


class SpeckleViewer(anywidget.AnyWidget):
    """Speckle's web viewer, fed with v3 objects instead of a server URL.

    ``SpeckleViewer(models)`` packs one model or a sequence of models with
    ``models_gz``; each model is a Speckle version's v3 objects, its root
    first, as ``bimpolars.speckle.version_objects`` gives them, or a
    ``bimpolars.BimDataFrame``, which ``specklewidgets.bim.bim_objects`` turns into
    v3 objects: one element per row with a mesh, coloured by its styles or by ``color``. The
    traits are the wire format and can be set directly as well.

    Clicking an element selects it; shift-click adds to the selection and a click on nothing
    clears it. A click on an instance selects its InstanceProxy, whose applicationId is the
    element's, with ``-instance-<n>`` appended when the element has several placements or
    geometry of its own (``bimpolars.speckle.read_speckle`` strips it to key its rows). Its
    ``definitionId`` has the model's root id in front (``<root id>/def-12``), as
    ``models_gz`` namespaces it.

    After each load the front end reports ``object_count`` and ``scene_bbox``; read them from a
    cell that references the marimo element, which reruns when they change.

    Args:
        models (ViewerModel | Sequence[ViewerModel] | None): One model or a sequence of
            models (→ ``objects_gz``, packed by ``models_gz``). A model is a Speckle
            version's v3 objects, its root first, parsed or as JSON array text; or a
            ``bimpolars.BimDataFrame``.
        color (str | pl.Expr | None): Colours the elements of the BimDataFrames by a column
            (its name) or a polars expression instead of by their styles; see
            ``specklewidgets.bim.bim_collection``.
        markers (Sequence[Marker | Mapping[str, Any]] | None): Axes with a label
            (→ ``markers``): ``Marker`` or the trait's dicts.
        **kwargs (Any): Traits, passed through unchanged, such as ``height=600``.

    Raises:
        ValueError: If ``color`` is given without a BimDataFrame to colour.
        ValueError: If a model is not one (see ``models_gz``).
    """

    _esm = _STATIC / "speckle-viewer.js"

    # Gzipped JSON of one or more models, each an array of v3 objects, root first; see models_gz
    objects_gz = traitlets.Bytes(b"").tag(sync=True)
    # Height in pixels; None: the height follows the notebook's width by aspect_ratio
    height = traitlets.Int(None, allow_none=True).tag(sync=True)
    # Width over height, when height is None
    aspect_ratio = traitlets.Float(16 / 9).tag(sync=True)
    # Raw data of the selected elements (without displayValue, elements, __closure)
    selected = traitlets.List[dict[str, Any]]([]).tag(sync=True)
    # Axes with a label: [{"name": label, "position": [x, y, z] in metres, "size": metres}]
    markers = traitlets.List[dict[str, Any]]([]).tag(sync=True)
    # Set by the front end after each load: the number of elements the viewer draws, as a click
    # selects them: an element with several meshes counts once, an instance once per placement
    object_count = traitlets.Int(0).tag(sync=True)
    # Set by the front end after each load: the scene's bounding box in metres (the viewer
    # scales every model to metres), [xmin, ymin, zmin, xmax, ymax, zmax]; [] when empty
    scene_bbox = traitlets.List[float]([]).tag(sync=True)

    def __init__(
        self,
        models: ViewerModel | Sequence[ViewerModel] | None = None,
        *,
        color: str | pl.Expr | None = None,
        markers: Sequence[Marker | Mapping[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        if models is not None or color is not None:
            as_models = [] if models is None else _as_models(models)
            kwargs["objects_gz"] = models_gz(*_speckle_models(as_models, color))
        if markers is not None:
            kwargs["markers"] = [_marker_trait(marker) for marker in markers]
        super().__init__(**kwargs)


def _as_models(models: ViewerModel | Sequence[ViewerModel]) -> list[ViewerModel]:
    """One model, or each of a sequence of models.

    A model is text, a BimDataFrame, or a sequence that starts with a mapping (an object). A
    single object counts as a model too, which ``models_gz`` then refuses as not a list.
    """
    if isinstance(models, str | Mapping) or _is_bim_data_frame(models):
        return [models]
    if len(models) > 0 and isinstance(models[0], Mapping):
        return [models]  # type: ignore[list-item]
    return list(models)  # type: ignore[arg-type]


def _speckle_models(models: Sequence[ViewerModel], color: str | pl.Expr | None) -> list[Model]:
    """The models as v3 objects: each BimDataFrame through ``bim_objects``.

    Raises:
        ValueError: If ``color`` is given and no model is a BimDataFrame.
    """
    speckle_models: list[Model] = []
    for model in models:
        if _is_bim_data_frame(model):
            # bimpolars and specklepy's serializer, imported only for a BimDataFrame
            from specklewidgets.bim import bim_objects

            speckle_models.append(bim_objects(model, color=color))
        else:
            speckle_models.append(model)
    if color is not None and not any(_is_bim_data_frame(model) for model in models):
        raise ValueError("color colours the elements of BimDataFrames; models has none")
    return speckle_models


def _is_bim_data_frame(value: object) -> TypeIs[BimDataFrame]:
    """Whether the value is a BimDataFrame, without importing bimpolars for it.

    A BimDataFrame exists only once bimpolars is imported, so the check looks for the class in
    the modules already imported.
    """
    frame = sys.modules.get("bimpolars.frame")
    return frame is not None and isinstance(value, frame.BimDataFrame)


def _marker_trait(marker: Marker | Mapping[str, Any]) -> dict[str, Any]:
    """A marker as the ``markers`` trait holds it."""
    if isinstance(marker, Marker):
        trait = asdict(marker)
        trait["position"] = list(marker.position)
        return trait
    return dict(marker)

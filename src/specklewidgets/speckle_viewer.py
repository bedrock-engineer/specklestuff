"""Speckle's web viewer in a notebook, fed with raw Speckle models: :class:`SpeckleViewer`.

The widget runs Speckle's own viewer (``@speckle/viewer``, the npm package behind the Speckle
web app, bundled with three.js into the widget) without a Speckle server. The v3 objects of one or
more models go to the browser as gzipped JSON (:func:`~specklewidgets.models_gz`), and a
``SpeckleLoader`` subclass hands each model to ``ObjectLoader2Factory.createFromObjects``,
the in-memory object loader.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import anywidget
import traitlets

from specklewidgets.models import Model, models_gz

_STATIC = Path(__file__).parent / "static"


@dataclass(frozen=True)
class Marker:
    """Axes (x red, y green, z blue) and a label at a named point.

    Attributes:
        name: The label.
        position: ``(x, y, z)`` in the viewer's world, which is in metres whatever the
            models' units.
        size: The length of the axes in metres.
    """

    name: str
    position: tuple[float, float, float]
    size: float = 5.0


class SpeckleViewer(anywidget.AnyWidget):
    """Speckle's web viewer, fed with v3 objects instead of a server URL.

    ``SpeckleViewer(models)`` packs one model or a sequence of models with
    :func:`~specklewidgets.models_gz`; each model is a Speckle version's v3 objects, its root
    first, as :func:`bimpolars.speckle.version_objects` gives them. The traits are the wire
    format and can be set directly as well.

    Clicking an element selects it; shift-click adds to the selection and a click on nothing
    clears it. A click on an instance selects its InstanceProxy, whose applicationId is the
    element's, with ``-instance-<n>`` appended when the element has several placements or
    geometry of its own (:func:`bimpolars.speckle.read_speckle` strips it to key its rows). Its
    ``definitionId`` has the model's root id in front (``<root id>/def-12``), as
    :func:`~specklewidgets.models_gz` namespaces it.

    After each load the front end reports ``object_count`` and ``scene_bbox``; read them from a
    cell that references the marimo element, which reruns when they change.
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
        models: Model | Sequence[Model] | None = None,
        *,
        markers: Sequence[Marker | Mapping[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """Pythonic facade over the JSON-flat traits.

        Args:
            models: One model or a sequence of models (→ ``objects_gz``, packed by
                :func:`~specklewidgets.models_gz`). A model is a Speckle version's v3
                objects, its root first: parsed, or as JSON array text.
            markers: Axes with a label (→ ``markers``): :class:`Marker` or the trait's dicts.
            **kwargs: Traits, passed through unchanged, such as ``height=600``.
        """
        if models is not None:
            kwargs["objects_gz"] = models_gz(*_as_models(models))
        if markers is not None:
            kwargs["markers"] = [_marker_trait(marker) for marker in markers]
        super().__init__(**kwargs)


def _as_models(models: Model | Sequence[Model]) -> list[Model]:
    """One model, or each of a sequence of models: a model is text or starts with a mapping."""
    if isinstance(models, str | Mapping) or (len(models) > 0 and isinstance(models[0], Mapping)):
        return [models]  # type: ignore[list-item]
    return list(models)  # type: ignore[arg-type]


def _marker_trait(marker: Marker | Mapping[str, Any]) -> dict[str, Any]:
    """A marker as the ``markers`` trait holds it."""
    if isinstance(marker, Marker):
        trait = asdict(marker)
        trait["position"] = list(marker.position)
        return trait
    return dict(marker)

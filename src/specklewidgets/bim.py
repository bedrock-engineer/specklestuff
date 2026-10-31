"""A BimDataFrame as a Speckle model for the viewer: :func:`bim_objects`.

:class:`bimpolars.BimDataFrame` holds a BIM model as one row per element, its geometry in the
``mesh`` column (faces sorted by style) in the model CRS's length unit. The viewer draws
Speckle v3 objects, so :func:`bim_collection` turns the rows into specklepy objects: one
``DataObject`` per row with a mesh, its geometry as one ``Mesh`` per style in ``displayValue``
and its data next to it, grouped into one ``Collection`` per class under a root
``Collection``. A style becomes a ``RenderMaterial`` (its name, colour and opacity), or a
column's values become the colours (``color``). :func:`bim_objects` serializes the tree to v3
objects with specklepy, root first: a model as :class:`~specklewidgets.SpeckleViewer` and
:func:`~specklewidgets.models_gz` take it.

This module needs bimpolars, which comes with any BimDataFrame; the rest of the package does
not import it, nor specklepy.
"""

from __future__ import annotations

import datetime
import decimal
import json
import math
import warnings
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl
from bimpolars.crs import as_linear_unit
from bimpolars.frame import CRS_COLUMN
from bimpolars.gltf import EXCLUDED_CLASSES
from bimpolars.mesh import UNSTYLED_RGBA, mesh_arrays
from bimpolars.speckle import OBJECT_SET, SPECKLE_UNITS
from specklepy.objects.data_objects import DataObject
from specklepy.objects.geometry import Mesh
from specklepy.objects.models.collections.collection import Collection
from specklepy.objects.other import RenderMaterial
from specklepy.objects.proxies import RenderMaterialProxy
from specklepy.serialization.base_object_serializer import BaseObjectSerializer
from specklepy.transports.memory import MemoryTransport

if TYPE_CHECKING:
    from bimpolars import BimDataFrame

    from specklewidgets.models import SpeckleObject

type Rgb = tuple[float, float, float]
"""A colour, each channel 0..1."""


def _hex_rgb(code: str) -> Rgb:
    """``#rrggbb`` as RGB 0..1."""
    return (int(code[1:3], 16) / 255, int(code[3:5], 16) / 255, int(code[5:7], 16) / 255)


CATEGORICAL_RGB: tuple[Rgb, ...] = tuple(
    _hex_rgb(code)
    for code in (
        "#2a78d6",
        "#eb6834",
        "#1baf7a",
        "#eda100",
        "#e87ba4",
        "#008300",
        "#6250d6",
        "#e34948",
    )
)
"""The colours of a categorical ``color`` column, in order: blue, orange, aqua, yellow,
magenta, green, violet, red. The most common value takes the first; the values past the
eighth share :data:`OTHER_RGB`."""

SEQUENTIAL_RGB: tuple[Rgb, ...] = tuple(
    _hex_rgb(code)
    for code in (
        "#86b6ef",
        "#6da7ec",
        "#5598e7",
        "#3987e5",
        "#2a78d6",
        "#256abf",
        "#1c5cab",
        "#184f95",
        "#104281",
        "#0d366b",
    )
)
"""The colours of a numeric ``color`` column, light to dark: one blue per tenth of the range
between its minimum and maximum."""

OTHER_RGB: Rgb = UNSTYLED_RGBA[:3]
"""The colour of the rows whose ``color`` value is null, or a category past the eighth: the
grey of faces without a style."""

PROPERTIES_FIELD = "properties"
"""The DataObject's property bag, where the property sets named ``properties.<group>`` go."""

_ROW_FIELDS = frozenset(
    {"id", "name", "class", "properties", "mesh", "bbox", "native_geom", CRS_COLUMN}
)
"""The columns that become the DataObject's own parts rather than a field of the same name;
``bim_crs`` gives the model's ``units`` and the root's name instead."""

_RESERVED_FIELDS = frozenset(
    {
        "id",
        "speckle_type",
        "applicationId",
        "totalChildrenCount",
        "units",
        "name",
        "category",
        "properties",
        "displayValue",
        "elements",
        "__closure",
    }
)
"""Fields of a DataObject that a column or property set of the same name must not overwrite;
such a column or set goes into ``properties`` instead."""

_UNCLASSIFIED = "unclassified"
"""The name of the collection of rows without a class."""

_JSON_PIPELINE_DEPRECATION = r".*JSON based send/receive pipelines are deprecated"
"""The DeprecationWarning of specklepy's v3 serializer, which :func:`bim_objects` uses on
purpose: the viewer reads v3 objects."""


def bim_objects(
    bdf: BimDataFrame, *, color: str | pl.Expr | None = None, name: str | None = None
) -> list[SpeckleObject]:
    """Turns a BimDataFrame into the v3 objects of one Speckle model, root first.

    The objects are those of :func:`bim_collection`, serialized with specklepy: each object
    gets its content hash as ``id``, the large vertex and face lists go into DataChunks, and
    the root lists every object below it in its ``__closure``. That is the model format of
    :class:`~specklewidgets.SpeckleViewer` and :func:`~specklewidgets.models_gz`, and of a
    Speckle server.

    Args:
        bdf: The model.
        color: Colours the elements by a column (its name) or an expression instead of by
            their styles; see :func:`bim_collection`.
        name: The root collection's name; the CRS's name by default.

    Returns:
        The parsed objects, the root first and the objects of its closure after it.

    Raises:
        ValueError: If a drawn row has no ``id`` or shares it with another, or ``color``
            does not give one value per row.
        TypeError: If ``color`` gives a nested or binary column.
    """
    root = bim_collection(bdf, color=color, name=name)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", _JSON_PIPELINE_DEPRECATION, DeprecationWarning)
        memory = MemoryTransport()
        root_id, _ = BaseObjectSerializer(write_transports=[memory]).traverse_base(root)
    objects: dict[str, str] = memory.objects
    return [
        json.loads(objects[root_id]),
        *(json.loads(text) for object_id, text in objects.items() if object_id != root_id),
    ]


def bim_collection(
    bdf: BimDataFrame, *, color: str | pl.Expr | None = None, name: str | None = None
) -> Collection:
    """Turns a BimDataFrame into a specklepy Collection: one DataObject per drawn row.

    The drawn rows are those with a ``mesh``, except the classes of
    :data:`bimpolars.gltf.EXCLUDED_CLASSES` (an ``IfcOpeningElement``'s mesh is the void it
    cuts), as :func:`bimpolars.element_meshes_glb` leaves them out. Each becomes a
    ``DataObject``:

    - ``applicationId``: the row's ``id``, which a click on the element reports.
    - ``name``: the row's ``name``, else its ``id``; ``category``: its ``class``.
    - The property sets of the ``properties`` column, each at the path its name gives, the
      dotted path of a group in a Speckle object as :func:`bimpolars.read_speckle` names
      them: ``properties.Parameters.Dimensions`` in ``properties`` → ``Parameters``,
      ``object`` as the object's own fields, and an IFC property set such as
      ``Pset_WallCommon`` as a field of that name.
    - The row's other columns as fields of their own (``container``, a column the caller
      added), except the geometry (``mesh``, ``bbox``, ``native_geom`` and the binary WKB
      columns).
    - ``displayValue``: one ``Mesh`` per style of the row's mesh (applicationId
      ``<id>/<style index>``), in the model's length unit when Speckle knows it, else in
      metres.

    Nulls are left out. A set or column named like a field every DataObject has (``units``,
    ``category``, ...) or with a name specklepy refuses for a field (with ``/`` or ``.``, or
    starting with ``@``) goes into ``properties`` instead.

    The DataObjects are grouped into one Collection per class (sorted by name) under a root
    Collection. Each style, a ``(name, rgba)`` of the meshes' ``styles``, becomes a
    ``RenderMaterial`` with that colour and opacity, in a ``RenderMaterialProxy`` on the root
    that targets the style's meshes; unstyled faces (a null ``name``) get none, so the viewer
    draws them in its default grey and :func:`bimpolars.read_speckle` reads them back
    unstyled.

    With ``color``, the values of a column colour the elements instead: one mesh per element,
    and a proxy per colour that targets the elements. A numeric column goes through
    :data:`SEQUENTIAL_RGB` in ten equal steps from its minimum to its maximum, any other
    through :data:`CATEGORICAL_RGB` by how many rows have the value, most first; a null value
    and the values past the eighth get :data:`OTHER_RGB`. Each material is named after what
    it shows, such as ``class: IfcWall`` or ``Volume: 1.2 to 2.4``.

    Args:
        bdf: The model.
        color: Colours the elements by a column, named, or by an expression on the frame
            (``pl.col("properties").struct.field("Pset_WallCommon").struct.field(
            "IsExternal")``) instead of by their styles. None: by their styles.
        name: The root collection's name; the CRS's name by default.

    Returns:
        The root Collection, its ``renderMaterialProxies`` set.

    Raises:
        ValueError: If a drawn row has no ``id`` or shares it with another, or ``color``
            does not give one value per row.
        TypeError: If ``color`` gives a nested or binary column.
    """
    frame = bdf.frame
    drawn = pl.col("mesh").is_not_null()
    if "class" in frame.columns:
        drawn &= ~pl.col("class").cast(pl.String).is_in(EXCLUDED_CLASSES).fill_null(False)
    frame = frame.filter(drawn)
    ids = frame["id"]
    if ids.null_count() or ids.n_unique() != len(ids):
        raise ValueError("every drawn row needs an id of its own, for its applicationId")

    unit = as_linear_unit(bdf)
    units = next((code for code, known in SPECKLE_UNITS.items() if known == unit), None)
    scale = 1.0 if units is not None else unit.conversion_factor
    meshes = _RowMeshes(frame["mesh"], scale)

    colours: list[tuple[str, Rgb]] = []
    colour_index: list[int] = []
    if color is not None:
        colours, colour_index = _colours(_color_values(frame, color))
    # Per material, its name and RGBA, the applicationIds it targets
    targets: dict[tuple[str, tuple[float, ...]], list[str]] = {}

    collections: dict[str, list[DataObject]] = {}
    row_fields = _row_fields(frame)
    for index, (row_id, row_name, row_class) in enumerate(
        frame.select("id", _optional(frame, "name"), _optional(frame, "class")).iter_rows()
    ):
        display_value = []
        if color is None:
            for style_index, (style, vertices, faces) in enumerate(meshes.by_style(index)):
                mesh = Mesh(vertices=vertices, faces=faces, units=units or "m")
                mesh.applicationId = f"{row_id}/{style_index}"
                display_value.append(mesh)
                if style["name"] is not None:
                    key = (style["name"], tuple(style["rgba"]))
                    targets.setdefault(key, []).append(mesh.applicationId)
        else:
            vertices, faces = meshes.whole(index)
            display_value.append(Mesh(vertices=vertices, faces=faces, units=units or "m"))
            colour_name, rgb = colours[colour_index[index]]
            targets.setdefault((colour_name, (*rgb, 1.0)), []).append(str(row_id))
        fields = row_fields[index]
        properties = fields.pop(PROPERTIES_FIELD, None)
        element = DataObject(
            name=str(row_name) if row_name is not None else str(row_id),
            properties=properties if isinstance(properties, dict) else {},
            displayValue=display_value,
        )
        element.applicationId = str(row_id)
        if row_class is not None:
            element["category"] = str(row_class)
        for field, value in fields.items():
            if field in _RESERVED_FIELDS or not _is_member_name(field):
                element.properties.setdefault(field, value)
            else:
                element[field] = value
        collections.setdefault(
            str(row_class) if row_class is not None else _UNCLASSIFIED, []
        ).append(element)

    root = Collection(
        name=name or bdf.crs.name or "BimDataFrame",
        elements=[
            Collection(name=class_name, elements=elements)
            for class_name, elements in sorted(collections.items())
        ],
    )
    root["units"] = units or "m"
    root["renderMaterialProxies"] = [
        RenderMaterialProxy(
            value=RenderMaterial(
                name=material_name,
                diffuse=_argb(rgba),
                opacity=float(rgba[3]),
            ),
            objects=objects,
        )
        for (material_name, rgba), objects in targets.items()
    ]
    return root


class _RowMeshes:
    """The meshes of a ``mesh`` column, sliced per row from :func:`bimpolars.mesh.mesh_arrays`."""

    def __init__(self, mesh: pl.Series, scale: float) -> None:
        self._arrays = mesh_arrays(mesh)
        self._scale = scale
        self._styles: list[list[dict[str, Any]]] = mesh.struct.field("styles").to_list()

    def _row(self, row: int) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        """A row's vertices ``(n, 3)``, scaled, and its faces ``(m, 3)``."""
        vertices, faces = self._arrays.row(row)
        return vertices * self._scale, faces

    def whole(self, row: int) -> tuple[list[float], list[int]]:
        """A row's vertices and its faces as Speckle lists them: ``3, a, b, c`` each."""
        vertices, faces = self._row(row)
        return vertices.ravel().tolist(), _speckle_faces(faces)

    def by_style(self, row: int) -> list[tuple[dict[str, Any], list[float], list[int]]]:
        """Per style of a row: the style, and the vertices and Speckle faces of its faces."""
        points, faces = self._row(row)
        styles = self._styles[row]
        if len(styles) < 2:
            only: dict[str, Any] = styles[0] if styles else {"name": None, "rgba": UNSTYLED_RGBA}
            return [(only, points.ravel().tolist(), _speckle_faces(faces))]
        parts = []
        start = 0
        for style in styles:
            block = faces[start : start + style["face_count"]]
            start += style["face_count"]
            used, local = np.unique(block, return_inverse=True)
            parts.append((style, points[used].ravel().tolist(), _speckle_faces(local)))
        return parts


def _speckle_faces(triangles: np.ndarray[Any, Any]) -> list[int]:
    """Triangles ``(m, 3)`` as Speckle's face list: the vertex count, 3, before each."""
    triangles = triangles.reshape(-1, 3)
    faces: list[int] = np.c_[np.full(len(triangles), 3), triangles].ravel().tolist()
    return faces


def _optional(frame: pl.DataFrame, column: str) -> pl.Expr:
    """The column, or nulls where the frame has none of that name."""
    if column in frame.columns:
        return pl.col(column)
    return pl.lit(None).alias(column)


def _color_values(frame: pl.DataFrame, color: str | pl.Expr) -> pl.Series:
    """The values that colour the rows, one per row, named after what gave them."""
    values = frame.select(pl.col(color) if isinstance(color, str) else color).to_series()
    if len(values) != len(frame):
        raise ValueError(f"color gives {len(values)} values for {len(frame)} rows")
    if values.dtype.is_nested() or values.dtype == pl.Binary:
        raise TypeError(f"color must give scalar values, not {values.dtype}")
    return values


def _colours(values: pl.Series) -> tuple[list[tuple[str, Rgb]], list[int]]:
    """The colours of a ``color`` column: per colour its name and RGB, and per row its index."""
    if values.dtype.is_numeric():
        return _numeric_colours(values.cast(pl.Float64), values.name)
    return _categorical_colours(values.cast(pl.String), values.name)


def _numeric_colours(values: pl.Series, label: str) -> tuple[list[tuple[str, Rgb]], list[int]]:
    """Ten equal steps of :data:`SEQUENTIAL_RGB` from the minimum to the maximum."""
    numbers = values.fill_nan(None).to_numpy()
    finite = np.isfinite(numbers)
    colours: list[tuple[str, Rgb]] = [(f"{label}: no value", OTHER_RGB)]
    index = np.zeros(len(numbers), dtype=np.int64)
    if not finite.any():
        return colours, index.tolist()
    low, high = float(numbers[finite].min()), float(numbers[finite].max())
    steps = len(SEQUENTIAL_RGB)
    width = (high - low) / steps
    step = np.zeros(len(numbers), dtype=np.int64)
    if width > 0:
        step[finite] = np.minimum(((numbers[finite] - low) / width).astype(np.int64), steps - 1)
    used = sorted(set(step[finite].tolist()))
    for position, k in enumerate(used, start=1):
        lower = low + k * width
        upper = high if k == steps - 1 or width == 0 else low + (k + 1) * width
        colours.append((f"{label}: {lower:.6g} to {upper:.6g}", SEQUENTIAL_RGB[k]))
        index[finite & (step == k)] = position
    return colours, index.tolist()


def _categorical_colours(values: pl.Series, label: str) -> tuple[list[tuple[str, Rgb]], list[int]]:
    """:data:`CATEGORICAL_RGB` by how many rows have each value; the rest grey."""
    counts = (
        values.rename("value")
        .drop_nulls()
        .value_counts(sort=False, name="rows")
        .sort(["rows", "value"], descending=[True, False])
    )
    ranked: list[str] = counts["value"].to_list()
    colours: list[tuple[str, Rgb]] = [
        (f"{label}: {value}", rgb) for value, rgb in zip(ranked, CATEGORICAL_RGB, strict=False)
    ]
    position = {value: k for k, value in enumerate(ranked[: len(CATEGORICAL_RGB)])}
    rest = len(colours)
    if len(ranked) > len(CATEGORICAL_RGB):
        colours.append((f"{label}: other", OTHER_RGB))
    if values.null_count():
        colours.append((f"{label}: no value", OTHER_RGB))
    no_value = len(colours) - 1
    index = [no_value if value is None else position.get(value, rest) for value in values.to_list()]
    return colours, index


def _row_fields(frame: pl.DataFrame) -> list[dict[str, Any]]:
    """Per row, the DataObject's fields: its property sets at their paths and its columns.

    A property set's name is the dotted path of its group in a Speckle object, as
    :func:`bimpolars.read_speckle` names them, so each set goes back to that path:
    ``properties.Parameters.Dimensions`` into ``properties`` → ``Parameters`` →
    ``Dimensions``, an IFC property set such as ``Pset_WallCommon`` into a field of that
    name, and :data:`bimpolars.speckle.OBJECT_SET` into the object's own fields. The columns
    other than those the DataObject is made of (and the geometry) follow as fields of their
    own. Nulls are left out.
    """
    rows: list[dict[str, Any]] = [{} for _ in range(len(frame))]
    if "properties" in frame.columns and isinstance(frame.schema["properties"], pl.Struct):
        # One set at a time, and only on the rows that have it: a model's sets are sparse
        # (most rows have a few of many), and boxing every null of a wide Struct into Python
        # would take most of the time
        for property_set in frame["properties"].struct.unnest().iter_columns():
            present = property_set.is_not_null().arg_true()
            path = [] if property_set.name == OBJECT_SET else property_set.name.split(".")
            for index, values in zip(
                present.to_list(), property_set.gather(present).to_list(), strict=True
            ):
                values = _jsonable(values)
                if values is not None:
                    _at_path(rows[index], path).update(values)
    columns = [
        column
        for column, dtype in frame.schema.items()
        if column not in _ROW_FIELDS and dtype not in (pl.Binary, pl.Null)
    ]
    if columns:
        for fields, values in zip(rows, frame.select(columns).iter_rows(named=True), strict=True):
            fields.update(_jsonable(values) or {})
    return rows


def _at_path(fields: dict[str, Any], path: Sequence[str]) -> dict[str, Any]:
    """The dict at a path of nested dicts, made where missing (or where a value is in the way)."""
    for key in path:
        child = fields.get(key)
        if not isinstance(child, dict):
            child = fields[key] = {}
        fields = child
    return fields


def _is_member_name(name: str) -> bool:
    """Whether specklepy takes the name for a field: not empty, no ``.`` or ``/``, no ``@``.

    A leading ``@`` would make specklepy detach the value into an object of its own.
    """
    return bool(name) and not name.startswith("@") and "." not in name and "/" not in name


def _jsonable(value: Any) -> Any:
    """A value as JSON holds it, its nulls (and NaN) left out; None if nothing is left.

    Dates and times become ISO text, decimals floats, and bytes are left out.
    """
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        items = {str(key): _jsonable(item) for key, item in value.items()}
        kept = {key: item for key, item in items.items() if item is not None}
        return kept or None
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return value.total_seconds()
    if isinstance(value, decimal.Decimal):
        return _jsonable(float(value))
    if isinstance(value, bytes | bytearray):
        return None
    return str(value)


def _argb(rgba: Sequence[float]) -> int:
    """An RGB colour 0..1 as Speckle's ARGB int, opaque, signed as the Revit connector writes it."""
    red, green, blue = (round(255 * channel) for channel in rgba[:3])
    return ((0xFF << 24) | (red << 16) | (green << 8) | blue) - (1 << 32)


__all__ = [
    "CATEGORICAL_RGB",
    "OTHER_RGB",
    "SEQUENTIAL_RGB",
    "bim_collection",
    "bim_objects",
]

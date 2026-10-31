"""Speckle's web viewer with the model's surroundings: a ground map and 3D Tiles around it.

``GeoSpeckleViewer`` is ``SpeckleViewer`` with two more traits: an
OpenStreetMap snapshot on a plane under the model (``ground_map``) and 3D Tiles such as
PDOK's 3D BAG around it (``tilesets``), each tileset without the buildings that lie mostly
within its ``hide_within`` polygons, to make room for the model. Both are in the viewer's
world: the models' coordinates in metres. ``specklewidgets.geo`` builds them for a
georeferenced BimDataFrame.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

import traitlets

from specklewidgets.speckle_viewer import _STATIC, Marker, SpeckleViewer, ViewerModel

if TYPE_CHECKING:
    import polars as pl


class GroundMap(TypedDict):
    """A map image under the model, north up: the ``ground_map`` trait.

    The front end draws OpenStreetMap's tiles over ``bounds`` into a ``width`` x ``height``
    image and lays it on a plane whose corners are the bounds' corners through
    ``lnglat_to_world``. ``specklewidgets.geo.osm_ground_map`` builds one.
    """

    bounds: list[float]
    """``[west, south, east, north]`` in degrees."""
    width: int
    """The image's width in pixels."""
    height: int
    """The image's height in pixels: the bounds' shape in Web Mercator."""
    lnglat_to_world: list[float]
    """An affine ``[a, b, c, d, e, f]`` from longitude and latitude to the viewer's world:
    ``x = a lon + b lat + c``, ``y = d lon + e lat + f``, in metres."""
    z: float
    """The plane's height in the viewer's world, metres."""
    opacity: float
    """The plane's opacity, 0..1."""


class Tileset(TypedDict):
    """3D Tiles around the model: an entry of the ``tilesets`` trait.

    ``specklewidgets.geo.pdok_3d_buildings`` builds one.
    """

    tileset: dict[str, Any]
    """The tileset JSON, its content URLs absolute (a ``tileset.json`` as 3D Tiles 1.1 has
    it; :func:`specklewidgets.geo.site_3d_tiles` cuts one to an area)."""
    ecef_to_world: list[float]
    """A 4x4 matrix, column-major, from ECEF (EPSG:4978), where the tiles are, to the
    viewer's world."""
    attribution: NotRequired[str]
    """The credit line the viewer shows for the tiles."""
    hide_within: NotRequired[list[list[list[list[float]]]]]
    """Polygons in the viewer's world, each as rings of ``[x, y]`` (the exterior, then the
    holes): a feature (an ``EXT_mesh_features`` id, a building in the 3D BAG) with more than
    half of its vertices inside one of them is left out."""


class GeoSpeckleViewer(SpeckleViewer):
    """``SpeckleViewer`` with the model's surroundings.

    ``GeoSpeckleViewer(models, ground_map=..., tilesets=[...])`` draws the models as
    ``SpeckleViewer`` does, on a ground map and among 3D Tiles, all in
    the viewer's world: the models' coordinates in metres. For a georeferenced BimDataFrame,
    ``specklewidgets.geo`` builds both. The map and the tiles are not elements:
    ``object_count`` and ``scene_bbox`` leave them out and a click does not select them. The
    front end reports what they show in ``surroundings``.

    Args:
        models (ViewerModel | Sequence[ViewerModel] | None): One model or a sequence of
            models, as for ``SpeckleViewer``.
        color (str | pl.Expr | None): Colours the elements of the BimDataFrames by a column
            or a polars expression, as for ``SpeckleViewer``.
        markers (Sequence[Marker | Mapping[str, Any]] | None): Axes with a label
            (→ ``markers``).
        ground_map (GroundMap | Mapping[str, Any] | None): The map under the model
            (→ ``ground_map``), such as ``specklewidgets.geo.osm_ground_map`` gives it.
        tilesets (Sequence[Tileset | Mapping[str, Any]] | None): 3D Tiles around the model
            (→ ``tilesets``), such as ``specklewidgets.geo.pdok_3d_buildings`` gives them.
        **kwargs (Any): Traits, passed through unchanged, such as ``height=600``.

    Raises:
        ValueError: As ``SpeckleViewer`` raises it.
    """

    _esm = _STATIC / "geospeckle-viewer.js"

    # The map under the model (GroundMap): bounds [west, south, east, north] in degrees, width
    # and height in pixels, lnglat_to_world (an affine [a, b, c, d, e, f]: x = a lon + b lat +
    # c, y = d lon + e lat + f), z in metres and opacity. {}: no map.
    ground_map = traitlets.Dict({}).tag(sync=True)
    # 3D Tiles (Tileset): [{"tileset": tileset JSON, "ecef_to_world": column-major 4x4,
    # "attribution": credit line, "hide_within": [polygon as rings of [x, y] in metres]}]
    tilesets = traitlets.List[dict[str, Any]]([]).tag(sync=True)
    # Set by the front end: the ground map's plane, [xmin, ymin, xmax, ymax] in metres ([]
    # until it is drawn); the tile contents loaded; how many features of those tiles
    # hide_within leaves out; and the heights those features span, [zmin, zmax] in metres ([]
    # for none), which tell where the tiles stand against the model
    surroundings = traitlets.Dict(
        {"ground_map": [], "tiles": 0, "hidden_features": 0, "hidden_heights": []},
    ).tag(sync=True)

    def __init__(
        self,
        models: ViewerModel | Sequence[ViewerModel] | None = None,
        *,
        color: str | pl.Expr | None = None,
        markers: Sequence[Marker | Mapping[str, Any]] | None = None,
        ground_map: GroundMap | Mapping[str, Any] | None = None,
        tilesets: Sequence[Tileset | Mapping[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        if ground_map is not None:
            kwargs["ground_map"] = dict(ground_map)
        if tilesets is not None:
            kwargs["tilesets"] = [dict(tileset) for tileset in tilesets]
        super().__init__(models, color=color, markers=markers, **kwargs)

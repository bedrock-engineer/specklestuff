"""The surroundings of a georeferenced BimDataFrame, for :class:`~specklewidgets.GeoSpeckleViewer`.

A BimDataFrame in the Engineering CRS of :func:`bimpolars.geobim.derived_engineering_crs`
(labelled with :func:`bimpolars.geobim.set_crs`) knows where it is on earth. From that,
:func:`osm_ground_map` lays an OpenStreetMap snapshot under the model,
:func:`pdok_3d_buildings` places the buildings of PDOK's 3D Basisvoorziening (the 3D BAG)
around it, cut to the area by :func:`site_3d_tiles`, and :func:`bag_panden_under` finds the
BAG panden the model takes the place of, which ``hide_within`` then leaves out of the 3D BAG.

The viewer's world is the model's coordinates in metres. One 4x4 matrix,
:func:`bimpolars.geobim.linearized_site_to_ecef`, takes it to ECEF and back for the ground
map, the panden and the tiles alike, so that the three line up with each other exactly; over
the few hundred metres around a site it strays from PROJ's own transformation by
millimetres. The ground map and the 3D BAG cover the model's plan extent and a margin around
it.

This module needs the ``[geo]`` extra (pyproj) and bimpolars, which comes with any
BimDataFrame. :func:`site_3d_tiles` and :func:`bag_panden_under` read PDOK's APIs on
api.pdok.nl; the browser fetches the map tiles and the 3D BAG's tiles itself.
"""

from __future__ import annotations

import functools
import json
import math
import urllib.parse
import urllib.request
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl
import shapely
import shapely.geometry
from bimpolars.crs import linear_unit
from shapely.geometry.base import BaseGeometry

try:
    import pyproj
    from bimpolars.geobim import linearized_site_to_ecef
except ImportError as error:
    raise ImportError(
        "specklewidgets.geo needs pyproj: install the extra specklewidgets[geo]"
    ) from error

from specklewidgets.geo_speckle_viewer import GroundMap, Tileset

if TYPE_CHECKING:
    from bimpolars import BimDataFrame

PDOK_3D_BUILDINGS = (
    "https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1/collections/gebouwen/3dtiles?f=json"
)
"""The 3D Tiles of PDOK's 3D Basisvoorziening buildings (LoD 2.2): the 3D BAG."""

PDOK_3D_ATTRIBUTION = "3D Basisvoorziening © Kadaster (CC BY 4.0)"
"""The credit line for :data:`PDOK_3D_BUILDINGS`."""

PDOK_BAG_PANDEN = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items"
"""The BAG's panden (buildings) in PDOK's OGC API Features, in OGC:CRS84."""

DEFAULT_MARGIN = 150.0
"""Metres of surroundings around the model's plan extent."""

_TIMEOUT = 30.0
"""Seconds to wait for one of PDOK's answers."""

_BAG_PAGE = 1000
"""Panden per page of the BAG's OGC API, its maximum."""

type Matrix = np.ndarray[Any, np.dtype[np.float64]]


def osm_ground_map(
    bdf: BimDataFrame,
    *,
    margin: float = DEFAULT_MARGIN,
    width: int = 2048,
    z: float = 0.0,
    opacity: float = 0.85,
) -> GroundMap:
    """An OpenStreetMap snapshot under the model, for ``GeoSpeckleViewer(ground_map=...)``.

    The map covers the model's plan extent and ``margin`` metres around it, north up, in
    longitude and latitude. Its corners go to the viewer's world through one affine transform
    from longitude and latitude, fitted on a 21 x 21 grid over the map: the meridians
    converge, so over the 500 m of Sixty5's map it is good to a centimetre (11 mm at the
    corners), and to a few centimetres over a kilometre or two.

    Args:
        bdf: The model, in a georeferenced CRS such as the Engineering CRS of
            :func:`bimpolars.geobim.derived_engineering_crs`, with its ``bbox`` column.
        margin: Metres of map around the model's plan extent.
        width: The map image's width in pixels; its height follows from the bounds.
        z: The map's height in the viewer's world, in metres: 0 is the height of the CRS's
            origin, the site's ground level in a derived Engineering CRS.
        opacity: The map's opacity, 0..1.

    Returns:
        The ``ground_map`` trait.

    Raises:
        ValueError: If no row has a ``bbox``, or pyproj cannot transform the model CRS to
            ECEF (a plain EngineeringCRS is not georeferenced).
    """
    world = _World(bdf.crs)
    west, south, east, north = world.lonlat_bounds(_plan_extent(bdf), margin, z)
    lon, lat = (
        grid.ravel()
        for grid in np.meshgrid(np.linspace(west, east, 21), np.linspace(south, north, 21))
    )
    xy = world.from_lonlat(lon, lat, world.height(z))[:, :2]
    design = np.column_stack([lon, lat, np.ones(lon.size)])
    affine = np.linalg.lstsq(design, xy, rcond=None)[0]  # columns: x, y
    # Pixels in proportion to the bounds in Web Mercator, which the tiles are drawn in
    mercator = [math.asinh(math.tan(math.radians(phi))) for phi in (south, north)]
    return {
        "bounds": [west, south, east, north],
        "width": width,
        "height": round(width * (mercator[1] - mercator[0]) / math.radians(east - west)),
        "lnglat_to_world": affine.T.ravel().tolist(),
        "z": z,
        "opacity": opacity,
    }


def pdok_3d_buildings(
    bdf: BimDataFrame,
    bounds: Sequence[float] | None = None,
    *,
    margin: float = DEFAULT_MARGIN,
    hide_within: Iterable[BaseGeometry] = (),
    hide_margin: float = 0.5,
) -> Tileset:
    """The buildings of PDOK's 3D Basisvoorziening around the model, for ``tilesets=[...]``.

    The 3D BAG's finest tiles that overlap ``bounds`` (see :func:`site_3d_tiles`), placed in
    the viewer's world, with the buildings mostly within ``hide_within`` left out.

    Args:
        bdf: The model, in a georeferenced CRS, with its ``bbox`` column.
        bounds: ``[west, south, east, north]`` in degrees, such as the ``bounds`` of
            :func:`osm_ground_map`; by default the model's plan extent and ``margin`` metres
            around it, the area :func:`osm_ground_map` covers.
        margin: Metres around the model's plan extent, without ``bounds``.
        hide_within: Polygons or multipolygons in the model's coordinates, such as the
            values of :func:`bag_panden_under`: a building with more than half of its
            vertices within one of them is left out, to make room for the model.
        hide_margin: Metres the ``hide_within`` polygons grow by, so that a building's
            vertices on the outline of its pand count as within.

    Returns:
        The ``tilesets`` entry, with PDOK's credit line.

    Raises:
        ValueError: As :func:`osm_ground_map` raises it, or if no tile of the 3D BAG
            overlaps ``bounds``.
        urllib.error.URLError: If api.pdok.nl does not answer.
    """
    world = _World(bdf.crs)
    if bounds is None:
        bounds = world.lonlat_bounds(_plan_extent(bdf), margin, 0.0)
    rings: list[list[list[list[float]]]] = []
    for geometry in hide_within:
        metres = shapely.transform(shapely.force_2d(geometry), lambda xy: xy * world.metres)
        grown = shapely.buffer(metres, hide_margin)
        polygons = shapely.get_parts(grown)
        rings.extend(
            [
                np.asarray(ring.coords)[:, :2].tolist()
                for ring in (polygon.exterior, *polygon.interiors)
            ]
            for polygon in polygons
            if not polygon.is_empty
        )
    return {
        "tileset": site_3d_tiles(PDOK_3D_BUILDINGS, bounds),
        "ecef_to_world": world.from_ecef.flatten(order="F").tolist(),
        "attribution": PDOK_3D_ATTRIBUTION,
        "hide_within": rings,
    }


def site_3d_tiles(tileset_url: str, bounds: Sequence[float]) -> dict[str, Any]:
    """A small tileset of only the finest tiles of ``tileset_url`` that overlap ``bounds``.

    The tree is walked only along tiles whose region overlaps the bounds, fetching just the
    external tilesets on that path. 3d-tiles-renderer 0.3.46, the one for the viewer's
    three.js, marks every child of a tile without content as used, in view or not, so on
    PDOK's whole tree it would fetch the external tilesets of half the country.

    Args:
        tileset_url: The URL of a 3D Tiles tileset whose tiles have region bounding volumes.
        bounds: ``[west, south, east, north]`` in degrees.

    Returns:
        A one-level tileset: an empty root over the content tiles, each with its accumulated
        transform and an absolute content URL.

    Raises:
        ValueError: If no content tile overlaps ``bounds``.
        urllib.error.URLError: If a tileset does not load.
    """
    west, south, east, north = (math.radians(value) for value in bounds)

    def overlaps(tile: dict[str, Any]) -> bool:
        region = tile["boundingVolume"].get("region")
        if region is None:  # a box or a sphere: walked into
            return True
        return bool(
            region[0] <= east and region[2] >= west and region[1] <= north and region[3] >= south
        )

    leaves: list[dict[str, Any]] = []

    def walk(tile: dict[str, Any], base_url: str, transform: Matrix) -> None:
        if not overlaps(tile):
            return
        if "transform" in tile:
            transform = transform @ np.array(tile["transform"], dtype=float).reshape(
                4, 4, order="F"
            )
        uri = tile.get("content", {}).get("uri")
        if uri and uri.split("?")[0].endswith(".json"):
            external_url = urllib.parse.urljoin(base_url, uri)
            walk(_fetch_json(external_url)["root"], external_url, transform)
            return
        children = [child for child in tile.get("children", []) if overlaps(child)]
        if uri and (not children or tile["geometricError"] == 0):
            leaves.append(
                {
                    "boundingVolume": tile["boundingVolume"],
                    "geometricError": 0,
                    "transform": transform.flatten(order="F").tolist(),
                    "content": {"uri": urllib.parse.urljoin(base_url, uri)},
                }
            )
            return
        for child in children:
            walk(child, base_url, transform)

    walk(_fetch_json(tileset_url)["root"], tileset_url, np.eye(4))
    if not leaves:
        raise ValueError(f"no tile of {tileset_url} overlaps {list(bounds)}")
    regions = [
        leaf["boundingVolume"]["region"] for leaf in leaves if "region" in leaf["boundingVolume"]
    ]
    root: dict[str, Any] = {"geometricError": 1000, "refine": "ADD", "children": leaves}
    if len(regions) == len(leaves):
        corners = np.array(regions)
        root["boundingVolume"] = {
            "region": [
                *corners[:, :2].min(axis=0).tolist(),
                *corners[:, 2:4].max(axis=0).tolist(),
                float(corners[:, 4].min()),
                float(corners[:, 5].max()),
            ]
        }
    else:
        # Regions of the area itself, from below the geoid to above any building
        root["boundingVolume"] = {"region": [west, south, east, north, -1000.0, 10_000.0]}
    return {"asset": {"version": "1.1"}, "geometricError": 1000, "root": root}


def bag_panden_under(
    bdf: BimDataFrame, footprint: BaseGeometry | None = None
) -> dict[str, BaseGeometry]:
    """The BAG panden (buildings) with more than half of their area under the model.

    The panden come from PDOK's OGC API (:data:`PDOK_BAG_PANDEN`) and go to the model's
    coordinates through the viewer's world, as the 3D BAG's tiles do, so that
    ``pdok_3d_buildings(bdf, hide_within=bag_panden_under(bdf).values())`` leaves exactly
    their buildings out.

    Args:
        bdf: The model, in a georeferenced CRS.
        footprint: The model's outline in plan, a polygon or multipolygon in its coordinates;
            by default the union of its ``footprint`` column (see
            :func:`bimpolars.simple_features`), which for a building is its outline.

    Returns:
        The panden by their ``identificatie``, as polygons in the model's coordinates (x and
        y; the BAG has no heights).

    Raises:
        ValueError: If there is no ``footprint`` to go by, or pyproj cannot transform the
            model CRS to ECEF.
        urllib.error.URLError: If api.pdok.nl does not answer.
    """
    world = _World(bdf.crs)
    if footprint is None:
        footprint = _union_of_footprints(bdf)
    footprint = shapely.force_2d(footprint)
    if footprint.is_empty:
        raise ValueError("bag_panden_under needs a footprint with an area")
    x0, y0, x1, y1 = footprint.bounds
    west, south, east, north = world.lonlat_bounds((x0, y0, x1, y1), 0.0, 0.0)
    url: str | None = (
        PDOK_BAG_PANDEN
        + "?"
        + urllib.parse.urlencode(
            {"bbox": f"{west},{south},{east},{north}", "f": "json", "limit": _BAG_PAGE}
        )
    )
    height = world.height(0.0)

    def to_model(lonlat: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        xyz = world.from_lonlat(lonlat[:, 0], lonlat[:, 1], height)
        return xyz[:, :2] / world.metres

    under: dict[str, BaseGeometry] = {}
    while url is not None:
        page = _fetch_json(url)
        for pand in page["features"]:
            polygon = shapely.transform(shapely.geometry.shape(pand["geometry"]), to_model)
            if polygon.intersection(footprint).area > polygon.area / 2:
                under[str(pand["properties"]["identificatie"])] = polygon
        url = next(
            (link["href"] for link in page.get("links", []) if link.get("rel") == "next"),
            None,
        )
    return under


class _World:
    """The viewer's world of a model: its coordinates in metres, placed on earth by one 4x4."""

    def __init__(self, crs: dict[str, Any]) -> None:
        self.metres = linear_unit(crs).conversion_factor
        """Metres per unit of the model's coordinates."""
        self.to_ecef: Matrix = linearized_site_to_ecef(crs)
        self.from_ecef: Matrix = np.linalg.inv(self.to_ecef)

    def to_lonlat(self, xyz: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        """Points of the world (n x 3, metres) as longitude, latitude and ellipsoidal height."""
        ecef = np.asarray(xyz, dtype=float) @ self.to_ecef[:3, :3].T + self.to_ecef[:3, 3]
        return np.column_stack(_geocentric_to_geographic().transform(*ecef.T))

    def from_lonlat(self, lon: Any, lat: Any, height: float) -> np.ndarray[Any, Any]:
        """Longitudes and latitudes at an ellipsoidal height as points of the world (n x 3)."""
        lon = np.asarray(lon, dtype=float)
        ecef = np.column_stack(
            _geocentric_to_geographic().transform(
                lon, np.asarray(lat, dtype=float), np.full(lon.shape, height), direction="INVERSE"
            )
        )
        return ecef @ self.from_ecef[:3, :3].T + self.from_ecef[:3, 3]

    def height(self, z: float) -> float:
        """The ellipsoidal height of the world's origin raised to ``z`` metres."""
        return float(self.to_lonlat(np.array([[0.0, 0.0, z]]))[0, 2])

    def lonlat_bounds(self, extent: Sequence[float], margin: float, z: float) -> list[float]:
        """``[west, south, east, north]`` of a plan extent in model units, grown by metres."""
        x0, y0, x1, y1 = (value * self.metres for value in extent)
        corners = np.array(
            [
                [x0 - margin, y0 - margin, z],
                [x1 + margin, y0 - margin, z],
                [x1 + margin, y1 + margin, z],
                [x0 - margin, y1 + margin, z],
            ]
        )
        lon, lat, _ = self.to_lonlat(corners).T
        return [float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())]


@functools.cache
def _geocentric_to_geographic() -> pyproj.Transformer:
    """ECEF to longitude, latitude and ellipsoidal height on WGS 84: a conversion, no datum."""
    return pyproj.Transformer.from_crs("EPSG:4978", "EPSG:4979", always_xy=True)


def _plan_extent(bdf: BimDataFrame) -> tuple[float, float, float, float]:
    """``(xmin, ymin, xmax, ymax)`` of the rows' ``bbox``, in model units."""
    bbox = bdf.frame.select(pl.col("bbox").struct.unnest()).drop_nulls()
    if bbox.is_empty():
        raise ValueError("the model has no geometry: no row has a bbox")
    extent = bbox.select(
        pl.col("xmin").min(), pl.col("ymin").min(), pl.col("xmax").max(), pl.col("ymax").max()
    ).row(0)
    return (float(extent[0]), float(extent[1]), float(extent[2]), float(extent[3]))


def _union_of_footprints(bdf: BimDataFrame) -> BaseGeometry:
    """The union of the frame's footprints in plan."""
    if "footprint" not in bdf.frame.columns:
        raise ValueError(
            "bag_panden_under needs a footprint: pass one, or add the footprint column with "
            "bimpolars.simple_features first"
        )
    wkb = bdf.frame["footprint"].drop_nulls().to_numpy()
    return shapely.union_all(shapely.force_2d(shapely.from_wkb(wkb)))


def _fetch_json(url: str) -> Any:
    """GETs a URL's JSON."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.load(response)

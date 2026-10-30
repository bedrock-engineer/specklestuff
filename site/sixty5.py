"""Writes the data of the demo page in site/: Sixty5 in a GeoSpeckleViewer and its footprints.

The page is static (GitHub Pages), so what examples/sixty5_geo.py computes in the notebook is
computed here, at build time, and written to a folder the page fetches from:

- ``objects.json.gz``: the ``objects_gz`` trait, the model as gzipped v3 objects.
- ``viewer.json``: GeoSpeckleViewer's other traits, the ground map and the 3D BAG among them.
- ``footprints.geojson``: the footprint of every row the viewer draws, in longitude and
  latitude (bimpolars' ``geog`` column without its heights), with the row's id, class, name
  and storey, for the page's MapLibre map.
- ``outline.geojson``: the union of those footprints, the building's outline on that map.

Run it from the repository's root, with PROJ's network on or the NSGI grids installed:

    uv run python site/sixty5.py site/public/data
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import polars as pl
import pyproj
import shapely
from bimpolars import BimDataFrame, data, read_ifc, simple_features
from bimpolars.geobim import derived_engineering_crs, set_crs, with_geog
from bimpolars.gltf import EXCLUDED_CLASSES

from specklewidgets import GeoSpeckleViewer, Marker
from specklewidgets.geo import bag_panden_under, osm_ground_map, pdok_3d_buildings

IFC = "sixty5_O-S1-CON-structural-engineering.ifc"

DECIMALS = 8
"""Decimals of a degree kept in the GeoJSON: 1e-8 degrees is about a millimetre."""

TRAITS = (
    "height",
    "aspect_ratio",
    "selected",
    "markers",
    "object_count",
    "scene_bbox",
    "ground_map",
    "tilesets",
    "surroundings",
)
"""GeoSpeckleViewer's synced traits besides ``objects_gz``: GeoSpeckleViewerModel in
packages/geospeckle-viewer/src/lib/types.ts."""


def sixty5() -> BimDataFrame:
    """The structural model of Sixty5 in its Engineering CRS, as examples/sixty5_geo.py has it.

    Returns:
        The BimDataFrame in the site grid, in millimetres, on earth through the CRS.
    """
    bdf = read_ifc(data.fetch(IFC))
    crs = derived_engineering_crs(
        "EPSG:7415",
        easting=160_071.5,
        northing=384_156.5,
        orthometric_height=18.625,
        rotation=math.degrees(math.atan2(-0.7700680491484481, 0.6379617540893054)),
        unit=bdf,
        name="Sixty5",
    )
    return set_crs(bdf, crs)


DRAWN = pl.col("mesh").is_not_null() & ~pl.col("class").cast(pl.String).is_in(
    list(EXCLUDED_CLASSES)
).fill_null(False)
"""The rows the viewer draws: those with a mesh, except the openings."""


def viewer(site: BimDataFrame) -> GeoSpeckleViewer:
    """The GeoSpeckleViewer of the notebook: the model, the ground map and the 3D BAG.

    Args:
        site: The model, georeferenced.

    Returns:
        The widget, with its traits set as the notebook sets them.
    """
    # The slabs and footings outline the building in plan (the storeys stay, they place the
    # footprints); the BAG panden mostly under them are Sixty5's own
    ground_floor = simple_features(
        site.with_frame(
            site.frame.filter(
                pl.col("class").is_in(["IfcSlab", "IfcFooting"]) | pl.col("mesh").is_null()
            )
        )
    )
    panden = bag_panden_under(ground_floor)
    ground_map = osm_ground_map(site)
    tilesets = [pdok_3d_buildings(site, ground_map["bounds"], hide_within=panden.values())]
    return GeoSpeckleViewer(
        site,
        ground_map=ground_map,
        tilesets=tilesets,
        markers=[Marker("site origin", (0, 0, 0), size=10)],
    )


def _lonlat(wkb: bytes) -> shapely.Geometry:
    """A ``geog`` footprint without its heights, rounded to DECIMALS."""
    return shapely.transform(shapely.from_wkb(wkb), lambda xy: xy.round(DECIMALS))


def footprints(site: BimDataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    """The footprints of the drawn rows in longitude and latitude, and their union.

    Args:
        site: The model, georeferenced.

    Returns:
        A GeoJSON FeatureCollection of the drawn rows that have a footprint with plan area
        (``id``, ``class``, ``name``, ``storey`` and ``elevation`` in metres as properties),
        and a FeatureCollection of the building's outline.
    """
    # The spatial rows stay: they place the footprints at their storeys
    frame = site.frame.filter(DRAWN | pl.col("mesh").is_null())
    geog = with_geog(simple_features(site.with_frame(frame))).frame
    storeys = geog.filter(pl.col("class") == "IfcBuildingStorey").select(
        pl.col("id").alias("container"),
        pl.col("name").alias("storey"),
        (pl.col("elevation") * site.crs.axis_info[0].unit_conversion_factor).alias(
            "storey_elevation"
        ),
    )
    rows = (
        geog.filter(DRAWN)
        .join(storeys, on="container", how="left")
        .select(
            "id",
            pl.col("class").cast(pl.String),
            "name",
            "storey",
            pl.col("storey_elevation").alias("elevation"),
            "geog",
        )
    )
    features = []
    shapes = []
    for row in rows.iter_rows(named=True):
        shape = _lonlat(row.pop("geog"))
        if shape.is_empty:
            continue
        shapes.append(shape)
        features.append(
            {"type": "Feature", "properties": row, "geometry": shapely.geometry.mapping(shape)}
        )
    outline = _lonlat(shapely.to_wkb(shapely.union_all(shapes)))
    return (
        {"type": "FeatureCollection", "features": features},
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Sixty5"},
                    "geometry": shapely.geometry.mapping(outline),
                }
            ],
        },
    )


def write(folder: Path) -> None:
    """Writes the page's data into folder.

    Args:
        folder: Created if it does not exist; the files in it are overwritten.
    """
    # PDOK's 3D Tiles stand at ellipsoidal heights, which take the NSGI grids: without them
    # the 3D BAG floats 44 m above the map (see examples/sixty5_geo.py)
    pyproj.network.set_network_enabled(True)
    site = sixty5()
    widget = viewer(site)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "objects.json.gz").write_bytes(widget.objects_gz)
    state = {name: getattr(widget, name) for name in TRAITS}
    (folder / "viewer.json").write_text(json.dumps(state, separators=(",", ":")))
    elements, outline = footprints(site)
    for name, collection in (("footprints", elements), ("outline", outline)):
        (folder / f"{name}.geojson").write_text(json.dumps(collection, separators=(",", ":")))
    sizes = ", ".join(
        f"{path.name} {path.stat().st_size / 1e6:.1f} MB" for path in sorted(folder.iterdir())
    )
    print(f"{folder}: {len(elements['features'])} footprints; {sizes}")


if __name__ == "__main__":
    write(Path(sys.argv[1] if len(sys.argv) > 1 else "site/public/data"))

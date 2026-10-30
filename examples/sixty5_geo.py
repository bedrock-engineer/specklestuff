import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell
def _():
    import html
    import json
    import math

    import marimo as mo
    import polars as pl
    import pyproj
    import shapely
    from bimpolars import data, read_ifc, simple_features
    from bimpolars.crs import linear_unit
    from bimpolars.geobim import derived_engineering_crs, set_crs

    from specklewidgets import GeoSpeckleViewer, Marker
    from specklewidgets.geo import bag_panden_under, osm_ground_map, pdok_3d_buildings

    return (
        GeoSpeckleViewer,
        Marker,
        bag_panden_under,
        data,
        derived_engineering_crs,
        html,
        json,
        linear_unit,
        math,
        mo,
        osm_ground_map,
        pdok_3d_buildings,
        pl,
        pyproj,
        read_ifc,
        set_crs,
        shapely,
        simple_features,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Sixty5 among its neighbours

    The structural model of Sixty5, a tower at Strijp-S in Eindhoven, read from its IFC with
    [bimpolars](https://github.com/bedrock-engineer/bimpolars) and placed on earth with its
    Engineering CRS: the site origin at RD New 160071.5, 384156.5 and NAP +18.625 m, the site
    grid turned by -50.36 degrees. `GeoSpeckleViewer` shows it on an OpenStreetMap ground
    map, among the buildings of PDOK's 3D Basisvoorziening (the 3D BAG). Sixty5 is in the 3D
    BAG too: its BAG pand, found under the model's slabs and footings, is left out to make
    room for the model.

    Click an element to read its row below the viewer; shift-click adds to the selection.
    The axes mark the site origin.
    """)
    return


@app.cell
def _(data, derived_engineering_crs, linear_unit, math, pyproj, read_ifc, set_crs):
    # PDOK's 3D Tiles stand at ellipsoidal heights, which take the NSGI grids: without them
    # PROJ passes NAP heights off as ellipsoidal ones (bimpolars warns) and the 3D BAG floats
    # 44 m above the map. With the network on, PROJ fetches them from cdn.proj.org
    pyproj.network.set_network_enabled(True)

    # The bimpolars test data: fetch downloads it from the bimpolars bucket on first use, or
    # finds it in BIMPOLARS_DATA_DIR. The IFC is not georeferenced; IFC-GeoReferencer's
    # export of the architectural model gives the numbers
    bdf = read_ifc(data.fetch("sixty5_O-S1-CON-structural-engineering.ifc"))
    crs = derived_engineering_crs(
        "EPSG:7415",
        easting=160_071.5,
        northing=384_156.5,
        orthometric_height=18.625,
        rotation=math.degrees(math.atan2(-0.7700680491484481, 0.6379617540893054)),
        unit=linear_unit(bdf.crs),
        name="Sixty5",
    )
    site = set_crs(bdf, crs)
    site
    return (site,)


@app.cell
def _(bag_panden_under, pl, simple_features, site):
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
    list(panden)
    return (panden,)


@app.cell
def _(osm_ground_map, panden, pdok_3d_buildings, site):
    # 150 m of map around the model, and the 3D BAG over the same area without Sixty5's pand
    ground_map = osm_ground_map(site)
    tilesets = [pdok_3d_buildings(site, ground_map["bounds"], hide_within=panden.values())]
    return ground_map, tilesets


@app.cell
def _(GeoSpeckleViewer, Marker, ground_map, mo, site, tilesets):
    viewer = mo.ui.anywidget(
        GeoSpeckleViewer(
            site,
            ground_map=ground_map,
            tilesets=tilesets,
            markers=[Marker("site origin", (0, 0, 0), size=10)],
            height=600,
        )
    )
    viewer
    return (viewer,)


@app.cell
def _(pl):
    def drawn(bdf):
        """The rows the viewer draws: those with a mesh, except the openings."""
        return bdf.frame.filter(
            pl.col("mesh").is_not_null()
            & (pl.col("class").cast(pl.String) != "IfcOpeningElement").fill_null(True)
        )

    def frame_bbox(bdf):
        """The drawn rows' bbox in metres, as the viewer reports its scene's."""
        bbox = drawn(bdf).select(pl.col("bbox").struct.unnest())
        corners = bbox.select(
            *(pl.col(c).min() for c in ("xmin", "ymin", "zmin")),
            *(pl.col(c).max() for c in ("xmax", "ymax", "zmax")),
        ).row(0)
        # read_ifc keeps the model's millimetres
        return [corner / 1000 for corner in corners]

    return drawn, frame_bbox


@app.cell
def _(drawn, frame_bbox, html, json, mo, panden, shapely, site, tilesets, viewer):
    # Reruns whenever the viewer reports: after each load, as the tiles come in, and on each
    # selection
    count, bbox = viewer.widget.object_count, viewer.widget.scene_bbox
    surroundings = viewer.widget.surroundings
    # The panden in the viewer's world: metres
    panden_bbox = (
        [b / 1000 for b in shapely.union_all(list(panden.values())).bounds] if panden else []
    )
    # The data attributes are what the headless test (e2e/geo.test.mjs) reads
    attributes = {
        "id": "geo-report",
        "data-object-count": count,
        "data-scene-bbox": json.dumps(bbox),
        "data-drawn-rows": len(drawn(site)),
        "data-frame-bbox": json.dumps(frame_bbox(site)),
        "data-panden": json.dumps(list(panden)),
        "data-panden-bbox": json.dumps(panden_bbox),
        "data-surroundings": json.dumps(surroundings),
        "data-leaves": len(tilesets[0]["tileset"]["root"]["children"]),
    }
    _text = " ".join(f"{name}='{html.escape(str(value))}'" for name, value in attributes.items())
    mo.Html(
        f"<p {_text}>Sixty5: {count:,} elements drawn of {len(drawn(site)):,} rows with a mesh. "
        f"The 3D BAG: {surroundings['tiles']} tiles in, {surroundings['hidden_features']} "
        f"buildings left out for BAG pand {', '.join(panden) or 'none'}.</p>"
    )
    return


@app.cell
def _(html, json, mo, pl, site, viewer):
    # A click reports the elements' applicationIds: the rows' ids
    _ids = [element["applicationId"] for element in viewer.widget.selected]
    _rows = site.frame.filter(pl.col("id").is_in(_ids)).drop("mesh", "bbox", "native_geom")
    # data-ids is what the headless test reads
    mo.vstack(
        [
            mo.Html(
                f"<p id='geo-selected' data-ids='{html.escape(json.dumps(_ids))}'>"
                f"<b>Selected:</b> {len(_ids)}</p>"
            ),
            _rows,
        ]
    ) if _ids else None
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell
def _():
    import html
    import json

    import marimo as mo
    import polars as pl
    from bimpolars import data, read_ifc, read_speckle, version_objects

    from specklewidgets import SpeckleViewer

    return SpeckleViewer, data, html, json, mo, pl, read_ifc, read_speckle, version_objects


@app.cell
def _(mo):
    mo.md(r"""
    # The Revit Advanced Sample's architecture as BimDataFrames

    The architectural model of Autodesk's Revit Advanced Sample Project twice, as
    [bimpolars](https://github.com/bedrock-engineer/bimpolars) reads it: on the left the
    Speckle version with its bundle (`read_speckle`), on the right the IFC export
    (`read_ifc`). `SpeckleViewer` turns each BimDataFrame into Speckle objects, one element per
    row with a mesh, coloured by the model's own materials or by a column. Click an element to
    read its row back below the viewers. The IFC export sits 9.2 m east and 22.6 m north of
    the Speckle model, which is placed at Revit's project base point.
    """)
    return


@app.cell
def _(data, read_speckle, version_objects):
    # The bimpolars test data: fetch downloads it from the bimpolars bucket on first use, or
    # finds it in BIMPOLARS_DATA_DIR
    arch = data.RVT_SPECKLE_ARCH
    speckle_objects = version_objects(data.fetch(data.RVT_SPECKLE_V3_OBJECTS), arch.version_id)
    speckle_bdf = read_speckle(speckle_objects, data.fetch_bundle(arch.bundle))
    speckle_bdf
    return (speckle_bdf,)


@app.cell
def _(data, read_ifc):
    # 45 s: ifcopenshell tessellates every element
    ifc_bdf = read_ifc(data.fetch("rvt-advanced-sample-arch.ifc"))
    ifc_bdf
    return (ifc_bdf,)


@app.cell
def _(mo):
    colours = {"their materials": None, "class": "class", "level": "container"}
    speckle_color = mo.ui.dropdown(colours, value="their materials", label="Colour by")
    ifc_color = mo.ui.dropdown(colours, value="class", label="Colour by")
    return ifc_color, speckle_color


@app.cell
def _(SpeckleViewer, mo, speckle_bdf, speckle_color):
    speckle_viewer = mo.ui.anywidget(
        SpeckleViewer(speckle_bdf, color=speckle_color.value, height=500)
    )
    return (speckle_viewer,)


@app.cell
def _(SpeckleViewer, ifc_bdf, ifc_color, mo):
    ifc_viewer = mo.ui.anywidget(SpeckleViewer(ifc_bdf, color=ifc_color.value, height=500))
    return (ifc_viewer,)


@app.cell
def _(ifc_color, ifc_viewer, mo, speckle_color, speckle_viewer):
    mo.hstack(
        [
            mo.vstack([mo.md("**read_speckle**"), speckle_color, speckle_viewer]),
            mo.vstack([mo.md("**read_ifc**"), ifc_color, ifc_viewer]),
        ],
        widths="equal",
    )
    return


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
        # read_speckle and read_ifc keep the models' millimetres
        return [corner / 1000 for corner in corners]

    return drawn, frame_bbox


@app.cell
def _(drawn, frame_bbox, html, ifc_bdf, ifc_viewer, json, mo, speckle_bdf, speckle_viewer):
    def report(key, viewer, bdf):
        # Reruns whenever the viewer reports: after each load, and on each selection
        count, bbox = viewer.widget.object_count, viewer.widget.scene_bbox
        corners = zip("xyz", bbox[:3], bbox[3:], strict=True) if bbox else []
        extent = ", ".join(f"{axis} {lo:.1f} to {hi:.1f}" for axis, lo, hi in corners)
        # The data attributes are what the headless test (e2e/bimdataframe.test.mjs) reads
        attributes = {
            "id": f"{key}-report",
            "data-object-count": count,
            "data-scene-bbox": json.dumps(bbox),
            "data-drawn-rows": len(drawn(bdf)),
            "data-frame-bbox": json.dumps(frame_bbox(bdf)),
        }
        text = " ".join(f"{name}='{html.escape(str(value))}'" for name, value in attributes.items())
        return mo.Html(
            f"<p {text}>{key}: {count:,} elements drawn of {len(drawn(bdf)):,} rows with a "
            f"mesh; the scene spans {extent or 'nothing'} m.</p>"
        )

    mo.vstack([report("speckle", speckle_viewer, speckle_bdf), report("ifc", ifc_viewer, ifc_bdf)])
    return


@app.cell
def _(html, ifc_bdf, ifc_viewer, json, mo, pl, speckle_bdf, speckle_viewer):
    def selected_rows(key, viewer, bdf):
        # A click reports the elements' applicationIds: the rows' ids
        ids = [element["applicationId"] for element in viewer.widget.selected]
        if not ids:
            return None
        rows = bdf.frame.filter(pl.col("id").is_in(ids)).drop("mesh", "bbox", "native_geom")
        # data-ids is what the headless test reads
        return mo.vstack(
            [
                mo.Html(
                    f"<p id='{key}-selected' data-ids='{html.escape(json.dumps(ids))}'>"
                    f"<b>Selected in the {key} viewer:</b> {len(ids)}</p>"
                ),
                rows,
            ]
        )

    selections = [
        selected_rows("speckle", speckle_viewer, speckle_bdf),
        selected_rows("ifc", ifc_viewer, ifc_bdf),
    ]
    mo.vstack([selection for selection in selections if selection is not None])
    return


if __name__ == "__main__":
    app.run()

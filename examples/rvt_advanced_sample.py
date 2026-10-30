import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell
def _():
    import html
    import json

    import marimo as mo
    from bimpolars import data
    from bimpolars.speckle import version_objects

    from specklewidgets import Marker, SpeckleViewer

    return Marker, SpeckleViewer, data, html, json, mo, version_objects


@app.cell
def _(mo):
    mo.md(r"""
    # Revit Advanced Sample Project in Speckle's viewer

    The architectural, structural and MEP models of Autodesk's Revit Advanced Sample Project,
    as Speckle v3 objects (the bimpolars test data), in one `SpeckleViewer`: no Speckle server,
    the objects go straight to the browser. Click an element to select it, shift-click to add
    to the selection. The axes mark the project base point, the origin of all three models.
    """)
    return


@app.cell
def _(data, version_objects):
    # One Parquet file holds the v3 objects of the three versions; fetch downloads it from the
    # bimpolars bucket on first use, or finds it in BIMPOLARS_DATA_DIR
    objects = data.fetch(data.RVT_SPECKLE_V3_OBJECTS)
    models = [
        version_objects(objects, version.version_id)
        for version in (data.RVT_SPECKLE_ARCH, data.RVT_SPECKLE_STR, data.RVT_SPECKLE_MEP)
    ]
    [len(model) for model in models]
    return (models,)


@app.cell
def _(Marker, SpeckleViewer, mo, models):
    viewer = mo.ui.anywidget(
        SpeckleViewer(
            models, height=600, markers=[Marker("project base point", (0, 0, 0), size=10)]
        )
    )
    viewer
    return (viewer,)


@app.cell
def _(json, mo, viewer):
    # Reruns whenever the viewer reports: after each load, and on each selection
    count, bbox = viewer.widget.object_count, viewer.widget.scene_bbox
    corners = zip("xyz", bbox[:3], bbox[3:], strict=True) if bbox else []
    extent = ", ".join(f"{axis} {lo:.1f} to {hi:.1f}" for axis, lo, hi in corners) or "nothing"
    # The data attributes are what the headless test (e2e/notebook.test.mjs) reads
    mo.Html(
        f"<p id='viewer-report' data-object-count='{count}' data-scene-bbox='{json.dumps(bbox)}'>"
        f"{count:,} elements drawn; the scene spans {extent} m.</p>"
    )
    return


@app.cell
def _(html, json, mo, viewer):
    selected = viewer.widget.selected
    # data-selected is what the headless test reads
    mo.vstack(
        [
            mo.Html(
                f"<p id='viewer-selected' data-selected='{html.escape(json.dumps(selected))}'>"
                f"<b>Selected:</b> {len(selected)}</p>"
            ),
            mo.tree(selected),
        ]
    ) if selected else None
    return


if __name__ == "__main__":
    app.run()

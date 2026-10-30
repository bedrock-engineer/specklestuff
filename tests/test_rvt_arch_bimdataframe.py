"""The Revit Advanced Sample's architectural model as BimDataFrames, as the viewer receives them.

read_speckle (the Speckle version with its bundle) and read_ifc (the IFC export) each give a
BimDataFrame; the intake turns its rows into v3 objects. The numbers here are the ones the
headless test (e2e/bimdataframe.test.mjs) expects the viewer to report for each: one element
per row with a mesh (openings left out), and the frame's bbox in metres.
"""

from typing import Any

import pytest

from speckle_objects import drawn_elements, mesh_bbox, unpack
from specklewidgets import models_gz

# bimpolars (and polars with it) is a dev dependency
data = pytest.importorskip("bimpolars.data")
bimpolars = pytest.importorskip("bimpolars")
bim = pytest.importorskip("specklewidgets.bim")
gltf = pytest.importorskip("bimpolars.gltf")
pl = pytest.importorskip("polars")

DRAWN_ROWS = {"speckle": 5568, "ifc": 5512}
"""Rows with a mesh, except the IFC's 135 openings: the elements the viewer draws."""

FRAME_BBOX = {
    "speckle": (-116.6763, -76.0339, -1.8288, 202.3891, 75.7287, 12.5745),
    "ifc": (-107.4743, -53.3989, -1.8288, 211.5911, 98.3638, 12.4854),
}
"""The drawn rows' xmin, ymin, zmin, xmax, ymax, zmax in metres, to 0.1 mm. The IFC export sits
9.2 m east and 22.6 m north of the Speckle model (bimpolars' docs/agents/test-data.md)."""


@pytest.fixture(scope="module")
def frames() -> dict[str, Any]:
    arch = data.RVT_SPECKLE_ARCH
    objects = bimpolars.version_objects(data.fetch(data.RVT_SPECKLE_V3_OBJECTS), arch.version_id)
    return {
        "speckle": bimpolars.read_speckle(objects, data.fetch_bundle(arch.bundle)),
        # 45 s
        "ifc": bimpolars.read_ifc(data.fetch("rvt-advanced-sample-arch.ifc")),
    }


@pytest.fixture(scope="module")
def packed(frames) -> dict[str, list[dict[str, Any]]]:
    models = [bim.bim_objects(frames["speckle"]), bim.bim_objects(frames["ifc"], color="class")]
    return dict(zip(frames, unpack(models_gz(*models)), strict=True))


def drawn(frame: Any) -> Any:
    return frame.filter(
        pl.col("mesh").is_not_null()
        & ~pl.col("class").cast(pl.String).is_in(gltf.EXCLUDED_CLASSES).fill_null(False)
    )


@pytest.mark.parametrize("name", DRAWN_ROWS)
def test_every_drawn_row_is_one_element(frames, packed, name):
    assert len(drawn(frames[name].frame)) == DRAWN_ROWS[name]
    assert drawn_elements(packed[name]) == DRAWN_ROWS[name]


@pytest.mark.parametrize("name", DRAWN_ROWS)
def test_the_meshes_span_the_frames_bbox(frames, packed, name):
    bbox = drawn(frames[name].frame).select(pl.col("bbox").struct.unnest())
    corners = bbox.select(
        *(pl.col(c).min() for c in ("xmin", "ymin", "zmin")),
        *(pl.col(c).max() for c in ("xmax", "ymax", "zmax")),
    ).row(0)
    # the frames keep the models' millimetres; the viewer works in metres, as mesh_bbox does
    metres = [c * frames[name].crs.axis_info[0].unit_conversion_factor for c in corners]
    assert metres == pytest.approx(FRAME_BBOX[name], abs=1e-4)
    assert mesh_bbox(packed[name]) == pytest.approx(metres, abs=1e-9)


def test_the_ifc_is_coloured_by_class(packed):
    proxies = packed["ifc"][0]["renderMaterialProxies"]
    names = [proxy["value"]["name"] for proxy in proxies]
    assert "class: IfcMember" in names
    assert sum(len(proxy["objects"]) for proxy in proxies) == DRAWN_ROWS["ifc"]


def test_the_speckle_model_keeps_its_styles(frames, packed):
    styles = drawn(frames["speckle"].frame).select(
        pl.col("mesh").struct.field("styles").explode().struct.field("name").drop_nulls().unique()
    )
    proxies = packed["speckle"][0]["renderMaterialProxies"]
    assert sorted({proxy["value"]["name"] for proxy in proxies}) == sorted(styles.to_series())

"""The BimDataFrame intake: rows to v3 objects, styles and a column to render materials."""

import math
from typing import Any

import pytest

from speckle_objects import unpack
from specklewidgets import SpeckleViewer, models_gz

# The intake needs bimpolars, a dev dependency
bimpolars = pytest.importorskip("bimpolars")
bim = pytest.importorskip("specklewidgets.bim")
pl = pytest.importorskip("polars")
np = pytest.importorskip("numpy")
from bimpolars.mesh import Style, mesh_frame, styled_mesh  # noqa: E402
from bimpolars.speckle import read_speckle  # noqa: E402

CONCRETE = Style("Concrete", (0.5, 0.5, 0.5, 1.0))
GLASS = Style("Glass", (0.2, 0.6, 0.8, 0.4))
UNSTYLED = Style(None, (0.7, 0.7, 0.7, 1.0))

# A unit cube's corners and its twelve triangles: two per side, the top two first
CUBE_VERTICES = [(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)]
CUBE_FACES = [
    *((4, 5, 6), (5, 7, 6)),
    *((0, 2, 1), (1, 2, 3), (0, 1, 4), (1, 5, 4), (2, 6, 3), (3, 6, 7)),
    *((0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)),
]


def cube(origin: tuple[float, float, float], styles: list[Style]) -> Any:
    """A unit cube at an origin, its top in the first style and the rest in the last."""
    vertices = np.array(CUBE_VERTICES, dtype=float) + origin
    style_ids = [0, 0] + [len(styles) - 1] * 10
    return styled_mesh(vertices, np.array(CUBE_FACES), np.array(style_ids), styles)


def bim_model(unit: str | bimpolars.LinearUnit = "millimetre") -> Any:
    """Five rows: a wall with two styles, a window, an unstyled slab, an opening and a storey.

    The opening (the void the window fills) and the storey (no geometry) are not drawn.
    """
    meshes = mesh_frame(
        [
            cube((0, 0, 0), [CONCRETE, GLASS]),
            cube((2000, 0, 0), [GLASS]),
            cube((0, 3000, 0), [UNSTYLED]),
            cube((2000, 0, 0), [UNSTYLED]),
        ]
    )
    properties = pl.Series(
        "properties",
        [
            {
                "Pset_WallCommon": {"IsExternal": True, "FireRating": None},
                "properties.Parameters.Dimensions": {"Volume": 1.5, "Area": None},
                "object": {"family": "Basic Wall"},
            },
            {"Pset_WallCommon": None, "properties.Parameters.Dimensions": {"Volume": 0.1}},
            {"Pset_WallCommon": {"IsExternal": False, "FireRating": "60"}},
            None,
            None,
        ],
    )
    frame = pl.DataFrame(
        {
            "id": ["wall", "window", "slab", "opening", "storey"],
            "name": ["Wall", None, "Slab", "Opening", "Level 0"],
            "class": pl.Series(
                ["IfcWall", "IfcWindow", "IfcSlab", "IfcOpeningElement", "IfcBuildingStorey"],
                dtype=pl.Categorical,
            ),
            "properties": properties,
            "container": ["storey", "storey", "storey", "storey", None],
            "elevation": [None, None, None, None, 0.0],
            "native_geom": pl.Series([None] * 5, dtype=pl.Binary),
            "mesh": pl.concat([meshes["mesh"], pl.Series("mesh", [None], meshes["mesh"].dtype)]),
            "bbox": pl.concat([meshes["bbox"], pl.Series("bbox", [None], meshes["bbox"].dtype)]),
            "footprint": pl.Series([b"\x01"] * 5, dtype=pl.Binary),
            "fire_compartment": ["A", "A", "B", None, None],
        }
    )
    return bimpolars.BimDataFrame(frame, bimpolars.engineering_crs("Test", unit=unit))


def data_objects(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {o["applicationId"]: o for o in objects if o["speckle_type"].endswith("DataObject")}


def meshes_of(objects: list[dict[str, Any]], element: dict[str, Any]) -> list[dict[str, Any]]:
    """The element's meshes, with their DataChunks' data inline."""
    by_id = {o["id"]: o for o in objects}

    def resolved(values: list[Any]) -> list[Any]:
        return [
            x
            for v in values
            for x in (by_id[v["referencedId"]]["data"] if "referencedId" in v else [v])
        ]

    meshes = [by_id[ref["referencedId"]] for ref in element["displayValue"]]
    return [
        {**m, "vertices": resolved(m["vertices"]), "faces": resolved(m["faces"])} for m in meshes
    ]


def materials(objects: list[dict[str, Any]]) -> dict[str, tuple[dict[str, Any], list[str]]]:
    return {
        p["value"]["name"]: (p["value"], p["objects"]) for p in objects[0]["renderMaterialProxies"]
    }


@pytest.fixture
def bdf() -> Any:
    return bim_model()


def test_one_data_object_per_drawn_row(bdf):
    objects = bim.bim_objects(bdf)
    assert sorted(data_objects(objects)) == ["slab", "wall", "window"]


def test_the_root_comes_first_and_lists_every_object(bdf):
    objects = bim.bim_objects(bdf)
    root = objects[0]
    assert root["speckle_type"].endswith("Collection")
    assert set(root["__closure"]) == {o["id"] for o in objects[1:]}


def test_one_collection_per_class(bdf):
    objects = bim.bim_objects(bdf)
    by_id = {o["id"]: o for o in objects}
    collections = [by_id[ref["referencedId"]] for ref in objects[0]["elements"]]
    assert [c["name"] for c in collections] == ["IfcSlab", "IfcWall", "IfcWindow"]


def test_an_element_carries_its_row(bdf):
    wall = data_objects(bim.bim_objects(bdf))["wall"]
    assert wall["name"] == "Wall"
    assert wall["category"] == "IfcWall"
    assert wall["container"] == "storey"
    assert wall["fire_compartment"] == "A"
    # each property set at the path its name gives, without the nulls
    assert wall["Pset_WallCommon"] == {"IsExternal": True}
    assert wall["properties"] == {"Parameters": {"Dimensions": {"Volume": 1.5}}}
    assert wall["family"] == "Basic Wall"
    # no geometry columns, no nulls
    for field in ("mesh", "bbox", "native_geom", "footprint", "elevation"):
        assert field not in wall


def test_an_element_without_a_name_is_named_by_its_id(bdf):
    window = data_objects(bim.bim_objects(bdf))["window"]
    assert window["name"] == "window"
    assert "Pset_WallCommon" not in window


def test_a_column_named_like_a_data_object_field_goes_into_properties(bdf):
    frame = bdf.frame.with_columns(units=pl.lit("pcs"), **{"a/b": pl.lit(1)})
    wall = data_objects(bim.bim_objects(bdf.with_frame(frame)))["wall"]
    assert "units" not in wall
    assert wall["properties"]["units"] == "pcs"
    assert wall["properties"]["a/b"] == 1


def test_a_mesh_per_style(bdf):
    objects = bim.bim_objects(bdf)
    wall = data_objects(objects)["wall"]
    top, sides = meshes_of(objects, wall)
    assert (top["applicationId"], sides["applicationId"]) == ("wall/0", "wall/1")
    assert top["units"] == sides["units"] == "mm"
    # the top's two triangles on the top's four corners, renumbered
    assert top["faces"] == [3, 0, 1, 2, 3, 1, 3, 2]
    assert sorted(top["vertices"][2::3]) == [1.0] * 4
    assert len(sides["vertices"]) == 3 * 8
    assert sides["faces"][::4] == [3] * 10


def test_a_style_becomes_a_render_material_of_its_meshes(bdf):
    by_name = materials(bim.bim_objects(bdf))
    assert set(by_name) == {"Concrete", "Glass"}
    concrete, targets = by_name["Concrete"]
    assert targets == ["wall/0"]
    assert concrete["diffuse"] == (0xFF808080 - (1 << 32))
    glass, targets = by_name["Glass"]
    assert targets == ["wall/1", "window/0"]
    assert glass["opacity"] == pytest.approx(0.4)
    assert (glass["roughness"], glass["metalness"]) == (1.0, 0.0)


def test_unstyled_faces_get_no_material(bdf):
    objects = bim.bim_objects(bdf)
    targeted = {target for _, targets in materials(objects).values() for target in targets}
    assert "slab/0" not in targeted


def test_read_speckle_reads_the_drawn_rows_back(bdf):
    back = read_speckle(bim.bim_objects(bdf))
    drawn = bdf.frame.filter(pl.col("id").is_in(["wall", "window", "slab"]))
    joined = drawn.join(back.frame, on="id", suffix="_back")
    assert len(back) == len(joined) == 3
    assert back.crs.axis_info[0].unit_name == "millimetre"
    assert (
        joined["class"].cast(pl.String).to_list() == joined["class_back"].cast(pl.String).to_list()
    )
    assert joined["bbox"].to_list() == joined["bbox_back"].to_list()
    for styles, back_styles in zip(
        joined["mesh"].struct.field("styles"),
        joined["mesh_back"].struct.field("styles"),
        strict=True,
    ):
        assert [(s["name"], s["face_count"]) for s in styles] == [
            (s["name"], s["face_count"]) for s in back_styles
        ]
        # Speckle's ARGB colours have 8 bits a channel
        for style, back_style in zip(styles, back_styles, strict=True):
            assert back_style["rgba"] == pytest.approx(style["rgba"], abs=1 / 255)
    wall = back.frame.filter(id="wall")["properties"].struct.unnest().row(0, named=True)
    assert wall["Pset_WallCommon"] == {"IsExternal": True, "FireRating": None}
    assert wall["properties.Parameters.Dimensions"] == {"Volume": 1.5}


def test_a_unit_speckle_does_not_know_becomes_metres():
    us_foot = bimpolars.LinearUnit("US survey foot", 1200 / 3937)
    objects = bim.bim_objects(bim_model(us_foot))
    wall = data_objects(objects)["wall"]
    top, _ = meshes_of(objects, wall)
    assert top["units"] == objects[0]["units"] == "m"
    assert max(top["vertices"]) == pytest.approx(1200 / 3937)


def test_color_by_a_column_colours_the_elements(bdf):
    objects = bim.bim_objects(bdf, color="fire_compartment")
    by_name = materials(objects)
    assert set(by_name) == {"fire_compartment: A", "fire_compartment: B"}
    a, targets = by_name["fire_compartment: A"]
    assert targets == ["wall", "window"]
    # the most common value takes the first colour
    assert a["diffuse"] == bim._argb(bim.CATEGORICAL_RGB[0])
    assert by_name["fire_compartment: B"][0]["diffuse"] == bim._argb(bim.CATEGORICAL_RGB[1])
    # one mesh per element, styles or not
    wall = data_objects(objects)["wall"]
    assert len(wall["displayValue"]) == 1
    assert len(meshes_of(objects, wall)[0]["faces"]) == 4 * 12


def test_color_past_eight_values_and_nulls_are_grey(bdf):
    values = [*"abcdefghij", None]
    frame = pl.concat([bdf.frame.head(1)] * len(values)).with_columns(
        id=pl.Series([f"wall-{i}" for i in range(len(values))]), kind=pl.Series(values)
    )
    by_name = materials(bim.bim_objects(bdf.with_frame(frame), color="kind"))
    assert [
        name for name in by_name if by_name[name][0]["diffuse"] == bim._argb(bim.OTHER_RGB)
    ] == [
        "kind: other",
        "kind: no value",
    ]
    assert len(by_name["kind: other"][1]) == 2
    assert len(by_name) == 8 + 2


def test_color_by_a_number_in_ten_steps(bdf):
    volumes = [0.0, 1.0, 2.5, 9.99, 10.0, None, float("nan")]
    frame = pl.concat([bdf.frame.head(1)] * len(volumes)).with_columns(
        id=pl.Series([f"wall-{i}" for i in range(len(volumes))]), volume=pl.Series(volumes)
    )
    by_name = materials(bim.bim_objects(bdf.with_frame(frame), color="volume"))
    assert {name: targets for name, (_, targets) in by_name.items()} == {
        "volume: 0 to 1": ["wall-0"],
        "volume: 1 to 2": ["wall-1"],
        "volume: 2 to 3": ["wall-2"],
        "volume: 9 to 10": ["wall-3", "wall-4"],
        "volume: no value": ["wall-5", "wall-6"],
    }
    assert by_name["volume: 0 to 1"][0]["diffuse"] == bim._argb(bim.SEQUENTIAL_RGB[0])
    assert by_name["volume: 9 to 10"][0]["diffuse"] == bim._argb(bim.SEQUENTIAL_RGB[-1])


def test_color_by_a_column_named_rows_or_value(bdf):
    frame = bdf.frame.with_columns(rows=pl.col("fire_compartment"), value=pl.col("class"))
    for column in ("rows", "value"):
        assert len(materials(bim.bim_objects(bdf.with_frame(frame), color=column))) == 2 + (
            column == "value"
        )


def test_color_by_a_constant_number_is_one_colour(bdf):
    frame = bdf.frame.with_columns(level=pl.lit(3))
    by_name = materials(bim.bim_objects(bdf.with_frame(frame), color="level"))
    assert list(by_name) == ["level: 3 to 3"]


def test_color_by_an_expression(bdf):
    external = pl.col("properties").struct.field("Pset_WallCommon").struct.field("IsExternal")
    by_name = materials(bim.bim_objects(bdf, color=external))
    assert {name: targets for name, (_, targets) in by_name.items()} == {
        "IsExternal: true": ["wall"],
        "IsExternal: false": ["slab"],
        "IsExternal: no value": ["window"],
    }


def test_color_by_a_nested_column_raises(bdf):
    with pytest.raises(TypeError, match="scalar"):
        bim.bim_objects(bdf, color="properties")


def test_rows_need_ids_of_their_own(bdf):
    frame = bdf.frame.with_columns(
        id=pl.when(pl.col("id") == "window").then(pl.lit("wall")).otherwise("id")
    )
    with pytest.raises(ValueError, match="id of its own"):
        bim.bim_objects(bdf.with_frame(frame))


def test_non_finite_values_are_left_out(bdf):
    frame = bdf.frame.with_columns(ratio=pl.Series([math.inf, float("nan"), 1.0, None, None]))
    elements = data_objects(bim.bim_objects(bdf.with_frame(frame)))
    assert "ratio" not in elements["wall"]
    assert "ratio" not in elements["window"]
    assert elements["slab"]["ratio"] == 1.0


def test_the_viewer_takes_a_bimdataframe(bdf):
    viewer = SpeckleViewer(bdf, color="class")
    assert unpack(viewer.objects_gz) == unpack(models_gz(bim.bim_objects(bdf, color="class")))


def test_the_viewer_takes_bimdataframes_and_speckle_models(bdf, model):
    viewer = SpeckleViewer([bdf, model])
    packed = unpack(viewer.objects_gz)
    assert [m[0]["id"] for m in packed] == [bim.bim_objects(bdf)[0]["id"], model[0]["id"]]


def test_color_needs_a_bimdataframe(model):
    with pytest.raises(ValueError, match="BimDataFrames"):
        SpeckleViewer(model, color="class")
    with pytest.raises(ValueError, match="BimDataFrames"):
        SpeckleViewer(color="class")

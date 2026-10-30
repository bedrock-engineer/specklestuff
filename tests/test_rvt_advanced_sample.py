"""The Revit Advanced Sample models as the viewer receives them, read with bimpolars.

The element counts and the bounding box here are the ones the headless test
(e2e/notebook.test.mjs) expects the viewer to report: this traversal and bimpolars'
read_speckle reach them independently of the viewer.
"""

from collections.abc import Iterator, Mapping
from typing import Any

import pytest

from speckle_objects import unpack
from specklewidgets import models_gz

# bimpolars (and polars with it) is a dev dependency, not in the minimal test group
data = pytest.importorskip("bimpolars.data")
speckle = pytest.importorskip("bimpolars.speckle")
pl = pytest.importorskip("polars")

DRAWN_ELEMENTS = {"arch": 5686, "str": 918, "mep": 6942}
"""Per model: elements with geometry plus instances whose definition has geometry."""

SCENE_BBOX = (-116.6763, -121.7323, -7.2, 202.3891, 75.7287, 15.2066)
"""The three models' xmin, ymin, zmin, xmax, ymax, zmax in metres, to 0.1 mm."""

VERSIONS = {"arch": data.RVT_SPECKLE_ARCH, "str": data.RVT_SPECKLE_STR, "mep": data.RVT_SPECKLE_MEP}


@pytest.fixture(scope="module")
def models() -> list[list[dict[str, Any]]]:
    objects = data.fetch(data.RVT_SPECKLE_V3_OBJECTS)
    return [speckle.version_objects(objects, v.version_id) for v in VERSIONS.values()]


@pytest.fixture(scope="module")
def packed(models) -> dict[str, list[dict[str, Any]]]:
    return dict(zip(VERSIONS, unpack(models_gz(*models)), strict=True))


def children(obj: Mapping[str, Any], by_id: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    for field in ("elements", "displayValue"):
        for child in obj.get(field) or []:
            yield by_id[child["referencedId"]] if "referencedId" in child else child


def drawn_elements(objects: list[dict[str, Any]]) -> int:
    """What a click can select: every object with a displayValue that draws a mesh, and every
    instance whose definition draws one. A definition's members draw only where an instance
    places them."""
    by_id = {obj["id"]: obj for obj in objects}
    by_application_id = {obj["applicationId"]: obj for obj in objects if "applicationId" in obj}
    definitions = {d["applicationId"]: d for d in objects[0].get("instanceDefinitionProxies", [])}
    members = {member for d in definitions.values() for member in d["objects"]}

    def placed(obj: dict[str, Any]) -> Iterator[dict[str, Any]]:
        if obj["speckle_type"].endswith("InstanceProxy"):
            yield from (by_application_id[m] for m in definitions[obj["definitionId"]]["objects"])
        else:
            yield from (c for c in children(obj, by_id) if c.get("applicationId") not in members)

    def draws(obj: dict[str, Any]) -> bool:
        if obj["speckle_type"].endswith("Mesh"):
            return bool(obj.get("vertices"))
        return any(draws(child) for child in placed(obj))

    count = 0
    stack = [objects[0]]
    while stack:
        obj = stack.pop()
        is_instance = obj["speckle_type"].endswith("InstanceProxy")
        if (is_instance or obj.get("displayValue")) and draws(obj):
            count += 1
        if not is_instance:
            stack.extend(placed(obj))
    return count


@pytest.mark.parametrize("name", VERSIONS)
def test_every_element_is_drawn_once(packed, name):
    assert drawn_elements(packed[name]) == DRAWN_ELEMENTS[name]


@pytest.mark.parametrize("name", VERSIONS)
def test_each_member_id_names_one_object(packed, name):
    objects = packed[name]
    members = [m for d in objects[0]["instanceDefinitionProxies"] for m in d["objects"]]
    carriers = [obj["applicationId"] for obj in objects if obj.get("applicationId") in members]
    assert sorted(carriers) == sorted(set(members))


@pytest.mark.parametrize("name", VERSIONS)
def test_collections_list_each_object_once(packed, name):
    for obj in packed[name]:
        listed = [e["referencedId"] for e in obj.get("elements") or [] if "referencedId" in e]
        assert len(listed) == len(set(listed))


def test_definitions_are_apart_across_models(packed):
    ids = [d["applicationId"] for m in packed.values() for d in m[0]["instanceDefinitionProxies"]]
    assert len(ids) == len(set(ids)) == 765 + 868 + 956


def test_the_scene_bbox_is_the_union_of_the_bimdataframes(models):
    frames = [speckle.read_speckle(model).frame for model in models]
    bbox = pl.concat([frame.select(pl.col("bbox").struct.unnest()) for frame in frames])
    corners = bbox.select(
        *(pl.col(c).min() for c in ("xmin", "ymin", "zmin")),
        *(pl.col(c).max() for c in ("xmax", "ymax", "zmax")),
    ).row(0)
    # read_speckle keeps the models' millimetres; the viewer works in metres
    assert [c / 1000 for c in corners] == pytest.approx(SCENE_BBOX, abs=1e-4)

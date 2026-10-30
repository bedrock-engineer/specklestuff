"""models_gz, tested through what the viewer receives: the unpacked models."""

import copy
import json

import pytest

from speckle_objects import ref, revit_like, unpack
from specklewidgets import models_gz


def by_id(objects):
    return {obj["id"]: obj for obj in objects}


def test_definition_ids_get_the_root_id_as_prefix(model):
    [packed] = unpack(models_gz(model))
    root, objects = packed[0], by_id(packed)
    definition = root["instanceDefinitionProxies"][0]
    assert definition["applicationId"] == "root-a/def-1"
    assert definition["objects"] == ["root-a/def-geo-0"]
    assert objects["door"]["definitionId"] == "root-a/def-1"
    assert objects["door-mesh"]["applicationId"] == "root-a/def-geo-0"
    assert root["renderMaterialProxies"][0]["objects"] == ["root-a/def-geo-0", "wall-guid"]


def test_element_ids_and_content_hashes_stay(model):
    [packed] = unpack(models_gz(model))
    objects = by_id(packed)
    assert [obj["id"] for obj in packed] == [obj["id"] for obj in model]
    assert objects["door"]["applicationId"] == "door-guid"
    assert objects["wall"]["applicationId"] == "wall-guid"
    assert packed[0]["applicationId"] == "artifact-root"
    assert packed[0]["renderMaterialProxies"][0]["value"]["applicationId"] == "mat-7"


def test_models_keep_their_definitions_apart():
    packed = unpack(models_gz(revit_like("root-a"), revit_like("root-b")))
    assert [model[0]["instanceDefinitionProxies"][0]["applicationId"] for model in packed] == [
        "root-a/def-1",
        "root-b/def-1",
    ]
    assert [by_id(model)["door"]["definitionId"] for model in packed] == [
        "root-a/def-1",
        "root-b/def-1",
    ]


def test_a_member_id_stays_on_the_mesh_its_data_object_displays(model):
    [packed] = unpack(models_gz(model))
    objects = by_id(packed)
    assert "applicationId" not in objects["geometry"]
    assert objects["geometry"]["displayValue"] == [ref("door-mesh")]
    carriers = [obj["id"] for obj in packed if obj.get("applicationId") == "root-a/def-geo-0"]
    assert carriers == ["door-mesh"]


def test_a_collection_lists_each_object_once(model):
    [packed] = unpack(models_gz(model))
    assert [element["referencedId"] for element in packed[0]["elements"]] == [
        "wall",
        "door",
        "geometry",
    ]


def test_the_input_is_not_changed(model):
    before = copy.deepcopy(model)
    models_gz(model)
    assert model == before


def test_json_text_is_a_model(model):
    assert unpack(models_gz(json.dumps(model))) == unpack(models_gz(model))


def test_a_model_without_definitions_passes_unchanged():
    plain = [obj for obj in revit_like() if obj["id"] in {"root-a", "wall", "wall-mesh"}]
    plain[0] = {**plain[0], "elements": [{"referencedId": "wall", "speckle_type": "reference"}]}
    del plain[0]["instanceDefinitionProxies"]
    assert unpack(models_gz(plain)) == [plain]


def test_no_models_pack_to_an_empty_list():
    assert unpack(models_gz()) == []


@pytest.mark.parametrize(
    "model", [[], [{"speckle_type": "Base"}], ["not an object"]], ids=["empty", "no-id", "text"]
)
def test_a_model_needs_a_root_with_an_id(model):
    with pytest.raises(ValueError, match="model 0 has no root"):
        models_gz(model)


@pytest.mark.parametrize("model", [{"id": "root-a"}, '{"id": "root-a"}'], ids=["object", "text"])
def test_one_object_is_not_a_model(model):
    with pytest.raises(ValueError, match="model 0 has no root"):
        models_gz(model)


def test_a_model_cannot_load_twice(model):
    with pytest.raises(ValueError, match="model 1 repeats the root root-a"):
        models_gz(model, model)

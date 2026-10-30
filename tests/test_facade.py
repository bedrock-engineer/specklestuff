"""The SpeckleViewer constructor facade: Pythonic arguments in, JSON-flat traits out."""

import json

from speckle_objects import revit_like, unpack
from specklewidgets import Marker, SpeckleViewer, models_gz


def test_one_model_packs_into_objects_gz(model):
    assert unpack(SpeckleViewer(model).objects_gz) == unpack(models_gz(model))


def test_a_sequence_of_models_packs_them_all():
    viewer = SpeckleViewer([revit_like("root-a"), revit_like("root-b")])
    assert [model[0]["id"] for model in unpack(viewer.objects_gz)] == ["root-a", "root-b"]


def test_json_text_is_one_model(model):
    assert unpack(SpeckleViewer(json.dumps(model)).objects_gz) == unpack(models_gz(model))


def test_no_models_leave_the_viewer_empty():
    viewer = SpeckleViewer()
    assert viewer.objects_gz == b""
    assert viewer.object_count == 0
    assert viewer.scene_bbox == []


def test_markers_mix_dataclasses_and_dicts():
    viewer = SpeckleViewer(
        markers=[Marker("origin", (0.0, 0.0, 0.0)), {"name": "pile 1", "position": [1, 2, 3]}]
    )
    assert viewer.markers == [
        {"name": "origin", "position": [0.0, 0.0, 0.0], "size": 5.0},
        {"name": "pile 1", "position": [1, 2, 3]},
    ]


def test_traits_pass_through(model):
    packed = models_gz(model)
    viewer = SpeckleViewer(objects_gz=packed, height=600, aspect_ratio=2.0)
    assert (viewer.objects_gz, viewer.height, viewer.aspect_ratio) == (packed, 600, 2.0)


def test_the_height_follows_the_width_by_default():
    viewer = SpeckleViewer()
    assert viewer.height is None
    assert viewer.aspect_ratio == 16 / 9

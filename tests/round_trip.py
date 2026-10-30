"""What receiving and sending must give, for the offline and the live tests of the server module.

The test data are the Revit Advanced Sample versions in the bimpolars bucket, read through
``bimpolars.data.fetch`` (``BIMPOLARS_DATA_DIR`` or a download).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from bimpolars import BimDataFrame, data, read_speckle, version_objects
from bimpolars.gltf import EXCLUDED_CLASSES
from bimpolars.mesh import mesh_arrays


@dataclass(frozen=True)
class BucketVersion:
    """A Speckle version as the bimpolars bucket has it, and where it lives on Speckle."""

    server: str
    project_id: str
    model_id: str
    version_id: str
    objects: list[dict[str, Any]]
    bundle: Path
    frame: BimDataFrame


def bucket_version(version: data.SpeckleVersion) -> BucketVersion:
    """A version of the bucket's ``speckle-v3-objects.parquet``, with its bundle and frame."""
    source = data.fetch(data.RVT_SPECKLE_V3_OBJECTS)
    server, project_id = (
        pl.scan_parquet(source)
        .filter(pl.col("version_id") == version.version_id, pl.col("is_root"))
        .select("server", "project_id")
        .collect()
        .row(0)
    )
    objects = version_objects(source, version.version_id)
    bundle = data.fetch_bundle(version.bundle)
    return BucketVersion(
        server,
        project_id,
        version.model_id,
        version.version_id,
        objects,
        bundle,
        read_speckle(objects, bundle),
    )


def drawn(bdf: BimDataFrame) -> pl.DataFrame:
    """The rows the intake sends: with a mesh, except the excluded classes (openings)."""
    return bdf.frame.filter(
        pl.col("mesh").is_not_null(),
        ~pl.col("class").cast(pl.String).is_in(EXCLUDED_CLASSES).fill_null(False),
    )


def assert_kept(sent: BimDataFrame, received: BimDataFrame) -> None:
    """Asserts that the received frame has the sent frame's drawn rows: ids, classes, meshes.

    A mesh is kept when it has the same triangles, corner by corner, whatever the order of its
    vertices: the intake writes one Speckle mesh per style, which read_speckle merges again.
    Its styles keep their names and face counts, and their colours to Speckle's 8 bits.
    """
    assert received.projjson["coordinate_system"] == sent.projjson["coordinate_system"]
    before = drawn(sent).sort("id")
    after = received.frame.filter(pl.col("mesh").is_not_null()).sort("id")
    assert after["id"].to_list() == before["id"].to_list()
    assert after["class"].cast(pl.String).to_list() == before["class"].cast(pl.String).to_list()
    before_meshes, after_meshes = mesh_arrays(before["mesh"]), mesh_arrays(after["mesh"])
    for row in range(len(before)):
        assert _triangles(*after_meshes.row(row)) == _triangles(*before_meshes.row(row))
    for styles, back in zip(
        before["mesh"].struct.field("styles").to_list(),
        after["mesh"].struct.field("styles").to_list(),
        strict=True,
    ):
        assert sorted((s["name"] or "", s["face_count"]) for s in back) == sorted(
            (s["name"] or "", s["face_count"]) for s in styles
        )
        colours = {s["name"]: s["rgba"] for s in styles}
        for style in back:
            assert np.allclose(style["rgba"], colours[style["name"]], atol=1 / 255)


def _triangles(
    vertices: np.ndarray[Any, Any], faces: np.ndarray[Any, Any]
) -> list[tuple[float, ...]]:
    """A mesh's triangles as sorted tuples of their corners' coordinates."""
    corners = vertices[faces].reshape(-1, 9)
    return sorted(map(tuple, corners.tolist()))

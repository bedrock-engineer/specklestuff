"""Small Speckle models for the tests, and the unpacking of what the viewer receives."""

import gzip
import json
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

COLLECTION = "Speckle.Core.Models.Collections.Collection"
DATA_OBJECT = "Objects.Data.DataObject"
MESH = "Objects.Geometry.Mesh"
INSTANCE = "Speckle.Core.Models.Instances.InstanceProxy"
DEFINITION = "Speckle.Core.Models.Instances.InstanceDefinitionProxy"


def ref(object_id: str) -> dict[str, str]:
    return {"referencedId": object_id, "speckle_type": "reference"}


def revit_like(root_id: str = "root-a") -> list[dict[str, Any]]:
    """A model shaped like the v3 objects specklepy builds from a Revit bundle, root first.

    One wall with its own mesh, and a door: an instance of def-1, whose member def-geo-0 is a
    DataObject named geometry displaying a Mesh with the same applicationId. The root lists
    that DataObject twice, as those v3 objects do for some members.
    """
    return [
        {
            "id": root_id,
            "speckle_type": COLLECTION,
            "name": "Received model",
            "applicationId": "artifact-root",
            "elements": [ref("wall"), ref("door"), ref("geometry"), ref("geometry")],
            "instanceDefinitionProxies": [
                {"speckle_type": DEFINITION, "applicationId": "def-1", "objects": ["def-geo-0"]}
            ],
            "renderMaterialProxies": [
                {
                    "speckle_type": "Objects.Other.RenderMaterialProxy",
                    "applicationId": "mat-7",
                    "objects": ["def-geo-0", "wall-guid"],
                    "value": {"applicationId": "mat-7", "name": "Oak", "diffuse": -1},
                }
            ],
        },
        {
            "id": "wall",
            "speckle_type": DATA_OBJECT,
            "applicationId": "wall-guid",
            "name": "Basic Wall",
            "displayValue": [ref("wall-mesh")],
        },
        {
            "id": "wall-mesh",
            "speckle_type": MESH,
            "applicationId": "wall-mesh-guid",
            "vertices": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            "faces": [3, 0, 1, 2],
        },
        {
            "id": "door",
            "speckle_type": INSTANCE,
            "applicationId": "door-guid",
            "definitionId": "def-1",
            "transform": [1, 0, 0, 5, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "units": "mm",
        },
        {
            "id": "geometry",
            "speckle_type": DATA_OBJECT,
            "applicationId": "def-geo-0",
            "name": "geometry",
            "displayValue": [ref("door-mesh")],
        },
        {
            "id": "door-mesh",
            "speckle_type": MESH,
            "applicationId": "def-geo-0",
            "vertices": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 2.0],
            "faces": [3, 0, 1, 2],
        },
    ]


def unpack(objects_gz: bytes) -> list[list[dict[str, Any]]]:
    unpacked: list[list[dict[str, Any]]] = json.loads(gzip.decompress(objects_gz))
    return unpacked


def run_without(modules: Sequence[str], code: str) -> list[str]:
    """Runs Python code in a subprocess that cannot import ``modules``; the lines it prints.

    ``sys.modules[name] = None`` makes every import of the module raise ImportError, which is
    how the tests check that the core does without a dependency (as bimpolars' tests do).
    """
    blocked = "".join(f"sys.modules[{name!r}] = None\n" for name in modules)
    result = subprocess.run(
        [sys.executable, "-c", f"import sys\n{blocked}{code}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip().splitlines()


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


METRES_PER_UNIT = {"mm": 0.001, "cm": 0.01, "m": 1.0}


def mesh_bbox(objects: list[dict[str, Any]]) -> list[float]:
    """xmin, ymin, zmin, xmax, ymax, zmax in metres of every mesh, its DataChunks resolved."""
    by_id = {obj["id"]: obj for obj in objects}
    low, high = [float("inf")] * 3, [float("-inf")] * 3
    for obj in objects:
        if not obj["speckle_type"].endswith("Mesh"):
            continue
        values = [
            value
            for item in obj["vertices"]
            for value in (by_id[item["referencedId"]]["data"] if "referencedId" in item else [item])
        ]
        scale = METRES_PER_UNIT[obj["units"]]
        for axis in range(3):
            low[axis] = min(low[axis], min(values[axis::3]) * scale)
            high[axis] = max(high[axis], max(values[axis::3]) * scale)
    return [*low, *high]

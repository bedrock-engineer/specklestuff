"""Small Speckle models for the tests, and the unpacking of what the viewer receives."""

import gzip
import json
from typing import Any

COLLECTION = "Speckle.Core.Models.Collections.Collection"
DATA_OBJECT = "Objects.Data.DataObject"
MESH = "Objects.Geometry.Mesh"
INSTANCE = "Speckle.Core.Models.Instances.InstanceProxy"
DEFINITION = "Speckle.Core.Models.Instances.InstanceDefinitionProxy"


def ref(object_id: str) -> dict[str, str]:
    return {"referencedId": object_id, "speckle_type": "reference"}


def revit_like(root_id: str = "root-a") -> list[dict[str, Any]]:
    """A model shaped like specklepy's projection of a Revit bundle, root first.

    One wall with its own mesh, and a door: an instance of def-1, whose member def-geo-0 is a
    DataObject named geometry displaying a Mesh with the same applicationId. The root lists
    that DataObject twice, as the projection does for some members.
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

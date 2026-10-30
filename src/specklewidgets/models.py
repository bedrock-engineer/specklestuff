"""Packs raw Speckle models for the viewer: :func:`models_gz`.

A model is a Speckle version's v3 objects, its root first, as
:func:`bimpolars.speckle.version_objects` gives them or as JSON array text. Three things in such
models trip the viewer (``@speckle/viewer`` 2.31.14), and :func:`models_gz` adjusts them:

- Several models load side by side in one viewer, but the ids of their instance definitions
  are only unique within a model: the projection of a Revit bundle numbers them ``def-1``,
  ``def-2``, ... in every model, and their members ``def-geo-0``, ``nested-inst-0``, ... So the
  ids of the definitions and their members get the model's root id as a prefix, everywhere the
  model names them.
- The viewer finds the members of the definitions by walking the model's tree and counting
  down the objects that carry a member id, and stops when the count reaches zero. specklepy's
  projection of a bundle gives a member's DataObject (named ``geometry``) and the Mesh it
  displays the same id, ``def-geo-<n>``, so the count runs out halfway: the viewer logs
  "Consumable applicationId ... could not be found" for the rest and draws none of their
  instances (13 of the 27 members of the RVT structural model). So such an id stays on the
  Mesh, the object the viewer settles on when it finds both, and the DataObject loses it.
- The viewer takes a member out of the tree once it has found it, to draw it only where an
  instance places it. The projection lists some members' DataObjects several times in the
  root collection (99 in the RVT architectural model), and the viewer takes out one copy: the
  others stay where the definition has them, and keep every instance of the mesh from being
  drawn (1638 meshes of 1368 instances in the architectural model). So a collection lists
  each object once.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

type SpeckleObject = Mapping[str, Any]
"""One v3 object as parsed JSON."""

type Model = Sequence[SpeckleObject] | str
"""One Speckle version's v3 objects, its root first: parsed, or as JSON array text."""

NAMESPACE_SEPARATOR = "/"
"""Joins a model's root id and a definition id: ``<root id>/def-1``."""

_REFERENCE_FIELDS = frozenset({"applicationId", "definitionId"})
"""Fields that hold one applicationId: an object's own, and the definition an instance places."""

_PROXY_TARGETS = "objects"
"""The field that lists the applicationIds a proxy (definition, material, level, ...) targets."""

_ELEMENTS = "elements"
"""The field that lists the objects of a collection, or an object's child objects."""

_DISPLAY_FIELDS = ("displayValue", _ELEMENTS)
"""The fields through which an object holds the objects below it."""


def models_gz(*models: Model, compresslevel: int = 6) -> bytes:
    """Packs models for :attr:`SpeckleViewer.objects_gz`, their instance definitions adjusted.

    The instance definitions of each model (the root's ``instanceDefinitionProxies``) and
    their members get the model's root id as a prefix, ``<root id>/def-1``, wherever the model
    names them: an object's ``applicationId``, an instance's ``definitionId`` and the
    ``objects`` that a proxy (definition, render material, level, ...) targets. Without that
    the ``def-1`` of one model would select the instances of another. A member id that an
    object and the object it displays both carry stays on the displayed one only, and an
    object that a collection lists more than once is listed once (see the module's docstring
    for why both trip the viewer). Other ids, such as the objects' content hashes and the
    elements' own applicationIds, are left as they are.

    Args:
        *models: Each model's v3 objects, root first: parsed (as
            :func:`bimpolars.speckle.version_objects` gives them) or as JSON array text.
        compresslevel: The gzip level. At 6 the three Revit Advanced Sample models (53 MB of
            JSON) pack to 6.0 MB in about 2 s; 9 saves 2 % and takes 20 % longer.

    Returns:
        Gzipped JSON: an array of the models, each an array of its objects. The input is not
        changed.

    Raises:
        ValueError: If a model is not a list of objects, has none, its first object is not a
            root with an ``id``, or two models share a root.
    """
    packed = []
    roots: set[str] = set()
    for index, model in enumerate(models):
        objects = json.loads(model) if isinstance(model, str) else model
        if (
            not isinstance(objects, Sequence)
            or isinstance(objects, str)
            or not objects
            or not isinstance(objects[0], Mapping)
            or "id" not in objects[0]
        ):
            raise ValueError(f"model {index} has no root object with an id first")
        root_id = str(objects[0]["id"])
        if root_id in roots:
            raise ValueError(f"model {index} repeats the root {root_id}")
        roots.add(root_id)
        packed.append(_viewer_model(objects))
    text = json.dumps(packed, separators=(",", ":"), allow_nan=False)
    return gzip.compress(text.encode(), compresslevel=compresslevel)


def _viewer_model(objects: Sequence[SpeckleObject]) -> list[SpeckleObject]:
    """The model's objects as the viewer needs them (see the module's docstring).

    Objects that change are copied; the others are the same objects.
    """
    root = objects[0]
    renamed: dict[str, str] = {}
    for definition in root.get("instanceDefinitionProxies") or []:
        for application_id in [definition.get("applicationId"), *definition.get("objects", [])]:
            if isinstance(application_id, str):
                renamed[application_id] = f"{root['id']}{NAMESPACE_SEPARATOR}{application_id}"
    displaying = _displaying_carriers(objects, renamed.keys())
    viewer_objects = []
    for obj in objects:
        new = _listed_once(_renamed(obj, renamed) if renamed else obj)
        if id(obj) in displaying:
            new = {key: value for key, value in new.items() if key != "applicationId"}
        viewer_objects.append(new)
    return viewer_objects


def _listed_once(obj: SpeckleObject) -> SpeckleObject:
    """The object with each detached object in its ``elements`` listed once, in first order."""
    elements = obj.get(_ELEMENTS)
    if not isinstance(elements, list):
        return obj
    seen: set[str] = set()
    once = []
    for element in elements:
        reference = element.get("referencedId") if isinstance(element, Mapping) else None
        if isinstance(reference, str):
            if reference in seen:
                continue
            seen.add(reference)
        once.append(element)
    if len(once) == len(elements):
        return obj
    return {**obj, _ELEMENTS: once}


def _displaying_carriers(objects: Sequence[SpeckleObject], members: Any) -> set[int]:
    """The objects (by ``id()``) that carry a member id and display another object with it."""
    carriers: dict[str, list[SpeckleObject]] = {}
    for obj in objects:
        application_id = obj.get("applicationId")
        if isinstance(application_id, str) and application_id in members:
            carriers.setdefault(application_id, []).append(obj)
    displaying = set()
    for same_id in carriers.values():
        if len(same_id) < 2:
            continue
        hashes = {obj.get("id") for obj in same_id}
        for obj in same_id:
            if any(child in hashes for child in _displayed(obj)):
                displaying.add(id(obj))
    return displaying


def _displayed(obj: SpeckleObject) -> Iterator[str]:
    """The ids of the objects directly below an object, detached or inline."""
    for field in _DISPLAY_FIELDS:
        for child in obj.get(field) or []:
            if isinstance(child, Mapping):
                child_id = child.get("referencedId", child.get("id"))
                if isinstance(child_id, str):
                    yield child_id


def _renamed(value: Any, renamed: Mapping[str, str]) -> Any:
    """The value with every definition id in a reference field renamed; unchanged parts shared."""
    if isinstance(value, Mapping):
        changed: dict[str, Any] | None = None
        for key, item in value.items():
            new: Any
            if key in _REFERENCE_FIELDS and isinstance(item, str):
                new = renamed.get(item, item)
            elif key == _PROXY_TARGETS and isinstance(item, list):
                new = _renamed_list(item, renamed, targets=True)
            else:
                new = _renamed(item, renamed)
            if new is not item:
                changed = changed if changed is not None else dict(value)
                changed[key] = new
        return value if changed is None else changed
    if isinstance(value, list):
        return _renamed_list(value, renamed, targets=False)
    return value


def _renamed_list(items: list[Any], renamed: Mapping[str, str], *, targets: bool) -> list[Any]:
    """The list with its items renamed (``targets``: its strings are applicationIds)."""
    # Coordinates and the data of DataChunks: nothing to rename, and most of a model's values
    if not items or isinstance(items[0], int | float):
        return items
    new = [
        renamed.get(item, item) if targets and isinstance(item, str) else _renamed(item, renamed)
        for item in items
    ]
    return new if any(a is not b for a, b in zip(new, items, strict=True)) else items

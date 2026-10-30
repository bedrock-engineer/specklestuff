# specklewidgets

Speckle's web viewer in a notebook: an engineer looks at one or more BIM models side by side,
clicks elements and reads their data back in Python.

## Language

**Model**:
One Speckle version's v3 objects, its root (a Collection) first, then everything in its
`__closure`. Several models load side by side, each into its own subtree of the viewer.
_Avoid_: version (the server's word for the same thing), project

**Element**:
What a click selects: an object with a `displayValue` (a DataObject such as a Revit wall), or
an instance placing a definition. `object_count` counts elements, not meshes: an element with
several meshes counts once, an instance once per placement.
_Avoid_: object (any v3 object, chunks and meshes included), node (the viewer's tree)

**Definition**:
An `InstanceDefinitionProxy` on the root: geometry shared by several placements, by
applicationId (`def-<n>` from the Revit connector, numbered per model).
_Avoid_: block, family, type

**Member**:
An object of a definition, named by applicationId in the definition's `objects`:
`def-geo-<n>` (a mesh) or `nested-inst-<n>` (an instance of another definition). Drawn only
where an instance places it.

**Instance**:
An `InstanceProxy`: a placement of a definition with a 4x4 `transform`. Its applicationId is
the element's, so selecting an instance selects the element.
_Avoid_: block reference, occurrence

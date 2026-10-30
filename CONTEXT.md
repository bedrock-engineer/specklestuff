# specklewidgets

Speckle's web viewer in a notebook: an engineer looks at one or more BIM models side by side,
clicks elements and reads their data back in Python.

## Language

**Model**:
One Speckle version's v3 objects, its root (a Collection) first, then everything in its
`__closure`. Several models load side by side, each into its own subtree of the viewer. A
BimDataFrame becomes one model: a DataObject per row with a mesh.
_Avoid_: version (the server's word for the same thing), project

**Element**:
What a click selects: an object with a `displayValue` (a DataObject such as a Revit wall), or
an instance placing a definition. `object_count` counts elements, not meshes: an element with
several meshes counts once, an instance once per placement.
_Avoid_: object (any v3 object, chunks and meshes included), node (the viewer's tree)

**Definition**:
An `InstanceDefinitionProxy` on the root: geometry shared by several placements, by
applicationId (`def-<n>`, which the projection of a Revit bundle numbers per model).
_Avoid_: block, family, type

**Member**:
An object of a definition, named by applicationId in the definition's `objects`:
`def-geo-<n>` (a mesh) or `nested-inst-<n>` (an instance of another definition). Drawn only
where an instance places it.

**Instance**:
An `InstanceProxy`: a placement of a definition with a 4x4 `transform`. Its applicationId is
the element's, with `-instance-<n>` appended when the element has several placements or
geometry of its own (185 of 5550 in the RVT architectural model; `read_speckle` strips it), so
selecting an instance selects the element.
_Avoid_: block reference, occurrence

**World**:
The viewer's coordinates: the models' own in metres, whatever their units. Markers, the ground
map and the tilesets' `ecef_to_world` and `hide_within` are in it.
_Avoid_: scene coordinates, site metres (the site's CRS may be in millimetres)

**Surroundings**:
What `GeoSpeckleViewer` shows around the models that is not an element: the ground map (an
OpenStreetMap snapshot on a plane) and tilesets (3D Tiles such as PDOK's 3D BAG). A click
does not select them and `object_count` and `scene_bbox` leave them out.
_Avoid_: context, basemap

**Pand**:
A building in the BAG, the Dutch register of buildings, by its `identificatie`. The panden
under a model are the buildings it takes the place of: `hide_within` leaves them out of the
3D BAG.
_Avoid_: building footprint (the model's own `footprint` column)

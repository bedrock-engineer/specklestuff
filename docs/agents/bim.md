# The BimDataFrame intake

`specklewidgets.bim` (`bim_objects`, `bim_collection`; the `[bim]` extra) turns a bimpolars
BimDataFrame into v3 objects. `SpeckleViewer` recognises a BimDataFrame by the class in
`sys.modules["bimpolars.frame"]` and imports `specklewidgets.bim` only then (the core
dependency rule is in [AGENTS.md](../../AGENTS.md)).

## What the intake draws

- It draws the rows with a mesh except `bimpolars.gltf.EXCLUDED_CLASSES` (openings), one
  DataObject per row (`applicationId` = `id`, so `object_count` = those rows).
- It writes each property set at the path its name gives, the inverse of
  `bimpolars.read_speckle`'s `_flatten`, so that `read_speckle` reads back the drawn rows' ids,
  classes, names, meshes and property sets (a test pins that).
- The other columns are plain fields, so they come back inside the `object` set, not as
  columns: `container` reads back null, and the spatial rows it points at have no mesh and are
  not drawn.
- Unstyled faces get no RenderMaterial, so they read back unstyled.
- Colours for `color` are the dataviz reference palette's light categorical slots and blue
  ramp (steps 250 to 700).

## A round trip through a server

A round trip through `send` and `receive` ([server.md](server.md)) keeps the drawn rows' ids,
classes, meshes and styles, not `container` (it comes back as the field
`properties.object.container`: `read_speckle` sets the column from a bundle only) nor the
levels (no mesh, not drawn); `simple_features` then lays each footprint at its own lowest z.
Left so on purpose (bimpolars#21); `test_a_sent_bimdataframe_comes_back` pins it.

## Known numbers

The architectural model as BimDataFrames (`examples/rvt_arch_bimdataframe.py`,
`tests/test_rvt_arch_bimdataframe.py`, read_ifc takes 45 s): `read_speckle` with the bundle
draws 5568 rows (every row with a mesh), bbox x -116.6763..202.3891, y -76.0339..75.7287,
z -1.8288..12.5745 m; `read_ifc` of `rvt-advanced-sample-arch.ifc` draws 5512 (5647 with a mesh
less 135 openings), bbox x -107.4743..211.5911, y -53.3989..98.3638, z -1.8288..12.4854 m.
`bim_objects` takes 4 to 6 s on either (specklepy hashes 17,600 objects, 36 to 45 MB of JSON).

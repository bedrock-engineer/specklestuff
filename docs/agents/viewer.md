# SpeckleViewer and @speckle/viewer

`SpeckleViewer` (`src/specklewidgets/speckle_viewer.py`: the traits and the constructor facade;
`Marker`) draws models that `models_gz` (`models.py`) packs, adjusting what trips the viewer.
The words model, element, definition, member and placement are defined in
[CONTEXT.md](../../CONTEXT.md).

## object_count and scene_bbox

- `object_count` is the number of elements the viewer draws, as a click selects them (nearest
  atomic node, then `elementOf`). `tests/test_rvt_advanced_sample.py` reaches the same numbers
  by a Python traversal, and the scene bbox from `bimpolars.read_speckle`: change both sides
  together.
- The viewer works in metres: `scene_bbox` and `markers` are in metres whatever the models'
  units.

## Viewer facts (2.31.14)

- `SpeckleOfflineLoader` ignores the objects it is given; `MemoryLoader` (a `SpeckleLoader`
  over `ObjectLoader2Factory.createFromObjects`) loads each model into its own subtree,
  resource `memory/<root id>`.
- Its converter finds instance definition members by counting down nodes with a member
  applicationId and stops at zero, so two objects with one member id (specklepy's `def-geo-<n>`
  DataObject and its Mesh) end the search early ("Consumable applicationId ... could not be
  found"); and it removes only one tree copy of a member, so a member listed twice stays drawn
  at the definition's origin and its instances are never batched (`findId(baseId)` returns the
  non-instanced copy). `models_gz` fixes both in the data.
- It batches an instance's geometry as instanced only from 10,000 vertices up; smaller
  instances are drawn as ordinary meshes under their InstanceProxy node, and a definition
  placed once is drawn as its own objects, hence `singlePlacements` for selection.
- Headless Chromium needs `--enable-unsafe-swiftshader` for WebGL; a frame of the three RVT
  models takes tens of seconds in SwiftShader, so screenshots need long timeouts.

## Known numbers

`examples/rvt_advanced_sample.py` and `tests/test_rvt_advanced_sample.py` read
`rvt-advanced-sample/speckle-v3-objects.parquet` (bucket file of 2026-10-29): arch 13,194
objects, str 5355, mep 16,173; drawn elements arch 5686, str 918, mep 6942 (13,546 together);
scene bbox x -116.6763..202.3891, y -121.7323..75.7287, z -7.2..15.2066 m; `models_gz` of the
three: 53 MB of JSON, 6.0 MB gzipped, 2 s.

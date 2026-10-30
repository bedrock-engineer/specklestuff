# @bedrock-engineer/geospeckle-viewer

Speckle's web viewer ([`@speckle/viewer`](https://www.npmjs.com/package/@speckle/viewer)) fed
with Speckle v3 objects instead of a Speckle server, on a ground map and among 3D Tiles such as
PDOK's 3D BAG. It is the front end of the Python package
[specklewidgets](https://github.com/bedrock-engineer/specklestuff), whose `SpeckleViewer` and
`GeoSpeckleViewer` widgets run it in marimo or Jupyter; this package runs it on any web page,
without Python.

```ts
import { mountGeoSpeckleViewer } from "@bedrock-engineer/geospeckle-viewer";

const objects = await fetch("objects.json.gz");
const { model, loaded, dispose } = mountGeoSpeckleViewer(document.getElementById("viewer")!, {
  objects_gz: await objects.arrayBuffer(),
  height: 600,
});
// Add handlers before awaiting loaded: the first report comes before it resolves
model.on("change:selected", () => console.log(model.get("selected")));
await loaded;
console.log(model.get("object_count"), model.get("scene_bbox"));
```

`mountGeoSpeckleViewer(el, traits)` takes the widget's traits, the JSON that specklewidgets
syncs, with specklewidgets' defaults for the ones left out:

- `objects_gz`: gzipped JSON of one or more models, each an array of v3 objects with its root
  first (specklewidgets' `models_gz`).
- `height` in pixels, or `null` for a height that follows the width by `aspect_ratio`.
- `markers`: axes and a label at named points.
- `ground_map` and `tilesets`: the surroundings, as `specklewidgets.geo` computes them. Without
  them the viewer is specklewidgets' plain `SpeckleViewer`.

The viewer reports in `selected` (the clicked elements' data), `object_count`, `scene_bbox` and
`surroundings`. `model.set(trait, value)` changes a trait, as Python does in a notebook. The
types (`GeoSpeckleViewerModel`, `GroundMap`, `Tileset`, `Marker`) mirror specklewidgets'
traits.

three.js, `@speckle/viewer`, `@speckle/objectloader2` and `3d-tiles-renderer` are dependencies,
not bundled in, at the exact versions the viewer needs (three.js 0.140.2). The specklewidgets
wheel bundles all of it into one file per widget instead.

Licensed under the Apache License 2.0.

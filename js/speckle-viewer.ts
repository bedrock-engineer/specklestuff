import type { RenderProps } from "@anywidget/types";
import {
  CameraController,
  DefaultViewerParams,
  SelectionExtension,
  Viewer,
  ViewerEvent,
} from "@speckle/viewer";
import type * as THREE from "three";
import { gunzipJson } from "./lib/gunzip";
import { disposeMarker, markerObject } from "./lib/markers";
import { MemoryLoader } from "./lib/memory-loader";
import { bboxList, drawnElements, type TreeNodeLike } from "./lib/scene";
import { elementOf, selectionData, singlePlacements } from "./lib/selection";
import type { NodeLike } from "./lib/selection";
import type { SpeckleObject, SpeckleViewerModel } from "./lib/types";

/**
 * Speckle's web viewer fed with v3 objects instead of a server URL. Each model in objects_gz
 * (its root first) loads through a MemoryLoader into its own subtree. After a load the
 * widget reports object_count and scene_bbox; a click selects an element (shift-click adds
 * to the selection, a click on nothing clears it) and reports it in selected.
 */
export default {
  async render({ model, el }: RenderProps<SpeckleViewerModel>) {
    const container = document.createElement("div");
    function size() {
      // A fixed height, or one that follows the notebook's width
      const height = model.get("height");
      container.style.cssText = height
        ? `position: relative; width: 100%; height: ${height}px;`
        : `position: relative; width: 100%; aspect-ratio: ${model.get("aspect_ratio")};`;
    }
    size();
    el.appendChild(container);
    const message = document.createElement("div");
    message.style.cssText =
      "position: absolute; left: 8px; top: 6px; font: 12px sans-serif; color: #b00; pointer-events: none;";
    container.appendChild(message);

    const viewer = new Viewer(container, { ...DefaultViewerParams, verbose: false });
    await viewer.init();
    const camera = viewer.createExtension(CameraController);
    const selection = viewer.createExtension(SelectionExtension);

    let placedBy = new Map<string, SpeckleObject>();
    viewer.on(ViewerEvent.ObjectClicked, () => {
      // Read the extension's selection once it has handled the click (shift adds to it)
      setTimeout(() => {
        // tree-model's typings leave out a node's model and parent
        const nodes = selection.getSelectedNodes() as unknown as NodeLike[];
        const elements = nodes.map((node) => elementOf(node, placedBy));
        model.set("selected", selectionData(elements));
        model.save_changes();
      });
    });

    function report(objectCount: number, bbox: number[]) {
      model.set("object_count", objectCount);
      model.set("scene_bbox", bbox);
      model.save_changes();
    }

    // Loads run one after the other; a load that a newer one has superseded stops early
    let loads = Promise.resolve();
    let latest = 0;
    async function load(generation: number) {
      if (generation !== latest) {
        return;
      }
      message.textContent = "";
      // Other objects: the old selection no longer applies
      if (model.get("selected").length) {
        model.set("selected", []);
        model.save_changes();
      }
      await viewer.unloadAll();
      placedBy = new Map();
      const buffer = model.get("objects_gz");
      if (!buffer || buffer.byteLength === 0) {
        report(0, []);
        return;
      }
      // One or more models, each its v3 objects with the root first
      const models = (await gunzipJson(buffer)) as SpeckleObject[][];
      for (const objects of models) {
        if (generation !== latest) {
          return;
        }
        for (const [member, instance] of singlePlacements(objects)) {
          placedBy.set(member, instance);
        }
        await viewer.loadObject(new MemoryLoader(viewer.getWorldTree(), objects), false);
      }
      camera.setCameraView(undefined, false);
      const renderer = viewer.getRenderer();
      const elements = drawnElements(
        // tree-model's typings leave out a node's model and parent
        viewer.getWorldTree().root.all(() => true) as unknown as TreeNodeLike[],
        new Set(renderer.batcher.getBatches().flatMap((batch) => batch.renderViews)),
        placedBy,
      );
      report(elements.size, bboxList(renderer.sceneBox));
    }
    function reload() {
      const generation = ++latest;
      loads = loads
        .then(() => load(generation))
        .catch((error: unknown) => {
          console.error("SpeckleViewer: loading the objects failed", error);
          message.textContent = `Loading failed: ${error}`;
        });
      return loads;
    }
    model.on("change:objects_gz", reload);
    await reload();

    let markers: THREE.Group[] = [];
    function placeMarkers() {
      const scene = viewer.getRenderer().scene;
      for (const marker of markers) {
        scene.remove(marker);
        disposeMarker(marker);
      }
      markers = model.get("markers").map(markerObject);
      for (const marker of markers) {
        scene.add(marker);
      }
      viewer.requestRender();
    }
    model.on("change:markers", placeMarkers);
    placeMarkers();

    model.on("change:height", size);
    model.on("change:aspect_ratio", size);
    // The viewer itself only follows the window's size, not its container's
    const resizing = new ResizeObserver(() => viewer.resize());
    resizing.observe(container);
    return () => {
      latest++;
      resizing.disconnect();
      viewer.dispose();
    };
  },
};

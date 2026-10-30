import { ObjectLayers, SpeckleLoader, Viewer, DefaultViewerParams, CameraController, SelectionExtension, ViewerEvent } from "https://esm.sh/@speckle/viewer@2.31.14?target=es2022&deps=@speckle/objectloader2@2.31.14,three@0.140.2";
import * as THREE from "https://esm.sh/three@0.140.2?target=es2022";
import { ObjectLoader2Factory } from "https://esm.sh/@speckle/objectloader2@2.31.14?target=es2022";
async function gunzipJson(buffer) {
  const bytes = ArrayBuffer.isView(buffer) ? new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength) : new Uint8Array(buffer);
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}
function markerObject({ name, position, size = 5 }) {
  const group = new THREE.Group();
  group.position.fromArray(position);
  const axes = new THREE.AxesHelper(size);
  axes.material.depthTest = false;
  group.add(axes);
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  context.font = "28px sans-serif";
  canvas.width = Math.ceil(context.measureText(name).width) + 16;
  canvas.height = 40;
  context.font = "28px sans-serif";
  context.fillStyle = "rgba(255, 255, 255, 0.85)";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#222";
  context.fillText(name, 8, 29);
  const label = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false })
  );
  label.scale.set(canvas.width / canvas.height, 1, 1).multiplyScalar(size / 4);
  label.position.set(0, 0, size * 1.2);
  group.add(label);
  group.traverse((object) => {
    object.layers.set(ObjectLayers.PROPS);
    object.renderOrder = 10;
  });
  return group;
}
function disposeMarker(group) {
  group.traverse((object) => {
    const { geometry, material } = object;
    geometry?.dispose();
    for (const each of Array.isArray(material) ? material : material ? [material] : []) {
      each.map?.dispose();
      each.dispose();
    }
  });
}
class MemoryLoader extends SpeckleLoader {
  constructor(tree, objects) {
    super(tree, `memory/${objects[0].id}`, void 0, void 0, objects);
  }
  initObjectLoader(_resource, _authToken, _enableCaching, resourceData) {
    return ObjectLoader2Factory.createFromObjects(resourceData);
  }
}
const INSTANCE_PROXY = "InstanceProxy";
function isInstanceProxy(raw) {
  return typeof raw?.speckle_type === "string" && raw.speckle_type.endsWith(INSTANCE_PROXY);
}
function singlePlacements(objects) {
  const placements = /* @__PURE__ */ new Map();
  for (const object of objects) {
    if (isInstanceProxy(object) && typeof object.definitionId === "string") {
      placements.set(object.definitionId, [...placements.get(object.definitionId) ?? [], object]);
    }
  }
  const placedBy = /* @__PURE__ */ new Map();
  const definitions = objects[0]?.instanceDefinitionProxies ?? [];
  for (const definition of definitions) {
    const placed = placements.get(definition.applicationId ?? "") ?? [];
    if (placed.length !== 1) {
      continue;
    }
    for (const member of definition.objects ?? []) {
      placedBy.set(member, placed[0]);
    }
  }
  return placedBy;
}
function elementOf(node, placedBy) {
  let element = node.model.raw;
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (isInstanceProxy(parent.model?.raw)) {
      element = parent.model.raw;
    }
  }
  for (let depth = 0; depth < 16; depth++) {
    const placement = placedBy.get(element.applicationId);
    if (!placement) {
      break;
    }
    element = placement;
  }
  return element;
}
const NOT_SELECTED = /* @__PURE__ */ new Set(["displayValue", "elements", "__closure"]);
function selectionData(elements) {
  const unique = [...new Set(elements)];
  return JSON.parse(
    JSON.stringify(unique, (key, value) => NOT_SELECTED.has(key) ? void 0 : value)
  );
}
function bboxList(box) {
  if (box.isEmpty()) {
    return [];
  }
  return [box.min.x, box.min.y, box.min.z, box.max.x, box.max.y, box.max.z];
}
function drawnElements(nodes, drawn, placedBy) {
  const elements = /* @__PURE__ */ new Set();
  for (let node of nodes) {
    if (!drawn.has(node.model.renderView)) {
      continue;
    }
    while (!node.model.atomic && node.parent) {
      node = node.parent;
    }
    elements.add(elementOf(node, placedBy));
  }
  return elements;
}
const speckleViewer = {
  async render({ model, el }) {
    const container = document.createElement("div");
    function size() {
      const height = model.get("height");
      container.style.cssText = height ? `position: relative; width: 100%; height: ${height}px;` : `position: relative; width: 100%; aspect-ratio: ${model.get("aspect_ratio")};`;
    }
    size();
    el.appendChild(container);
    const message = document.createElement("div");
    message.style.cssText = "position: absolute; left: 8px; top: 6px; font: 12px sans-serif; color: #b00; pointer-events: none;";
    container.appendChild(message);
    const viewer = new Viewer(container, { ...DefaultViewerParams, verbose: false });
    await viewer.init();
    const camera = viewer.createExtension(CameraController);
    const selection = viewer.createExtension(SelectionExtension);
    let placedBy = /* @__PURE__ */ new Map();
    viewer.on(ViewerEvent.ObjectClicked, () => {
      setTimeout(() => {
        const nodes = selection.getSelectedNodes();
        const elements = nodes.map((node) => elementOf(node, placedBy));
        model.set("selected", selectionData(elements));
        model.save_changes();
      });
    });
    function report(objectCount, bbox) {
      model.set("object_count", objectCount);
      model.set("scene_bbox", bbox);
      model.save_changes();
    }
    let loads = Promise.resolve();
    let latest = 0;
    async function load(generation) {
      if (generation !== latest) {
        return;
      }
      message.textContent = "";
      if (model.get("selected").length) {
        model.set("selected", []);
        model.save_changes();
      }
      await viewer.unloadAll();
      placedBy = /* @__PURE__ */ new Map();
      const buffer = model.get("objects_gz");
      if (!buffer || buffer.byteLength === 0) {
        report(0, []);
        return;
      }
      const models = await gunzipJson(buffer);
      for (const objects of models) {
        if (generation !== latest) {
          return;
        }
        for (const [member, instance] of singlePlacements(objects)) {
          placedBy.set(member, instance);
        }
        await viewer.loadObject(new MemoryLoader(viewer.getWorldTree(), objects), false);
      }
      camera.setCameraView(void 0, false);
      const renderer = viewer.getRenderer();
      const elements = drawnElements(
        // tree-model's typings leave out a node's model and parent
        viewer.getWorldTree().root.all(() => true),
        new Set(renderer.batcher.getBatches().flatMap((batch) => batch.renderViews)),
        placedBy
      );
      report(elements.size, bboxList(renderer.sceneBox));
    }
    function reload() {
      const generation = ++latest;
      loads = loads.then(() => load(generation)).catch((error) => {
        console.error("SpeckleViewer: loading the objects failed", error);
        message.textContent = `Loading failed: ${error}`;
      });
      return loads;
    }
    model.on("change:objects_gz", reload);
    await reload();
    let markers = [];
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
    const resizing = new ResizeObserver(() => viewer.resize());
    resizing.observe(container);
    return () => {
      latest++;
      resizing.disconnect();
      viewer.dispose();
    };
  }
};
export {
  speckleViewer as default
};

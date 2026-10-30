import { Extension, ObjectLayers, SpeckleLoader, Viewer, DefaultViewerParams, CameraController, SelectionExtension, ViewerEvent } from "https://esm.sh/@speckle/viewer@2.31.14?target=es2022";
import { TilesRenderer } from "https://esm.sh/3d-tiles-renderer@0.3.46?target=es2022&deps=three@0.140.2";
import { GLTFLoader } from "https://esm.sh/three@0.140.2/examples/jsm/loaders/GLTFLoader.js?target=es2022";
import { MeshoptDecoder } from "https://esm.sh/three@0.140.2/examples/jsm/libs/meshopt_decoder.module.js?target=es2022";
import * as THREE from "https://esm.sh/three@0.140.2?target=es2022";
import { ObjectLoader2Factory } from "https://esm.sh/@speckle/objectloader2@2.31.14?target=es2022";
const FEATURE_ID = "_feature_id_0";
function insidePolygon(x, y, rings) {
  let inside2 = false;
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i];
      const [xj, yj] = ring[j];
      if (yi > y !== yj > y && x < (xj - xi) * (y - yi) / (yj - yi) + xi) {
        inside2 = !inside2;
      }
    }
  }
  return inside2;
}
function area(rings) {
  const points = rings.flat();
  return {
    rings,
    min: [Math.min(...points.map(([x]) => x)), Math.min(...points.map(([, y]) => y))],
    max: [Math.max(...points.map(([x]) => x)), Math.max(...points.map(([, y]) => y))]
  };
}
function inside(x, y, areas) {
  return areas.some(
    ({ rings, min, max }) => x >= min[0] && x <= max[0] && y >= min[1] && y <= max[1] && insidePolygon(x, y, rings)
  );
}
function denormalizeScale(attribute) {
  if (!attribute.normalized) {
    return 1;
  }
  const array = attribute.array;
  if (array instanceof Int8Array) {
    return 1 / 127;
  }
  if (array instanceof Uint8Array) {
    return 1 / 255;
  }
  if (array instanceof Int16Array) {
    return 1 / 32767;
  }
  if (array instanceof Uint16Array) {
    return 1 / 65535;
  }
  return 1;
}
function hideFeaturesWithin(geometry, matrix, polygons) {
  const hidden = /* @__PURE__ */ new Set();
  const featureIds = geometry.getAttribute(FEATURE_ID);
  if (!featureIds || !geometry.index || polygons.length === 0) {
    return hidden;
  }
  const areas = polygons.map(area);
  const position = geometry.getAttribute("position");
  const scale = denormalizeScale(position);
  const vertex = new THREE.Vector3();
  const counts = /* @__PURE__ */ new Map();
  for (let i = 0; i < position.count; i++) {
    const id = featureIds.getX(i);
    let count = counts.get(id);
    if (!count) {
      count = [0, 0];
      counts.set(id, count);
    }
    vertex.fromBufferAttribute(position, i).multiplyScalar(scale).applyMatrix4(matrix);
    if (inside(vertex.x, vertex.y, areas)) {
      count[0]++;
    }
    count[1]++;
  }
  for (const [id, [within, total]] of counts) {
    if (within > total / 2) {
      hidden.add(id);
    }
  }
  if (hidden.size > 0) {
    const index = geometry.index.array;
    const kept = index.filter(
      (_, i) => !hidden.has(featureIds.getX(index[i - i % 3]))
    );
    geometry.setIndex(new THREE.BufferAttribute(kept, 1));
  }
  return hidden;
}
class ContextTiles extends Extension {
  tilesets = [];
  /** Hidden features per loaded tile content */
  loaded = /* @__PURE__ */ new Map();
  onChange = () => {
  };
  report() {
    let hiddenFeatures = 0;
    for (const count of this.loaded.values()) {
      hiddenFeatures += count;
    }
    return { tiles: this.loaded.size, hiddenFeatures };
  }
  setTilesets(tilesets) {
    this.clear();
    const scene = this.viewer.getRenderer().scene;
    this.tilesets = tilesets.map(({ tileset, ecef_to_world, hide_within = [] }) => {
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(tileset)], { type: "application/json" })
      );
      const tiles = new TilesRenderer(url);
      const gltfLoader = new GLTFLoader(tiles.manager);
      gltfLoader.setMeshoptDecoder(MeshoptDecoder);
      tiles.manager.addHandler(/\.(gltf|glb)$/g, gltfLoader);
      tiles.group.matrixAutoUpdate = false;
      tiles.group.matrix.fromArray(ecef_to_world);
      tiles.addEventListener("load-model", ({ scene: content, tile }) => {
        const hidden = /* @__PURE__ */ new Set();
        content.traverse((object) => {
          object.layers.set(ObjectLayers.PROPS);
          const mesh = object;
          if (mesh.isMesh && hide_within.length) {
            object.updateWorldMatrix(true, false);
            const toWorld = tiles.group.matrix.clone().multiply(object.matrixWorld);
            for (const id of hideFeaturesWithin(mesh.geometry, toWorld, hide_within)) {
              hidden.add(id);
            }
          }
        });
        this.loaded.set(tile, hidden.size);
        this.onChange(this.report());
        this.viewer.requestRender();
      });
      tiles.addEventListener("dispose-model", ({ tile }) => {
        this.loaded.delete(tile);
        this.onChange(this.report());
      });
      scene.add(tiles.group);
      return { tiles, url };
    });
    this.onChange(this.report());
    this.viewer.requestRender();
  }
  clear() {
    const scene = this.viewer.getRenderer().scene;
    for (const { tiles, url } of this.tilesets) {
      scene.remove(tiles.group);
      tiles.dispose();
      URL.revokeObjectURL(url);
    }
    this.tilesets = [];
    this.loaded.clear();
  }
  onEarlyUpdate() {
    const renderer = this.viewer.getRenderer();
    const camera = renderer.renderingCamera;
    if (!camera) {
      return;
    }
    for (const { tiles } of this.tilesets) {
      tiles.setCamera(camera);
      tiles.setResolutionFromRenderer(camera, renderer.renderer);
      camera.updateMatrixWorld();
      tiles.group.updateMatrixWorld(true);
      tiles.update();
    }
  }
}
const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_MAX_ZOOM = 19;
const OSM_ATTRIBUTION = "© OpenStreetMap contributors";
const TILE_SIZE = 256;
function isGroundMap(value) {
  return "bounds" in value;
}
function tileX(lon, zoom) {
  return (lon + 180) / 360 * 2 ** zoom;
}
function tileY(lat, zoom) {
  const phi = lat * Math.PI / 180;
  return (1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2 * 2 ** zoom;
}
function tilesFor({ bounds, width, height }, maxZoom = OSM_MAX_ZOOM) {
  const [west, south, east, north] = bounds;
  const across = tileX(east, 0) - tileX(west, 0);
  const z = Math.max(0, Math.min(maxZoom, Math.round(Math.log2(width / (TILE_SIZE * across)))));
  const [x0, x1] = [tileX(west, z), tileX(east, z)];
  const [y0, y1] = [tileY(north, z), tileY(south, z)];
  const [scaleX, scaleY] = [width / (x1 - x0), height / (y1 - y0)];
  const tiles = [];
  for (let y = Math.floor(y0); y < y1; y++) {
    for (let x = Math.floor(x0); x < x1; x++) {
      tiles.push({
        z,
        x,
        y,
        left: (x - x0) * scaleX,
        top: (y - y0) * scaleY,
        width: scaleX,
        height: scaleY
      });
    }
  }
  return tiles;
}
function tileUrl(template, { z, x, y }) {
  return template.replace("{z}", `${z}`).replace("{x}", `${x}`).replace("{y}", `${y}`);
}
function mapToWorld({ lnglat_to_world: t, z }, lon, lat) {
  return [t[0] * lon + t[1] * lat + t[2], t[3] * lon + t[4] * lat + t[5], z];
}
function mapCorners(groundMap) {
  const [west, south, east, north] = groundMap.bounds;
  return [
    mapToWorld(groundMap, west, south),
    mapToWorld(groundMap, east, south),
    mapToWorld(groundMap, east, north),
    mapToWorld(groundMap, west, north)
  ];
}
async function groundMapImage(groundMap, template = OSM_TILES) {
  const canvas = document.createElement("canvas");
  canvas.width = groundMap.width;
  canvas.height = groundMap.height;
  const context = canvas.getContext("2d");
  const tiles = tilesFor(groundMap);
  const loaded = await Promise.allSettled(
    tiles.map(async (tile) => {
      const response = await fetch(tileUrl(template, tile));
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      const bitmap = await createImageBitmap(await response.blob());
      context.drawImage(bitmap, tile.left, tile.top, tile.width, tile.height);
      bitmap.close();
    })
  );
  const failed = loaded.filter((result) => result.status === "rejected");
  if (failed.length === tiles.length) {
    throw new Error(`none of the ${tiles.length} map tiles loaded: ${failed[0]?.reason}`);
  }
  return canvas;
}
function groundMapMesh(groundMap, image) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(mapCorners(groundMap).flat(), 3)
  );
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
  const texture = new THREE.CanvasTexture(image);
  texture.encoding = THREE.sRGBEncoding;
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    side: THREE.DoubleSide,
    transparent: groundMap.opacity < 1,
    opacity: groundMap.opacity
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.layers.set(ObjectLayers.PROPS);
  return mesh;
}
function disposeGroundMap(mesh) {
  const material = mesh.material;
  material.map?.dispose();
  material.dispose();
  mesh.geometry.dispose();
}
class GroundInView extends Extension {
  ground = null;
  onLateUpdate() {
    const camera = this.viewer.getRenderer().renderingCamera;
    if (!this.ground || !camera) {
      return;
    }
    const corners = this.ground.geometry.getAttribute("position");
    const corner = new THREE.Vector3();
    let farthest = 0;
    for (let i = 0; i < corners.count; i++) {
      corner.fromBufferAttribute(corners, i);
      farthest = Math.max(farthest, camera.position.distanceTo(corner));
    }
    if (camera.far < 1.05 * farthest) {
      camera.far = 1.05 * farthest;
      camera.updateProjectionMatrix();
    }
  }
}
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
async function mountSpeckleViewer(model, el) {
  const traits = model;
  const container = document.createElement("div");
  function size() {
    const height = traits.get("height");
    container.style.cssText = height ? `position: relative; width: 100%; height: ${height}px;` : `position: relative; width: 100%; aspect-ratio: ${traits.get("aspect_ratio")};`;
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
      traits.set("selected", selectionData(elements));
      traits.save_changes();
    });
  });
  function report(objectCount, bbox) {
    traits.set("object_count", objectCount);
    traits.set("scene_bbox", bbox);
    traits.save_changes();
  }
  let loads = Promise.resolve();
  let latest = 0;
  async function load(generation) {
    if (generation !== latest) {
      return;
    }
    message.textContent = "";
    if (traits.get("selected").length) {
      traits.set("selected", []);
      traits.save_changes();
    }
    await viewer.unloadAll();
    placedBy = /* @__PURE__ */ new Map();
    const buffer = traits.get("objects_gz");
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
  traits.on("change:objects_gz", reload);
  await reload();
  let markers = [];
  function placeMarkers() {
    const scene = viewer.getRenderer().scene;
    for (const marker of markers) {
      scene.remove(marker);
      disposeMarker(marker);
    }
    markers = traits.get("markers").map(markerObject);
    for (const marker of markers) {
      scene.add(marker);
    }
    viewer.requestRender();
  }
  traits.on("change:markers", placeMarkers);
  placeMarkers();
  traits.on("change:height", size);
  traits.on("change:aspect_ratio", size);
  const resizing = new ResizeObserver(() => viewer.resize());
  resizing.observe(container);
  return {
    viewer,
    container,
    showMessage(text) {
      message.textContent = text;
    },
    dispose() {
      latest++;
      resizing.disconnect();
      viewer.dispose();
    }
  };
}
const REPORT_DELAY_MS = 250;
function planeBounds(groundMap) {
  const corners = mapCorners(groundMap);
  const xs = corners.map(([x]) => x);
  const ys = corners.map(([, y]) => y);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
const geoSpeckleViewer = {
  async render({ model, el }) {
    const mounted = await mountSpeckleViewer(model, el);
    const { viewer, container } = mounted;
    const groundInView = viewer.createExtension(GroundInView);
    const contextTiles = viewer.createExtension(ContextTiles);
    let groundBounds = [];
    let tilesReport = { tiles: 0, hiddenFeatures: 0 };
    let reporting;
    function report() {
      clearTimeout(reporting);
      reporting = setTimeout(() => {
        model.set("surroundings", {
          ground_map: groundBounds,
          tiles: tilesReport.tiles,
          hidden_features: tilesReport.hiddenFeatures
        });
        model.save_changes();
      }, REPORT_DELAY_MS);
    }
    contextTiles.onChange = (tiles) => {
      tilesReport = tiles;
      report();
    };
    const attribution = document.createElement("div");
    attribution.style.cssText = "position: absolute; right: 4px; bottom: 2px; font: 11px sans-serif; color: #555; pointer-events: none;";
    container.appendChild(attribution);
    function updateAttribution() {
      const credits = [
        ...isGroundMap(model.get("ground_map")) ? [OSM_ATTRIBUTION] : [],
        ...model.get("tilesets").map((entry) => entry.attribution).filter(Boolean)
      ];
      attribution.textContent = credits.join(" | ");
    }
    let ground = null;
    let latest = 0;
    async function placeGroundMap() {
      const generation = ++latest;
      updateAttribution();
      const groundMap = model.get("ground_map");
      let mesh = null;
      if (isGroundMap(groundMap)) {
        try {
          mesh = groundMapMesh(groundMap, await groundMapImage(groundMap));
        } catch (error) {
          console.error("GeoSpeckleViewer: the ground map failed", error);
          mounted.showMessage(`The ground map failed: ${error}`);
        }
      }
      if (generation !== latest) {
        if (mesh) {
          disposeGroundMap(mesh);
        }
        return;
      }
      const scene = viewer.getRenderer().scene;
      if (ground) {
        scene.remove(ground);
        disposeGroundMap(ground);
      }
      ground = groundInView.ground = mesh;
      if (mesh) {
        scene.add(mesh);
      }
      groundBounds = mesh && isGroundMap(groundMap) ? planeBounds(groundMap) : [];
      report();
      viewer.requestRender();
    }
    function placeTilesets() {
      contextTiles.setTilesets(model.get("tilesets"));
      updateAttribution();
    }
    model.on("change:tilesets", placeTilesets);
    placeTilesets();
    model.on("change:ground_map", placeGroundMap);
    void placeGroundMap();
    return () => {
      latest++;
      clearTimeout(reporting);
      contextTiles.clear();
      mounted.dispose();
    };
  }
};
export {
  geoSpeckleViewer as default
};

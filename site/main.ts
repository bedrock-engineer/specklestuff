// The demo page: Sixty5 in a GeoSpeckleViewer beside a MapLibre map of the selected element's
// footprint. The page is static: site/sixty5.py computes the widget's traits and the
// footprints at build time, and @bedrock-engineer/geospeckle-viewer runs the widget without a
// kernel.
import {
  type GeoSpeckleViewerModel,
  mountGeoSpeckleViewer,
} from "@bedrock-engineer/geospeckle-viewer";
import type { FeatureCollection } from "geojson";
import { type Basemap, FootprintMap, type Footprints, selectedFootprints } from "./footprint-map";
import { splitter } from "./splitter";

/** Where site/sixty5.py's files are, relative to the page: any repository's Pages path works */
const DATA = "data/";

function byId<T extends HTMLElement = HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}

async function fetchData(name: string): Promise<Response> {
  const response = await fetch(DATA + name);
  if (!response.ok) {
    throw new Error(`${name}: HTTP ${response.status}`);
  }
  return response;
}

function paragraph(className: string, text: string): HTMLParagraphElement {
  const p = document.createElement("p");
  p.className = className;
  p.textContent = text;
  return p;
}

function level(elevation: number | null): string {
  return elevation === null ? "" : ` · level ${elevation >= 0 ? "+" : ""}${elevation.toFixed(2)} m`;
}

/** The card on the map: what is selected, nothing without a selection (the header says how) */
function describe(card: HTMLElement, ids: string[], footprints: Footprints) {
  const { features, storeys } = selectedFootprints(footprints, ids);
  const lines: HTMLElement[] = [];
  if (ids.length === 1 && features.length === 1) {
    const { properties } = features[0];
    lines.push(paragraph("class", properties.class ?? "element"));
    lines.push(paragraph("name", properties.name ?? properties.id));
    if (properties.storey) {
      lines.push(paragraph("storey", properties.storey + level(properties.elevation)));
    }
  } else if (ids.length > 1) {
    const on = storeys.length === 1 ? "storey" : "storeys";
    lines.push(paragraph("name", `${ids.length} elements on ${storeys.length} ${on}`));
    const list = document.createElement("ul");
    for (const { properties } of features) {
      const item = document.createElement("li");
      item.textContent = `${properties.class}: ${properties.name ?? properties.id}`;
      list.appendChild(item);
    }
    lines.push(list);
  }
  if (features.length < ids.length) {
    const without = ids.length - features.length;
    lines.push(
      paragraph("hint", `${without === 1 ? "One element has" : `${without} have`} no footprint.`),
    );
  }
  card.replaceChildren(...lines);
}

async function main() {
  const viewerPane = byId("viewer-pane");
  const loading = byId("loading");
  const card = byId("selection");
  // The viewer and the map follow their panes' sizes themselves
  splitter(byId("splitter"), viewerPane.parentElement as HTMLElement);
  try {
    const [state, objects, footprints, outline] = await Promise.all([
      fetchData("viewer.json").then(
        (r) => r.json() as Promise<Omit<GeoSpeckleViewerModel, "objects_gz">>,
      ),
      fetchData("objects.json.gz").then((r) => r.arrayBuffer()),
      fetchData("footprints.geojson").then((r) => r.json() as Promise<Footprints>),
      fetchData("outline.geojson").then((r) => r.json() as Promise<FeatureCollection>),
    ]);

    const map = new FootprintMap(byId("map"), footprints, outline);
    for (const button of document.querySelectorAll<HTMLButtonElement>(".basemaps button")) {
      button.addEventListener("click", () => {
        map.setBasemap(button.dataset.basemap as Basemap);
        for (const other of document.querySelectorAll(".basemaps button")) {
          other.setAttribute("aria-pressed", String(other === button));
        }
      });
    }

    // The viewer fills its pane: its height trait follows the pane's
    const { model, loaded } = mountGeoSpeckleViewer(byId("viewer"), {
      ...state,
      objects_gz: objects,
      height: viewerPane.clientHeight,
    });
    new ResizeObserver(() => model.set("height", viewerPane.clientHeight)).observe(viewerPane);

    // A click in the viewer reports the elements' applicationIds: the rows' ids
    model.on("change:selected", () => {
      const ids = model.get("selected").map((element) => element.applicationId as string);
      card.dataset.ids = JSON.stringify(ids);
      card.dataset.drawn = "[]";
      describe(card, ids, footprints);
      map.select(ids);
      // What the map draws once it is still, for the headless test (e2e/site.test.mjs)
      map.map.once("idle", () => {
        card.dataset.drawn = JSON.stringify(map.drawnSelection());
      });
    });
    // What the viewer reports, for the headless test
    model.on("change:object_count", () => {
      viewerPane.dataset.objectCount = String(model.get("object_count"));
    });
    model.on("change:surroundings", () => {
      viewerPane.dataset.surroundings = JSON.stringify(model.get("surroundings"));
    });

    await loaded;
    loading.hidden = true;
  } catch (error) {
    console.error("The page failed to load", error);
    loading.textContent = `The model failed to load: ${error}`;
  }
}

void main();

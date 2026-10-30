import { describe, expect, it } from "vitest";
import { bboxList, drawnElements, type TreeNodeLike } from "./scene";
import { singlePlacements } from "./selection";
import type { SpeckleObject } from "./types";

const INSTANCE = "Speckle.Core.Models.Instances.InstanceProxy";

function box(min: number[], max: number[], empty = false) {
  const [x0, y0, z0] = min;
  const [x1, y1, z1] = max;
  return { min: { x: x0, y: y0, z: z0 }, max: { x: x1, y: y1, z: z1 }, isEmpty: () => empty };
}

describe("bboxList", () => {
  it("lists the corners as xmin, ymin, zmin, xmax, ymax, zmax", () => {
    expect(bboxList(box([1, 2, 3], [4, 5, 6]))).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("is empty for an empty box", () => {
    expect(
      bboxList(box([Infinity, Infinity, Infinity], [-Infinity, -Infinity, -Infinity], true)),
    ).toEqual([]);
  });
});

describe("drawnElements", () => {
  function node(
    raw: Record<string, unknown>,
    parent: TreeNodeLike | null,
    extra = {},
  ): TreeNodeLike {
    return { model: { raw, ...extra }, parent };
  }

  it("counts an element once for all its meshes and an instance once per placement", () => {
    const root = node({ id: "root" }, null);
    const wall = node({ id: "wall" }, root, { atomic: true });
    const wallMeshes = [1, 2].map((i) => node({ id: `wm${i}` }, wall, { renderView: `wall-${i}` }));
    const placements = [1, 2].map((i) => {
      const instance = node({ id: `w${i}`, speckle_type: INSTANCE }, root, { atomic: true });
      const transform = node({ id: `t${i}` }, instance);
      return node({ id: `m${i}` }, transform, { renderView: `window-${i}` });
    });
    const hidden = node({ id: "h" }, wall, { renderView: "not drawn" });
    const nodes = [root, wall, ...wallMeshes, ...placements, hidden];
    const drawn = new Set<unknown>(["wall-1", "wall-2", "window-1", "window-2"]);
    const elements = drawnElements(nodes, drawn, new Map());
    expect([...elements].map((raw) => raw.id)).toEqual(["wall", "w1", "w2"]);
  });

  it("counts a single placement drawn as the definition's own mesh as the instance", () => {
    const objects: SpeckleObject[] = [
      {
        id: "root",
        instanceDefinitionProxies: [{ id: "d", applicationId: "def-1", objects: ["def-geo-0"] }],
      },
      { id: "door", speckle_type: INSTANCE, applicationId: "door-guid", definitionId: "def-1" },
    ];
    const root = node({ id: "root" }, null);
    const member = node({ id: "dm", applicationId: "def-geo-0" }, root, {
      atomic: true,
      renderView: "door",
    });
    const elements = drawnElements([root, member], new Set(["door"]), singlePlacements(objects));
    expect([...elements]).toEqual([objects[1]]);
  });
});

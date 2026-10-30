import { describe, expect, it } from "vitest";
import { elementOf, type NodeLike, selectionData, singlePlacements } from "./selection";
import type { SpeckleObject } from "./types";

const INSTANCE = "Speckle.Core.Models.Instances.InstanceProxy";

/** A root with two definitions: def-1 placed once (door), def-2 placed twice (windows) */
function model(): SpeckleObject[] {
  return [
    {
      id: "root",
      speckle_type: "Speckle.Core.Models.Collections.Collection",
      instanceDefinitionProxies: [
        { id: "d1", applicationId: "root/def-1", objects: ["root/def-geo-0"] },
        { id: "d2", applicationId: "root/def-2", objects: ["root/def-geo-1"] },
      ],
    },
    { id: "door", speckle_type: INSTANCE, applicationId: "door-guid", definitionId: "root/def-1" },
    { id: "w1", speckle_type: INSTANCE, applicationId: "window-1", definitionId: "root/def-2" },
    { id: "w2", speckle_type: INSTANCE, applicationId: "window-2", definitionId: "root/def-2" },
  ];
}

/** A chain of tree nodes, outermost first; returns the innermost */
function chain(...raws: Record<string, unknown>[]): NodeLike {
  let parent: NodeLike | null = null;
  for (const raw of raws) {
    parent = { model: { raw }, parent };
  }
  return parent!;
}

describe("singlePlacements", () => {
  it("maps the members of a definition placed once to its instance", () => {
    const placedBy = singlePlacements(model());
    expect([...placedBy.keys()]).toEqual(["root/def-geo-0"]);
    expect(placedBy.get("root/def-geo-0")?.applicationId).toBe("door-guid");
  });

  it("is empty without definitions", () => {
    expect(singlePlacements([{ id: "root" }]).size).toBe(0);
  });
});

describe("elementOf", () => {
  const objects = model();
  const placedBy = singlePlacements(objects);

  it("is the node's own object outside instances", () => {
    const wall = { id: "wall", applicationId: "wall-guid" };
    expect(elementOf(chain({ id: "root" }, wall), placedBy)).toBe(wall);
  });

  it("is the instance a node hangs under", () => {
    const mesh = { id: "mesh", applicationId: "root/def-geo-1" };
    expect(elementOf(chain({ id: "root" }, objects[2], { id: "t" }, mesh), placedBy)).toBe(
      objects[2],
    );
  });

  it("is the outermost of nested instances", () => {
    const inner = { id: "inner", speckle_type: INSTANCE, applicationId: "root/nested-inst-0" };
    const mesh = { id: "mesh", applicationId: "root/def-geo-1" };
    expect(elementOf(chain(objects[2], inner, mesh), placedBy)).toBe(objects[2]);
  });

  it("is the single placement of a member drawn as the definition's own object", () => {
    const member = { id: "door-mesh", applicationId: "root/def-geo-0" };
    expect(elementOf(chain({ id: "root" }, member), placedBy)).toBe(objects[1]);
  });
});

describe("selectionData", () => {
  it("drops geometry and children, and repeats", () => {
    const wall = {
      id: "wall",
      name: "Basic Wall",
      displayValue: [{ referencedId: "m" }],
      elements: [],
      __closure: { m: 1 },
      properties: { Height: 3000 },
    };
    expect(selectionData([wall, wall])).toEqual([
      { id: "wall", name: "Basic Wall", properties: { Height: 3000 } },
    ]);
  });
});

import { describe, expect, it, vi } from "vitest";
import { StaticModel } from "./static-model";

describe("StaticModel", () => {
  it("holds the traits it was given", () => {
    const model = new StaticModel({ height: 600, selected: [] as string[] });
    expect(model.get("height")).toBe(600);
    expect(model.get("selected")).toEqual([]);
  });

  it("fires change:<trait> and change when a trait changes", () => {
    const model = new StaticModel({ height: 600, aspect_ratio: 1.5 });
    const height = vi.fn();
    const any = vi.fn();
    const other = vi.fn();
    model.on("change:height", height);
    model.on("change", any);
    model.on("change:aspect_ratio", other);
    model.set("height", 400);
    expect(model.get("height")).toBe(400);
    expect(height).toHaveBeenCalledOnce();
    expect(any).toHaveBeenCalledOnce();
    expect(other).not.toHaveBeenCalled();
  });

  it("stays quiet when a trait is set to the value it has", () => {
    const model = new StaticModel({ height: 600 });
    const height = vi.fn();
    model.on("change:height", height);
    model.set("height", 600);
    expect(height).not.toHaveBeenCalled();
  });

  it("removes handlers", () => {
    const model = new StaticModel({ height: 600 });
    const kept = vi.fn();
    const removed = vi.fn();
    model.on("change:height", kept);
    model.on("change:height", removed);
    model.off("change:height", removed);
    model.set("height", 1);
    model.off("change:height");
    model.set("height", 2);
    expect(kept).toHaveBeenCalledOnce();
    expect(removed).not.toHaveBeenCalled();
  });
});

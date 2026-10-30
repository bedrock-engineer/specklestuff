import * as THREE from "three";
import { describe, expect, it } from "vitest";
import { denormalizeScale, hideFeaturesWithin, insidePolygon, spanHeights } from "./hide-features";
import type { Rings } from "./types";

const SQUARE: Rings = [
  [
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10],
  ],
];
const SQUARE_WITH_HOLE: Rings = [
  ...SQUARE,
  [
    [4, 4],
    [6, 4],
    [6, 6],
    [4, 6],
  ],
];

describe("insidePolygon", () => {
  it("is true inside the exterior and false outside", () => {
    expect(insidePolygon(5, 5, SQUARE)).toBe(true);
    expect(insidePolygon(11, 5, SQUARE)).toBe(false);
    expect(insidePolygon(5, -1, SQUARE)).toBe(false);
  });

  it("is false in a hole", () => {
    expect(insidePolygon(5, 5, SQUARE_WITH_HOLE)).toBe(false);
    expect(insidePolygon(2, 2, SQUARE_WITH_HOLE)).toBe(true);
  });
});

describe("denormalizeScale", () => {
  it("scales normalized integers to -1..1 or 0..1", () => {
    expect(denormalizeScale(new THREE.BufferAttribute(new Int16Array(3), 3, true))).toBe(1 / 32767);
    expect(denormalizeScale(new THREE.BufferAttribute(new Uint8Array(3), 3, true))).toBe(1 / 255);
    expect(denormalizeScale(new THREE.BufferAttribute(new Int16Array(3), 3, false))).toBe(1);
    expect(denormalizeScale(new THREE.BufferAttribute(new Float32Array(3), 3))).toBe(1);
  });
});

/**
 * Two buildings as feature 0 and feature 1, a square of two triangles each: feature 0 over
 * x 1..3, feature 1 over x 21..23, both y 1..3.
 */
function twoFeatures(positions: THREE.BufferAttribute = floatPositions()) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", positions);
  geometry.setAttribute(
    "_feature_id_0",
    new THREE.BufferAttribute(new Float32Array([0, 0, 0, 0, 1, 1, 1, 1]), 1),
  );
  geometry.setIndex(
    new THREE.BufferAttribute(new Uint16Array([0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7]), 1),
  );
  return geometry;
}

function floatPositions() {
  // prettier-ignore
  return new THREE.BufferAttribute(new Float32Array([
    1, 1, 0, 3, 1, 0, 3, 3, 0, 1, 3, 0,
    21, 1, 0, 23, 1, 0, 23, 3, 0, 21, 3, 0,
  ]), 3);
}

describe("hideFeaturesWithin", () => {
  it("drops the triangles of the features mostly inside a polygon", () => {
    const geometry = twoFeatures();
    const hidden = hideFeaturesWithin(geometry, new THREE.Matrix4(), [SQUARE]);
    expect(hidden.ids).toEqual(new Set([0]));
    expect(Array.from(geometry.index!.array)).toEqual([4, 5, 6, 4, 6, 7]);
  });

  it("places the mesh in the world with the matrix first", () => {
    const geometry = twoFeatures();
    const hidden = hideFeaturesWithin(geometry, new THREE.Matrix4().makeTranslation(-20, 0, 0), [
      SQUARE,
    ]);
    expect(hidden.ids).toEqual(new Set([1]));
    expect(Array.from(geometry.index!.array)).toEqual([0, 1, 2, 0, 2, 3]);
  });

  it("keeps a feature with half of its vertices or fewer inside", () => {
    const geometry = twoFeatures();
    // x 2..12 holds two of feature 0's four vertices
    const half: Rings = [
      [
        [2, 0],
        [12, 0],
        [12, 10],
        [2, 10],
      ],
    ];
    expect(hideFeaturesWithin(geometry, new THREE.Matrix4(), [half]).ids).toEqual(new Set());
    expect(geometry.index!.count).toBe(12);
  });

  it("reads quantized positions as their values", () => {
    // The same squares in int16 steps of 1/32767, scaled back by the matrix
    const quantized = Int16Array.from(Array.from(floatPositions().array), (value) =>
      Math.round(value * 1000),
    );
    const geometry = twoFeatures(new THREE.BufferAttribute(quantized, 3, true));
    const scale = 32767 / 1000;
    const hidden = hideFeaturesWithin(geometry, new THREE.Matrix4().makeScale(scale, scale, 1), [
      SQUARE,
    ]);
    expect(hidden.ids).toEqual(new Set([0]));
  });

  it("reports the heights the dropped features span in the world", () => {
    // Feature 0 from 0 to 4 high, feature 1 at 10, all lifted by 1
    // prettier-ignore
    const positions = new THREE.BufferAttribute(new Float32Array([
      1, 1, 0, 3, 1, 0, 3, 3, 4, 1, 3, 4,
      21, 1, 10, 23, 1, 10, 23, 3, 10, 21, 3, 10,
    ]), 3);
    const lift = new THREE.Matrix4().makeTranslation(0, 0, 1);
    expect(hideFeaturesWithin(twoFeatures(positions), lift, [SQUARE]).heights).toEqual([1, 5]);
  });

  it("leaves a mesh without feature ids or polygons as it is", () => {
    const geometry = twoFeatures();
    geometry.deleteAttribute("_feature_id_0");
    expect(hideFeaturesWithin(geometry, new THREE.Matrix4(), [SQUARE])).toEqual({
      ids: new Set(),
      heights: [],
    });
    expect(hideFeaturesWithin(twoFeatures(), new THREE.Matrix4(), [])).toEqual({
      ids: new Set(),
      heights: [],
    });
  });
});

describe("spanHeights", () => {
  it("spans both ranges, where [] spans nothing", () => {
    expect(spanHeights([1, 5], [-2, 3])).toEqual([-2, 5]);
    expect(spanHeights([], [1, 2])).toEqual([1, 2]);
    expect(spanHeights([1, 2], [])).toEqual([1, 2]);
    expect(spanHeights([], [])).toEqual([]);
  });
});

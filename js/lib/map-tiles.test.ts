import { describe, expect, it } from "vitest";
import { isGroundMap, mapCorners, tilesFor, tileUrl, tileX, tileY } from "./map-tiles";
import type { GroundMap } from "./types";

describe("tileX and tileY", () => {
  it("span the world from 180 W and the north edge of Web Mercator", () => {
    expect(tileX(-180, 3)).toBe(0);
    expect(tileX(180, 3)).toBe(8);
    expect(tileX(0, 3)).toBe(4);
    expect(tileY(0, 3)).toBeCloseTo(4, 12);
    expect(tileY(85.0511287798, 3)).toBeCloseTo(0, 6);
  });

  it("put Strijp-S in OpenStreetMap's tile 135047/87240 at zoom 18", () => {
    // The Sixty5 site origin
    expect(Math.floor(tileX(5.46015, 18))).toBe(135047);
    expect(Math.floor(tileY(51.44648, 18))).toBe(87240);
  });
});

describe("tilesFor", () => {
  // Four tiles across and two down at zoom 10, from the corner of tile 520/340
  const west = (520 / 1024) * 360 - 180;
  const east = (524 / 1024) * 360 - 180;
  const latitude = (y: number) =>
    (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / 1024))) * 180) / Math.PI;
  const bounds: GroundMap["bounds"] = [west, latitude(342), east, latitude(340)];

  it("takes the zoom whose tiles match the image's resolution", () => {
    const tiles = tilesFor({ bounds, width: 1024, height: 512 });
    expect(tiles).toHaveLength(8);
    expect(new Set(tiles.map((tile) => tile.z))).toEqual(new Set([10]));
    for (const tile of tiles) {
      expect(tile.width).toBeCloseTo(256, 6);
      expect(tile.height).toBeCloseTo(256, 6);
    }
    expect(tiles[0]).toMatchObject({ x: 520, y: 340 });
    expect(tiles[0].left).toBeCloseTo(0, 6);
    expect(tiles[0].top).toBeCloseTo(0, 6);
    expect(tiles.at(-1)).toMatchObject({ x: 523, y: 341 });
  });

  it("covers the whole image, scaling the tiles in between zoom levels", () => {
    const tiles = tilesFor({ bounds, width: 1500, height: 750 });
    expect(new Set(tiles.map((tile) => tile.z))).toEqual(new Set([11]));
    expect(Math.min(...tiles.map((tile) => tile.left))).toBeCloseTo(0, 6);
    expect(Math.min(...tiles.map((tile) => tile.top))).toBeCloseTo(0, 6);
    expect(Math.max(...tiles.map((tile) => tile.left + tile.width))).toBeCloseTo(1500, 6);
    expect(Math.max(...tiles.map((tile) => tile.top + tile.height))).toBeCloseTo(750, 6);
    expect(tiles[0].width).toBeCloseTo(1500 / 8, 6);
  });

  it("stops at the maximum zoom", () => {
    const tiles = tilesFor({ bounds, width: 1024 * 2 ** 12, height: 512 * 2 ** 12 }, 19);
    expect(tiles[0].z).toBe(19);
  });

  it("covers bounds that do not start on a tile edge", () => {
    const shifted: GroundMap["bounds"] = [
      tileXToLon(520.5),
      latitude(341.75),
      tileXToLon(522.25),
      latitude(340.2),
    ];
    const tiles = tilesFor({ bounds: shifted, width: 448, height: 396.8 });
    expect(new Set(tiles.map((tile) => tile.x))).toEqual(new Set([520, 521, 522]));
    expect(new Set(tiles.map((tile) => tile.y))).toEqual(new Set([340, 341]));
    expect(tiles[0].left).toBeCloseTo(-0.5 * 256, 6);
    expect(tiles[0].top).toBeCloseTo(-0.2 * 256, 6);
  });

  function tileXToLon(x: number) {
    return (x / 1024) * 360 - 180;
  }
});

describe("tileUrl", () => {
  it("fills a {z}/{x}/{y} template", () => {
    const tile = { z: 18, x: 1, y: 2, left: 0, top: 0, width: 256, height: 256 };
    expect(tileUrl("https://tile.example/{z}/{x}/{y}.png", tile)).toBe(
      "https://tile.example/18/1/2.png",
    );
  });
});

describe("mapCorners", () => {
  it("takes the bounds' corners through lnglat_to_world, at the map's height", () => {
    const groundMap: GroundMap = {
      bounds: [5, 51, 6, 52],
      width: 100,
      height: 100,
      lnglat_to_world: [2, 0, -10, 0, 3, -153],
      z: -1.5,
      opacity: 1,
    };
    expect(mapCorners(groundMap)).toEqual([
      [0, 0, -1.5],
      [2, 0, -1.5],
      [2, 3, -1.5],
      [0, 3, -1.5],
    ]);
  });
});

describe("isGroundMap", () => {
  it("is false for the empty trait", () => {
    expect(isGroundMap({})).toBe(false);
  });
});

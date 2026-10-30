import { describe, expect, it } from "vitest";
import { MAX_SHARE, MIN_SHARE, clampShare, shareAt } from "./splitter";

describe("shareAt", () => {
  it("puts the separator's middle under the pointer", () => {
    // 1010 px of panes: 1000 px for the two, 10 px of separator
    expect(shareAt(605, 0, 1010, 10)).toBe(60);
    expect(shareAt(405, 100, 1010, 10)).toBe(30);
  });

  it("keeps both panes at least MIN_SHARE wide", () => {
    expect(shareAt(0, 0, 1010, 10)).toBe(MIN_SHARE);
    expect(shareAt(2000, 0, 1010, 10)).toBe(MAX_SHARE);
    expect(clampShare(MIN_SHARE - 1)).toBe(MIN_SHARE);
    expect(clampShare(50)).toBe(50);
  });
});

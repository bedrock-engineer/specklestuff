import { describe, expect, it } from "vitest";
import { gunzipJson } from "./gunzip";

async function gzip(text: string): Promise<ArrayBuffer> {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

describe("gunzipJson", () => {
  it("reads an ArrayBuffer", async () => {
    expect(await gunzipJson(await gzip('[[{"id": "root"}]]'))).toEqual([[{ id: "root" }]]);
  });

  it("reads the part of a buffer a DataView shows, as anywidget hands Bytes over", async () => {
    const packed = new Uint8Array(await gzip('{"a": 1}'));
    const padded = new Uint8Array(packed.length + 8);
    padded.set(packed, 4);
    expect(await gunzipJson(new DataView(padded.buffer, 4, packed.length))).toEqual({ a: 1 });
  });
});

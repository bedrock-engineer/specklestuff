/** One Speckle v3 object as parsed JSON */
export interface SpeckleObject {
  id: string;
  speckle_type?: string;
  applicationId?: string;
  [field: string]: unknown;
}

/** Axes and a label at a named point: the TS mirror of the Python `Marker` */
export interface Marker {
  name: string;
  /** [x, y, z] in the viewer's world: metres */
  position: [number, number, number];
  /** Length of the axes in metres */
  size?: number;
}

/** The synced traits: the TS mirror of SpeckleViewer's traitlets, change them together */
export interface SpeckleViewerModel {
  /** Gzipped JSON of one or more models, each an array of v3 objects, root first */
  objects_gz: DataView<ArrayBuffer> | ArrayBuffer;
  /** Height in pixels; null: the height follows the width by aspect_ratio */
  height: number | null;
  /** Width over height, when height is null */
  aspect_ratio: number;
  /** Raw data of the selected elements, without their geometry and children */
  selected: Record<string, unknown>[];
  markers: Marker[];
  /** Set by the front end: the number of elements the viewer draws, as a click selects them */
  object_count: number;
  /** Set by the front end: [xmin, ymin, zmin, xmax, ymax, zmax] in metres, [] when empty */
  scene_bbox: number[];
}

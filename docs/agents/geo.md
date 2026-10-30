# The surroundings: GeoSpeckleViewer and specklewidgets.geo

`GeoSpeckleViewer` (`src/specklewidgets/geospeckle_viewer.py`) is a `SpeckleViewer` subclass
with its own `_esm`, and the `GroundMap` and `Tileset` TypedDicts of its traits. Its JS entry
adds the ground map (`packages/geospeckle-viewer/src/lib/ground-map.ts`, `map-tiles.ts`) and the 3D Tiles
(`context-tiles.ts`, `hide-features.ts`) to the shared viewer. `specklewidgets.geo` (bimpolars
and its pyproj) builds the surroundings of a georeferenced BimDataFrame: `osm_ground_map`,
`pdok_3d_buildings`, `site_3d_tiles`, `bag_panden_under`. `examples/sixty5_geo.py` shows Sixty5's structural model at
Strijp-S.

## The world

- The viewer's world is the models' coordinates in metres. `specklewidgets.geo` goes from it to
  ECEF and back through one matrix, `bimpolars.geobim.linearized_site_to_ecef` of the
  BimDataFrame's CRS (`_World`), and between ECEF and longitude/latitude with pyproj's
  EPSG:4978/4979 conversion: the ground map, the 3D BAG (`ecef_to_world` is its inverse) and
  the BAG panden line up with each other exactly, and with PROJ's own transformation (by way of
  the Engineering CRS's base, as `with_geog` goes) to under a centimetre over Sixty5
  (`test_the_viewers_world_is_proj_to_a_centimetre`).
- A model must sit near its CRS's origin: a frame in EPSG:7415 would be linearized at RD's
  origin, off the map.

## The ground map

- `osm_ground_map`'s affine from longitude and latitude to the world is good to 11 mm at the
  corners of Sixty5's 500 m map: the meridians converge.
- The front end draws OSM's raster tiles into a canvas itself (`map-tiles.ts`: the zoom whose
  tiles come closest to the image's resolution, up to 19), where geospeckle rendered a MapLibre
  map off-screen: no MapLibre and no second WebGL context.
- The map and the tiles are on the PROPS layer and added to the scene directly, as the markers
  are, so `object_count` and `scene_bbox` leave them out. `GroundInView` pushes the camera's far
  plane out to the map's farthest corner every frame.

## The 3D Tiles

- `ContextTiles` updates the tiles for the camera every frame and hides the features of each
  tile as it arrives (`hideFeaturesWithin`: more than half of a feature's vertices in a
  polygon; three.js 0.140 returns quantized positions as stored, so they are scaled first).
  `surroundings` reports the map's plane, the tile contents loaded, the features hidden in them
  and the heights those span in the world, 250 ms after the last change.
- PDOK's 3D BAG is a tree of external tilesets; `site_3d_tiles` walks it along the tiles that
  overlap the area (3d-tiles-renderer 0.3.46 would fetch every child of a tile without content,
  half the country's tilesets) and gives a one-level tileset of the finest tiles there (and of
  the content of the tiles that refine by `ADD` on the way).
- `bag_panden_under` keeps a pand with more than half of its area under the footprint;
  `pdok_3d_buildings` grows the `hide_within` polygons by `hide_margin` (0.5 m) so that a
  building's vertices on its pand's outline count as within.

## Heights and the NSGI grids

PDOK's 3D Tiles are at ellipsoidal heights, and the world's z = 0 is the site origin's NAP
height, so the 3D BAG stands on the ground map only with the NSGI grids. Without them PROJ
passes NAP off as ellipsoidal heights (bimpolars warns): the model sits within about a metre of
PDOK's data in plan, and the 3D BAG floats 44 m above it.

- The example turns PROJ's network on (`pyproj.network.set_network_enabled(True)`, as
  bimpolars' Sixty5 notebook does), so PROJ fetches the grids; CI's pytest sets
  `PROJ_NETWORK=ON`, so that the tests of the `grids` fixture run, and the offline stand-in's
  tile stands at the true height.
- The tiles' `region` heights say nothing about it: both of PDOK's leaves at Sixty5 (zoom 9,
  2026-10-30) start at 23.91 m, where the ground is at 62.5 m ellipsoidal (18.6 m NAP). What
  does is `surroundings.hidden_heights`, the world heights of the 3D BAG's Sixty5 as drawn: the
  geo e2e wants its bottom within 3 m of the map (z = 0, AHN4 at the site origin).
- In a cloud container, put the grids in place before the geo e2e ([testing.md](testing.md)).

## Known numbers

Sixty5's structural model (`tests/test_geo.py`, `e2e/geo.test.mjs`): read_ifc takes 14 s; its
BAG pand (under the slabs and footings) is `0772100001025175`, and the 3D BAG over the map two
zoom-9 tiles (PDOK, 2026-10-30); 1363 rows drawn (with a mesh, less 1284 openings), bbox x
-2.24..33.585, y -0.001..55.69, z -30.4..56.64 m in the site grid; the plan extent of all rows'
`bbox` turned by -50.36 degrees gives `osm_ground_map` bounds 5.457095..5.464129 E,
51.444345..51.448716 N with the 150 m margin, a 2048 x 2042 image (without the grids). The site
origin is at 5.4601517 E, 51.4464756 N, ellipsoidal height 62.544 m (NAP 18.625 m and
NLGEO2018's 43.919 m) with the NSGI grids, and at 5.460153 E, 51.446476 N, 18.625 m without
them. The live e2e (CI, 2026-10-30) draws the 3D BAG's Sixty5 from 0.04 to 57.28 m: PDOK's
heights are ellipsoidal, and with the grids the 3D BAG stands on the map.

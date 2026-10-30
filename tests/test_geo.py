"""The surroundings of a georeferenced BimDataFrame: specklewidgets.geo on Sixty5.

The structural model of Sixty5 (Strijp-S, Eindhoven) read with read_ifc and placed with its
derived Engineering CRS (bimpolars' docs/agents/test-data.md has the numbers). PDOK's APIs are
out of reach from some environments (the cloud containers), so the tests of what is read from
them answer with synthetic tilesets and panden; the tests marked by the ``pdok`` fixture read
the real ones and skip where api.pdok.nl does not answer.
"""

import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import numpy as np
import pytest

# bimpolars (with polars, shapely and numpy) is a dev dependency, pyproj the [geo] extra
data = pytest.importorskip("bimpolars.data")
bimpolars = pytest.importorskip("bimpolars")
geobim = pytest.importorskip("bimpolars.geobim")
geo = pytest.importorskip("specklewidgets.geo")
pyproj = pytest.importorskip("pyproj")
pl = pytest.importorskip("polars")
shapely = pytest.importorskip("shapely")
pytest.importorskip("shapely.affinity")

from specklewidgets import GeoSpeckleViewer  # noqa: E402

SIXTY5 = "sixty5_O-S1-CON-structural-engineering.ifc"
SIXTY5_ORIGIN = (160071.5, 384156.5, 18.625)
"""E, N in RD New and NAP height of the site origin (IFC-GeoReferencer, AHN4)."""
SIXTY5_ROTATION = math.degrees(math.atan2(-0.7700680491484481, 0.6379617540893054))
SIXTY5_LONLAT = (5.46015, 51.44648)
"""The site origin to 0.00001 degrees, which is under a metre."""
SIXTY5_PANDEN = ["0772100001025175"]
"""The BAG panden mostly under the slabs and footings (``identificatie``): Sixty5's own."""
NLGEO2018_AT_SIXTY5 = 43.919
"""The quasi-geoid height at the site origin (NLGEO2018): its ellipsoidal less its NAP height."""

METRES_PER_DEGREE = 111_320.0
"""Of latitude, and of longitude at the equator: enough to compare positions to a centimetre."""


@pytest.fixture(scope="module")
def plain() -> Any:
    """Sixty5 as read_ifc gives it: in a plain EngineeringCRS, in millimetres."""
    return bimpolars.read_ifc(data.fetch(SIXTY5))


@pytest.fixture(scope="module")
def site(plain) -> Any:
    """Sixty5 in its derived Engineering CRS: the same coordinates, now on earth."""
    crs = geobim.derived_engineering_crs(
        "EPSG:7415",
        *SIXTY5_ORIGIN,
        SIXTY5_ROTATION,
        unit=bimpolars.crs.linear_unit(plain.crs),
        name="Sixty5",
    )
    return geobim.set_crs(plain, crs)


@pytest.fixture(scope="module")
def world(site) -> Any:
    return geo._World(site.crs)


@pytest.fixture(scope="module")
def ground_map(site) -> Any:
    return geo.osm_ground_map(site)


@pytest.fixture(scope="module")
def grids() -> None:
    """Skips where PROJ has neither the NSGI grids nor the network to fetch them."""
    if not pyproj.transformer.TransformerGroup("EPSG:7415", "EPSG:4979").best_available:
        pytest.skip("no NSGI grids: install them, or set PROJ_NETWORK=ON for cdn.proj.org")


def slabs_and_footings(site) -> Any:
    """The slabs and footings with their footprints, and the storeys that place them."""
    keep = pl.col("class").is_in(["IfcSlab", "IfcFooting"]) | pl.col("mesh").is_null()
    return bimpolars.simple_features(site.with_frame(site.frame.filter(keep)))


def plan_extent_metres(site) -> np.ndarray:
    return np.array(geo._plan_extent(site)) / 1000


# The ground map


def test_the_ground_map_is_at_strijp_s(ground_map):
    west, south, east, north = ground_map["bounds"]
    assert west < SIXTY5_LONLAT[0] < east
    assert south < SIXTY5_LONLAT[1] < north
    # The model, 36 by 57 m and turned by 50 degrees, with 150 m around it
    assert 400 < (east - west) * METRES_PER_DEGREE * math.cos(math.radians(51.45)) < 600
    assert 400 < (north - south) * METRES_PER_DEGREE < 600


def lnglat_to_world(ground_map, lon, lat):
    a, b, c, d, e, f = ground_map["lnglat_to_world"]
    return np.column_stack([a * lon + b * lat + c, d * lon + e * lat + f])


def test_the_ground_maps_affine_is_the_viewers_world_to_a_centimetre(ground_map, world):
    # A degree of longitude is 1e-4 shorter at the map's north edge than at its south edge,
    # which the affine fit spreads to 11 mm at the corners
    west, south, east, north = ground_map["bounds"]
    lon, lat = (
        g.ravel() for g in np.meshgrid(np.linspace(west, east, 7), np.linspace(south, north, 7))
    )
    exact = world.from_lonlat(lon, lat, world.height(0.0))[:, :2]
    assert np.abs(lnglat_to_world(ground_map, lon, lat) - exact).max() < 0.015


def test_the_ground_map_puts_the_site_origin_at_the_worlds(ground_map):
    origin = lnglat_to_world(ground_map, np.array([SIXTY5_LONLAT[0]]), np.array([SIXTY5_LONLAT[1]]))
    assert np.hypot(*origin[0]) < 1.0


def test_the_ground_map_covers_the_model_and_the_margin(site, ground_map):
    west, south, east, north = ground_map["bounds"]
    corners = lnglat_to_world(
        ground_map, np.array([west, east, east, west]), np.array([south, south, north, north])
    )
    plane = shapely.Polygon(corners)
    xmin, ymin, xmax, ymax = plan_extent_metres(site)
    model_and_margin = shapely.box(xmin - 150, ymin - 150, xmax + 150, ymax + 150)
    # The model's corners lie on the map's edges, to the affine's centimetre
    assert plane.buffer(0.02).contains(model_and_margin)


def test_the_ground_maps_pixels_are_square_on_the_ground(ground_map):
    west, south, east, north = ground_map["bounds"]
    across = (east - west) * math.cos(math.radians((south + north) / 2))
    assert ground_map["height"] / ground_map["width"] == pytest.approx(
        (north - south) / across, rel=2e-3
    )
    assert ground_map["width"] == 2048
    assert (ground_map["z"], ground_map["opacity"]) == (0.0, 0.85)


def test_the_viewers_world_is_proj_to_a_centimetre(site, world):
    # with_geog moves the footprints through PROJ's own transformation, by way of the
    # Engineering CRS's base, where the world goes through one linearized 4x4
    features = slabs_and_footings(site)
    geog = geobim.with_geog(features).frame
    rows = geog.filter(pl.col("footprint").is_not_null())
    model = shapely.get_coordinates(shapely.from_wkb(rows["footprint"].to_numpy()), include_z=True)
    exact = shapely.get_coordinates(shapely.from_wkb(rows["geog"].to_numpy()), include_z=True)
    linear = world.to_lonlat(model / 1000)
    north = (linear[:, 1] - exact[:, 1]) * METRES_PER_DEGREE
    east = (linear[:, 0] - exact[:, 0]) * METRES_PER_DEGREE * math.cos(math.radians(51.45))
    assert np.hypot(north, east).max() < 0.01
    assert np.abs(linear[:, 2] - exact[:, 2]).max() < 0.01


def test_the_world_stands_at_ellipsoidal_heights(world, grids):
    # PDOK's 3D Tiles are in ECEF, at ellipsoidal heights, and the ground map lies at the
    # world's z = 0, the site origin's NAP height. Without the grids PROJ passes that NAP
    # height off as an ellipsoidal one, and the 3D BAG would float 44 m above the map
    nap = SIXTY5_ORIGIN[2]
    assert world.height(0.0) == pytest.approx(nap + NLGEO2018_AT_SIXTY5, abs=0.01)


def test_a_plain_engineering_crs_is_not_on_earth(plain):
    with pytest.raises(ValueError, match="EngineeringCRS"):
        geo.osm_ground_map(plain)


# The 3D BAG, from a synthetic tileset


def region(west, south, east, north, low=0.0, high=100.0):
    return [math.radians(v) for v in (west, south, east, north)] + [low, high]


SITE_REGION = region(5.45, 51.44, 5.47, 51.45)
FAR_REGION = region(4.0, 52.0, 4.1, 52.1)
TRANSFORM = np.eye(4)
TRANSFORM[:3, 3] = [3_900_000.0, 370_000.0, 4_970_000.0]


def synthetic_tilesets() -> dict[str, Any]:
    """A root over the country, with one external tileset at the site and one far away."""
    return {
        "https://tiles.test/3dtiles?f=json": {
            "asset": {"version": "1.1"},
            "root": {
                "boundingVolume": {"region": region(3, 50, 8, 54)},
                "geometricError": 500,
                "children": [
                    {
                        "boundingVolume": {"region": SITE_REGION},
                        "geometricError": 100,
                        "content": {"uri": "sub/eindhoven.json?f=json"},
                    },
                    {
                        "boundingVolume": {"region": FAR_REGION},
                        "geometricError": 100,
                        "content": {"uri": "sub/amsterdam.json"},
                    },
                ],
            },
        },
        "https://tiles.test/sub/eindhoven.json?f=json": {
            "asset": {"version": "1.1"},
            "root": {
                "boundingVolume": {"region": SITE_REGION},
                "transform": TRANSFORM.flatten(order="F").tolist(),
                "geometricError": 50,
                "content": {"uri": "t/coarse.glb"},
                "children": [
                    {
                        "boundingVolume": {"region": region(5.455, 51.44, 5.465, 51.45)},
                        "geometricError": 0,
                        "content": {"uri": "t/strijp.glb"},
                    },
                    {
                        "boundingVolume": {"region": region(5.469, 51.449, 5.47, 51.45)},
                        "geometricError": 0,
                        "content": {"uri": "t/elsewhere.glb"},
                    },
                ],
            },
        },
    }


class Fetched:
    """The URLs the code under test asked for, and the answers it gets."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.answers: dict[str, Any] = synthetic_tilesets()
        self.bag: Any = None
        """Answers the BAG's queries: a function of the URL."""

    def __call__(self, url: str) -> Any:
        self.asked.append(url)
        if url in self.answers:
            return self.answers[url]
        if url.startswith(geo.PDOK_BAG_PANDEN) and self.bag is not None:
            return self.bag(url)
        raise urllib.error.URLError(f"{url} is not in the test's answers")


@pytest.fixture
def fetched(monkeypatch) -> Fetched:
    """Answers PDOK's URLs with the synthetic tilesets and panden."""
    fetch = Fetched()
    monkeypatch.setattr(geo, "_fetch_json", fetch)
    return fetch


def test_site_3d_tiles_keeps_the_finest_tiles_over_the_site(fetched):
    tileset = geo.site_3d_tiles("https://tiles.test/3dtiles?f=json", (5.455, 51.442, 5.466, 51.449))
    leaves = tileset["root"]["children"]
    assert [leaf["content"]["uri"] for leaf in leaves] == ["https://tiles.test/sub/t/strijp.glb"]
    assert leaves[0]["transform"] == TRANSFORM.flatten(order="F").tolist()
    assert leaves[0]["geometricError"] == 0
    assert tileset["root"]["boundingVolume"]["region"] == pytest.approx(
        region(5.455, 51.44, 5.465, 51.45)
    )
    assert tileset["root"]["refine"] == "ADD"
    # The tileset far away is never fetched
    assert fetched.asked == [
        "https://tiles.test/3dtiles?f=json",
        "https://tiles.test/sub/eindhoven.json?f=json",
    ]


def test_site_3d_tiles_takes_a_coarse_tile_when_no_child_overlaps(fetched):
    # Over the site's region but outside both children
    tileset = geo.site_3d_tiles(
        "https://tiles.test/3dtiles?f=json", (5.451, 51.4405, 5.452, 51.441)
    )
    uris = [leaf["content"]["uri"] for leaf in tileset["root"]["children"]]
    assert uris == ["https://tiles.test/sub/t/coarse.glb"]


def test_site_3d_tiles_keeps_what_a_tile_refines_by_addition(fetched):
    # The root of the external tileset adds its children to its own content, rather than
    # being replaced by them
    fetched.answers["https://tiles.test/sub/eindhoven.json?f=json"]["root"]["refine"] = "ADD"
    tileset = geo.site_3d_tiles("https://tiles.test/3dtiles?f=json", (5.455, 51.442, 5.466, 51.449))
    uris = [leaf["content"]["uri"] for leaf in tileset["root"]["children"]]
    assert uris == ["https://tiles.test/sub/t/coarse.glb", "https://tiles.test/sub/t/strijp.glb"]


def test_site_3d_tiles_needs_a_tile(fetched):
    with pytest.raises(ValueError, match="no tile"):
        geo.site_3d_tiles("https://tiles.test/3dtiles?f=json", (0.0, 0.0, 0.1, 0.1))


def test_pdok_3d_buildings_places_the_tiles_in_the_world(site, world, fetched, monkeypatch):
    monkeypatch.setattr(geo, "PDOK_3D_BUILDINGS", "https://tiles.test/3dtiles?f=json")
    xmin, ymin, xmax, ymax = geo._plan_extent(site)
    hide = shapely.box(xmin, ymin, xmax, ymax)
    entry = geo.pdok_3d_buildings(site, hide_within=[hide])
    ecef_to_world = np.array(entry["ecef_to_world"]).reshape(4, 4, order="F")
    assert ecef_to_world @ geobim.linearized_site_to_ecef(site.crs) == pytest.approx(
        np.eye(4), abs=1e-9
    )
    assert entry["attribution"] == geo.PDOK_3D_ATTRIBUTION
    assert [leaf["content"]["uri"] for leaf in entry["tileset"]["root"]["children"]] == [
        "https://tiles.test/sub/t/strijp.glb"
    ]
    # The model's plan in metres, 0.5 m wider, as one ring
    (rings,) = entry["hide_within"]
    assert len(rings) == 1
    hidden = shapely.Polygon(rings[0])
    assert hidden.bounds == pytest.approx(
        (xmin / 1000 - 0.5, ymin / 1000 - 0.5, xmax / 1000 + 0.5, ymax / 1000 + 0.5), abs=1e-9
    )


def test_pdok_3d_buildings_covers_the_ground_map_by_default(site, ground_map, fetched, monkeypatch):
    seen: list[Any] = []
    monkeypatch.setattr(geo, "site_3d_tiles", lambda url, bounds: seen.append(bounds) or {})
    geo.pdok_3d_buildings(site)
    assert seen[0] == pytest.approx(ground_map["bounds"])


def test_hide_within_keeps_holes_and_parts(site, fetched, monkeypatch):
    monkeypatch.setattr(geo, "site_3d_tiles", lambda url, bounds: {})
    ring = shapely.box(0, 0, 10_000, 10_000).difference(shapely.box(4000, 4000, 6000, 6000))
    parts = shapely.MultiPolygon([ring, shapely.box(20_000, 0, 30_000, 10_000)])
    entry = geo.pdok_3d_buildings(site, hide_within=[parts], hide_margin=0.0)
    holed, plain = sorted(entry["hide_within"], key=len, reverse=True)
    assert (len(holed), len(plain)) == (2, 1)
    assert shapely.Polygon(holed[0], holed[1:]).area == pytest.approx(96.0)
    assert shapely.Polygon(plain[0]).area == pytest.approx(100.0)


# The BAG panden, synthetic


def feature_collection(features, next_url=None):
    links = [{"rel": "next", "href": next_url}] if next_url else []
    return {"type": "FeatureCollection", "features": features, "links": links}


def pand(identificatie: str, polygon_in_model, world) -> dict[str, Any]:
    """A pand of the BAG at a polygon in the model's coordinates."""
    xy = np.asarray(polygon_in_model.exterior.coords) / 1000
    lonlat = world.to_lonlat(np.column_stack([xy, np.zeros(len(xy))]))
    return {
        "type": "Feature",
        "properties": {"identificatie": identificatie},
        "geometry": {"type": "Polygon", "coordinates": [lonlat[:, :2].tolist()]},
    }


def test_bag_panden_under_finds_the_pand_under_the_model(site, world, fetched):
    xmin, ymin, xmax, ymax = geo._plan_extent(site)
    footprint = shapely.box(xmin, ymin, xmax, ymax)
    # The pand under the model, a neighbour 60 m east, and one that is 40 % under it
    under = pand("0772100000000001", footprint, world)
    neighbour = pand("0772100000000002", shapely.affinity.translate(footprint, 60_000), world)
    partly = shapely.box(xmax - 4000, ymin, xmax + 6000, ymin + 10_000)
    pages = {
        "first": feature_collection([under, neighbour], next_url="https://api.test/next"),
        "https://api.test/next": feature_collection([pand("0772100000000003", partly, world)]),
    }
    queries: list[dict[str, list[str]]] = []

    def bag(url: str) -> Any:
        queries.append(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query))
        return pages["first"]

    fetched.bag = bag
    fetched.answers["https://api.test/next"] = pages["https://api.test/next"]

    panden = geo.bag_panden_under(site, footprint)

    assert list(panden) == ["0772100000000001"]
    # Back where it was, to well under a millimetre
    assert shapely.hausdorff_distance(panden["0772100000000001"], footprint) < 1e-3
    # The query's bbox holds the footprint, in longitude and latitude
    west, south, east, north = map(float, queries[0]["bbox"][0].split(","))
    assert west < SIXTY5_LONLAT[0] < east and south < SIXTY5_LONLAT[1] < north
    assert fetched.asked[-1] == "https://api.test/next"


def test_bag_panden_under_goes_by_the_footprints(site, world, fetched):
    features = slabs_and_footings(site)
    outline = shapely.union_all(
        shapely.force_2d(shapely.from_wkb(features.frame["footprint"].drop_nulls().to_numpy()))
    )
    fetched.bag = lambda url: feature_collection(
        [pand("0772100000000001", shapely.convex_hull(outline), world)]
    )
    assert list(geo.bag_panden_under(features)) == ["0772100000000001"]


def test_bag_panden_under_needs_a_footprint(site):
    with pytest.raises(ValueError, match="simple_features"):
        geo.bag_panden_under(site)


# The real thing: PDOK


@pytest.fixture(scope="module")
def pdok() -> None:
    try:
        urllib.request.urlopen(f"{geo.PDOK_BAG_PANDEN}?f=json&limit=1", timeout=15).close()
    except (urllib.error.URLError, TimeoutError) as error:
        pytest.skip(f"api.pdok.nl is out of reach: {error}")


@pytest.fixture(scope="module")
def sixty5_panden(pdok, site) -> dict[str, Any]:
    features = slabs_and_footings(site)
    return geo.bag_panden_under(features)


def test_sixty5_stands_on_its_bag_pand(site, sixty5_panden):
    # The panden are picked for lying under the model, so the id is what tells that the
    # model stands where it should
    bounds = {key: pand.bounds for key, pand in sixty5_panden.items()}
    assert list(sixty5_panden) == SIXTY5_PANDEN, f"BAG panden under Sixty5: {bounds}"


@pytest.fixture(scope="module")
def sixty5_3d_bag(site, sixty5_panden) -> Any:
    return geo.pdok_3d_buildings(site, hide_within=sixty5_panden.values())


def test_the_3d_bag_has_tiles_at_sixty5(sixty5_3d_bag, sixty5_panden):
    leaves = sixty5_3d_bag["tileset"]["root"]["children"]
    assert len(leaves) >= 1
    west, south, east, north = sixty5_3d_bag["tileset"]["root"]["boundingVolume"]["region"][:4]
    lon, lat = (math.radians(value) for value in SIXTY5_LONLAT)
    assert west < lon < east and south < lat < north
    assert len(sixty5_3d_bag["hide_within"]) == len(sixty5_panden)


# The widget


def test_geo_speckle_viewer_takes_the_surroundings(site, ground_map):
    tileset = {"tileset": {"root": {}}, "ecef_to_world": np.eye(4).ravel().tolist()}
    viewer = GeoSpeckleViewer(ground_map=ground_map, tilesets=(tileset,))
    assert viewer.ground_map == ground_map
    assert viewer.tilesets == [tileset]
    assert viewer.surroundings == {
        "ground_map": [],
        "tiles": 0,
        "hidden_features": 0,
        "hidden_heights": [],
    }

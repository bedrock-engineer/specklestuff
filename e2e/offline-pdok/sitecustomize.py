"""Answers PDOK's APIs for the offline headless test of examples/sixty5_geo.py.

`npm run e2e` puts this folder on PYTHONPATH when api.pdok.nl is out of reach (the cloud
containers), so that Python imports it at startup. It answers urllib's requests to
api.pdok.nl, which specklewidgets.geo makes, with a 3D BAG and a BAG of its own around the
Sixty5 site; e2e/geo.test.mjs serves the 3D BAG's one tile (TILE_URL) and the map tiles.
Other requests go out as they would.

Everything sits in the east-north-up frame of the Sixty5 site origin: the pand is a square
around the model's middle, under its slabs, and the tile holds the boxes of BOXES (in
e2e/geo.test.mjs), of which only the first stands on the pand.
"""

import io
import json
import math
import urllib.error
import urllib.request
from typing import Any

ORIGIN = (5.460153, 51.446476, 18.625)
"""The Sixty5 site origin: longitude, latitude, ellipsoidal height (NAP passed off as it)."""

MIDDLE = (31.9, 6.1)
"""The model's middle, east and north of its origin, in metres: the site grid's (15.7,
28.5) m turned by -50.36 degrees."""

PAND_HALF_SIZE = 6.0
"""Half the pand's size in metres: within the slabs."""

TILE_URL = "https://tiles.e2e.test/boxes.glb"

_A = 6_378_137.0
_E2 = 6.694379990141317e-3
"""WGS 84's semi-major axis and first eccentricity squared."""


def _ecef(lon: float, lat: float, height: float) -> list[float]:
    lam, phi = math.radians(lon), math.radians(lat)
    n = _A / math.sqrt(1 - _E2 * math.sin(phi) ** 2)
    return [
        (n + height) * math.cos(phi) * math.cos(lam),
        (n + height) * math.cos(phi) * math.sin(lam),
        (n * (1 - _E2) + height) * math.sin(phi),
    ]


def _enu_to_ecef() -> list[float]:
    """The column-major 4x4 from the origin's east-north-up frame to ECEF."""
    lam, phi = math.radians(ORIGIN[0]), math.radians(ORIGIN[1])
    east = [-math.sin(lam), math.cos(lam), 0.0]
    north = [-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)]
    up = [math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)]
    return [*east, 0.0, *north, 0.0, *up, 0.0, *_ecef(*ORIGIN), 1.0]


def _lonlat(east: float, north: float) -> list[float]:
    """A point east and north of the origin, to well under a millimetre over tens of metres."""
    phi = math.radians(ORIGIN[1])
    w = math.sqrt(1 - _E2 * math.sin(phi) ** 2)
    meridian = _A * (1 - _E2) / w**3
    prime = _A / w
    return [
        ORIGIN[0] + math.degrees(east / (prime * math.cos(phi))),
        ORIGIN[1] + math.degrees(north / meridian),
    ]


def _tileset() -> dict[str, Any]:
    west, south = (math.radians(v - 0.01) for v in ORIGIN[:2])
    east, north = (math.radians(v + 0.01) for v in ORIGIN[:2])
    return {
        "asset": {"version": "1.1"},
        "geometricError": 100,
        "root": {
            "boundingVolume": {"region": [west, south, east, north, -100.0, 200.0]},
            "geometricError": 0,
            "refine": "ADD",
            "transform": _enu_to_ecef(),
            "content": {"uri": TILE_URL},
        },
    }


def _panden() -> dict[str, Any]:
    x, y, half = *MIDDLE, PAND_HALF_SIZE
    corners = [
        (x - half, y - half),
        (x + half, y - half),
        (x + half, y + half),
        (x - half, y + half),
    ]
    ring = [_lonlat(*corner) for corner in [*corners, corners[0]]]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"identificatie": "0772100000e2e000"},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
        "links": [],
    }


def _answer(url: str) -> Any:
    if "/3d-basisvoorziening/" in url:
        return _tileset()
    if "/bag/" in url:
        return _panden()
    raise urllib.error.URLError(f"the offline PDOK has no {url}")


_urlopen = urllib.request.urlopen


def _offline_urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
    full_url = url.full_url if isinstance(url, urllib.request.Request) else str(url)
    if full_url.startswith("https://api.pdok.nl/"):
        return io.BytesIO(json.dumps(_answer(full_url)).encode())
    return _urlopen(url, *args, **kwargs)


urllib.request.urlopen = _offline_urlopen

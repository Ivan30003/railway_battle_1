from __future__ import annotations

import math
from pathlib import Path

import pytest

from game.core.errors import MapError
from game.core.map_loader import load_map, parse_map
from game.core.tilemap import Direction, Tile

ROOT = Path(__file__).resolve().parents[1]

RING = """\
START=0,0
DIR=RIGHT
RD SH LD
SV 00 SV
RU SH LU
"""

CROSSING = """\
START=0,0
DIR=RIGHT
RD XX LD
SV 00 SV
RU SH LU
"""

FIGURE_EIGHT = """\
START=1,1
DIR=LEFT
RD LD 00
RU XX LD
00 RU LU
"""


def test_simple_ring_parses() -> None:
    map_data = parse_map(RING, tile_size=32)

    assert map_data.width == 3
    assert map_data.height == 3
    assert map_data.start == (0, 0)
    assert map_data.direction is Direction.EAST
    assert len(map_data.route_tiles) == 8
    assert map_data.track_tile_count == 8
    # Curved turns replace the sharp corners, so the route is shorter than the
    # old centre-to-centre polyline but still spans the ring.
    assert 208.0 < map_data.route_length < 256.0
    assert len(map_data.route.points) > len(map_data.route_tiles)
    assert map_data.route.sample(0.0).position == pytest.approx((16.0, 32.0))
    assert map_data.pixel_size == (96, 96)
    assert map_data.grid.get(0, 0) is Tile.TURN_DOWN_RIGHT


def test_curved_turns_can_be_disabled() -> None:
    map_data = parse_map(RING, tile_size=32, curved_turns=False)

    assert map_data.route_length == pytest.approx(8 * 32)
    assert len(map_data.route.points) == 8
    assert map_data.route.sample(0.0).position == pytest.approx((16.0, 16.0))


def test_crossing_is_passed_straight_through() -> None:
    map_data = parse_map(CROSSING, tile_size=32)

    assert map_data.route_tiles[0] == (0, 0)
    assert map_data.route_tiles[1] == (1, 0)
    assert map_data.route_tiles[2] == (2, 0)
    assert map_data.route_tiles.count((1, 0)) == 1
    assert 208.0 < map_data.route_length < 256.0


def test_shipped_map2_crossing_is_passed_vertically_and_horizontally() -> None:
    map_data = load_map(ROOT / "maps" / "map2.txt", tile_size=32)
    crossings = [
        (x, y) for x, y, tile in map_data.grid.iter_tiles() if tile is Tile.CROSSING
    ]

    assert crossings == [(11, 6)]
    crossing = crossings[0]
    assert map_data.route_tiles.count(crossing) == 2

    passages = []
    for index, coord in enumerate(map_data.route_tiles):
        if coord != crossing:
            continue
        previous = map_data.route_tiles[index - 1]
        following = map_data.route_tiles[(index + 1) % len(map_data.route_tiles)]
        passages.append((previous, following))

    # One pass arrives from the north and leaves south, the other arrives from
    # the west and leaves east: the crossing keeps the incoming direction.
    assert ((11, 5), (11, 7)) in passages
    assert ((10, 6), (12, 6)) in passages


def test_figure_eight_uses_crossing_twice() -> None:
    map_data = parse_map(FIGURE_EIGHT, tile_size=32)

    assert map_data.start == (1, 1)
    assert map_data.direction is Direction.WEST
    assert map_data.route_tiles.count((1, 1)) == 2
    assert len(map_data.route_tiles) == 8
    assert 0.0 < map_data.route_length < 8 * 32


def test_curved_route_turns_gradually() -> None:
    map_data = parse_map(RING, tile_size=32)
    points = map_data.route.points
    count = len(points)

    largest = 0.0
    for index in range(count):
        first = points[index]
        second = points[(index + 1) % count]
        third = points[(index + 2) % count]
        a = (second[0] - first[0], second[1] - first[1])
        b = (third[0] - second[0], third[1] - second[1])
        a_len = math.hypot(*a)
        b_len = math.hypot(*b)
        if a_len == 0.0 or b_len == 0.0:
            continue
        cosine = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / (a_len * b_len)))
        largest = max(largest, math.degrees(math.acos(cosine)))

    assert largest < 10.0


def test_comments_bom_crlf_and_header_order() -> None:
    text = (
        "\ufeff# a comment\r\n"
        "DIR = right\r\n"
        "START = 1,1  # inline comment\r\n"
        "\r\n"
        "00 00 00 00 00\r\n"
        "00 RD SH LD 00\r\n"
        "00 SV 00 SV 00\r\n"
        "00 RU SH LU 00\r\n"
        "00 00 00 00 00\r\n"
    )

    map_data = parse_map(text, tile_size=16)

    assert map_data.start == (1, 1)
    assert map_data.direction is Direction.EAST
    assert map_data.pixel_size == (80, 80)
    assert len(map_data.route_tiles) == 8


@pytest.mark.parametrize("name", ["map1.txt", "map2.txt"])
def test_shipped_maps_are_valid(name: str) -> None:
    map_data = load_map(ROOT / "maps" / name, tile_size=32)

    assert map_data.pixel_size == (20 * 32, 15 * 32)
    assert map_data.track_tile_count == len(set(map_data.route_tiles))
    assert map_data.route_length > 0
    first = map_data.route.sample(0.0)
    middle = map_data.route.sample(map_data.route_length / 2.0)
    start_centre = map_data.grid.tile_center(*map_data.start, map_data.tile_size)
    previous_centre = map_data.grid.tile_center(
        *map_data.route_tiles[-1], map_data.tile_size
    )
    entry = (
        (start_centre[0] + previous_centre[0]) / 2.0,
        (start_centre[1] + previous_centre[1]) / 2.0,
    )
    assert first.position == pytest.approx(entry)
    assert middle.position != pytest.approx(first.position)
    assert map_data.route.sample(map_data.route_length).position == pytest.approx(
        first.position
    )


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(MapError, match="Cannot read map"):
        load_map(tmp_path / "missing.txt")


@pytest.mark.parametrize(
    "text, message",
    [
        ("DIR=RIGHT\nSH\n", "START"),
        ("START=0,0\nSH\n", "DIR"),
        ("START=5,0\nDIR=RIGHT\nSH\n", "outside"),
        ("START=1,0\nDIR=LEFT\nSH 00\n", "empty tile"),
        ("START=0,0\nDIR=UP\nRD SH LD\nSV 00 SV\nRU SH LU\n", "does not connect UP"),
        ("START=0,0\nDIR=RIGHT\nSH SH\n00\n", "expected 2 tiles"),
        ("START=0,0\nDIR=RIGHT\nZZ\n", "Unknown tile token"),
        ("START=0,0\nDIR=RIGHT\nSH SH\n", "leaves the map"),
        (
            "START=0,0\nDIR=RIGHT\nRD SH LD\nSV 00 SV\nRU SH LU\n00 SH 00\n",
            "Stray track tile",
        ),
        ("START=0,0\nSTART=0,0\nDIR=RIGHT\nSH\n", "duplicate header"),
        ("START=0,0\nDIR=RIGHT\nSIZE=3\nSH\n", "unknown header"),
        ("START=0\nDIR=RIGHT\nSH\n", "START=x,y"),
        ("START=x,0\nDIR=RIGHT\nSH\n", "integers"),
        ("START=0,0\nDIR=SIDEWAYS\nSH\n", "DIR must be one of"),
    ],
)
def test_invalid_maps_raise(text: str, message: str) -> None:
    with pytest.raises(MapError, match=message):
        parse_map(text)

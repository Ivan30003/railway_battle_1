from __future__ import annotations

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
RD X LD
SV 00 SV
RU SH LU
"""

FIGURE_EIGHT = """\
START=1,1
DIR=LEFT
RD LD 00
RU X LD
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
    assert map_data.route_length == pytest.approx(8 * 32)
    assert map_data.pixel_size == (96, 96)
    assert map_data.grid.get(0, 0) is Tile.TURN_DOWN_RIGHT


def test_crossing_is_passed_straight_through() -> None:
    map_data = parse_map(CROSSING, tile_size=32)

    assert map_data.route_tiles[0] == (0, 0)
    assert map_data.route_tiles[1] == (1, 0)
    assert map_data.route_tiles[2] == (2, 0)
    assert map_data.route_tiles.count((1, 0)) == 1
    assert map_data.route_length == pytest.approx(8 * 32)


def test_figure_eight_uses_crossing_twice() -> None:
    map_data = parse_map(FIGURE_EIGHT, tile_size=32)

    assert map_data.start == (1, 1)
    assert map_data.direction is Direction.WEST
    assert map_data.route_tiles.count((1, 1)) == 2
    assert len(map_data.route_tiles) == 8
    assert map_data.route_length == pytest.approx(8 * 32)


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
    assert first.position == pytest.approx(
        map_data.grid.tile_center(*map_data.start, map_data.tile_size)
    )
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

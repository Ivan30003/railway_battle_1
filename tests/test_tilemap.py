from __future__ import annotations

import pytest

from game.core.tilemap import Direction, Tile, TileGrid


def test_direction_opposites() -> None:
    assert Direction.NORTH.opposite is Direction.SOUTH
    assert Direction.EAST.opposite is Direction.WEST
    assert Direction.SOUTH.opposite is Direction.NORTH
    assert Direction.WEST.opposite is Direction.EAST


def test_direction_header_names() -> None:
    assert Direction.from_header("UP") is Direction.NORTH
    assert Direction.from_header("right") is Direction.EAST
    assert Direction.NORTH.header_name == "UP"
    assert Direction.WEST.header_name == "LEFT"


def test_direction_rejects_unknown_header() -> None:
    with pytest.raises(ValueError, match="DIR must be one of"):
        Direction.from_header("SIDEWAYS")


@pytest.mark.parametrize(
    "token, expected",
    [
        ("SV", {Direction.NORTH, Direction.SOUTH}),
        ("SH", {Direction.EAST, Direction.WEST}),
        ("X", {Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST}),
        ("LD", {Direction.SOUTH, Direction.WEST}),
        ("RD", {Direction.SOUTH, Direction.EAST}),
        ("LU", {Direction.NORTH, Direction.WEST}),
        ("RU", {Direction.NORTH, Direction.EAST}),
    ],
)
def test_tile_connections(token: str, expected: set[Direction]) -> None:
    assert Tile.from_token(token).connections == expected


def test_empty_tile_is_not_path() -> None:
    assert not Tile.from_token("00").is_path
    assert Tile.from_token("SH").is_path


def test_unknown_token_raises() -> None:
    with pytest.raises(ValueError, match="Unknown tile token"):
        Tile.from_token("ZZ")


def test_tile_grid_basics() -> None:
    grid = TileGrid(
        (
            (Tile.TURN_DOWN_RIGHT, Tile.STRAIGHT_HORIZONTAL),
            (Tile.TURN_UP_RIGHT, Tile.EMPTY),
        )
    )

    assert grid.width == 2
    assert grid.height == 2
    assert grid.in_bounds(1, 1)
    assert not grid.in_bounds(2, 0)
    assert grid.get(1, 0) is Tile.STRAIGHT_HORIZONTAL
    assert grid.tile_center(0, 0, 32) == (16.0, 16.0)
    assert [entry[0:2] for entry in grid.iter_tiles()] == [
        (0, 0),
        (1, 0),
        (0, 1),
        (1, 1),
    ]
    with pytest.raises(IndexError):
        grid.get(-1, 0)


def test_tile_grid_rejects_ragged_rows() -> None:
    with pytest.raises(ValueError, match="equal length"):
        TileGrid(((Tile.EMPTY,), (Tile.EMPTY, Tile.EMPTY)))

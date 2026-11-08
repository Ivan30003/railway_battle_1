"""Tile types, directions and a small immutable tile grid."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    NORTH = (0, -1)
    EAST = (1, 0)
    SOUTH = (0, 1)
    WEST = (-1, 0)

    @property
    def delta(self) -> tuple[int, int]:
        return self.value

    @property
    def opposite(self) -> Direction:
        return _OPPOSITE[self]

    @classmethod
    def from_header(cls, value: str) -> Direction:
        try:
            return _HEADER_DIRECTIONS[value.strip().upper()]
        except KeyError as exc:
            choices = ", ".join(sorted(_HEADER_DIRECTIONS))
            raise ValueError(f"DIR must be one of: {choices}") from exc

    @property
    def header_name(self) -> str:
        return _HEADER_NAMES[self]


_OPPOSITE = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
}

_HEADER_DIRECTIONS = {
    "UP": Direction.NORTH,
    "RIGHT": Direction.EAST,
    "DOWN": Direction.SOUTH,
    "LEFT": Direction.WEST,
}

_HEADER_NAMES = {value: key for key, value in _HEADER_DIRECTIONS.items()}


class Tile(Enum):
    EMPTY = "0"
    STRAIGHT_VERTICAL = "SV"
    STRAIGHT_HORIZONTAL = "SH"
    CROSSING = "X"
    TURN_DOWN_LEFT = "LD"
    TURN_DOWN_RIGHT = "RD"
    TURN_UP_LEFT = "LU"
    TURN_UP_RIGHT = "RU"

    @classmethod
    def from_token(cls, token: str) -> Tile:
        try:
            return cls(token)
        except ValueError as exc:
            raise ValueError(f"Unknown tile token: {token!r}") from exc

    @property
    def is_path(self) -> bool:
        return self is not Tile.EMPTY

    @property
    def connections(self) -> frozenset[Direction]:
        return _CONNECTIONS[self]


_CONNECTIONS: dict[Tile, frozenset[Direction]] = {
    Tile.EMPTY: frozenset(),
    Tile.STRAIGHT_VERTICAL: frozenset({Direction.NORTH, Direction.SOUTH}),
    Tile.STRAIGHT_HORIZONTAL: frozenset({Direction.EAST, Direction.WEST}),
    Tile.CROSSING: frozenset(
        {Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST}
    ),
    # "LD" is the south-west corner (turn between down and left).
    Tile.TURN_DOWN_LEFT: frozenset({Direction.SOUTH, Direction.WEST}),
    Tile.TURN_DOWN_RIGHT: frozenset({Direction.SOUTH, Direction.EAST}),
    Tile.TURN_UP_LEFT: frozenset({Direction.NORTH, Direction.WEST}),
    Tile.TURN_UP_RIGHT: frozenset({Direction.NORTH, Direction.EAST}),
}


@dataclass(frozen=True)
class TileGrid:
    tiles: tuple[tuple[Tile, ...], ...]

    def __post_init__(self) -> None:
        if not self.tiles or not self.tiles[0]:
            raise ValueError("TileGrid cannot be empty")
        width = len(self.tiles[0])
        if any(len(row) != width for row in self.tiles):
            raise ValueError("TileGrid rows must have equal length")

    @property
    def width(self) -> int:
        return len(self.tiles[0])

    @property
    def height(self) -> int:
        return len(self.tiles)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> Tile:
        if not self.in_bounds(x, y):
            raise IndexError(f"Tile coordinate out of bounds: ({x}, {y})")
        return self.tiles[y][x]

    def iter_tiles(self) -> Iterator[tuple[int, int, Tile]]:
        for y, row in enumerate(self.tiles):
            for x, tile in enumerate(row):
                yield x, y, tile

    def tile_center(self, x: int, y: int, tile_size: int) -> tuple[float, float]:
        return (
            (x + 0.5) * tile_size,
            (y + 0.5) * tile_size,
        )

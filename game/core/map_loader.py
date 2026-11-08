"""Parsing and validation of the plain-text railway maps.

Map format
----------

    START=x,y
    DIR=RIGHT
    RD SH SH LD
    SV 0  0  SV
    RU SH SH LU

``START`` is a zero-based column/row pair. ``DIR`` is one of ``UP``,
``RIGHT``, ``DOWN`` or ``LEFT`` and points along the rail the train leaves the
start tile on. The remaining non-empty lines are whitespace-separated tile
tokens. Lines may be commented with ``#``; the loader also accepts CRLF, a
UTF-8 BOM and arbitrary leading/trailing whitespace.

A map is valid only when every track tile belongs to one closed loop and the
loop can be traversed from ``START`` in ``DIR``. Crossings (``X``) are passed
straight through and may be visited twice when the loop crosses itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from game.core.errors import MapError
from game.core.path import PathRoute
from game.core.tilemap import Direction, Tile, TileGrid

Coord = tuple[int, int]

_KNOWN_HEADERS = {"START", "DIR"}
_MAX_CROSSING_VISITS = 2


@dataclass(frozen=True)
class MapData:
    """A validated map together with its derived route."""

    grid: TileGrid
    start: Coord
    direction: Direction
    route: PathRoute
    route_tiles: tuple[Coord, ...]
    tile_size: int
    source_path: Path | None = None

    @property
    def width(self) -> int:
        return self.grid.width

    @property
    def height(self) -> int:
        return self.grid.height

    @property
    def pixel_size(self) -> tuple[int, int]:
        return self.width * self.tile_size, self.height * self.tile_size

    @property
    def track_tile_count(self) -> int:
        return sum(1 for _, _, tile in self.grid.iter_tiles() if tile.is_path)

    @property
    def route_length(self) -> float:
        return self.route.total_length


def load_map(path: str | Path, *, tile_size: int = 32) -> MapData:
    """Load and validate a map from disk."""
    map_path = Path(path)
    try:
        text = map_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise MapError(f"Cannot read map {map_path}: {exc}") from exc
    return parse_map(text, tile_size=tile_size, source_path=map_path)


def parse_map(
    text: str,
    *,
    tile_size: int = 32,
    source_path: Path | None = None,
) -> MapData:
    """Parse and validate map text."""
    if tile_size <= 0:
        raise MapError(f"tile_size must be positive, got {tile_size}")

    headers, rows = _split_headers_and_rows(text)
    start = _parse_start(headers)
    direction = _parse_direction(headers)
    grid = _build_grid(rows)

    if not grid.in_bounds(*start):
        raise MapError(
            f"START={start[0]},{start[1]} is outside the {grid.width}x{grid.height} map"
        )
    start_tile = grid.get(*start)
    if not start_tile.is_path:
        raise MapError(f"START={start[0]},{start[1]} points at an empty tile")
    if direction not in start_tile.connections:
        raise MapError(
            f"START tile at {start[0]},{start[1]} does not connect "
            f"{direction.header_name}"
        )

    route_tiles = _walk_route(grid, start, direction)
    points = [grid.tile_center(x, y, tile_size) for x, y in route_tiles]
    try:
        route = PathRoute(points)
    except ValueError as exc:  # pragma: no cover - guarded by validation above
        raise MapError(f"Cannot build route: {exc}") from exc

    return MapData(
        grid=grid,
        start=start,
        direction=direction,
        route=route,
        route_tiles=route_tiles,
        tile_size=tile_size,
        source_path=source_path,
    )


def _split_headers_and_rows(
    text: str,
) -> tuple[dict[str, tuple[str, int]], list[tuple[int, list[str]]]]:
    headers: dict[str, tuple[str, int]] = {}
    rows: list[tuple[int, list[str]]] = []
    grid_started = False
    cleaned = text.lstrip("\ufeff")

    for line_number, raw_line in enumerate(cleaned.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if not grid_started and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip().upper()
            value = value.strip()
            if not key:
                raise MapError(f"Line {line_number}: empty header name")
            if key not in _KNOWN_HEADERS:
                allowed = ", ".join(sorted(_KNOWN_HEADERS))
                raise MapError(
                    f"Line {line_number}: unknown header {key!r} (expected {allowed})"
                )
            if key in headers:
                raise MapError(f"Line {line_number}: duplicate header {key}")
            if not value:
                raise MapError(f"Line {line_number}: header {key} has no value")
            headers[key] = (value, line_number)
            continue

        grid_started = True
        rows.append((line_number, line.split()))

    if not rows:
        raise MapError("Map contains no tile rows")
    return headers, rows


def _parse_start(headers: dict[str, tuple[str, int]]) -> Coord:
    if "START" not in headers:
        raise MapError("Map is missing the START header")
    raw, line_number = headers["START"]
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2 or not all(parts):
        raise MapError(f"Line {line_number}: START must use the form START=x,y")
    try:
        x = int(parts[0])
        y = int(parts[1])
    except ValueError as exc:
        raise MapError(f"Line {line_number}: START coordinates must be integers") from exc
    return x, y


def _parse_direction(headers: dict[str, tuple[str, int]]) -> Direction:
    if "DIR" not in headers:
        raise MapError("Map is missing the DIR header")
    raw, line_number = headers["DIR"]
    try:
        return Direction.from_header(raw)
    except ValueError as exc:
        raise MapError(f"Line {line_number}: {exc}") from exc


def _build_grid(rows: list[tuple[int, list[str]]]) -> TileGrid:
    width = len(rows[0][1])
    if width == 0:
        raise MapError(f"Line {rows[0][0]}: tile row is empty")
    tiles: list[tuple[Tile, ...]] = []
    for line_number, tokens in rows:
        if len(tokens) != width:
            raise MapError(
                f"Line {line_number}: expected {width} tiles, found {len(tokens)}"
            )
        parsed: list[Tile] = []
        for column, token in enumerate(tokens):
            try:
                parsed.append(Tile.from_token(token))
            except ValueError as exc:
                raise MapError(f"Line {line_number}, column {column}: {exc}") from exc
        tiles.append(tuple(parsed))
    return TileGrid(tuple(tiles))


def _walk_route(grid: TileGrid, start: Coord, start_direction: Direction) -> tuple[Coord, ...]:
    x, y = start
    heading = start_direction
    tiles: list[Coord] = [start]
    visits: dict[Coord, int] = {start: 1}
    headings: dict[Coord, list[Direction]] = {}
    max_steps = grid.width * grid.height * _MAX_CROSSING_VISITS + 8

    for _ in range(max_steps):
        tile = grid.get(x, y)
        if heading not in tile.connections:
            raise MapError(
                f"Tile at {x},{y} has no connection {heading.header_name}"
            )
        headings.setdefault((x, y), []).append(heading)

        nx = x + heading.delta[0]
        ny = y + heading.delta[1]
        if not grid.in_bounds(nx, ny):
            raise MapError(
                f"Route leaves the map at {x},{y} heading {heading.header_name}"
            )

        next_tile = grid.get(nx, ny)
        if not next_tile.is_path:
            raise MapError(f"Route runs into an empty tile at {nx},{ny}")

        entry = heading.opposite
        if entry not in next_tile.connections:
            raise MapError(
                f"Tile at {nx},{ny} is not connected back towards {x},{y}"
            )

        if next_tile is Tile.CROSSING:
            next_heading = heading
        else:
            options = next_tile.connections - {entry}
            if len(options) != 1:
                raise MapError(f"Cannot determine the route through tile at {nx},{ny}")
            next_heading = next(iter(options))

        if (nx, ny) == start:
            if next_heading == start_direction:
                break
            if next_tile is not Tile.CROSSING:
                raise MapError(
                    f"Route returns to START={start[0]},{start[1]} heading "
                    f"{next_heading.header_name}, but DIR={start_direction.header_name}"
                )
            # A crossing start tile may be traversed twice by a figure-eight loop.

        visits[(nx, ny)] = visits.get((nx, ny), 0) + 1
        if visits[(nx, ny)] > _MAX_CROSSING_VISITS:
            raise MapError(f"Route visits tile at {nx},{ny} too many times")
        tiles.append((nx, ny))
        x, y, heading = nx, ny, next_heading
    else:
        raise MapError("Route does not close back to START")

    _validate_route_coverage(grid, visits, headings)
    return tuple(tiles)


def _validate_route_coverage(
    grid: TileGrid,
    visits: dict[Coord, int],
    headings: dict[Coord, list[Direction]],
) -> None:
    for x, y, tile in grid.iter_tiles():
        if not tile.is_path:
            continue
        count = visits.get((x, y), 0)
        if count == 0:
            raise MapError(
                f"Stray track tile at {x},{y}: it is not part of the route from START"
            )
        if tile is Tile.CROSSING:
            if count > _MAX_CROSSING_VISITS:
                raise MapError(f"Crossing at {x},{y} is visited too many times")
            used = headings.get((x, y), [])
            if count == _MAX_CROSSING_VISITS and not _perpendicular(used[0], used[1]):
                raise MapError(
                    f"Crossing at {x},{y} is reused in the same direction; "
                    "a crossing may only be traversed straight"
                )
        elif count != 1:
            raise MapError(
                f"Tile at {x},{y} is visited {count} times; every non-crossing "
                "track tile must belong to the loop exactly once"
            )


def _perpendicular(a: Direction, b: Direction) -> bool:
    return a.delta[0] * b.delta[0] + a.delta[1] * b.delta[1] == 0

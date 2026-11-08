"""Procedural rendering of the track map, route and debug marker."""

from __future__ import annotations

from game.core.map_loader import MapData
from game.core.path import RouteSample
from game.core.tilemap import Direction
from game.view.renderer import Renderer
from game.view.theme import Theme

Point = tuple[float, float]


class TrackLayer:
    """Draws the map background, rails, start marker and (optionally) the route."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def draw(
        self,
        renderer: Renderer,
        map_data: MapData,
        *,
        marker: RouteSample | None = None,
        debug: bool = False,
    ) -> None:
        width, height = renderer.virtual_size
        renderer.draw_rect(self.theme.world, (0, 0, width, height))
        self._draw_grid(renderer, map_data, debug)
        self._draw_rails(renderer, map_data)
        self._draw_start(renderer, map_data, debug)
        if debug:
            self._draw_route_line(renderer, map_data)
        if marker is not None:
            self._draw_marker(renderer, map_data, marker)

    # ------------------------------------------------------------------
    # Layers
    # ------------------------------------------------------------------
    def _draw_grid(self, renderer: Renderer, map_data: MapData, debug: bool) -> None:
        tile_size = map_data.tile_size
        width, height = renderer.virtual_size
        color = self.theme.panel_border if debug else self.theme.grid
        for x in range(0, width + 1, tile_size):
            renderer.draw_line(color, (x, 0), (x, height), 1)
        for y in range(0, height + 1, tile_size):
            renderer.draw_line(color, (0, y), (width, y), 1)

    def _draw_rails(self, renderer: Renderer, map_data: MapData) -> None:
        points = map_data.route.points
        tile_size = map_data.tile_size
        sleeper_width = max(6, tile_size // 5)
        rail_width = max(2, tile_size // 12)
        count = len(points)
        for index in range(count):
            start = points[index]
            end = points[(index + 1) % count]
            renderer.draw_line(self.theme.track_sleeper, start, end, sleeper_width)
            renderer.draw_line(self.theme.track_rail, start, end, rail_width)

    def _draw_start(self, renderer: Renderer, map_data: MapData, debug: bool) -> None:
        center = map_data.grid.tile_center(*map_data.start, map_data.tile_size)
        color = self.theme.success if debug else self.theme.track_rail
        radius = map_data.tile_size * 0.16
        renderer.draw_circle(color, center, radius, 2)
        if not debug:
            return
        tip = _offset(center, map_data.direction.delta, map_data.tile_size * 0.42)
        renderer.draw_line(color, center, tip, 2)
        self._draw_arrow_head(renderer, tip, map_data.direction, map_data.tile_size * 0.14, color)

    def _draw_route_line(self, renderer: Renderer, map_data: MapData) -> None:
        points = map_data.route.points
        count = len(points)
        for index in range(count):
            renderer.draw_line(
                self.theme.track_route,
                points[index],
                points[(index + 1) % count],
                1,
            )

    def _draw_marker(
        self,
        renderer: Renderer,
        map_data: MapData,
        marker: RouteSample,
    ) -> None:
        tile_size = map_data.tile_size
        radius = tile_size * 0.24
        center = marker.position
        direction = marker.direction
        perpendicular = (-direction[1], direction[0])
        nose = _offset(center, direction, radius * 1.1)
        left = _offset(_offset(center, direction, -radius * 0.8), perpendicular, radius * 0.8)
        right = _offset(_offset(center, direction, -radius * 0.8), perpendicular, -radius * 0.8)
        renderer.draw_polygon(self.theme.marker_dark, (nose, left, right), 0)
        inner_nose = _offset(center, direction, radius * 0.85)
        inner_left = _offset(
            _offset(center, direction, -radius * 0.6), perpendicular, radius * 0.6
        )
        inner_right = _offset(
            _offset(center, direction, -radius * 0.6), perpendicular, -radius * 0.6
        )
        renderer.draw_polygon(self.theme.marker, (inner_nose, inner_left, inner_right), 0)
        renderer.draw_circle(self.theme.marker_dark, center, max(2, radius * 0.28))
        renderer.draw_circle(self.theme.marker, center, max(1, radius * 0.18))

    @staticmethod
    def _draw_arrow_head(
        renderer: Renderer,
        tip: Point,
        direction: Direction,
        size: float,
        color: tuple[int, int, int],
    ) -> None:
        delta = direction.delta
        perpendicular = (-delta[1], delta[0])
        base = (tip[0] - delta[0] * size, tip[1] - delta[1] * size)
        left = (base[0] + perpendicular[0] * size * 0.6, base[1] + perpendicular[1] * size * 0.6)
        right = (
            base[0] - perpendicular[0] * size * 0.6,
            base[1] - perpendicular[1] * size * 0.6,
        )
        renderer.draw_polygon(color, (tip, left, right), 0)


def _offset(origin: Point, direction: tuple[float, float], distance: float) -> Point:
    return origin[0] + direction[0] * distance, origin[1] + direction[1] * distance


__all__ = ["TrackLayer"]

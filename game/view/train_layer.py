"""Procedural locomotive and wagon rendering."""

from __future__ import annotations

from game.core.train import LOCOMOTIVE, Train, TrainCar
from game.view.renderer import Renderer
from game.view.theme import Color, Theme

Point = tuple[float, float]

_WAGON_COLORS: dict[str, Color] = {
    "MACHINEGUN": (196, 120, 80),
    "ICE": (110, 178, 210),
    "MORTAR": (180, 156, 92),
    "SNIPER": (156, 124, 196),
}


class TrainLayer:
    """Draws the locomotive and its wagons as placeholder shapes."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def draw(self, renderer: Renderer, train: Train, tile_size: int) -> None:
        for car in reversed(train.car_samples()):
            if car.kind == LOCOMOTIVE:
                self._draw_locomotive(renderer, car, tile_size)
            else:
                self._draw_wagon(renderer, car, tile_size)

    # ------------------------------------------------------------------
    # Locomotive
    # ------------------------------------------------------------------
    def _draw_locomotive(self, renderer: Renderer, car: TrainCar, tile_size: int) -> None:
        center = car.sample.position
        direction = car.sample.direction
        length = tile_size * 0.98
        width = tile_size * 0.68

        body = _oriented_rect(center, direction, length, width)
        renderer.draw_polygon((10, 12, 16), _shift(body, 2.0, 3.0), 0)
        renderer.draw_polygon(self.theme.marker_dark, body, 0)
        renderer.draw_polygon(
            self.theme.marker,
            _oriented_rect(center, direction, length * 0.82, width * 0.76),
            0,
        )
        self._draw_wheels(renderer, center, direction, length, width, tile_size)

        # Chimney and headlight make the direction of travel readable.
        chimney = _offset(center, direction, length * 0.12)
        renderer.draw_circle(self.theme.marker_dark, chimney, tile_size * 0.11)
        renderer.draw_circle(self.theme.track_rail, chimney, tile_size * 0.055)
        headlight = _offset(center, direction, length * 0.36)
        renderer.draw_circle(self.theme.text, headlight, tile_size * 0.07)

    # ------------------------------------------------------------------
    # Wagons
    # ------------------------------------------------------------------
    def _draw_wagon(self, renderer: Renderer, car: TrainCar, tile_size: int) -> None:
        center = car.sample.position
        direction = car.sample.direction
        length = tile_size * 0.86
        width = tile_size * 0.58
        color = _WAGON_COLORS.get(car.kind, self.theme.panel_alt)

        body = _oriented_rect(center, direction, length, width)
        renderer.draw_polygon((10, 12, 16), _shift(body, 2.0, 3.0), 0)
        renderer.draw_polygon(self.theme.panel_border, body, 0)
        inner = _oriented_rect(center, direction, length * 0.8, width * 0.72)
        renderer.draw_polygon(color, inner, 0)
        self._draw_wheels(renderer, center, direction, length, width, tile_size)

        # A small central dot keeps different wagon kinds distinguishable.
        renderer.draw_circle(self.theme.panel, center, tile_size * 0.08)
        renderer.draw_circle(self.theme.text, center, tile_size * 0.045)

    # ------------------------------------------------------------------
    # Shared parts
    # ------------------------------------------------------------------
    @staticmethod
    def _draw_wheels(
        renderer: Renderer,
        center: Point,
        direction: tuple[float, float],
        length: float,
        width: float,
        tile_size: int,
    ) -> None:
        perpendicular = (-direction[1], direction[0])
        radius = max(2.0, tile_size * 0.085)
        for along in (-length * 0.28, length * 0.28):
            for side in (-width * 0.54, width * 0.54):
                wheel = _offset(_offset(center, direction, along), perpendicular, side)
                renderer.draw_circle((18, 20, 26), wheel, radius)
                renderer.draw_circle((74, 80, 92), wheel, max(1.0, radius * 0.45))


def _oriented_rect(
    center: Point,
    direction: tuple[float, float],
    length: float,
    width: float,
) -> tuple[Point, Point, Point, Point]:
    forward = (direction[0] * length / 2.0, direction[1] * length / 2.0)
    side = (-direction[1] * width / 2.0, direction[0] * width / 2.0)
    return (
        (center[0] + forward[0] + side[0], center[1] + forward[1] + side[1]),
        (center[0] + forward[0] - side[0], center[1] + forward[1] - side[1]),
        (center[0] - forward[0] - side[0], center[1] - forward[1] - side[1]),
        (center[0] - forward[0] + side[0], center[1] - forward[1] + side[1]),
    )


def _shift(points: tuple[Point, ...], dx: float, dy: float) -> tuple[Point, ...]:
    return tuple((point[0] + dx, point[1] + dy) for point in points)


def _offset(origin: Point, direction: tuple[float, float], distance: float) -> Point:
    return origin[0] + direction[0] * distance, origin[1] + direction[1] * distance


__all__ = ["TrainLayer"]

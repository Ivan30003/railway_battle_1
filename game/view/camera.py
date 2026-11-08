"""Camera and letterbox scaling helpers.

The renderer draws the world into a fixed virtual canvas; this module maps
between that canvas and the actual window.
"""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True)
class Letterbox:
    scale: float
    offset_x: float
    offset_y: float
    width: float
    height: float


def compute_letterbox(
    window_size: tuple[int, int],
    virtual_size: tuple[int, int],
) -> Letterbox:
    window_width, window_height = max(1, int(window_size[0])), max(1, int(window_size[1]))
    virtual_width, virtual_height = max(1, int(virtual_size[0])), max(1, int(virtual_size[1]))
    scale = min(window_width / virtual_width, window_height / virtual_height)
    draw_width = virtual_width * scale
    draw_height = virtual_height * scale
    return Letterbox(
        scale=scale,
        offset_x=(window_width - draw_width) / 2.0,
        offset_y=(window_height - draw_height) / 2.0,
        width=draw_width,
        height=draw_height,
    )


@dataclass
class Camera:
    """Static camera; the map always fits the virtual canvas."""

    x: float = 0.0
    y: float = 0.0

    def world_to_screen(self, position: Point) -> Point:
        return position[0] - self.x, position[1] - self.y

    def screen_to_world(self, position: Point) -> Point:
        return position[0] + self.x, position[1] + self.y

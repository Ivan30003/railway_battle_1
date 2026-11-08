"""Frame renderer: virtual canvas, letterbox scaling and primitive drawing."""

from __future__ import annotations

from typing import Any

import pygame

from game.assets.loader import AssetLoader
from game.view.camera import Letterbox, compute_letterbox
from game.view.theme import Color, Theme

Point = tuple[float, float]
RectLike = pygame.Rect | tuple[int, int, int, int] | tuple[float, float, float, float]


class Renderer:
    def __init__(
        self,
        window: pygame.Surface,
        virtual_size: tuple[int, int],
        assets: AssetLoader,
        theme: Theme,
    ) -> None:
        self.window = window
        self.virtual_size = (int(virtual_size[0]), int(virtual_size[1]))
        self.assets = assets
        self.theme = theme
        self.surface = pygame.Surface(self.virtual_size)
        self.letterbox = compute_letterbox(window.get_size(), self.virtual_size)

    def set_window(self, window: pygame.Surface) -> None:
        self.window = window
        self._refresh_letterbox()

    def set_virtual_size(self, size: tuple[int, int]) -> None:
        self.virtual_size = (max(1, int(size[0])), max(1, int(size[1])))
        self.surface = pygame.Surface(self.virtual_size)
        self._refresh_letterbox()

    def _refresh_letterbox(self) -> None:
        self.letterbox = compute_letterbox(self.window.get_size(), self.virtual_size)

    def begin_frame(self, color: Color | None = None) -> None:
        self.surface.fill(color if color is not None else self.theme.background)

    def present(self) -> None:
        self._refresh_letterbox()
        self.window.fill((0, 0, 0))
        width = max(1, int(round(self.letterbox.width)))
        height = max(1, int(round(self.letterbox.height)))
        if (width, height) == self.virtual_size:
            scaled = self.surface
        else:
            scale = self.letterbox.scale
            if scale >= 1.0 and abs(scale - round(scale)) < 1e-6:
                scaled = pygame.transform.scale(self.surface, (width, height))
            else:
                scaled = pygame.transform.smoothscale(self.surface, (width, height))
        offset = (
            int(round(self.letterbox.offset_x)),
            int(round(self.letterbox.offset_y)),
        )
        self.window.blit(scaled, offset)
        pygame.display.flip()

    def window_to_virtual(self, position: Point) -> Point:
        box = self.letterbox
        return (
            (position[0] - box.offset_x) / box.scale,
            (position[1] - box.offset_y) / box.scale,
        )

    def virtual_to_window(self, position: Point) -> Point:
        box = self.letterbox
        return (
            position[0] * box.scale + box.offset_x,
            position[1] * box.scale + box.offset_y,
        )

    def draw_rect(
        self,
        color: Color,
        rect: RectLike,
        width: int = 0,
        border_radius: int = 0,
    ) -> pygame.Rect:
        target = pygame.Rect(rect)
        pygame.draw.rect(self.surface, color, target, width, border_radius=border_radius)
        return target

    def draw_circle(
        self,
        color: Color,
        center: Point,
        radius: float,
        width: int = 0,
    ) -> None:
        pygame.draw.circle(
            self.surface,
            color,
            (int(center[0]), int(center[1])),
            max(1, int(radius)),
            width,
        )

    def draw_polygon(
        self,
        color: Color,
        points: list[Point] | tuple[Point, ...],
        width: int = 0,
    ) -> None:
        pygame.draw.polygon(
            self.surface,
            color,
            [(int(point[0]), int(point[1])) for point in points],
            width,
        )

    def draw_line(
        self,
        color: Color,
        start: Point,
        end: Point,
        width: int = 1,
    ) -> None:
        pygame.draw.line(
            self.surface,
            color,
            (int(start[0]), int(start[1])),
            (int(end[0]), int(end[1])),
            width,
        )

    def draw_panel(
        self,
        rect: RectLike,
        fill: Color,
        border: Color,
        width: int = 2,
        radius: int = 6,
    ) -> pygame.Rect:
        target = self.draw_rect(fill, rect, border_radius=radius)
        if width > 0:
            pygame.draw.rect(self.surface, border, target, width, border_radius=radius)
        return target

    def overlay(self, color: Color = (0, 0, 0), alpha: int = 170) -> None:
        layer = pygame.Surface(self.virtual_size, pygame.SRCALPHA)
        layer.fill((color[0], color[1], color[2], max(0, min(255, alpha))))
        self.surface.blit(layer, (0, 0))

    def draw_text(
        self,
        text: str,
        size: int,
        color: Color,
        position: Point,
        anchor: str = "topleft",
        bold: bool = False,
    ) -> pygame.Rect:
        image = self.assets.font(max(1, int(size)), bold=bold).render(str(text), True, color)
        rect = image.get_rect()
        if not hasattr(rect, anchor):
            raise ValueError(f"Unknown text anchor: {anchor}")
        setattr(rect, anchor, (int(position[0]), int(position[1])))
        self.surface.blit(image, rect)
        return rect

    def text_size(self, text: str, size: int, bold: bool = False) -> tuple[int, int]:
        return self.assets.font(max(1, int(size)), bold=bold).size(str(text))

    def draw_debug_rect(self, rect: RectLike, color: Color) -> None:
        self.draw_rect(color, rect, width=1)


def as_color(value: Any, fallback: Color) -> Color:
    """Small helper kept for scenes that want to sanitise theme values."""
    if (
        isinstance(value, tuple)
        and len(value) == 3
        and all(isinstance(channel, int) for channel in value)
    ):
        return value
    return fallback


__all__ = ["Letterbox", "Renderer", "as_color"]

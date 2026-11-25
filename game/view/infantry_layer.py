"""Procedural infantryman rendering."""

from __future__ import annotations

import math

from game.core.infantry import Soldier
from game.view.renderer import Renderer
from game.view.theme import Theme


class InfantryLayer:
    """Draws the soldiers dropped by infantry wagons."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def draw(self, renderer: Renderer, soldiers: list[Soldier]) -> None:
        for soldier in soldiers:
            self._draw_soldier(renderer, soldier)

    def _draw_soldier(self, renderer: Renderer, soldier: Soldier) -> None:
        center = soldier.position
        radius = max(3.0, soldier.radius)
        renderer.draw_circle((8, 10, 12), (center[0] + 1.5, center[1] + 2.0), radius + 1.0)
        renderer.draw_circle(self.theme.monster_outline, center, radius + 1.5)
        renderer.draw_circle(self.theme.soldier, center, radius)
        renderer.draw_circle(
            self.theme.soldier_dark,
            (center[0], center[1] - radius * 0.25),
            radius * 0.72,
        )

        angle = math.radians(soldier.angle_deg)
        dx = math.cos(angle)
        dy = math.sin(angle)
        start = (center[0] + dx * radius * 0.3, center[1] + dy * radius * 0.3)
        end = (center[0] + dx * radius * 2.3, center[1] + dy * radius * 2.3)
        renderer.draw_line(self.theme.monster_outline, start, end, 3)
        renderer.draw_line(self.theme.soldier_rifle, start, end, 1)


__all__ = ["InfantryLayer"]

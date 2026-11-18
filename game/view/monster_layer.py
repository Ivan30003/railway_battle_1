"""Procedural monster rendering."""

from __future__ import annotations

import math

from game.core.monsters import TANK_KIND, Monster
from game.view.renderer import Renderer
from game.view.theme import Theme


class MonsterLayer:
    """Draws monsters as small coloured creatures with a health bar."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def draw(self, renderer: Renderer, monsters: list[Monster]) -> None:
        for monster in monsters:
            self._draw_monster(renderer, monster)

    def _draw_monster(self, renderer: Renderer, monster: Monster) -> None:
        center = monster.position
        radius = max(3.0, monster.radius)
        body = self.theme.monster_tank if monster.kind == TANK_KIND else self.theme.monster_fast

        renderer.draw_circle((8, 8, 12), (center[0] + 2, center[1] + 3), radius + 1)
        renderer.draw_circle(self.theme.monster_outline, center, radius + 2)
        renderer.draw_circle(body, center, radius)

        eye_radius = max(1.0, radius * 0.2)
        eye_offset = radius * 0.34
        eye_y = center[1] - radius * 0.28
        renderer.draw_circle(self.theme.text, (center[0] - eye_offset, eye_y), eye_radius)
        renderer.draw_circle(self.theme.text, (center[0] + eye_offset, eye_y), eye_radius)
        renderer.draw_circle(
            self.theme.monster_outline,
            (center[0] - eye_offset, eye_y),
            max(1.0, eye_radius * 0.5),
        )
        renderer.draw_circle(
            self.theme.monster_outline,
            (center[0] + eye_offset, eye_y),
            max(1.0, eye_radius * 0.5),
        )

        if monster.is_slowed:
            self._draw_slow_indicator(renderer, monster, radius)

        if monster.hp < monster.max_hp:
            self._draw_health_bar(renderer, monster, radius)

    def _draw_slow_indicator(
        self,
        renderer: Renderer,
        monster: Monster,
        radius: float,
    ) -> None:
        center = monster.position
        renderer.draw_circle(self.theme.slow, center, radius + 4.0, width=2)
        for index in range(4):
            angle = math.radians(45.0 + index * 90.0)
            dx = math.cos(angle)
            dy = math.sin(angle)
            start = (center[0] + dx * (radius + 1.0), center[1] + dy * (radius + 1.0))
            end = (center[0] + dx * (radius + 6.0), center[1] + dy * (radius + 6.0))
            renderer.draw_line(self.theme.slow, start, end, 1)

    def _draw_health_bar(self, renderer: Renderer, monster: Monster, radius: float) -> None:
        width = max(12.0, radius * 2.4)
        height = 3.0
        left = monster.position[0] - width / 2.0
        top = monster.position[1] - radius - 8.0
        ratio = max(0.0, min(1.0, monster.hp / monster.max_hp))
        renderer.draw_rect(self.theme.monster_outline, (left, top, width, height))
        renderer.draw_rect(
            self.theme.monster_hp,
            (left, top, width * ratio, height),
        )

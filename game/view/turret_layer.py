"""Locomotive cannon, wagon turret barrels, tracers and area-of-effect blasts."""

from __future__ import annotations

import math
from dataclasses import dataclass

from game.core.combat import Blast, CombatSystem, Shot
from game.core.train import Train
from game.view.renderer import Renderer
from game.view.theme import Color, Theme

Point = tuple[float, float]

TRACER_LIFETIME = 0.08
BLAST_LIFETIME = 0.5

_CANNON_COLOR: Color = (240, 214, 150)
_TURRET_COLORS: dict[str, Color] = {
    "MACHINEGUN": (236, 156, 92),
    "ICE": (128, 204, 238),
    "MORTAR": (222, 192, 112),
    "SNIPER": (186, 150, 232),
}
_SHOT_COLORS: dict[str, Color] = {
    "CANNON": _CANNON_COLOR,
    **_TURRET_COLORS,
}


@dataclass
class Tracer:
    """A fading hitscan line drawn for a fraction of a second."""

    start: Point
    end: Point
    color: Color
    width: int
    ttl: float = TRACER_LIFETIME


@dataclass
class BlastEffect:
    """An expanding ring left by a mortar or ice impact."""

    position: Point
    radius: float
    kind: str
    ttl: float = BLAST_LIFETIME


class TurretLayer:
    """Draws rotating barrels, tracers and area-of-effect blasts."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self.tracers: list[Tracer] = []
        self.blasts: list[BlastEffect] = []

    def add_shots(self, shots: tuple[Shot, ...]) -> None:
        for shot in shots:
            self.tracers.append(
                Tracer(
                    start=shot.origin,
                    end=shot.target,
                    color=_SHOT_COLORS.get(shot.kind, self.theme.accent),
                    width=3 if shot.kind == "CANNON" else 2,
                )
            )

    def add_blasts(self, blasts: tuple[Blast, ...]) -> None:
        for blast in blasts:
            self.blasts.append(
                BlastEffect(
                    position=blast.position,
                    radius=blast.radius,
                    kind=blast.kind,
                )
            )

    def update(self, dt: float) -> None:
        if self.tracers:
            for tracer in self.tracers:
                tracer.ttl -= dt
            self.tracers = [tracer for tracer in self.tracers if tracer.ttl > 0.0]
        if self.blasts:
            for blast in self.blasts:
                blast.ttl -= dt
            self.blasts = [blast for blast in self.blasts if blast.ttl > 0.0]

    def draw(
        self,
        renderer: Renderer,
        combat: CombatSystem,
        train: Train,
        tile_size: int,
    ) -> None:
        cars = train.car_samples()
        if cars:
            cannon_angle = combat.cannon.angle_deg
            if cannon_angle is None:
                cannon_angle = _direction_angle(cars[0].sample.direction)
            self._draw_barrel(
                renderer,
                cars[0].sample.position,
                cannon_angle,
                length=tile_size * 0.62,
                width=5,
                color=_CANNON_COLOR,
                base=tile_size * 0.15,
            )

        for turret in combat.turrets:
            car_index = turret.index + 1
            if car_index >= len(cars):
                continue
            angle = turret.angle_deg
            if angle is None:
                angle = _direction_angle(cars[car_index].sample.direction)
            self._draw_barrel(
                renderer,
                cars[car_index].sample.position,
                angle,
                length=tile_size * 0.42,
                width=3,
                color=_TURRET_COLORS.get(turret.kind, self.theme.text),
                base=tile_size * 0.11,
            )

    def draw_tracers(self, renderer: Renderer) -> None:
        for tracer in self.tracers:
            fade = max(0.0, min(1.0, tracer.ttl / TRACER_LIFETIME))
            width = max(1, int(round(tracer.width * (0.5 + 0.5 * fade))))
            renderer.draw_line(tracer.color, tracer.start, tracer.end, width)
            renderer.draw_circle(tracer.color, tracer.end, 1.5 + 2.0 * fade)

    def draw_effects(self, renderer: Renderer) -> None:
        for blast in self.blasts:
            fade = max(0.0, min(1.0, blast.ttl / BLAST_LIFETIME))
            progress = 1.0 - fade
            if blast.kind == "ICE":
                self._draw_ice_blast(renderer, blast.position, blast.radius, progress)
            else:
                self._draw_mortar_blast(renderer, blast.position, blast.radius, progress)

    def _draw_mortar_blast(
        self,
        renderer: Renderer,
        center: Point,
        radius: float,
        progress: float,
    ) -> None:
        outer = radius * (0.45 + 0.55 * progress)
        inner = radius * (0.2 + 0.35 * progress)
        renderer.draw_circle(self.theme.blast_dim, center, outer, width=2)
        renderer.draw_circle(self.theme.blast, center, inner, width=2)
        core = max(2.0, radius * 0.18 * (1.0 - progress))
        renderer.draw_circle(self.theme.blast, center, core)

    def _draw_ice_blast(
        self,
        renderer: Renderer,
        center: Point,
        radius: float,
        progress: float,
    ) -> None:
        outer = radius * (1.0 - 0.25 * progress)
        renderer.draw_circle(self.theme.ice_dim, center, outer, width=2)
        renderer.draw_circle(self.theme.ice, center, outer * 0.62, width=1)
        for index in range(6):
            angle = math.radians(index * 60.0 + progress * 30.0)
            dx = math.cos(angle)
            dy = math.sin(angle)
            start = (center[0] + dx * outer * 0.3, center[1] + dy * outer * 0.3)
            end = (center[0] + dx * outer * 0.92, center[1] + dy * outer * 0.92)
            renderer.draw_line(self.theme.ice, start, end, 1)

    def _draw_barrel(
        self,
        renderer: Renderer,
        center: Point,
        angle_deg: float,
        *,
        length: float,
        width: int,
        color: Color,
        base: float,
    ) -> None:
        angle = math.radians(angle_deg)
        tip = (
            center[0] + math.cos(angle) * length,
            center[1] + math.sin(angle) * length,
        )
        renderer.draw_circle(self.theme.monster_outline, center, base + 1.5)
        renderer.draw_circle(self.theme.panel_border, center, base)
        renderer.draw_line(self.theme.monster_outline, center, tip, width + 2)
        renderer.draw_line(color, center, tip, width)
        renderer.draw_circle(color, tip, max(1.5, width * 0.45))


def _direction_angle(direction: Point) -> float:
    return math.degrees(math.atan2(direction[1], direction[0])) % 360.0


__all__ = [
    "BLAST_LIFETIME",
    "TRACER_LIFETIME",
    "BlastEffect",
    "Tracer",
    "TurretLayer",
]

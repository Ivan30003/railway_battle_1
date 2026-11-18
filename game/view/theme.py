"""Central colour palette for the placeholder UI."""

from __future__ import annotations

from dataclasses import dataclass

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    background: Color = (18, 22, 28)
    world: Color = (24, 30, 40)
    panel: Color = (34, 41, 53)
    panel_alt: Color = (28, 34, 44)
    panel_border: Color = (68, 80, 98)
    disabled: Color = (30, 35, 43)
    text: Color = (232, 236, 242)
    text_muted: Color = (146, 156, 172)
    accent: Color = (232, 176, 74)
    accent_dim: Color = (86, 70, 40)
    danger: Color = (212, 92, 92)
    success: Color = (112, 190, 132)
    grid: Color = (37, 45, 58)
    overlay: Color = (6, 8, 12)
    debug: Color = (120, 230, 170)
    track_bed: Color = (46, 42, 38)
    track_sleeper: Color = (84, 72, 58)
    track_rail: Color = (166, 174, 186)
    track_route: Color = (120, 230, 170)
    marker: Color = (232, 176, 74)
    marker_dark: Color = (96, 66, 24)
    monster_fast: Color = (214, 100, 86)
    monster_tank: Color = (150, 116, 214)
    monster_outline: Color = (34, 26, 40)
    monster_hp: Color = (220, 76, 76)
    blast: Color = (238, 166, 84)
    blast_dim: Color = (150, 96, 48)
    ice: Color = (132, 208, 240)
    ice_dim: Color = (64, 118, 150)
    slow: Color = (144, 216, 246)

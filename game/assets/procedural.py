"""Procedural placeholder graphics used until real assets are supplied."""

from __future__ import annotations

import pygame

_PALETTE = (
    (66, 92, 122),
    (96, 74, 112),
    (102, 92, 62),
    (60, 106, 92),
    (112, 70, 70),
    (72, 84, 120),
)


def placeholder_image(name: str, size: tuple[int, int]) -> pygame.Surface:
    """Create a deterministic placeholder rectangle for a logical asset name."""
    width = max(1, int(size[0]))
    height = max(1, int(size[1]))
    surface = pygame.Surface((width, height), pygame.SRCALPHA)

    seed = sum(ord(char) for char in name)
    base = _PALETTE[seed % len(_PALETTE)]
    border = tuple(max(0, channel - 30) for channel in base)
    surface.fill(base)

    rect = surface.get_rect()
    pygame.draw.rect(surface, border, rect, 2)
    pygame.draw.line(surface, border, (0, 0), (width - 1, height - 1), 1)
    pygame.draw.line(surface, border, (0, height - 1), (width - 1, 0), 1)
    return surface

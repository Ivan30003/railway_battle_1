"""Small immediate-mode UI widgets used by the placeholder screens."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from game.io.input import InputState
from game.view.renderer import Renderer
from game.view.theme import Theme


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    subtitle: str | None = None
    enabled: bool = True
    font_size: int = 20
    subtitle_size: int = 13

    def hovered(self, mouse_position: tuple[float, float]) -> bool:
        return self.enabled and self.rect.collidepoint(mouse_position)

    def clicked(self, input_state: InputState) -> bool:
        return (
            self.enabled
            and input_state.mouse_pressed(1)
            and self.rect.collidepoint(input_state.mouse_virtual)
        )

    def draw(self, renderer: Renderer, theme: Theme, mouse_position: tuple[float, float]) -> None:
        hovered = self.hovered(mouse_position)
        if not self.enabled:
            fill = theme.disabled
            border = theme.panel_border
            text_color = theme.text_muted
        else:
            fill = theme.accent_dim if hovered else theme.panel_alt
            border = theme.accent if hovered else theme.panel_border
            text_color = theme.text

        renderer.draw_panel(self.rect, fill, border, width=2, radius=6)
        if self.subtitle is None:
            renderer.draw_text(
                self.label,
                self.font_size,
                text_color,
                self.rect.center,
                anchor="center",
            )
            return

        renderer.draw_text(
            self.label,
            self.font_size,
            text_color,
            (self.rect.centerx, self.rect.centery - 9),
            anchor="center",
        )
        renderer.draw_text(
            self.subtitle,
            self.subtitle_size,
            theme.text_muted,
            (self.rect.centerx, self.rect.centery + 12),
            anchor="center",
        )

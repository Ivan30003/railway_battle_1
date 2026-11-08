"""Shared placeholder end screen for victory and defeat."""

from __future__ import annotations

from abc import abstractmethod

import pygame

from game.app.scene import Scene
from game.io.actions import Action
from game.io.input import InputState
from game.view.renderer import Renderer
from game.view.ui import Button


class EndScene(Scene):
    title = "КОНЕЦ"
    subtitle = ""
    accent_name = "accent"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._restart = Button(pygame.Rect(0, 0, 220, 44), "Заново", font_size=20)
        self._menu = Button(pygame.Rect(0, 0, 220, 44), "В меню", font_size=20)
        self._layout()

    def _layout(self) -> None:
        width, height = self.app.renderer.virtual_size
        self._restart.rect = pygame.Rect((width - 220) // 2, height // 2 + 30, 220, 44)
        self._menu.rect = pygame.Rect((width - 220) // 2, height // 2 + 88, 220, 44)

    @abstractmethod
    def render(self, renderer: Renderer) -> None:
        raise NotImplementedError

    def handle_actions(self, input_state: InputState) -> None:
        if input_state.was_action(Action.CONFIRM) or input_state.was_action(Action.RESTART):
            self.app.scene_manager.request_scene("game")
        elif (
            input_state.was_action(Action.CANCEL)
            or input_state.was_action(Action.MENU)
            or self._menu.clicked(input_state)
        ):
            self.app.scene_manager.request_scene("menu")
        elif self._restart.clicked(input_state):
            self.app.scene_manager.request_scene("game")

    def render_end(self, renderer: Renderer) -> None:
        width, height = renderer.virtual_size
        theme = renderer.theme
        accent = getattr(theme, self.accent_name)

        renderer.draw_rect(theme.world, (0, 0, width, height))
        for x in range(0, width, 32):
            renderer.draw_line(theme.grid, (x, 0), (x, height), 1)
        for y in range(0, height, 32):
            renderer.draw_line(theme.grid, (0, y), (width, y), 1)

        frame = pygame.Rect(16, 16, width - 32, height - 32)
        renderer.draw_panel(frame, theme.background, theme.panel_border, width=2, radius=8)

        renderer.draw_text(
            self.title,
            44,
            accent,
            (width // 2, height // 2 - 120),
            anchor="center",
            bold=True,
        )
        renderer.draw_text(
            self.subtitle,
            14,
            theme.text_muted,
            (width // 2, height // 2 - 78),
            anchor="center",
        )
        renderer.draw_text(
            "Здесь будет итоговая статистика забега",
            12,
            theme.text_muted,
            (width // 2, height // 2 - 30),
            anchor="center",
        )

        mouse = self.app.input.mouse_virtual
        self._restart.draw(renderer, theme, mouse)
        self._menu.draw(renderer, theme, mouse)

        renderer.draw_text(
            "Enter — заново   Esc — в меню   F1 — debug",
            11,
            theme.text_muted,
            (width // 2, height - 36),
            anchor="center",
        )

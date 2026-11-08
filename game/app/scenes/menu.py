"""Main menu placeholder."""

from __future__ import annotations

import pygame

from game.app.scene import Scene
from game.io.actions import Action
from game.io.input import InputState
from game.view.renderer import Renderer
from game.view.ui import Button


class MenuScene(Scene):
    display_name = "Menu"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._play = Button(pygame.Rect(0, 0, 220, 46), "Играть", font_size=22)
        self._quit = Button(pygame.Rect(0, 0, 220, 46), "Выход", font_size=22)
        self._layout()

    def _layout(self) -> None:
        width, height = self.app.renderer.virtual_size
        self._play.rect = pygame.Rect((width - 220) // 2, height // 2 - 10, 220, 46)
        self._quit.rect = pygame.Rect((width - 220) // 2, height // 2 + 50, 220, 46)

    def handle_actions(self, input_state: InputState) -> None:
        if input_state.was_action(Action.CONFIRM) or self._play.clicked(input_state):
            self.app.scene_manager.request_scene("game")
        elif (
            input_state.was_action(Action.CANCEL)
            or input_state.was_action(Action.QUIT)
            or self._quit.clicked(input_state)
        ):
            self.app.request_quit()

    def render(self, renderer: Renderer) -> None:
        width, height = renderer.virtual_size
        theme = renderer.theme

        for x in range(0, width, 32):
            renderer.draw_line(theme.grid, (x, 0), (x, height), 1)
        for y in range(0, height, 32):
            renderer.draw_line(theme.grid, (0, y), (width, y), 1)

        frame = pygame.Rect(16, 16, width - 32, height - 32)
        renderer.draw_panel(frame, theme.background, theme.panel_border, width=2, radius=8)

        renderer.draw_text(
            "ПАРОВОЗ",
            54,
            theme.accent,
            (width // 2, height // 2 - 150),
            anchor="center",
            bold=True,
        )
        renderer.draw_text(
            "MILESTONE 2 — TRAIN & LAPS",
            13,
            theme.text_muted,
            (width // 2, height // 2 - 108),
            anchor="center",
        )
        renderer.draw_text(
            "Выживи как можно больше кругов",
            16,
            theme.text,
            (width // 2, height // 2 - 70),
            anchor="center",
        )

        mouse = self.app.input.mouse_virtual
        self._play.draw(renderer, theme, mouse)
        self._quit.draw(renderer, theme, mouse)

        renderer.draw_text(
            "Enter — играть   Esc — выход   F1 — debug",
            11,
            theme.text_muted,
            (width // 2, height - 36),
            anchor="center",
        )

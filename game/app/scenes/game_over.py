"""Defeat screen placeholder."""

from __future__ import annotations

from game.app.scenes.end import EndScene
from game.view.renderer import Renderer


class GameOverScene(EndScene):
    display_name = "GameOver"
    title = "ПОРАЖЕНИЕ"
    subtitle = "Паровоз уничтожен"
    accent_name = "danger"

    def render(self, renderer: Renderer) -> None:
        self.render_end(renderer)

"""Victory screen placeholder."""

from __future__ import annotations

from game.app.scenes.end import EndScene
from game.view.renderer import Renderer


class VictoryScene(EndScene):
    display_name = "Victory"
    title = "ПОБЕДА"
    subtitle = "Все карты пройдены"
    accent_name = "success"

    def render(self, renderer: Renderer) -> None:
        self.render_end(renderer)

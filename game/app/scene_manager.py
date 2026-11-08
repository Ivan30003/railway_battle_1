"""Scene switching and lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.app.scenes.game import GameScene
from game.app.scenes.game_over import GameOverScene
from game.app.scenes.menu import MenuScene
from game.app.scenes.victory import VictoryScene

if TYPE_CHECKING:
    from game.app.main import App
    from game.app.scene import Scene
    from game.io.input import InputState
    from game.view.renderer import Renderer


class SceneManager:
    def __init__(self, app: App) -> None:
        self.app = app
        self.current: Scene | None = None
        self._pending: str | None = None

    def set_initial(self, name: str) -> None:
        self._activate(name)

    def request_scene(self, name: str) -> None:
        self._pending = name

    def apply_pending(self) -> None:
        if self._pending is None:
            return
        name = self._pending
        self._pending = None
        self._activate(name)

    def _create(self, name: str) -> Scene:
        if name == "menu":
            return MenuScene(self.app)
        if name == "game":
            return GameScene(self.app)
        if name == "shop":
            return GameScene(self.app, start_in_shop=True)
        if name == "gameover":
            return GameOverScene(self.app)
        if name == "victory":
            return VictoryScene(self.app)
        raise ValueError(f"Unknown scene: {name}")

    def _activate(self, name: str) -> None:
        if self.current is not None:
            self.current.on_exit()
        self.current = self._create(name)
        self.current.on_enter()

    def handle_actions(self, input_state: InputState) -> None:
        if self.current is not None:
            self.current.handle_actions(input_state)

    def update(self, dt: float, input_state: InputState) -> None:
        if self.current is not None:
            self.current.update(dt, input_state)

    def render(self, renderer: Renderer) -> None:
        if self.current is not None:
            self.current.render(renderer)

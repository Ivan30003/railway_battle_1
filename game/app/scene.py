"""Base scene interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.app.main import App
    from game.io.input import InputState
    from game.view.renderer import Renderer


class Scene(ABC):
    display_name = "Scene"

    def __init__(self, app: App) -> None:
        self.app = app

    def on_enter(self) -> None:
        return None

    def on_exit(self) -> None:
        return None

    def handle_actions(self, input_state: InputState) -> None:
        return None

    def update(self, dt: float, input_state: InputState) -> None:
        return None

    @abstractmethod
    def render(self, renderer: Renderer) -> None:
        raise NotImplementedError

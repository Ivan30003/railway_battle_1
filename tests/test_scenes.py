from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.app.main import DEFAULT_CONFIG_PATH, App
from game.core.config import GameConfig
from game.core.game_state import GamePhase
from game.io.actions import Action


def _press(app: App, key: int) -> None:
    app.input.begin_frame()
    app.input.process_event(
        pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")
    )
    app.scene_manager.handle_actions(app.input)
    app.scene_manager.apply_pending()


def test_scene_navigation_and_shop_pause() -> None:
    config = GameConfig.load(DEFAULT_CONFIG_PATH)
    app = App(config, initial_scene="menu")
    try:
        _press(app, pygame.K_RETURN)
        assert app.scene_manager.current is not None
        assert app.scene_manager.current.display_name == "Game"

        game = app.scene_manager.current
        assert game.display_name == "Game"
        assert app.renderer.virtual_size == app.map_data.pixel_size
        assert game.marker_distance == 0.0

        game.update(0.5, app.input)
        assert game.marker_distance > 0.0

        _press(app, pygame.K_b)
        assert game.state.phase == GamePhase.SHOP

        _press(app, pygame.K_ESCAPE)
        assert game.state.phase == GamePhase.PLAYING

        _press(app, pygame.K_ESCAPE)
        assert game.state.phase == GamePhase.PAUSED

        _press(app, pygame.K_ESCAPE)
        assert game.state.phase == GamePhase.PLAYING

        _press(app, pygame.K_m)
        assert app.scene_manager.current.display_name == "Menu"
    finally:
        pygame.quit()


def test_debug_toggle() -> None:
    config = GameConfig.load(DEFAULT_CONFIG_PATH)
    app = App(config, initial_scene="game", debug=False)
    try:
        assert app.debug_overlay.enabled is False
        app.input.begin_frame()
        app.input.process_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1, mod=0, unicode="")
        )
        app._handle_global_actions()
        assert app.debug_overlay.enabled is True
        assert app.input.was_action(Action.TOGGLE_DEBUG)
    finally:
        pygame.quit()

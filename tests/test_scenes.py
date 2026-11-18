from __future__ import annotations

import dataclasses
import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from game.app.main import DEFAULT_CONFIG_PATH, App
from game.core.config import GameConfig
from game.core.game_state import GamePhase
from game.core.monsters import FAST_KIND, Monster
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
        assert game.train.travelled == 0.0
        assert game.state.rounds_on_map == 0
        assert game.train.wagon_count == len(config.start_wagons)
        assert game.combat.ice_slow_max == config.ice_slow_max
        assert game.combat.ice_slow_duration == config.ice_slow_duration
        assert game.combat.mortar_aoe_radius == config.mortar_aoe_radius

        game.update(0.5, app.input)
        assert game.train.travelled > 0.0
        moved = game.train.travelled

        _press(app, pygame.K_b)
        assert game.state.phase == GamePhase.SHOP
        game.update(1.0, app.input)
        assert game.train.travelled == pytest.approx(moved)

        _press(app, pygame.K_ESCAPE)
        assert game.state.phase == GamePhase.PLAYING

        _press(app, pygame.K_ESCAPE)
        assert game.state.phase == GamePhase.PAUSED
        game.update(1.0, app.input)
        assert game.train.travelled == pytest.approx(moved)

        _press(app, pygame.K_ESCAPE)
        assert game.state.phase == GamePhase.PLAYING

        game.train.travelled = game.map_data.route.total_length - 1.0
        game.update(1.0, app.input)
        assert game.state.rounds_on_map == 1
        assert game._lap_flash > 0.0

        _press(app, pygame.K_m)
        assert app.scene_manager.current.display_name == "Menu"
    finally:
        pygame.quit()


def _fast_monster(position: tuple[float, float]) -> Monster:
    return Monster(
        kind=FAST_KIND,
        position=position,
        hp=10.0,
        max_hp=10.0,
        speed=80.0,
        gold=1,
        damage=5.0,
        attack_interval=1.0,
        radius=10.0,
    )


def test_monsters_damage_crush_and_defeat() -> None:
    config = GameConfig.load(DEFAULT_CONFIG_PATH)
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        # This test checks monsters, crushing and defeat, so keep the guns out
        # of the way.
        game.combat.cannon.range = -1.0
        game.combat.turrets.clear()
        locomotive = game.train.locomotive_sample()
        ahead = (
            locomotive.position[0] + locomotive.direction[0] * 34.0,
            locomotive.position[1] + locomotive.direction[1] * 34.0,
        )
        game.monsters.monsters = [_fast_monster(ahead)]

        hp = game.state.locomotive_hp
        game.update(0.01, app.input)
        assert game.state.locomotive_hp == pytest.approx(hp - 5.0)
        assert len(game.monsters.monsters) == 1

        game.monsters.monsters = [_fast_monster(game.train.locomotive_sample().position)]
        gold = game.state.gold
        game.update(0.01, app.input)
        assert game.state.gold == gold + 1
        assert game.monsters.monsters == []
        assert game._crush_slow > 0.0
        game.render(app.renderer)

        travelled = game.train.travelled
        game.update(0.2, app.input)
        delta = game.train.travelled - travelled
        assert delta < config.train_speed * 0.2
        assert delta == pytest.approx(
            config.train_speed * 0.2 * config.crush_slow_factor
        )

        game.state.locomotive_hp = 5.0
        locomotive = game.train.locomotive_sample()
        ahead = (
            locomotive.position[0] + locomotive.direction[0] * 34.0,
            locomotive.position[1] + locomotive.direction[1] * 34.0,
        )
        game.monsters.monsters = [_fast_monster(ahead)]
        game.update(0.01, app.input)
        assert game.state.locomotive_hp == 0.0
        assert game.state.phase == GamePhase.GAME_OVER
    finally:
        pygame.quit()


def test_locomotive_cannon_kills_a_monster() -> None:
    config = GameConfig.load(DEFAULT_CONFIG_PATH)
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.turrets.clear()
        locomotive = game.train.locomotive_sample()
        ahead = (
            locomotive.position[0] + locomotive.direction[0] * 60.0,
            locomotive.position[1] + locomotive.direction[1] * 60.0,
        )
        game.monsters.monsters = [_fast_monster(ahead)]
        hp = game.state.locomotive_hp
        gold = game.state.gold
        app.input.mouse_virtual = ahead
        app.input.mouse_buttons_held.add(1)

        game.update(0.01, app.input)

        assert game.monsters.monsters == []
        assert game.state.gold == gold + 1
        assert game.combat.kills_total == 1
        assert game.state.locomotive_hp == pytest.approx(hp)
        assert len(game.turret_layer.tracers) == 1
        game.render(app.renderer)
    finally:
        pygame.quit()


def test_ice_turret_slows_monsters_and_spawns_a_blast() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        start_wagons=("ICE",),
    )
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.cannon.range = -1.0
        ice_car = game.train.car_samples()[1].sample
        target_position = (
            ice_car.position[0] - ice_car.direction[1] * 60.0,
            ice_car.position[1] + ice_car.direction[0] * 60.0,
        )
        game.monsters.monsters = [_fast_monster(target_position)]
        game.combat.turrets[0].angle_deg = math.degrees(
            math.atan2(
                target_position[1] - ice_car.position[1],
                target_position[0] - ice_car.position[0],
            )
        ) % 360.0

        game.update(0.01, app.input)

        target = game.monsters.monsters[0]
        assert target.slow_percent == pytest.approx(0.2)
        assert target.slow_timer == pytest.approx(config.ice_slow_duration)
        assert [blast.kind for blast in game.turret_layer.blasts] == ["ICE"]
        game.render(app.renderer)
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

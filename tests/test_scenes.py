from __future__ import annotations

import dataclasses
import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from game.app.main import DEFAULT_CONFIG_PATH, PROJECT_ROOT, App
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


def _click(app: App, position: tuple[float, float]) -> None:
    app.input.begin_frame()
    app.input.process_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))
    )
    app.input.mouse_virtual = position
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


def test_destroyed_wagon_disappears_with_its_turret() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        start_wagons=("ICE", "MORTAR"),
    )
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.cannon.range = -1.0
        wagon = game.train.car_samples()[1]
        direction = wagon.sample.direction
        game.monsters.monsters = [
            _fast_monster(
                (
                    wagon.sample.position[0] - direction[1] * 30.0,
                    wagon.sample.position[1] + direction[0] * 30.0,
                )
            )
        ]
        game.train.wagon_health[0] = 5.0
        locomotive_hp = game.state.locomotive_hp

        game.update(0.01, app.input)

        assert game.train.wagons == ["MORTAR"]
        assert game.state.locomotive_hp == pytest.approx(locomotive_hp)
        assert [turret.kind for turret in game.combat.turrets] == ["MORTAR"]
        assert [turret.index for turret in game.combat.turrets] == [0]
        game.render(app.renderer)
    finally:
        pygame.quit()


def test_infantry_wagon_drops_soldiers_and_renders() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        start_wagons=("INFANTRY",),
    )
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.cannon.range = -1.0
        game.monsters.spawner._timer = 10000.0

        game.update(8.05, app.input)

        assert [turret.kind for turret in game.combat.turrets] == ["INFANTRY"]
        assert len(game.infantry.soldiers) == 2
        game.render(app.renderer)
    finally:
        pygame.quit()


def test_shop_purchases_an_infantry_wagon_with_the_keyboard() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        start_gold=100,
    )
    app = App(config, initial_scene="shop")
    try:
        game = app.scene_manager.current
        before = game.train.wagon_count

        _press(app, pygame.K_5)

        assert game.train.wagons[-1] == "INFANTRY"
        assert game.combat.turrets[-1].kind == "INFANTRY"
        assert game.combat.turrets[-1].index == before
        assert game.state.total_purchased == 1
        game.render(app.renderer)
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


def test_shop_purchases_a_wagon_with_the_keyboard() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        start_gold=100,
    )
    app = App(config, initial_scene="shop")
    try:
        game = app.scene_manager.current
        assert game.state.phase == GamePhase.SHOP
        assert game.state.gold == 100
        assert game._price() == config.wagon_base_cost
        before = game.train.wagon_count

        _press(app, pygame.K_3)

        assert game.train.wagons[-1] == "MORTAR"
        assert game.combat.turrets[-1].kind == "MORTAR"
        assert game.combat.turrets[-1].index == before
        assert game.state.total_purchased == 1
        assert game.state.gold == 100 - config.wagon_base_cost
        assert game._price() == config.wagon_base_cost + config.wagon_cost_step
        assert game._shop_message_ok is True
        game.render(app.renderer)
    finally:
        pygame.quit()


def test_shop_buttons_buy_with_the_mouse_and_respect_gold() -> None:
    config = GameConfig.load(DEFAULT_CONFIG_PATH)
    app = App(config, initial_scene="shop")
    try:
        game = app.scene_manager.current
        game.state.gold = 0
        game._refresh_shop_buttons()
        wagon_count = game.train.wagon_count

        _press(app, pygame.K_1)
        assert game.train.wagon_count == wagon_count
        assert game.state.total_purchased == 0
        assert game._shop_message_ok is False

        _click(app, game._shop_buttons[0].rect.center)
        assert game.train.wagon_count == wagon_count

        game.state.gold = game._price()
        game._refresh_shop_buttons()
        _click(app, game._shop_buttons[1].rect.center)

        assert game.train.wagons[-1] == "ICE"
        assert game.combat.turrets[-1].kind == "ICE"
        assert game.state.total_purchased == 1
        assert game.state.gold == 0
        game.render(app.renderer)
    finally:
        pygame.quit()


def test_map_finishes_only_after_rounds_per_map() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        rounds_per_map=2,
    )
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.cannon.range = -1.0
        game.combat.turrets.clear()
        route = game.map_data.route

        game.train.travelled = route.total_length - 1.0
        game.update(1.0, app.input)

        assert game.state.rounds_on_map == 1
        assert game.state.map_index == 0

        game.train.travelled = route.total_length * 2 - 1.0
        game.update(1.0, app.input)

        assert game.state.rounds_on_map == 0
        assert game.state.map_index == 1
        assert game.state.stats.rounds_cleared == 2
        assert game.state.stats.maps_cleared == 1
        assert game.map_data.source_path.name == "map2.txt"
    finally:
        pygame.quit()


def test_map_switch_keeps_gold_hp_and_wagons() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        rounds_per_map=1,
        start_gold=50,
    )
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.cannon.range = -1.0
        game.combat.turrets.clear()
        game.state.gold = 77
        game.state.locomotive_hp = 42.0
        game.state.stats.gold_earned = 21
        game.state.stats.crushed = 3
        game.train.add_wagon("MORTAR")
        game.combat.add_wagon("MORTAR")
        game.train.wagon_health[0] = 12.0
        first_map = game.map_data
        assert first_map.source_path.name == "map1.txt"
        assert app.map_count == 2

        game.train.travelled = first_map.route.total_length - 1.0
        game.update(1.0, app.input)

        assert game.state.phase == GamePhase.PLAYING
        assert game.state.map_index == 1
        assert game.state.rounds_on_map == 0
        assert game.state.stats.maps_cleared == 1
        assert game.state.stats.rounds_cleared == 1
        assert game.map_data.source_path.name == "map2.txt"
        assert app.map_data is game.map_data
        assert app.map_paths[1].name == "map2.txt"
        assert app.renderer.virtual_size == game.map_data.pixel_size
        assert game.state.gold == 77
        assert game.state.locomotive_hp == pytest.approx(42.0)
        assert game.state.stats.gold_earned == 21
        expected_wagons = list(config.start_wagons) + ["MORTAR"]
        assert game.train.wagons == expected_wagons
        assert game.train.wagon_health[0] == pytest.approx(12.0)
        assert game.train.wagon_health[1:] == pytest.approx([30.0, 30.0])
        assert [turret.kind for turret in game.combat.turrets] == expected_wagons
        assert game.train.travelled == 0.0
        assert game.monsters.monsters == []
        assert game._map_banner > 0.0
        game.render(app.renderer)
    finally:
        pygame.quit()


def test_clearing_the_last_map_wins_and_restart_resets_the_run() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        rounds_per_map=1,
        start_gold=12,
    )
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.cannon.range = -1.0
        game.combat.turrets.clear()
        game.state.gold = 34
        game.state.stats.gold_earned = 22

        game.train.travelled = game.map_data.route.total_length - 1.0
        game.update(1.0, app.input)
        assert game.state.map_index == 1
        assert app.scene_manager.current is game

        # Newly built turrets must not change the outcome of this check.
        game.combat.cannon.range = -1.0
        game.combat.turrets.clear()
        game.train.travelled = game.map_data.route.total_length - 1.0
        game.update(1.0, app.input)

        assert game.state.phase == GamePhase.VICTORY
        stats = app.run_stats
        assert stats is game.state.stats
        assert stats.won is True
        assert stats.maps_cleared == 2
        assert stats.rounds_cleared == 2
        assert stats.gold_left == 34

        app.scene_manager.apply_pending()
        end = app.scene_manager.current
        assert end.display_name == "Victory"
        assert end.title == "ПОБЕДА"
        end.render(app.renderer)

        _press(app, pygame.K_RETURN)

        restarted = app.scene_manager.current
        assert restarted.display_name == "Game"
        assert restarted.state.map_index == 0
        assert restarted.state.rounds_on_map == 0
        assert restarted.state.stats.maps_cleared == 0
        assert app.map_data.source_path.name == "map1.txt"
        assert restarted.state.gold == config.start_gold
        assert restarted.state.locomotive_hp == pytest.approx(config.locomotive_hp)
        assert restarted.train.wagons == list(config.start_wagons)
    finally:
        pygame.quit()


def test_defeat_records_the_run_summary() -> None:
    config = GameConfig.load(DEFAULT_CONFIG_PATH)
    app = App(config, initial_scene="game")
    try:
        game = app.scene_manager.current
        game.combat.cannon.range = -1.0
        game.combat.turrets.clear()
        game.state.locomotive_hp = 5.0
        game.state.gold = 13
        game.state.stats.kills = 2
        game.state.stats.crushed = 1
        game.state.stats.gold_earned = 9
        game.state.stats.wagons_bought = 1
        locomotive = game.train.locomotive_sample()
        ahead = (
            locomotive.position[0] + locomotive.direction[0] * 34.0,
            locomotive.position[1] + locomotive.direction[1] * 34.0,
        )
        game.monsters.monsters = [_fast_monster(ahead)]

        game.update(0.01, app.input)

        assert game.state.locomotive_hp == 0.0
        assert game.state.phase == GamePhase.GAME_OVER
        stats = app.run_stats
        assert stats is game.state.stats
        assert stats.won is False
        assert stats.monsters_defeated == 3
        assert stats.gold_left == 13

        app.scene_manager.apply_pending()
        end = app.scene_manager.current
        assert end.display_name == "GameOver"
        assert end.title == "ПОРАЖЕНИЕ"
        end.render(app.renderer)
    finally:
        pygame.quit()


def test_explicit_map_runs_a_single_map_campaign() -> None:
    config = dataclasses.replace(
        GameConfig.load(DEFAULT_CONFIG_PATH),
        rounds_per_map=1,
    )
    map_path = PROJECT_ROOT / "maps" / "map2.txt"
    app = App(config, initial_scene="game", map_path=map_path)
    try:
        game = app.scene_manager.current
        assert app.map_count == 1
        assert app.map_paths == (map_path,)
        assert game.map_data.source_path == map_path
        assert game.state.map_index == 0

        game.combat.cannon.range = -1.0
        game.combat.turrets.clear()
        game.train.travelled = game.map_data.route.total_length - 1.0
        game.update(1.0, app.input)

        assert game.state.phase == GamePhase.VICTORY
        assert app.run_stats.maps_cleared == 1
    finally:
        pygame.quit()


def test_spawn_cooldown_uses_purchases_not_the_live_train() -> None:
    config = GameConfig.from_dict(
        {
            "start_gold": 100,
            "monsters_cooldown_start": 2.0,
            "monsters_cooldown_step": 0.25,
            "monsters_cooldown_min": 0.5,
        }
    )
    app = App(config, initial_scene="shop")
    try:
        game = app.scene_manager.current
        assert game.monsters.spawner.cooldown == pytest.approx(2.0)

        _press(app, pygame.K_1)

        assert game.state.total_purchased == 1
        assert game.monsters.spawner.cooldown == pytest.approx(1.75)

        game.train.remove_wagon(-1)  # simulate a destroyed wagon
        assert len(game.train.wagons) == len(config.start_wagons)
        assert game.monsters.spawner.cooldown == pytest.approx(1.75)
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

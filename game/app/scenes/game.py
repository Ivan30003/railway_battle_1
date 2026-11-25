"""Game scene: track, train, monsters, combat, economy and map rotation.

Milestone 7 turns the game into a run over several maps. A map is completed
after ``rounds_per_map`` laps; the train keeps its wagons, gold and remaining
HP while the route, monsters and turrets are rebuilt on the next map. Clearing
the last map leads to victory, losing all locomotive HP leads to defeat.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import pygame

from game.app.scene import Scene
from game.core.combat import CombatSystem
from game.core.game_state import GamePhase, GameState
from game.core.monsters import MonsterSystem
from game.core.shop import Shop
from game.core.train import Train
from game.io.actions import Action
from game.io.input import InputState
from game.view.camera import Camera
from game.view.monster_layer import MonsterLayer
from game.view.renderer import Renderer
from game.view.track_layer import TrackLayer
from game.view.train_layer import TrainLayer
from game.view.turret_layer import TurretLayer
from game.view.ui import Button

_WAGON_LABELS = {
    "MACHINEGUN": "Пулемётный",
    "ICE": "Ледяной",
    "MORTAR": "Миномётный",
    "SNIPER": "Снайперский",
}
_WAGON_ORDER = ("MACHINEGUN", "ICE", "MORTAR", "SNIPER")
_BUY_ACTIONS = {
    "MACHINEGUN": Action.BUY_MACHINEGUN,
    "ICE": Action.BUY_ICE,
    "MORTAR": Action.BUY_MORTAR,
    "SNIPER": Action.BUY_SNIPER,
}


class GameScene(Scene):
    display_name = "Game"

    def __init__(self, app, start_in_shop: bool = False) -> None:
        super().__init__(app)
        self.camera = Camera()
        self.state = GameState(
            gold=app.config.start_gold,
            locomotive_hp=float(app.config.locomotive_hp),
        )
        self.app.run_stats = self.state.stats
        self.shop = Shop(
            app.config.wagon_configs,
            base_cost=app.config.wagon_base_cost,
            cost_step=app.config.wagon_cost_step,
        )
        self.track_layer = TrackLayer(app.theme)
        self.train_layer = TrainLayer(app.theme)
        self.monster_layer = MonsterLayer(app.theme)
        self.turret_layer = TurretLayer(app.theme)

        # A new run always starts from the first map of the current campaign.
        self.map_data = app.set_map(0)
        self._create_systems(list(app.config.start_wagons))

        self._lap_flash = 0.0
        self._damage_flash = 0.0
        self._crush_slow = 0.0
        self._map_banner = 2.4
        self._shop_message = "1–4 или ЛКМ — купить"
        self._shop_message_ok: bool | None = None
        if start_in_shop:
            self.state.phase = GamePhase.SHOP

        self._shop_icon = pygame.Rect(0, 0, 1, 1)
        self._shop_panel = pygame.Rect(0, 0, 1, 1)
        self._shop_buttons: list[Button] = []
        self._shop_close = Button(pygame.Rect(0, 0, 1, 1), "Закрыть", font_size=16)
        self._pause_panel = pygame.Rect(0, 0, 1, 1)
        self._pause_resume = Button(pygame.Rect(0, 0, 1, 1), "Продолжить", font_size=18)
        self._pause_menu = Button(pygame.Rect(0, 0, 1, 1), "В меню", font_size=18)
        self._layout()
        self._refresh_shop_buttons()

    # ------------------------------------------------------------------
    # Run and level lifecycle
    # ------------------------------------------------------------------
    def _create_systems(
        self,
        wagons: Sequence[str],
        wagon_health: Sequence[float] | None = None,
        wagon_max_health: Sequence[float] | None = None,
    ) -> None:
        """Build train, monsters and combat for the current map."""
        max_health = (
            list(wagon_max_health)
            if wagon_max_health is not None
            else [self.app.config.wagon_configs[kind].hp for kind in wagons]
        )
        health = list(wagon_health) if wagon_health is not None else list(max_health)
        self.train = Train(
            route=self.map_data.route,
            speed=self.app.config.train_speed,
            wagon_spacing=self.app.config.wagon_spacing,
            wagons=list(wagons),
            wagon_health=health,
            wagon_max_health=max_health,
        )
        self.monsters = MonsterSystem(
            self.app.config.spawn,
            self.app.config.monster_configs,
            world_size=self.app.renderer.virtual_size,
            train_center=self.train.center,
            attack_range=self.app.config.monster_attack_range,
            crush_radius=self.app.config.train_crush_radius,
            hit_radius=self.app.config.monster_hit_radius,
            rng=random.Random(self.app.seed + self.state.map_index),
            purchased_wagons=lambda: self.state.total_purchased,
        )
        self.combat = CombatSystem(
            self.app.config.cannon,
            self.app.config.wagon_configs,
            list(wagons),
            ice_slow_per_wagon=self.app.config.ice_slow_per_wagon,
            ice_slow_max=self.app.config.ice_slow_max,
            ice_slow_duration=self.app.config.ice_slow_duration,
            mortar_aoe_radius=self.app.config.mortar_aoe_radius,
        )

    def _load_level(self) -> None:
        """Switch to the current map while keeping the run-wide state."""
        wagons = list(self.train.wagons)
        wagon_health = list(self.train.wagon_health)
        wagon_max_health = list(self.train.wagon_max_health)
        self.map_data = self.app.set_map(self.state.map_index)
        self.camera = Camera()
        self.turret_layer = TurretLayer(self.app.theme)
        self._create_systems(wagons, wagon_health, wagon_max_health)
        self._lap_flash = 0.0
        self._damage_flash = 0.0
        self._crush_slow = 0.0
        self._map_banner = 2.4
        self._layout()
        self._refresh_shop_buttons()

    def _complete_map(self) -> None:
        """Finish the current map and move on, or win after the last one."""
        self.state.stats.maps_cleared += 1
        if self.state.map_index + 1 >= self.app.map_count:
            self._finish_run(victory=True)
            return
        self.state.map_index += 1
        self.state.rounds_on_map = 0
        self._load_level()

    def _finish_run(self, *, victory: bool) -> None:
        """Freeze the run summary and request the matching end scene."""
        stats = self.state.stats
        stats.gold_left = self.state.gold
        stats.won = victory
        if victory:
            stats.maps_cleared = self.app.map_count
            self.state.phase = GamePhase.VICTORY
        else:
            self.state.phase = GamePhase.GAME_OVER
        self.app.run_stats = stats
        self.app.scene_manager.request_scene("victory" if victory else "gameover")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _layout(self) -> None:
        width, height = self.app.renderer.virtual_size

        self._shop_icon = pygame.Rect(width - 104, 8, 96, 26)

        panel_width = min(460, width - 32)
        panel_height = min(330, height - 48)
        left = (width - panel_width) // 2
        top = (height - panel_height) // 2
        self._shop_panel = pygame.Rect(left, top, panel_width, panel_height)

        gap = 10
        inner = 20
        button_width = (panel_width - inner * 2 - gap) // 2
        button_height = 62
        first_row = top + 80
        self._shop_buttons = []
        for index, wagon_type in enumerate(_WAGON_ORDER):
            row, column = divmod(index, 2)
            rect = pygame.Rect(
                left + inner + column * (button_width + gap),
                first_row + row * (button_height + gap),
                button_width,
                button_height,
            )
            self._shop_buttons.append(
                Button(
                    rect,
                    f"{index + 1}. {_WAGON_LABELS[wagon_type]}",
                    subtitle="30 золота",
                    enabled=False,
                    font_size=16,
                    subtitle_size=12,
                )
            )

        close_width = 150
        self._shop_close.rect = pygame.Rect(
            left + (panel_width - close_width) // 2,
            top + panel_height - 48,
            close_width,
            34,
        )

        pause_width = 300
        pause_height = 178
        pause_left = (width - pause_width) // 2
        pause_top = (height - pause_height) // 2
        self._pause_panel = pygame.Rect(pause_left, pause_top, pause_width, pause_height)
        self._pause_resume.rect = pygame.Rect(pause_left + 34, pause_top + 72, 232, 38)
        self._pause_menu.rect = pygame.Rect(pause_left + 34, pause_top + 118, 232, 38)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_actions(self, input_state: InputState) -> None:
        if input_state.was_action(Action.MENU):
            self.app.scene_manager.request_scene("menu")
            return

        if input_state.was_action(Action.TOGGLE_SHOP):
            if self.state.phase == GamePhase.PLAYING:
                self.state.phase = GamePhase.SHOP
                self._refresh_shop_buttons()
            elif self.state.phase == GamePhase.SHOP:
                self.state.phase = GamePhase.PLAYING

        if input_state.was_action(Action.CANCEL):
            if self.state.phase == GamePhase.SHOP:
                self.state.phase = GamePhase.PLAYING
            elif self.state.phase == GamePhase.PAUSED:
                self.state.phase = GamePhase.PLAYING
            elif self.state.phase == GamePhase.PLAYING:
                self.state.phase = GamePhase.PAUSED

        if (
            self.state.phase in (GamePhase.PLAYING, GamePhase.SHOP)
            and input_state.mouse_pressed(1)
            and self._shop_icon.collidepoint(input_state.mouse_virtual)
        ):
            self.state.phase = (
                GamePhase.PLAYING if self.state.phase == GamePhase.SHOP else GamePhase.SHOP
            )
            if self.state.phase == GamePhase.SHOP:
                self._refresh_shop_buttons()

        if self.state.phase == GamePhase.SHOP:
            for index, wagon_type in enumerate(_WAGON_ORDER):
                keyboard = input_state.was_action(_BUY_ACTIONS[wagon_type])
                clicked = self._shop_buttons[index].clicked(input_state)
                if keyboard or clicked:
                    self._purchase(wagon_type)
                    break

        if self.state.phase == GamePhase.SHOP and self._shop_close.clicked(input_state):
            self.state.phase = GamePhase.PLAYING

        if self.state.phase == GamePhase.PAUSED:
            if self._pause_resume.clicked(input_state) or input_state.was_action(Action.CONFIRM):
                self.state.phase = GamePhase.PLAYING
            elif self._pause_menu.clicked(input_state):
                self.app.scene_manager.request_scene("menu")

    def update(self, dt: float, input_state: InputState) -> None:
        if dt > 0.0 and self._map_banner > 0.0:
            self._map_banner = max(0.0, self._map_banner - dt)

        if self.state.phase != GamePhase.PLAYING or dt <= 0.0:
            return

        stats = self.state.stats
        self._damage_flash = max(0.0, self._damage_flash - dt)
        speed_scale = 1.0
        if self._crush_slow > 0.0:
            speed_scale = self.app.config.crush_slow_factor
            self._crush_slow = max(0.0, self._crush_slow - dt)
        train_moving = speed_scale > 0.0
        laps = self.train.update(dt * speed_scale)
        map_finished = False
        if laps:
            self.state.rounds_on_map += laps
            stats.rounds_cleared += laps
            self._lap_flash = 0.8
            map_finished = self.state.rounds_on_map >= self.app.config.rounds_per_map
        if laps == 0 and self._lap_flash > 0.0:
            self._lap_flash = max(0.0, self._lap_flash - dt)

        result = self.monsters.update(dt, self.train, train_moving=train_moving)
        if result.crushed:
            seconds = self.app.config.train_stop_per_crush_ms / 1000.0
            self._crush_slow += result.crushed * seconds
            stats.crushed += result.crushed
        if result.gold:
            self.state.gold += result.gold
            stats.gold_earned += result.gold
        if result.destroyed_wagons:
            for index in result.destroyed_wagons:
                self.combat.remove_wagon(index)
        if result.damage:
            self.state.locomotive_hp = max(0.0, self.state.locomotive_hp - result.damage)
            self._damage_flash = 0.45

        combat = self.combat.update(
            dt,
            self.train,
            self.monsters.monsters,
            aim_point=input_state.mouse_virtual,
            fire=input_state.mouse_held(1),
        )
        self.turret_layer.add_shots(combat.shots)
        self.turret_layer.add_blasts(combat.blasts)
        self.turret_layer.update(dt)
        if combat.gold:
            self.state.gold += combat.gold
            stats.gold_earned += combat.gold
        if combat.kills:
            stats.kills += combat.kills

        if self.state.locomotive_hp <= 0.0:
            self._finish_run(victory=False)
            return
        if map_finished:
            self._complete_map()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _price(self) -> int:
        return self.shop.price(self.state.total_purchased)

    def _purchase(self, wagon_type: str) -> bool:
        purchase = self.shop.buy(
            wagon_type,
            self.state.gold,
            self.state.total_purchased,
        )
        if purchase is None:
            self._shop_message = "Недостаточно золота"
            self._shop_message_ok = False
            return False

        self.state.gold = purchase.gold_after
        self.state.total_purchased = purchase.purchased_after
        self.state.stats.wagons_bought += 1
        self.train.add_wagon(
            wagon_type,
            max_hp=self.app.config.wagon_configs[wagon_type].hp,
        )
        self.combat.add_wagon(wagon_type)
        self._shop_message = (
            f"Куплен вагон: {_WAGON_LABELS[wagon_type]} за {purchase.price} золота"
        )
        self._shop_message_ok = True
        self._refresh_shop_buttons()
        return True

    def _refresh_shop_buttons(self) -> None:
        price = self._price()
        affordable = self.state.gold >= price
        for button in self._shop_buttons:
            button.subtitle = f"{price} золота"
            button.enabled = affordable

    def _draw_world(self, renderer: Renderer) -> None:
        self.track_layer.draw(
            renderer,
            self.map_data,
            debug=self.app.debug_overlay.enabled,
        )
        self.monster_layer.draw(renderer, self.monsters.monsters)
        self.train_layer.draw(renderer, self.train, self.map_data.tile_size)
        self.turret_layer.draw(renderer, self.combat, self.train, self.map_data.tile_size)
        self.turret_layer.draw_tracers(renderer)
        self.turret_layer.draw_effects(renderer)

    def _draw_hud(self, renderer: Renderer) -> None:
        width, _ = renderer.virtual_size
        theme = renderer.theme
        renderer.draw_rect(theme.panel, (0, 0, width, 40))
        renderer.draw_line(theme.panel_border, (0, 40), (width, 40), 2)

        font_size = 11
        y = 14
        renderer.draw_text(
            f"ЗОЛОТО  {self.state.gold}",
            font_size,
            theme.accent,
            (12, y),
        )
        renderer.draw_text(
            f"КРУГ  {self.state.rounds_on_map}/{self.app.config.rounds_per_map}",
            font_size,
            theme.success if self._lap_flash > 0.0 else theme.text,
            (110, y),
        )
        renderer.draw_text(
            f"КАРТА  {self.state.map_index + 1}/{self.app.map_count}",
            font_size,
            theme.text,
            (208, y),
        )
        renderer.draw_text(
            f"ПАРОВОЗ  {self.state.locomotive_hp:.0f}/{self.app.config.locomotive_hp:.0f}",
            font_size,
            theme.danger,
            (304, y),
        )
        renderer.draw_text(
            f"ВАГОНЫ  {self.train.wagon_count}",
            font_size,
            theme.text,
            (432, y),
        )

        affordable = self.state.gold >= self._price()
        border = theme.accent if affordable else theme.panel_border
        renderer.draw_panel(self._shop_icon, theme.panel_alt, border, width=2, radius=5)
        renderer.draw_text(
            "B  МАГАЗИН",
            10,
            theme.accent if affordable else theme.text,
            self._shop_icon.center,
            anchor="center",
        )

    def _draw_shop(self, renderer: Renderer) -> None:
        theme = renderer.theme
        renderer.overlay(theme.overlay, 185)
        renderer.draw_panel(self._shop_panel, theme.panel, theme.panel_border, width=2, radius=8)
        panel = self._shop_panel

        renderer.draw_text(
            "МАГАЗИН",
            30,
            theme.accent,
            (panel.centerx, panel.top + 26),
            anchor="center",
            bold=True,
        )
        renderer.draw_text(
            f"Следующий вагон: {self._price()} золота   •   В наличии: {self.state.gold}",
            13,
            theme.text_muted,
            (panel.centerx, panel.top + 56),
            anchor="center",
        )

        self._refresh_shop_buttons()
        mouse = self.app.input.mouse_virtual
        for button in self._shop_buttons:
            button.draw(renderer, theme, mouse)

        self._shop_close.draw(renderer, theme, mouse)
        if self._shop_message_ok is None:
            message_color = theme.text_muted
        elif self._shop_message_ok:
            message_color = theme.success
        else:
            message_color = theme.danger
        renderer.draw_text(
            self._shop_message,
            10,
            message_color,
            (panel.centerx, panel.top + panel.height - 64),
            anchor="center",
        )

    def _draw_pause(self, renderer: Renderer) -> None:
        theme = renderer.theme
        renderer.overlay(theme.overlay, 170)
        renderer.draw_panel(self._pause_panel, theme.panel, theme.panel_border, width=2, radius=8)
        panel = self._pause_panel
        renderer.draw_text(
            "ПАУЗА",
            30,
            theme.text,
            (panel.centerx, panel.top + 30),
            anchor="center",
            bold=True,
        )
        renderer.draw_text(
            "Симуляция не идёт",
            12,
            theme.text_muted,
            (panel.centerx, panel.top + 54),
            anchor="center",
        )
        mouse = self.app.input.mouse_virtual
        self._pause_resume.draw(renderer, theme, mouse)
        self._pause_menu.draw(renderer, theme, mouse)

    def render(self, renderer: Renderer) -> None:
        self._draw_world(renderer)
        self._draw_hud(renderer)

        width, height = renderer.virtual_size
        if self._map_banner > 0.0 and self.state.phase == GamePhase.PLAYING:
            fade = min(1.0, self._map_banner / 0.6)
            color = renderer.theme.accent if fade >= 1.0 else renderer.theme.text_muted
            renderer.draw_text(
                f"КАРТА {self.state.map_index + 1}/{self.app.map_count}",
                30,
                color,
                (width // 2, height // 2 - 10),
                anchor="center",
                bold=True,
            )
        if self._damage_flash > 0.0:
            renderer.draw_rect(renderer.theme.danger, (0, 0, width, height), width=4)
        if self._crush_slow > 0.0:
            renderer.draw_text(
                f"ДАВКА — скорость {self.app.config.crush_slow_factor * 100:.0f}%"
                f"   {self._crush_slow:.1f} с",
                10,
                renderer.theme.accent,
                (width // 2, height - 36),
                anchor="center",
            )
        renderer.draw_text(
            "B — магазин   Esc — пауза   M — меню   F1 — debug",
            10,
            renderer.theme.text_muted,
            (width // 2, height - 20),
            anchor="center",
        )

        if self.state.phase == GamePhase.SHOP:
            self._draw_shop(renderer)
        elif self.state.phase == GamePhase.PAUSED:
            self._draw_pause(renderer)

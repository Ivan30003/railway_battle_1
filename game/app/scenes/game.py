"""Game scene: track, train, monsters, combat and lap counter.

Milestone 4 adds the locomotive cannon and wagon turrets. The player aims the
cannon with the mouse and fires with the left button, while wagon turrets acquire
and reserve targets on their own. Milestone 3 monsters still spawn beside the
route, chase the locomotive, damage it on contact and are crushed by a moving
train.
"""

from __future__ import annotations

import random

import pygame

from game.app.scene import Scene
from game.core.combat import CombatSystem
from game.core.game_state import GamePhase, GameState
from game.core.monsters import MonsterSystem
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


class GameScene(Scene):
    display_name = "Game"

    def __init__(self, app, start_in_shop: bool = False) -> None:
        super().__init__(app)
        self.camera = Camera()
        self.state = GameState(locomotive_hp=float(app.config.locomotive_hp))
        self.map_data = app.map_data
        self.track_layer = TrackLayer(app.theme)
        self.train_layer = TrainLayer(app.theme)
        self.monster_layer = MonsterLayer(app.theme)
        self.turret_layer = TurretLayer(app.theme)
        self.train = Train(
            route=self.map_data.route,
            speed=app.config.train_speed,
            wagon_spacing=app.config.wagon_spacing,
            wagons=list(app.config.start_wagons),
        )
        self.monsters = MonsterSystem(
            self.map_data.route,
            app.config.spawn,
            app.config.monster_configs,
            attack_range=app.config.monster_attack_range,
            crush_radius=app.config.train_crush_radius,
            hit_radius=app.config.monster_hit_radius,
            rng=random.Random(app.seed),
        )
        self.combat = CombatSystem(
            app.config.cannon,
            app.config.wagon_configs,
            list(app.config.start_wagons),
        )
        self._lap_flash = 0.0
        self._damage_flash = 0.0
        self._crush_slow = 0.0
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
                    _WAGON_LABELS[wagon_type],
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

        if self.state.phase == GamePhase.SHOP and self._shop_close.clicked(input_state):
            self.state.phase = GamePhase.PLAYING

        if self.state.phase == GamePhase.PAUSED:
            if self._pause_resume.clicked(input_state) or input_state.was_action(Action.CONFIRM):
                self.state.phase = GamePhase.PLAYING
            elif self._pause_menu.clicked(input_state):
                self.app.scene_manager.request_scene("menu")

    def update(self, dt: float, input_state: InputState) -> None:
        if self.state.phase != GamePhase.PLAYING or dt <= 0.0:
            return

        self._damage_flash = max(0.0, self._damage_flash - dt)
        speed_scale = 1.0
        if self._crush_slow > 0.0:
            speed_scale = self.app.config.crush_slow_factor
            self._crush_slow = max(0.0, self._crush_slow - dt)
        train_moving = speed_scale > 0.0
        laps = self.train.update(dt * speed_scale)
        if laps:
            self.state.rounds_on_map += laps
            self._lap_flash = 0.8
        if laps == 0 and self._lap_flash > 0.0:
            self._lap_flash = max(0.0, self._lap_flash - dt)

        result = self.monsters.update(dt, self.train, train_moving=train_moving)
        if result.crushed:
            seconds = self.app.config.train_stop_per_crush_ms / 1000.0
            self._crush_slow += result.crushed * seconds
        if result.gold:
            self.state.gold += result.gold
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
        self.turret_layer.update(dt)
        if combat.gold:
            self.state.gold += combat.gold

        if self.state.locomotive_hp <= 0.0:
            self.state.phase = GamePhase.GAME_OVER
            self.app.scene_manager.request_scene("gameover")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _price(self) -> int:
        return self.app.config.wagon_base_cost + self.app.config.wagon_cost_step * (
            self.state.total_purchased
        )

    def _refresh_shop_buttons(self) -> None:
        price = self._price()
        for button in self._shop_buttons:
            button.subtitle = f"{price} золота"
            button.enabled = self.state.gold >= price

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
            f"КАРТА  {self.state.map_index + 1}/{len(self.app.config.maps)}",
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
        renderer.draw_text(
            "Покупки станут доступны в milestone 6",
            10,
            theme.text_muted,
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

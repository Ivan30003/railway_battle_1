"""Pygame event handling and frame-local input state."""

from __future__ import annotations

from collections.abc import Iterable

import pygame

from game.io.actions import Action

_KEY_ACTIONS: dict[int, Action] = {
    pygame.K_RETURN: Action.CONFIRM,
    pygame.K_KP_ENTER: Action.CONFIRM,
    pygame.K_SPACE: Action.CONFIRM,
    pygame.K_ESCAPE: Action.CANCEL,
    pygame.K_b: Action.TOGGLE_SHOP,
    pygame.K_F1: Action.TOGGLE_DEBUG,
    pygame.K_m: Action.MENU,
    pygame.K_r: Action.RESTART,
    pygame.K_1: Action.BUY_MACHINEGUN,
    pygame.K_KP1: Action.BUY_MACHINEGUN,
    pygame.K_2: Action.BUY_ICE,
    pygame.K_KP2: Action.BUY_ICE,
    pygame.K_3: Action.BUY_MORTAR,
    pygame.K_KP3: Action.BUY_MORTAR,
    pygame.K_4: Action.BUY_SNIPER,
    pygame.K_KP4: Action.BUY_SNIPER,
}


class InputState:
    """Keyboard and mouse state for the current frame.

    ``actions`` contains edge-triggered actions collected since the previous
    frame. Held keys/buttons stay in the sets until a release event arrives.
    """

    def __init__(self) -> None:
        self.actions: list[Action] = []
        self.keys_held: set[int] = set()
        self.mouse_buttons_held: set[int] = set()
        self._mouse_pressed: set[int] = set()
        self._mouse_released: set[int] = set()
        self.mouse_window: tuple[int, int] = (0, 0)
        self.mouse_virtual: tuple[float, float] = (0.0, 0.0)

    def begin_frame(self) -> None:
        self.actions.clear()
        self._mouse_pressed.clear()
        self._mouse_released.clear()

    def process_events(self, events: Iterable[pygame.event.Event]) -> None:
        for event in events:
            self.process_event(event)

    def process_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.keys_held.add(event.key)
            action = _KEY_ACTIONS.get(event.key)
            if action is not None:
                self.actions.append(action)
            if event.key == pygame.K_q and event.mod & pygame.KMOD_CTRL:
                self.actions.append(Action.QUIT)
        elif event.type == pygame.KEYUP:
            self.keys_held.discard(event.key)
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_window = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN:
            button = event.button
            self.mouse_window = event.pos
            self.mouse_buttons_held.add(button)
            self._mouse_pressed.add(button)
        elif event.type == pygame.MOUSEBUTTONUP:
            button = event.button
            self.mouse_window = event.pos
            self.mouse_buttons_held.discard(button)
            self._mouse_released.add(button)
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.keys_held.clear()
            self.mouse_buttons_held.clear()

    def set_virtual_mouse(self, position: tuple[float, float]) -> None:
        self.mouse_virtual = position

    def was_action(self, action: Action) -> bool:
        return action in self.actions

    def key_held(self, key: int) -> bool:
        return key in self.keys_held

    def mouse_held(self, button: int = 1) -> bool:
        return button in self.mouse_buttons_held

    def mouse_pressed(self, button: int = 1) -> bool:
        return button in self._mouse_pressed

    def mouse_released(self, button: int = 1) -> bool:
        return button in self._mouse_released

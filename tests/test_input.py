from __future__ import annotations

import pygame

from game.io.actions import Action
from game.io.input import InputState


def _key_event(event_type: int, key: int, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(event_type, key=key, mod=mod, unicode="")


def test_keyboard_actions_are_edge_triggered() -> None:
    state = InputState()
    state.begin_frame()
    state.process_event(_key_event(pygame.KEYDOWN, pygame.K_b))

    assert state.was_action(Action.TOGGLE_SHOP)
    assert state.key_held(pygame.K_b)

    state.begin_frame()
    assert not state.was_action(Action.TOGGLE_SHOP)
    assert state.key_held(pygame.K_b)

    state.process_event(_key_event(pygame.KEYUP, pygame.K_b))
    assert not state.key_held(pygame.K_b)


def test_ctrl_q_requests_quit() -> None:
    state = InputState()
    state.begin_frame()
    state.process_event(
        pygame.event.Event(
            pygame.KEYDOWN,
            key=pygame.K_q,
            mod=pygame.KMOD_CTRL,
            unicode="",
        )
    )

    assert state.was_action(Action.QUIT)


def test_mouse_edges_and_held_state() -> None:
    state = InputState()
    state.begin_frame()
    state.process_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 120), button=1)
    )

    assert state.mouse_pressed(1)
    assert state.mouse_held(1)
    assert state.mouse_window == (100, 120)

    state.begin_frame()
    assert not state.mouse_pressed(1)
    assert state.mouse_held(1)

    state.process_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(100, 120), button=1)
    )
    assert not state.mouse_held(1)
    assert state.mouse_released(1)

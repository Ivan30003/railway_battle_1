"""Input actions shared between the IO layer and the scenes."""

from __future__ import annotations

from enum import Enum


class Action(Enum):
    CONFIRM = "confirm"
    CANCEL = "cancel"
    TOGGLE_SHOP = "toggle_shop"
    TOGGLE_DEBUG = "toggle_debug"
    MENU = "menu"
    RESTART = "restart"
    QUIT = "quit"
    BUY_MACHINEGUN = "buy_machinegun"
    BUY_ICE = "buy_ice"
    BUY_MORTAR = "buy_mortar"
    BUY_SNIPER = "buy_sniper"

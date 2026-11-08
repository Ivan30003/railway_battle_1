"""Game state placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GamePhase(str, Enum):
    PLAYING = "playing"
    SHOP = "shop"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    VICTORY = "victory"


@dataclass
class GameState:
    """Minimal state container shared by the scenes.

    The gameplay systems will fill in the real values in later milestones.
    """

    phase: GamePhase = GamePhase.PLAYING
    gold: int = 0
    rounds_on_map: int = 0
    map_index: int = 0
    total_purchased: int = 0
    locomotive_hp: float = 0.0

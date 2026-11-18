"""Run-wide game state and statistics.

A run is a sequence of maps. Each map has to survive ``rounds_per_map`` laps;
once the last map is completed the run ends in victory, while a destroyed
locomotive ends it in defeat. ``RunStats`` keeps the numbers shown on the end
screen, so they survive the switch from the game scene to the end scene.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GamePhase(str, Enum):
    PLAYING = "playing"
    SHOP = "shop"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    VICTORY = "victory"


@dataclass
class RunStats:
    """Summary of one run from the first map to victory or defeat."""

    maps_cleared: int = 0
    rounds_cleared: int = 0
    kills: int = 0
    crushed: int = 0
    gold_earned: int = 0
    wagons_bought: int = 0
    gold_left: int = 0
    won: bool = False

    @property
    def monsters_defeated(self) -> int:
        return self.kills + self.crushed


@dataclass
class GameState:
    """State container shared by the scenes during a run."""

    phase: GamePhase = GamePhase.PLAYING
    gold: int = 0
    rounds_on_map: int = 0
    map_index: int = 0
    total_purchased: int = 0
    locomotive_hp: float = 0.0
    stats: RunStats = field(default_factory=RunStats)

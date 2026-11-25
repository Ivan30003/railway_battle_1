"""Infantry wagons and the soldiers they drop.

An infantry wagon releases a small squad every ``drop_interval`` seconds. The
soldiers jump out on both sides of the wagon (perpendicular to the direction of
travel); the train keeps moving and leaves them behind. From that moment the
soldiers are independent: they hold their ground and fire hitscan rifles at the
nearest monster within ``soldier_range``.

Soldiers are fragile by design: a single monster attack kills one. To make them
worth their price, monsters treat any living soldier as a priority target and
ignore the train until the soldiers are gone (see :mod:`game.core.monsters`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from game.core.combat import Shot
from game.core.config import INFANTRY_WAGON, WagonConfig
from game.core.monsters import Monster
from game.core.train import Train

Point = tuple[float, float]

SOLDIER_KIND = "INFANTRY"


@dataclass
class Soldier:
    """A single infantryman dropped by an infantry wagon."""

    position: Point
    damage: float
    range: float
    fire_interval: float
    radius: float = 6.0
    hp: float = 1.0
    max_hp: float = 1.0
    cooldown: float = 0.0
    angle_deg: float = 0.0

    @property
    def is_alive(self) -> bool:
        return self.hp > 0.0

    def take_damage(self, amount: float) -> None:
        self.hp = max(0.0, self.hp - max(0.0, amount))


@dataclass(frozen=True)
class InfantryUpdate:
    """Outcome of one infantry-system tick."""

    shots: tuple[Shot, ...] = ()
    kills: int = 0
    gold: int = 0
    spawned: int = 0


class InfantrySystem:
    """Owns the soldiers and the drop timers of all infantry wagons."""

    def __init__(self, config: WagonConfig) -> None:
        self.drop_interval = _required(config.drop_interval, "drop_interval")
        self.soldiers_per_drop = int(
            _required(config.soldiers_per_drop, "soldiers_per_drop")
        )
        self.drop_offset = _required(config.drop_offset, "drop_offset")
        self.soldier_range = _required(config.soldier_range, "soldier_range")
        self.soldier_damage = _required(config.soldier_damage, "soldier_damage")
        self.soldier_fire_interval = _required(
            config.soldier_fire_interval,
            "soldier_fire_interval",
        )
        self.soldier_radius = _required(config.soldier_radius, "soldier_radius")
        self.soldiers: list[Soldier] = []
        self.spawned_total = 0
        self._kinds: list[str] = []
        self._timers: list[float] = []

    def update(
        self,
        dt: float,
        train: Train,
        monsters: list[Monster],
    ) -> InfantryUpdate:
        """Drop new soldiers and let the existing ones fire."""
        if dt <= 0.0:
            return InfantryUpdate()

        self._sync(train)
        spawned = self._drop(dt, train)
        shots, kills, gold = self._fire(dt, monsters)
        return InfantryUpdate(
            shots=shots,
            kills=kills,
            gold=gold,
            spawned=spawned,
        )

    # ------------------------------------------------------------------
    # Drop timers
    # ------------------------------------------------------------------
    def _sync(self, train: Train) -> None:
        """Keep one drop timer per wagon, following wagon removal and purchase.

        Wagon indices are not stable: destroying a wagon in the middle shifts
        every wagon behind it forward. The timer list is reconciled with the
        current kinds, so each infantry wagon keeps its own countdown.
        """
        kinds = list(train.wagons)
        if kinds == self._kinds:
            return

        old_kinds = list(self._kinds)
        timers = list(self._timers)
        index = 0
        while index < len(old_kinds) and index < len(kinds):
            if old_kinds[index] == kinds[index]:
                index += 1
                continue
            # The wagon at this slot was removed and the rest moved forward.
            old_kinds.pop(index)
            timers.pop(index)
        while len(old_kinds) > len(kinds):
            old_kinds.pop()
            timers.pop()
        while len(old_kinds) < len(kinds):
            slot = len(old_kinds)
            old_kinds.append(kinds[slot])
            timers.append(self.drop_interval)

        self._kinds = kinds
        self._timers = timers

    def _drop(self, dt: float, train: Train) -> int:
        if not self._timers:
            return 0

        cars = {
            car.wagon_index: car
            for car in train.car_samples()
            if car.wagon_index is not None
        }
        spawned = 0
        for index, kind in enumerate(train.wagons):
            if kind != INFANTRY_WAGON or index >= len(self._timers):
                continue
            car = cars.get(index)
            if car is None:
                continue
            self._timers[index] -= dt
            while self._timers[index] <= 0.0:
                self._timers[index] += self.drop_interval
                self._spawn_squad(car.sample.position, car.sample.direction)
                spawned += self.soldiers_per_drop
        self.spawned_total += spawned
        return spawned

    def _spawn_squad(self, center: Point, direction: Point) -> None:
        perpendicular = (-direction[1], direction[0])
        for side in (-1.0, 1.0):
            position = (
                center[0] + perpendicular[0] * self.drop_offset * side,
                center[1] + perpendicular[1] * self.drop_offset * side,
            )
            self.soldiers.append(
                Soldier(
                    position=position,
                    damage=self.soldier_damage,
                    range=self.soldier_range,
                    fire_interval=self.soldier_fire_interval,
                    radius=self.soldier_radius,
                )
            )

    # ------------------------------------------------------------------
    # Rifle fire
    # ------------------------------------------------------------------
    def _fire(
        self,
        dt: float,
        monsters: list[Monster],
    ) -> tuple[tuple[Shot, ...], int, int]:
        shots: list[Shot] = []
        for soldier in self.soldiers:
            soldier.cooldown = max(0.0, soldier.cooldown - dt)
            target = _nearest_monster(soldier.position, soldier.range, monsters)
            if target is None:
                continue
            soldier.angle_deg = _angle_to(soldier.position, target.position)
            if soldier.cooldown > 0.0:
                continue
            soldier.cooldown = soldier.fire_interval
            before = target.hp
            target.take_damage(soldier.damage)
            dealt = min(soldier.damage, before)
            shots.append(
                Shot(
                    origin=soldier.position,
                    target=target.position,
                    damage=dealt,
                    kind=SOLDIER_KIND,
                )
            )

        killed = [monster for monster in monsters if not monster.is_alive]
        if killed:
            monsters[:] = [monster for monster in monsters if monster.is_alive]
        gold = sum(monster.gold for monster in killed)
        return tuple(shots), len(killed), gold


def _required(value: float | int | None, field: str) -> float:
    if value is None:
        raise ValueError(f"Infantry config is missing {field}")
    return float(value)


def _nearest_monster(position: Point, reach: float, monsters: list[Monster]) -> Monster | None:
    best: Monster | None = None
    best_distance = math.inf
    for monster in monsters:
        if not monster.is_alive:
            continue
        distance = math.hypot(
            monster.position[0] - position[0],
            monster.position[1] - position[1],
        )
        if distance > reach:
            continue
        if distance < best_distance:
            best_distance = distance
            best = monster
    return best


def _angle_to(origin: Point, target: Point) -> float:
    return math.degrees(math.atan2(target[1] - origin[1], target[0] - origin[0])) % 360.0


__all__ = [
    "SOLDIER_KIND",
    "InfantrySystem",
    "InfantryUpdate",
    "Soldier",
]

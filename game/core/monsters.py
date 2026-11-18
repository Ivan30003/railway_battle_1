"""Monsters: spawning, chasing, attacking and being crushed by the train.

Monsters spawn beside the railway at ``spawn_margin`` pixels from the route,
then chase the locomotive. They attack from ``monster_attack_range`` plus their
own radius, while a moving train crushes anything inside ``train_crush_radius``
plus the monster radius. Crushing rewards gold but briefly slows the train.

Ice turrets stack ``slow_percent`` on a monster up to a cap and refresh its
``slow_timer``; while the timer runs the monster moves at ``effective_speed``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass

from game.core.config import MonsterConfig, SpawnConfig
from game.core.path import PathRoute
from game.core.train import Train

Point = tuple[float, float]

FAST_KIND = "FAST_WEAK"
TANK_KIND = "SLOW_TANK"
_TANK_RADIUS_SCALE = 1.35
_DEFAULT_MAX_MONSTERS = 300


@dataclass
class Monster:
    """A single monster chasing the train."""

    kind: str
    position: Point
    hp: float
    max_hp: float
    speed: float
    gold: int
    damage: float
    attack_interval: float
    radius: float
    attack_timer: float = 0.0
    slow_percent: float = 0.0
    slow_timer: float = 0.0

    @property
    def is_alive(self) -> bool:
        return self.hp > 0.0

    @property
    def is_slowed(self) -> bool:
        return self.slow_timer > 0.0 and self.slow_percent > 0.0

    @property
    def effective_speed(self) -> float:
        if not self.is_slowed:
            return self.speed
        return self.speed * (1.0 - self.slow_percent)

    def distance_to(self, point: Point) -> float:
        return math.hypot(self.position[0] - point[0], self.position[1] - point[1])

    def apply_slow(self, percent: float, duration: float, *, max_percent: float = 1.0) -> None:
        """Add a slow effect, capping it at ``max_percent``.

        Repeated hits stack their percentages and refresh the timer, so a
        steady ice stream keeps a monster slowed for as long as it keeps
        hitting.
        """
        percent = max(0.0, percent)
        if percent <= 0.0 or duration <= 0.0:
            return
        cap = max(0.0, min(1.0, max_percent))
        self.slow_percent = min(cap, self.slow_percent + percent)
        if self.slow_percent > 0.0:
            self.slow_timer = max(self.slow_timer, duration)

    def tick_slow(self, dt: float) -> None:
        """Advance the slow timer and clear the effect once it expires."""
        if self.slow_timer <= 0.0:
            self.slow_timer = 0.0
            self.slow_percent = 0.0
            return
        self.slow_timer = max(0.0, self.slow_timer - dt)
        if self.slow_timer == 0.0:
            self.slow_percent = 0.0

    def move_toward(self, target: Point, dt: float) -> None:
        """Move towards ``target`` without overshooting it."""
        distance = self.distance_to(target)
        if distance <= 0.0 or dt <= 0.0:
            return
        step = min(distance, self.effective_speed * dt)
        self.position = (
            self.position[0] + (target[0] - self.position[0]) / distance * step,
            self.position[1] + (target[1] - self.position[1]) / distance * step,
        )

    def take_damage(self, amount: float) -> None:
        self.hp = max(0.0, self.hp - max(0.0, amount))


class MonsterSpawner:
    """Spawns monsters with a ramping interval and tank probability."""

    def __init__(
        self,
        route: PathRoute,
        spawn: SpawnConfig,
        monster_configs: Mapping[str, MonsterConfig],
        *,
        hit_radius: float,
        rng: random.Random | None = None,
    ) -> None:
        if not monster_configs:
            raise ValueError("At least one monster type is required")
        self.route = route
        self.spawn = spawn
        self.monster_configs = dict(monster_configs)
        self.hit_radius = hit_radius
        self.rng = rng if rng is not None else random.Random()
        self.elapsed = 0.0
        self._timer = spawn.initial_interval

    @property
    def ramp(self) -> float:
        if self.spawn.ramp_seconds <= 0.0:
            return 1.0
        return min(self.elapsed / self.spawn.ramp_seconds, 1.0)

    @property
    def spawn_interval(self) -> float:
        return self.spawn.initial_interval + (
            self.spawn.min_interval - self.spawn.initial_interval
        ) * self.ramp

    @property
    def tank_share(self) -> float:
        return self.spawn.tank_share_start + (
            self.spawn.tank_share_max - self.spawn.tank_share_start
        ) * self.ramp

    def update(self, dt: float) -> list[Monster]:
        """Advance the spawn timer and return all monsters spawned this tick."""
        if dt <= 0.0:
            return []
        self.elapsed += dt
        self._timer -= dt
        spawned: list[Monster] = []
        while self._timer <= 0.0:
            spawned.append(self.spawn_one())
            self._timer += self.spawn_interval
        return spawned

    def spawn_one(self) -> Monster:
        sample = self.route.sample(self.rng.uniform(0.0, self.route.total_length))
        side = self.rng.choice((-1.0, 1.0))
        perpendicular = (-sample.direction[1], sample.direction[0])
        margin = self.spawn.spawn_margin * side
        position = (
            sample.position[0] + perpendicular[0] * margin,
            sample.position[1] + perpendicular[1] * margin,
        )

        kind = TANK_KIND if self.rng.random() < self.tank_share else FAST_KIND
        config = self.monster_configs.get(kind)
        if config is None:
            kind = next(iter(self.monster_configs))
            config = self.monster_configs[kind]
        radius = self.hit_radius * (_TANK_RADIUS_SCALE if kind == TANK_KIND else 1.0)
        return Monster(
            kind=kind,
            position=position,
            hp=config.hp,
            max_hp=config.hp,
            speed=config.speed,
            gold=config.gold,
            damage=config.damage,
            attack_interval=config.attack_interval,
            radius=radius,
            attack_timer=config.attack_interval,
        )


@dataclass(frozen=True)
class MonsterUpdate:
    """Outcome of one monster-system tick."""

    damage: float = 0.0
    gold: int = 0
    crushed: int = 0


class MonsterSystem:
    """Owns the monsters, the spawner and their interactions with the train."""

    def __init__(
        self,
        route: PathRoute,
        spawn: SpawnConfig,
        monster_configs: Mapping[str, MonsterConfig],
        *,
        attack_range: float,
        crush_radius: float,
        hit_radius: float,
        rng: random.Random | None = None,
        max_monsters: int = _DEFAULT_MAX_MONSTERS,
    ) -> None:
        self.spawner = MonsterSpawner(
            route,
            spawn,
            monster_configs,
            hit_radius=hit_radius,
            rng=rng,
        )
        self.monsters: list[Monster] = []
        self.attack_range = attack_range
        self.crush_radius = crush_radius
        self.max_monsters = max_monsters
        self.crushed_total = 0

    def update(
        self,
        dt: float,
        train: Train,
        *,
        train_moving: bool = True,
    ) -> MonsterUpdate:
        if dt <= 0.0:
            return MonsterUpdate()

        for monster in self.spawner.update(dt):
            if len(self.monsters) < self.max_monsters:
                self.monsters.append(monster)
        self.monsters = [monster for monster in self.monsters if monster.is_alive]

        target = train.locomotive_sample().position
        for monster in self.monsters:
            monster.attack_timer = max(0.0, monster.attack_timer - dt)
            monster.tick_slow(dt)
            if monster.distance_to(target) > self.attack_range + monster.radius:
                monster.move_toward(target, dt)

        crushed, gold = self._crush(train) if train_moving else (0, 0)

        damage = 0.0
        for monster in self.monsters:
            reach = self.attack_range + monster.radius
            if monster.distance_to(target) <= reach and monster.attack_timer <= 0.0:
                damage += monster.damage
                monster.attack_timer = monster.attack_interval

        self.monsters = [monster for monster in self.monsters if monster.is_alive]
        self.crushed_total += crushed
        return MonsterUpdate(damage=damage, gold=gold, crushed=crushed)

    def _crush(self, train: Train) -> tuple[int, int]:
        cars = train.car_samples()
        survivors: list[Monster] = []
        crushed = 0
        gold = 0
        for monster in self.monsters:
            hit = any(
                monster.distance_to(car.sample.position)
                <= self.crush_radius + monster.radius
                for car in cars
            )
            if hit:
                crushed += 1
                gold += monster.gold
            else:
                survivors.append(monster)
        self.monsters = survivors
        return crushed, gold

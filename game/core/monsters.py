"""Monsters: spawning, chasing, attacking and being crushed by the train.

Monsters spawn on the screen edge opposite the average position of the train,
then chase their target. They attack from ``monster_attack_range`` plus their
own radius, while a moving train crushes anything inside ``train_crush_radius``
plus the monster radius. Crushing rewards gold but briefly slows the train.

Soldiers dropped by infantry wagons are a priority target: while at least one
living soldier exists, every monster runs at the nearest one and ignores the
train. A single monster attack kills a soldier.

Ice turrets stack ``slow_percent`` on a monster up to a cap and refresh its
``slow_timer``; while the timer runs the monster moves at ``effective_speed``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from game.core.config import MonsterConfig, SpawnConfig
from game.core.train import Train

Point = tuple[float, float]

FAST_KIND = "FAST_WEAK"
TANK_KIND = "SLOW_TANK"
_TANK_RADIUS_SCALE = 1.35
_DEFAULT_MAX_MONSTERS = 300


class SoldierLike(Protocol):
    """Minimal interface the monster system needs from a soldier."""

    position: Point
    radius: float

    @property
    def is_alive(self) -> bool: ...

    def take_damage(self, amount: float) -> None: ...


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
    """Spawns monsters on the screen edge opposite the train.

    The train's average position (locomotive plus wagons) is compared with the
    screen centre. Monsters appear on the opposite edge, so a train driving
    along the right side of the map is attacked from the left side.
    """

    def __init__(
        self,
        spawn: SpawnConfig,
        monster_configs: Mapping[str, MonsterConfig],
        *,
        world_size: Point,
        train_center: Callable[[], Point],
        hit_radius: float,
        rng: random.Random | None = None,
        purchased_wagons: Callable[[], int] | None = None,
    ) -> None:
        if not monster_configs:
            raise ValueError("At least one monster type is required")
        if world_size[0] <= 0.0 or world_size[1] <= 0.0:
            raise ValueError("world_size must be positive")
        self.spawn = spawn
        self.monster_configs = dict(monster_configs)
        self.world_size = (float(world_size[0]), float(world_size[1]))
        self.train_center = train_center
        self.hit_radius = hit_radius
        self.rng = rng if rng is not None else random.Random()
        self.purchased_wagons = purchased_wagons if purchased_wagons is not None else lambda: 0
        self._timer = self.cooldown

    @property
    def cooldown(self) -> float:
        """Enemy spawn cooldown for the current number of bought wagons.

        The cooldown starts at ``cooldown_start`` and drops by ``cooldown_step``
        for every wagon bought. ``purchased_wagons`` is the cumulative purchase
        counter, so losing a wagon later does not make spawning slower again.
        """
        purchased = max(0, int(self.purchased_wagons()))
        return max(
            self.spawn.cooldown_min,
            self.spawn.cooldown_start - self.spawn.cooldown_step * purchased,
        )

    def update(self, dt: float) -> list[Monster]:
        """Advance the spawn timer and return all monsters spawned this tick."""
        if dt <= 0.0:
            return []
        self._timer -= dt
        spawned: list[Monster] = []
        while self._timer <= 0.0:
            spawned.append(self.spawn_one())
            self._timer += self.cooldown
        return spawned

    def spawn_one(self) -> Monster:
        kind = self._choose_kind()
        config = self.monster_configs.get(kind)
        if config is None:
            kind = next(iter(self.monster_configs))
            config = self.monster_configs[kind]
        radius = self.hit_radius * (_TANK_RADIUS_SCALE if kind == TANK_KIND else 1.0)
        return Monster(
            kind=kind,
            position=self._edge_position(radius),
            hp=config.hp,
            max_hp=config.hp,
            speed=config.speed,
            gold=config.gold,
            damage=config.damage,
            attack_interval=config.attack_interval,
            radius=radius,
            attack_timer=config.attack_interval,
        )

    def _edge_position(self, radius: float) -> Point:
        """Pick a point on the screen edge opposite the train's average position.

        ``radius`` is used as an inset so the whole monster sprite is visible
        while its rim still touches the screen border.
        """
        width, height = self.world_size
        train_x, train_y = self.train_center()
        offset_x = (train_x - width / 2.0) / (width / 2.0)
        offset_y = (train_y - height / 2.0) / (height / 2.0)
        if abs(offset_x) >= abs(offset_y):
            edge = "left" if offset_x > 0.0 else "right"
        else:
            edge = "top" if offset_y > 0.0 else "bottom"

        inset_x = min(radius, width / 2.0)
        inset_y = min(radius, height / 2.0)
        if edge == "left":
            return (inset_x, self.rng.uniform(inset_y, height - inset_y))
        if edge == "right":
            return (width - inset_x, self.rng.uniform(inset_y, height - inset_y))
        if edge == "top":
            return (self.rng.uniform(inset_x, width - inset_x), inset_y)
        return (self.rng.uniform(inset_x, width - inset_x), height - inset_y)

    def _choose_kind(self) -> str:
        roll = self.rng.random()
        cumulative = 0.0
        last_kind = ""
        for kind, probability in self.spawn.probability_spawn_dist_start.items():
            last_kind = kind
            cumulative += probability
            if roll < cumulative:
                return kind
        return last_kind if last_kind else next(iter(self.monster_configs))


@dataclass(frozen=True)
class MonsterUpdate:
    """Outcome of one monster-system tick."""

    damage: float = 0.0
    gold: int = 0
    crushed: int = 0
    destroyed_wagons: tuple[int, ...] = ()
    soldiers_lost: int = 0


class MonsterSystem:
    """Owns the monsters, the spawner and their interactions with the train."""

    def __init__(
        self,
        spawn: SpawnConfig,
        monster_configs: Mapping[str, MonsterConfig],
        *,
        world_size: Point,
        train_center: Callable[[], Point],
        attack_range: float,
        crush_radius: float,
        hit_radius: float,
        rng: random.Random | None = None,
        purchased_wagons: Callable[[], int] | None = None,
        max_monsters: int = _DEFAULT_MAX_MONSTERS,
    ) -> None:
        self.spawner = MonsterSpawner(
            spawn,
            monster_configs,
            world_size=world_size,
            train_center=train_center,
            hit_radius=hit_radius,
            rng=rng,
            purchased_wagons=purchased_wagons,
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
        soldiers: list[SoldierLike] | None = None,
        train_moving: bool = True,
    ) -> MonsterUpdate:
        if dt <= 0.0:
            return MonsterUpdate()

        soldiers = soldiers if soldiers is not None else []

        for monster in self.spawner.update(dt):
            if len(self.monsters) < self.max_monsters:
                self.monsters.append(monster)
        self.monsters = [monster for monster in self.monsters if monster.is_alive]

        destroyed_wagons: list[int] = []
        damage = 0.0
        for monster in self.monsters:
            monster.attack_timer = max(0.0, monster.attack_timer - dt)
            monster.tick_slow(dt)
            soldier = _nearest_soldier(monster.position, soldiers)
            if soldier is not None:
                target_position = soldier.position
            else:
                target_position = train.nearest_car(monster.position).sample.position
            if monster.distance_to(target_position) > self.attack_range + monster.radius:
                monster.move_toward(target_position, dt)

        crushed, gold = self._crush(train) if train_moving else (0, 0)

        soldiers_before = sum(1 for soldier in soldiers if soldier.is_alive)
        for monster in self.monsters:
            soldier = _nearest_soldier(monster.position, soldiers)
            if soldier is not None:
                target_position = soldier.position
            else:
                target_position = train.nearest_car(monster.position).sample.position
            reach = self.attack_range + monster.radius
            if monster.distance_to(target_position) > reach:
                continue
            if monster.attack_timer > 0.0:
                continue
            monster.attack_timer = monster.attack_interval
            if soldier is not None:
                # Soldiers are fragile: one monster attack is enough.
                soldier.take_damage(monster.damage)
                continue
            car = train.nearest_car(monster.position)
            if car.wagon_index is None:
                damage += monster.damage
            elif train.damage_wagon(car.wagon_index, monster.damage):
                destroyed_wagons.append(car.wagon_index)

        soldiers[:] = [soldier for soldier in soldiers if soldier.is_alive]
        soldiers_lost = soldiers_before - len(soldiers)
        self.monsters = [monster for monster in self.monsters if monster.is_alive]
        self.crushed_total += crushed
        return MonsterUpdate(
            damage=damage,
            gold=gold,
            crushed=crushed,
            destroyed_wagons=tuple(destroyed_wagons),
            soldiers_lost=soldiers_lost,
        )

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


def _nearest_soldier(
    position: Point,
    soldiers: list[SoldierLike],
) -> SoldierLike | None:
    """Return the closest living soldier, which monsters always prefer."""
    best: SoldierLike | None = None
    best_distance = math.inf
    for soldier in soldiers:
        if not soldier.is_alive:
            continue
        distance = math.hypot(
            soldier.position[0] - position[0],
            soldier.position[1] - position[1],
        )
        if distance < best_distance:
            best_distance = distance
            best = soldier
    return best

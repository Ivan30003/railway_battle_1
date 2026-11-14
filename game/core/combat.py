"""Locomotive cannon, wagon turrets and target reservation.

The locomotive cannon automatically tracks the nearest monster in range. Wagon
turrets rotate towards their target and fire only when the barrel is within
``aim_threshold_deg`` of it. ``reserve`` makes a turret claim its target so
other turrets pick different monsters:

* ``target`` — exclusive target;
* ``primary`` — may take over a target claimed by a ``target`` turret and is
  exclusive among other ``primary`` turrets;
* ``none`` — ignores all reservations and does not reserve anything.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from game.core.config import CannonConfig, WagonConfig
from game.core.monsters import Monster
from game.core.path import RouteSample
from game.core.train import Train

Point = tuple[float, float]

RESERVE_NONE = 0
RESERVE_TARGET = 1
RESERVE_PRIMARY = 2
_RESERVE_LEVELS = {
    "none": RESERVE_NONE,
    "target": RESERVE_TARGET,
    "primary": RESERVE_PRIMARY,
}
CANNON_ROTATION_SPEED_DEG_PER_SEC = 720.0
_TRACER_LIFETIME = 0.08


@dataclass(frozen=True)
class Shot:
    """A hitscan shot used both for damage and for visual tracers."""

    origin: Point
    target: Point
    damage: float
    kind: str
    wagon_index: int | None = None


@dataclass(frozen=True)
class CombatUpdate:
    """Outcome of one combat tick."""

    shots: tuple[Shot, ...] = ()
    damage: float = 0.0
    kills: int = 0
    gold: int = 0


@dataclass(frozen=True)
class _Reservation:
    turret_id: int
    level: int


class ReservationBook:
    """Tracks which turret has claimed which monster."""

    def __init__(self) -> None:
        self._claims: dict[int, _Reservation] = {}

    @property
    def count(self) -> int:
        return len(self._claims)

    def retain(self, alive: set[int]) -> None:
        """Drop claims for monsters that no longer exist."""
        if not self._claims:
            return
        self._claims = {
            key: claim for key, claim in self._claims.items() if key in alive
        }

    def release(self, turret_id: int) -> None:
        self._claims = {
            key: claim
            for key, claim in self._claims.items()
            if claim.turret_id != turret_id
        }

    def is_available(self, monster: Monster, level: int, turret_id: int) -> bool:
        if level == RESERVE_NONE:
            return True
        claim = self._claims.get(id(monster))
        if claim is None or claim.turret_id == turret_id:
            return True
        if level == RESERVE_PRIMARY:
            return claim.level < RESERVE_PRIMARY
        return False

    def claim(self, turret_id: int, monster: Monster, level: int) -> None:
        if level == RESERVE_NONE:
            return
        key = id(monster)
        existing = self._claims.get(key)
        if existing is not None and existing.turret_id != turret_id and existing.level > level:
            return
        self._claims[key] = _Reservation(turret_id, level)


@dataclass
class LocomotiveCannon:
    damage: float
    fire_interval: float
    range: float
    aim_threshold_deg: float
    rotation_speed_deg_per_sec: float = CANNON_ROTATION_SPEED_DEG_PER_SEC
    angle_deg: float | None = None
    cooldown: float = 0.0
    target: Monster | None = None


@dataclass
class WagonTurret:
    index: int
    kind: str
    config: WagonConfig
    angle_deg: float | None = None
    cooldown: float = 0.0
    target: Monster | None = None

    @property
    def reserve_level(self) -> int:
        return _RESERVE_LEVELS.get(self.config.reserve, RESERVE_NONE)


class CombatSystem:
    """Owns the locomotive cannon and the wagon turrets."""

    def __init__(
        self,
        cannon: CannonConfig,
        wagon_configs: Mapping[str, WagonConfig],
        wagon_kinds: list[str],
        *,
        aim_threshold_deg: float,
    ) -> None:
        self.cannon = LocomotiveCannon(
            damage=cannon.damage,
            fire_interval=cannon.fire_interval,
            range=cannon.range,
            aim_threshold_deg=aim_threshold_deg,
        )
        self.turrets: list[WagonTurret] = []
        for index, kind in enumerate(wagon_kinds):
            config = wagon_configs.get(kind)
            if config is None:
                raise ValueError(f"Unknown wagon type: {kind}")
            self.turrets.append(WagonTurret(index=index, kind=kind, config=config))
        self.reservations = ReservationBook()
        self.kills_total = 0
        self.damage_total = 0.0

    def update(
        self,
        dt: float,
        train: Train,
        monsters: list[Monster],
    ) -> CombatUpdate:
        """Advance aiming/firing and apply damage directly to ``monsters``."""
        if dt <= 0.0:
            return CombatUpdate()

        alive = [monster for monster in monsters if monster.is_alive]
        self.reservations.retain({id(monster) for monster in alive})
        cars = train.car_samples()
        shots: list[Shot] = []
        damage = 0.0

        if cars:
            damage += self._update_cannon(dt, cars[0].sample, alive, shots)
        for turret in self.turrets:
            car_index = turret.index + 1
            if car_index < len(cars):
                damage += self._update_turret(dt, turret, cars[car_index].sample, alive, shots)
            else:
                if turret.target is not None:
                    self.reservations.release(turret.index)
                turret.target = None

        killed = [monster for monster in alive if not monster.is_alive]
        monsters[:] = [monster for monster in monsters if monster.is_alive]
        gold = sum(monster.gold for monster in killed)
        self.kills_total += len(killed)
        self.damage_total += damage
        return CombatUpdate(
            shots=tuple(shots),
            damage=damage,
            kills=len(killed),
            gold=gold,
        )

    # ------------------------------------------------------------------
    # Locomotive cannon
    # ------------------------------------------------------------------
    def _update_cannon(
        self,
        dt: float,
        sample: RouteSample,
        monsters: list[Monster],
        shots: list[Shot],
    ) -> float:
        cannon = self.cannon
        cannon.cooldown = max(0.0, cannon.cooldown - dt)
        if cannon.angle_deg is None:
            cannon.angle_deg = _direction_angle(sample.direction)

        target = self._nearest_target(sample.position, cannon.range, monsters)
        cannon.target = target
        if target is None:
            return 0.0

        desired = _angle_to(sample.position, target.position)
        cannon.angle_deg = _rotate_toward(
            cannon.angle_deg,
            desired,
            cannon.rotation_speed_deg_per_sec * dt,
        )
        if cannon.cooldown > 0.0:
            return 0.0
        if _angle_difference(cannon.angle_deg, desired) > cannon.aim_threshold_deg:
            return 0.0
        if not target.is_alive:
            return 0.0

        dealt = _apply_damage(target, cannon.damage)
        shots.append(
            Shot(
                origin=sample.position,
                target=target.position,
                damage=cannon.damage,
                kind="CANNON",
            )
        )
        cannon.cooldown = cannon.fire_interval
        return dealt

    @staticmethod
    def _nearest_target(origin: Point, reach: float, monsters: list[Monster]) -> Monster | None:
        candidates = [
            monster
            for monster in monsters
            if monster.is_alive and _distance(origin, monster.position) <= reach
        ]
        return min(
            candidates,
            key=lambda monster: _distance(origin, monster.position),
            default=None,
        )

    # ------------------------------------------------------------------
    # Wagon turrets
    # ------------------------------------------------------------------
    def _update_turret(
        self,
        dt: float,
        turret: WagonTurret,
        sample: RouteSample,
        monsters: list[Monster],
        shots: list[Shot],
    ) -> float:
        turret.cooldown = max(0.0, turret.cooldown - dt)
        if turret.angle_deg is None:
            turret.angle_deg = _direction_angle(sample.direction)

        candidates = self._turret_candidates(turret, sample.position, monsters)
        target = self._choose_target(turret, sample.position, candidates)
        if target is not turret.target:
            self.reservations.release(turret.index)
            turret.target = target
        if target is None:
            return 0.0

        if turret.reserve_level != RESERVE_NONE:
            self.reservations.claim(turret.index, target, turret.reserve_level)

        desired = _angle_to(sample.position, target.position)
        turret.angle_deg = _rotate_toward(
            turret.angle_deg,
            desired,
            turret.config.rotation_speed_deg_per_sec * dt,
        )
        if turret.cooldown > 0.0:
            return 0.0
        if _angle_difference(turret.angle_deg, desired) > turret.config.aim_threshold_deg:
            return 0.0
        if not target.is_alive:
            return 0.0

        dealt = _apply_damage(target, turret.config.damage)
        shots.append(
            Shot(
                origin=sample.position,
                target=target.position,
                damage=turret.config.damage,
                kind=turret.kind,
                wagon_index=turret.index,
            )
        )
        turret.cooldown = turret.config.fire_interval
        return dealt

    def _turret_candidates(
        self,
        turret: WagonTurret,
        origin: Point,
        monsters: list[Monster],
    ) -> list[Monster]:
        level = turret.reserve_level
        return [
            monster
            for monster in monsters
            if monster.is_alive
            and _distance(origin, monster.position) <= turret.config.radius
            and self.reservations.is_available(monster, level, turret.index)
        ]

    def _choose_target(
        self,
        turret: WagonTurret,
        origin: Point,
        candidates: list[Monster],
    ) -> Monster | None:
        if not candidates:
            return None

        best = min(
            candidates,
            key=lambda monster: self._target_key(turret, origin, monster),
        )
        current = turret.target
        if current is not None and any(monster is current for monster in candidates):
            if (
                self._target_key(turret, origin, current)[0]
                <= self._target_key(turret, origin, best)[0]
            ):
                return current
        return best

    @staticmethod
    def _target_key(turret: WagonTurret, origin: Point, monster: Monster) -> tuple[int, float]:
        priority = turret.config.priority
        if priority is None:
            rank = 0
        else:
            try:
                rank = priority.index(monster.kind)
            except ValueError:
                rank = len(priority)
        return rank, _distance(origin, monster.position)


def _apply_damage(monster: Monster, damage: float) -> float:
    before = monster.hp
    monster.take_damage(damage)
    return before - monster.hp


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _angle_to(origin: Point, target: Point) -> float:
    return math.degrees(math.atan2(target[1] - origin[1], target[0] - origin[0])) % 360.0


def _direction_angle(direction: Point) -> float:
    return math.degrees(math.atan2(direction[1], direction[0])) % 360.0


def _angle_difference(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _rotate_toward(current: float, target: float, max_step: float) -> float:
    if max_step <= 0.0:
        return current % 360.0
    delta = (target - current + 180.0) % 360.0 - 180.0
    if abs(delta) <= max_step:
        return target % 360.0
    return (current + math.copysign(max_step, delta)) % 360.0

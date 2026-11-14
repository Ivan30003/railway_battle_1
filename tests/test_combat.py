from __future__ import annotations

import math

import pytest

from game.core.combat import (
    RESERVE_TARGET,
    CombatSystem,
    ReservationBook,
)
from game.core.config import CannonConfig, WagonConfig
from game.core.monsters import FAST_KIND, TANK_KIND, Monster
from game.core.path import PathRoute
from game.core.train import Train


def _route() -> PathRoute:
    return PathRoute([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])


def _train(wagons: list[str] | None = None) -> Train:
    return Train(
        route=_route(),
        speed=70.0,
        wagon_spacing=10.0,
        wagons=[] if wagons is None else wagons,
    )


def _cannon(**overrides: object) -> CannonConfig:
    params = {"damage": 30.0, "fire_interval": 0.35, "range": 450.0}
    params.update(overrides)
    return CannonConfig(**params)  # type: ignore[arg-type]


def _wagon(reserve: str = "target", **overrides: object) -> WagonConfig:
    params = {
        "radius": 150.0,
        "rotation_speed_deg_per_sec": 360.0,
        "fire_interval": 0.2,
        "damage": 5.0,
        "hp": 50.0,
        "aim_threshold_deg": 7.0,
        "priority": None,
        "reserve": reserve,
    }
    params.update(overrides)
    return WagonConfig(**params)  # type: ignore[arg-type]


def _monster(
    kind: str = FAST_KIND,
    position: tuple[float, float] = (0.0, 0.0),
    *,
    hp: float | None = None,
    gold: int = 1,
) -> Monster:
    base_hp = 10.0 if kind == FAST_KIND else 50.0
    total_hp = base_hp if hp is None else hp
    return Monster(
        kind=kind,
        position=position,
        hp=total_hp,
        max_hp=total_hp,
        speed=80.0,
        gold=gold,
        damage=5.0,
        attack_interval=1.0,
        radius=10.0,
    )


def _combat(
    wagons: list[str] | None = None,
    configs: dict[str, WagonConfig] | None = None,
    *,
    cannon: CannonConfig | None = None,
    aim_threshold_deg: float = 7.0,
    disable_cannon: bool = True,
) -> CombatSystem:
    kinds = [] if wagons is None else wagons
    if configs is None:
        configs = {kind: _wagon() for kind in kinds}
    system = CombatSystem(
        cannon if cannon is not None else _cannon(),
        configs,
        kinds,
        aim_threshold_deg=aim_threshold_deg,
    )
    if disable_cannon:
        system.cannon.range = -1.0
    return system


def _car_origin(train: Train, index: int) -> tuple[float, float]:
    return train.car_samples()[index].sample.position


def _point_at(
    origin: tuple[float, float],
    angle_deg: float,
    distance: float,
) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (
        origin[0] + math.cos(angle) * distance,
        origin[1] + math.sin(angle) * distance,
    )


# ----------------------------------------------------------------------
# Locomotive cannon
# ----------------------------------------------------------------------
def test_cannon_hits_the_nearest_monster_in_range() -> None:
    system = _combat(cannon=_cannon(damage=10.0), disable_cannon=False)
    near = _monster(position=(100.0, 0.0), hp=20.0)
    far = _monster(position=(200.0, 0.0), hp=20.0)

    result = system.update(0.01, _train(), [near, far])

    assert near.hp == pytest.approx(10.0)
    assert far.hp == pytest.approx(20.0)
    assert result.damage == pytest.approx(10.0)
    assert len(result.shots) == 1
    assert result.shots[0].kind == "CANNON"


def test_cannon_ignores_monsters_out_of_range() -> None:
    system = _combat(cannon=_cannon(range=100.0), disable_cannon=False)
    monster = _monster(position=(500.0, 0.0))

    result = system.update(0.01, _train(), [monster])

    assert monster.hp == pytest.approx(10.0)
    assert result.shots == ()
    assert system.cannon.target is None


def test_cannon_waits_for_the_fire_interval() -> None:
    system = _combat(cannon=_cannon(damage=30.0), disable_cannon=False)
    monster = _monster(position=(100.0, 0.0), hp=100.0)

    system.update(0.01, _train(), [monster])
    assert monster.hp == pytest.approx(70.0)

    system.update(0.1, _train(), [monster])
    assert monster.hp == pytest.approx(70.0)

    system.update(0.3, _train(), [monster])
    assert monster.hp == pytest.approx(40.0)


def test_cannon_rotates_towards_the_target_before_firing() -> None:
    system = _combat(cannon=_cannon(damage=10.0), disable_cannon=False)
    monster = _monster(position=(0.0, 100.0), hp=20.0)

    result = system.update(0.05, _train(), [monster])

    assert system.cannon.angle_deg == pytest.approx(36.0)
    assert result.shots == ()

    system.update(0.05, _train(), [monster])
    system.update(0.05, _train(), [monster])

    assert monster.hp == pytest.approx(10.0)


def test_cannon_respects_the_aim_threshold() -> None:
    system = _combat(cannon=_cannon(), disable_cannon=False)
    monster = _monster(position=(0.0, 100.0))
    train = _train()

    system.cannon.angle_deg = 80.0
    assert system.update(0.001, train, [monster]).shots == ()

    system.cannon.angle_deg = 88.0
    assert len(system.update(0.001, train, [monster]).shots) == 1


# ----------------------------------------------------------------------
# Wagon turrets
# ----------------------------------------------------------------------
def test_turret_fires_only_when_its_barrel_is_aimed() -> None:
    configs = {"MACHINEGUN": _wagon(damage=7.0)}
    system = _combat(["MACHINEGUN"], configs)
    train = _train(["MACHINEGUN"])
    origin = _car_origin(train, 1)
    system.turrets[0].angle_deg = 0.0
    monster = _monster(position=_point_at(origin, 0.0, 60.0), hp=20.0)

    result = system.update(0.01, train, [monster])

    assert monster.hp == pytest.approx(13.0)
    assert len(result.shots) == 1
    assert result.shots[0].kind == "MACHINEGUN"


def test_turret_turns_at_its_configured_speed() -> None:
    configs = {"MACHINEGUN": _wagon(rotation_speed_deg_per_sec=90.0)}
    system = _combat(["MACHINEGUN"], configs)
    train = _train(["MACHINEGUN"])
    origin = _car_origin(train, 1)
    system.turrets[0].angle_deg = 0.0
    monster = _monster(position=_point_at(origin, 90.0, 50.0))

    system.update(0.1, train, [monster])

    assert system.turrets[0].angle_deg == pytest.approx(9.0)


def test_turret_uses_its_own_aim_threshold() -> None:
    configs = {"SNIPER": _wagon(aim_threshold_deg=20.0, rotation_speed_deg_per_sec=90.0)}
    system = _combat(["SNIPER"], configs)
    train = _train(["SNIPER"])
    origin = _car_origin(train, 1)
    system.turrets[0].angle_deg = 75.0
    monster = _monster(position=_point_at(origin, 90.0, 50.0), hp=100.0)

    system.update(0.01, train, [monster])

    assert monster.hp == pytest.approx(95.0)


def test_turret_priority_prefers_the_configured_kind() -> None:
    configs = {"SNIPER": _wagon(priority=(TANK_KIND, FAST_KIND), damage=5.0)}
    system = _combat(["SNIPER"], configs)
    train = _train(["SNIPER"])
    origin = _car_origin(train, 1)
    system.turrets[0].angle_deg = 0.0
    fast = _monster(FAST_KIND, _point_at(origin, 0.0, 50.0), hp=100.0)
    tank = _monster(TANK_KIND, _point_at(origin, 0.0, 80.0), hp=100.0)

    system.update(0.01, train, [fast, tank])

    assert system.turrets[0].target is tank
    assert tank.hp == pytest.approx(95.0)
    assert fast.hp == pytest.approx(100.0)


def test_turret_without_priority_targets_the_nearest_monster() -> None:
    configs = {"MACHINEGUN": _wagon(priority=None)}
    system = _combat(["MACHINEGUN"], configs)
    train = _train(["MACHINEGUN"])
    origin = _car_origin(train, 1)
    system.turrets[0].angle_deg = 0.0
    near = _monster(position=_point_at(origin, 0.0, 40.0), hp=100.0)
    far = _monster(position=_point_at(origin, 0.0, 80.0), hp=100.0)

    system.update(0.01, train, [near, far])

    assert system.turrets[0].target is near
    assert near.hp == pytest.approx(95.0)
    assert far.hp == pytest.approx(100.0)


# ----------------------------------------------------------------------
# Reservations
# ----------------------------------------------------------------------
def _two_turret_system(
    first_kind: str,
    second_kind: str,
    *,
    first_reserve: str = "target",
    second_reserve: str = "target",
) -> tuple[CombatSystem, Train, Monster, Monster]:
    configs = {first_kind: _wagon(first_reserve)}
    if second_kind != first_kind:
        configs[second_kind] = _wagon(second_reserve)
    system = _combat([first_kind, second_kind], configs)
    train = _train([first_kind, second_kind])
    first_origin = _car_origin(train, 1)
    second_origin = _car_origin(train, 2)
    midpoint = (
        (first_origin[0] + second_origin[0]) / 2.0,
        (first_origin[1] + second_origin[1]) / 2.0,
    )
    first = _monster(position=_point_at(midpoint, 0.0, 50.0), hp=100.0)
    second = _monster(position=_point_at(midpoint, 0.0, 60.0), hp=100.0)
    return system, train, first, second


def test_target_reservations_are_exclusive() -> None:
    system, train, first, second = _two_turret_system("MACHINEGUN", "MACHINEGUN")

    system.update(0.01, train, [first, second])

    assert system.turrets[0].target is first
    assert system.turrets[1].target is second
    assert system.reservations.count == 2


def test_primary_turret_can_take_a_target_reservation() -> None:
    system, train, first, second = _two_turret_system(
        "MACHINEGUN",
        "MORTAR",
        first_reserve="target",
        second_reserve="primary",
    )

    system.update(0.01, train, [first, second])

    assert system.turrets[0].target is first
    assert system.turrets[1].target is first
    assert system.reservations.count == 1


def test_none_reservation_ignores_other_claims_and_reserves_nothing() -> None:
    system, train, first, second = _two_turret_system(
        "MACHINEGUN",
        "ICE",
        first_reserve="target",
        second_reserve="none",
    )

    system.update(0.01, train, [first, second])

    assert system.turrets[0].target is first
    assert system.turrets[1].target is first
    assert system.reservations.count == 1


def test_reservation_moves_to_the_new_target() -> None:
    configs = {"MACHINEGUN": _wagon()}
    system = _combat(["MACHINEGUN"], configs)
    train = _train(["MACHINEGUN"])
    origin = _car_origin(train, 1)
    first = _monster(position=_point_at(origin, 0.0, 50.0), hp=100.0)
    second = _monster(position=_point_at(origin, 0.0, 60.0), hp=100.0)

    system.update(0.01, train, [first])
    assert system.reservations.is_available(first, RESERVE_TARGET, 999) is False

    system.update(0.01, train, [second])

    assert system.turrets[0].target is second
    assert system.reservations.count == 1
    assert system.reservations.is_available(first, RESERVE_TARGET, 999) is True
    assert system.reservations.is_available(second, RESERVE_TARGET, 999) is False


def test_reservation_book_drops_stale_claims() -> None:
    book = ReservationBook()
    first = _monster()
    second = _monster()
    book.claim(1, first, RESERVE_TARGET)
    assert book.count == 1

    book.retain({id(second)})

    assert book.count == 0


# ----------------------------------------------------------------------
# Kills and gold
# ----------------------------------------------------------------------
def test_killed_monsters_are_removed_and_reward_gold() -> None:
    system = _combat(cannon=_cannon(damage=30.0), disable_cannon=False)
    monster = _monster(position=(100.0, 0.0), hp=10.0, gold=7)
    monsters = [monster]

    result = system.update(0.01, _train(), monsters)

    assert result.kills == 1
    assert result.gold == 7
    assert result.damage == pytest.approx(10.0)
    assert system.kills_total == 1
    assert monsters == []


def test_dead_monsters_are_not_targeted_or_kept() -> None:
    system = _combat(cannon=_cannon(damage=30.0), disable_cannon=False)
    dead = _monster(position=(100.0, 0.0), hp=0.0)
    monsters = [dead]

    result = system.update(0.01, _train(), monsters)

    assert result.shots == ()
    assert monsters == []

from __future__ import annotations

import random

import pytest

from game.core.config import GameConfig, MonsterConfig, SpawnConfig
from game.core.infantry import InfantrySystem, Soldier
from game.core.monsters import FAST_KIND, Monster, MonsterSystem
from game.core.path import PathRoute
from game.core.train import Train


def _route() -> PathRoute:
    return PathRoute([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])


def _train(wagons: list[str] | None = None, **kwargs: object) -> Train:
    params: dict[str, object] = {
        "route": _route(),
        "speed": 10.0,
        "wagon_spacing": 40.0,
        "wagons": [] if wagons is None else wagons,
    }
    params.update(kwargs)
    return Train(**params)  # type: ignore[arg-type]


def _infantry() -> InfantrySystem:
    return InfantrySystem(GameConfig.from_dict({}).wagon_configs["INFANTRY"])


def _monster(
    position: tuple[float, float] = (0.0, 0.0),
    *,
    hp: float = 10.0,
    gold: int = 1,
) -> Monster:
    return Monster(
        kind=FAST_KIND,
        position=position,
        hp=hp,
        max_hp=hp,
        speed=80.0,
        gold=gold,
        damage=5.0,
        attack_interval=1.0,
        radius=10.0,
    )


def _monster_system(monsters: list[Monster] | None = None) -> MonsterSystem:
    configs = {
        FAST_KIND: MonsterConfig(
            hp=10.0,
            speed=80.0,
            gold=1,
            damage=5.0,
            attack_interval=1.0,
        ),
    }
    spawn = SpawnConfig(
        cooldown_start=1000.0,
        cooldown_step=0.0,
        cooldown_min=1000.0,
        probability_spawn_dist_start={FAST_KIND: 1.0},
    )
    system = MonsterSystem(
        spawn,
        configs,
        world_size=(200.0, 100.0),
        train_center=lambda: (0.0, 0.0),
        attack_range=24.0,
        crush_radius=18.0,
        hit_radius=10.0,
        rng=random.Random(0),
    )
    if monsters is not None:
        system.monsters = monsters
    return system


def _soldier(position: tuple[float, float]) -> Soldier:
    config = GameConfig.from_dict({}).wagon_configs["INFANTRY"]
    assert config.soldier_damage is not None
    assert config.soldier_range is not None
    assert config.soldier_fire_interval is not None
    assert config.soldier_radius is not None
    return Soldier(
        position=position,
        damage=config.soldier_damage,
        range=config.soldier_range,
        fire_interval=config.soldier_fire_interval,
        radius=config.soldier_radius,
    )


# ----------------------------------------------------------------------
# Dropping soldiers
# ----------------------------------------------------------------------
def test_infantry_wagon_drops_two_soldiers_on_both_sides() -> None:
    train = _train(["INFANTRY"], travelled=40.0)
    infantry = _infantry()

    assert infantry.update(7.0, train, []).spawned == 0
    result = infantry.update(1.1, train, [])

    assert result.spawned == 2
    assert len(infantry.soldiers) == 2
    positions = sorted(soldier.position for soldier in infantry.soldiers)
    assert [point[0] for point in positions] == pytest.approx([0.0, 0.0])
    assert [point[1] for point in positions] == pytest.approx([-26.0, 26.0])
    assert infantry.spawned_total == 2


def test_each_infantry_wagon_drops_on_its_own_timer() -> None:
    train = _train(["INFANTRY", "INFANTRY"], travelled=120.0)
    infantry = _infantry()

    result = infantry.update(8.05, train, [])

    assert result.spawned == 4
    assert len(infantry.soldiers) == 4


def test_drop_timer_follows_a_wagon_that_moves_forward() -> None:
    train = _train(["ICE", "INFANTRY"], travelled=40.0)
    infantry = _infantry()
    assert infantry.update(7.0, train, []).spawned == 0

    train.remove_wagon(0)  # the ICE wagon is destroyed, infantry moves forward
    result = infantry.update(1.1, train, [])

    assert result.spawned == 2
    positions = sorted(soldier.position for soldier in infantry.soldiers)
    assert [point[0] for point in positions] == pytest.approx([0.0, 0.0])
    assert [point[1] for point in positions] == pytest.approx([-26.0, 26.0])


def test_destroyed_infantry_wagon_leaves_its_soldiers_behind() -> None:
    train = _train(["INFANTRY"], travelled=40.0)
    infantry = _infantry()
    infantry.update(8.05, train, [])
    assert len(infantry.soldiers) == 2

    train.remove_wagon(0)
    result = infantry.update(0.1, train, [])

    assert result.spawned == 0
    assert len(infantry.soldiers) == 2


# ----------------------------------------------------------------------
# Rifle fire
# ----------------------------------------------------------------------
def test_soldier_fires_hitscan_at_a_monster_in_range() -> None:
    infantry = _infantry()
    infantry.soldiers = [_soldier((0.0, 0.0))]
    monster = _monster((50.0, 0.0))

    result = infantry.update(0.01, _train(), [monster])

    assert monster.hp == pytest.approx(6.0)
    assert len(result.shots) == 1
    assert result.shots[0].kind == "INFANTRY"
    assert result.shots[0].damage == pytest.approx(4.0)


def test_soldier_respects_its_fire_interval() -> None:
    infantry = _infantry()
    infantry.soldiers = [_soldier((0.0, 0.0))]
    monster = _monster((50.0, 0.0))

    infantry.update(0.01, _train(), [monster])
    assert infantry.update(0.5, _train(), [monster]).shots == ()
    assert monster.hp == pytest.approx(6.0)

    infantry.update(0.7, _train(), [monster])
    assert monster.hp == pytest.approx(2.0)


def test_soldier_ignores_monsters_outside_its_small_range() -> None:
    infantry = _infantry()
    infantry.soldiers = [_soldier((0.0, 0.0))]
    monster = _monster((200.0, 0.0))

    result = infantry.update(0.01, _train(), [monster])

    assert result.shots == ()
    assert monster.hp == pytest.approx(10.0)


def test_soldier_kill_awards_gold_and_removes_the_monster() -> None:
    infantry = _infantry()
    infantry.soldiers = [_soldier((0.0, 0.0))]
    monsters = [_monster((20.0, 0.0), hp=3.0, gold=7)]

    result = infantry.update(0.01, _train(), monsters)

    assert result.kills == 1
    assert result.gold == 7
    assert monsters == []


# ----------------------------------------------------------------------
# Monster priority
# ----------------------------------------------------------------------
def test_monster_ignores_the_train_and_chases_a_soldier() -> None:
    system = _monster_system([_monster((0.0, 0.0))])
    soldiers = [_soldier((100.0, 0.0))]
    train = _train(travelled=0.0)  # locomotive at (0, 0)

    result = system.update(0.1, train, soldiers=soldiers, train_moving=False)

    assert result.damage == 0.0
    assert result.soldiers_lost == 0
    assert system.monsters[0].position[0] == pytest.approx(8.0)


def test_monster_kills_a_soldier_in_one_attack() -> None:
    system = _monster_system([_monster((0.0, 0.0))])
    soldiers = [_soldier((20.0, 0.0))]
    train = _train(travelled=0.0)

    result = system.update(0.01, train, soldiers=soldiers, train_moving=False)

    assert result.soldiers_lost == 1
    assert result.damage == 0.0
    assert soldiers == []


def test_monster_returns_to_the_train_after_soldiers_are_gone() -> None:
    system = _monster_system([_monster((0.0, 0.0))])
    soldiers = [_soldier((20.0, 0.0))]
    train = _train(travelled=0.0)

    system.update(0.01, train, soldiers=soldiers, train_moving=False)
    result = system.update(1.01, train, soldiers=soldiers, train_moving=False)

    assert result.damage == pytest.approx(5.0)
    assert result.soldiers_lost == 0

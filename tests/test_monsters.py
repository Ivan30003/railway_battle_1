from __future__ import annotations

import pytest

from game.core.config import MonsterConfig, SpawnConfig
from game.core.monsters import (
    FAST_KIND,
    TANK_KIND,
    Monster,
    MonsterSpawner,
    MonsterSystem,
)
from game.core.path import PathRoute
from game.core.train import Train


def _route() -> PathRoute:
    return PathRoute([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])


def _train(wagons: list[str] | None = None, **kwargs: object) -> Train:
    params: dict[str, object] = {
        "route": _route(),
        "speed": 70.0,
        "wagon_spacing": 40.0,
        "wagons": ["ICE"] if wagons is None else wagons,
    }
    params.update(kwargs)
    return Train(**params)  # type: ignore[arg-type]


def _spawn(**overrides: object) -> SpawnConfig:
    params = {
        "cooldown_start": 2.0,
        "cooldown_step": 0.0,
        "cooldown_min": 0.5,
        "probability_spawn_dist_start": {FAST_KIND: 1.0, TANK_KIND: 0.0},
    }
    params.update(overrides)
    return SpawnConfig(**params)  # type: ignore[arg-type]


def _monster_configs() -> dict[str, MonsterConfig]:
    return {
        FAST_KIND: MonsterConfig(
            hp=10.0,
            speed=80.0,
            gold=1,
            damage=5.0,
            attack_interval=1.0,
        ),
        TANK_KIND: MonsterConfig(
            hp=50.0,
            speed=30.0,
            gold=5,
            damage=15.0,
            attack_interval=1.5,
        ),
    }


class FakeRng:
    """Deterministic RNG with explicit values for each spawner decision."""

    def __init__(self, *, distance: float = 40.0, roll: float = 0.5) -> None:
        self.distance = distance
        self.roll = roll

    def uniform(self, start: float, end: float) -> float:
        return self.distance

    def random(self) -> float:
        return self.roll


_WORLD_SIZE = (200.0, 100.0)


def _spawner(
    *,
    train_center: tuple[float, float] = (150.0, 50.0),
    distance: float = 40.0,
    roll: float = 0.5,
    **overrides: object,
) -> MonsterSpawner:
    return MonsterSpawner(
        _spawn(**overrides),
        _monster_configs(),
        world_size=_WORLD_SIZE,
        train_center=lambda: train_center,
        hit_radius=10.0,
        rng=FakeRng(distance=distance, roll=roll),
    )


def _monster(kind: str = FAST_KIND, position: tuple[float, float] = (0.0, 0.0)) -> Monster:
    config = _monster_configs()[kind]
    return Monster(
        kind=kind,
        position=position,
        hp=config.hp,
        max_hp=config.hp,
        speed=config.speed,
        gold=config.gold,
        damage=config.damage,
        attack_interval=config.attack_interval,
        radius=10.0,
    )


def _system(monsters: list[Monster] | None = None) -> MonsterSystem:
    system = MonsterSystem(
        _spawn(cooldown_start=1000.0),
        _monster_configs(),
        world_size=_WORLD_SIZE,
        train_center=lambda: (100.0, 50.0),
        attack_range=24.0,
        crush_radius=18.0,
        hit_radius=10.0,
        rng=FakeRng(),
    )
    if monsters is not None:
        system.monsters = monsters
    return system


def test_spawn_appears_on_the_edge_opposite_the_train() -> None:
    spawner = _spawner(train_center=(150.0, 50.0), distance=40.0)

    monster = spawner.spawn_one()

    assert monster.position == pytest.approx((10.0, 40.0))
    assert monster.kind == FAST_KIND
    assert monster.radius == pytest.approx(10.0)
    assert monster.attack_timer == pytest.approx(monster.attack_interval)


@pytest.mark.parametrize(
    "train_center, expected",
    [
        ((150.0, 50.0), (10.0, 40.0)),
        ((50.0, 50.0), (190.0, 40.0)),
        ((100.0, 20.0), (40.0, 90.0)),
        ((100.0, 80.0), (40.0, 10.0)),
    ],
)
def test_spawn_uses_the_opposite_screen_edge(
    train_center: tuple[float, float],
    expected: tuple[float, float],
) -> None:
    spawner = _spawner(train_center=train_center, distance=40.0)

    assert spawner.spawn_one().position == pytest.approx(expected)


def test_spawn_stays_inside_the_screen_by_its_radius() -> None:
    spawner = _spawner(
        train_center=(150.0, 50.0),
        distance=40.0,
        probability_spawn_dist_start={FAST_KIND: 0.0, TANK_KIND: 1.0},
        roll=0.0,
    )

    monster = spawner.spawn_one()

    assert monster.kind == TANK_KIND
    assert monster.position == pytest.approx((13.5, 40.0))


def test_tank_is_chosen_by_probability() -> None:
    spawner = _spawner(
        probability_spawn_dist_start={FAST_KIND: 0.0, TANK_KIND: 1.0},
        roll=0.0,
    )

    monster = spawner.spawn_one()
    assert monster.kind == TANK_KIND
    assert monster.radius == pytest.approx(13.5)


def test_spawn_waits_for_the_cooldown() -> None:
    spawner = _spawner(cooldown_min=2.0)

    assert spawner.update(1.9) == []
    assert len(spawner.update(0.11)) == 1


def test_cooldown_decreases_with_each_purchased_wagon() -> None:
    purchased = 0
    spawner = MonsterSpawner(
        _spawn(cooldown_start=2.0, cooldown_step=0.25, cooldown_min=1.0),
        _monster_configs(),
        world_size=_WORLD_SIZE,
        train_center=lambda: (100.0, 50.0),
        hit_radius=10.0,
        rng=FakeRng(),
        purchased_wagons=lambda: purchased,
    )

    assert spawner.cooldown == pytest.approx(2.0)

    purchased = 2
    assert spawner.cooldown == pytest.approx(1.5)

    purchased = 10
    assert spawner.cooldown == pytest.approx(1.0)


def test_spawn_distribution_chooses_the_monster_kind() -> None:
    spawner = _spawner(
        probability_spawn_dist_start={FAST_KIND: 0.75, TANK_KIND: 0.25},
        roll=0.8,
    )

    assert spawner.spawn_one().kind == TANK_KIND

    spawner.rng = FakeRng(roll=0.1)
    assert spawner.spawn_one().kind == FAST_KIND


def test_initial_timer_uses_the_purchase_scaled_cooldown() -> None:
    spawner = MonsterSpawner(
        _spawn(cooldown_start=2.0, cooldown_step=0.5, cooldown_min=0.5),
        _monster_configs(),
        world_size=_WORLD_SIZE,
        train_center=lambda: (100.0, 50.0),
        hit_radius=10.0,
        rng=FakeRng(),
        purchased_wagons=lambda: 2,
    )

    assert spawner.cooldown == pytest.approx(1.0)
    assert spawner.update(0.9) == []
    assert len(spawner.update(0.11)) == 1


def test_monster_moves_towards_the_locomotive() -> None:
    system = _system([_monster(position=(0.0, 100.0))])

    result = system.update(0.5, _train(wagons=[]), train_moving=False)

    assert result.damage == 0.0
    assert system.monsters[0].position == pytest.approx((0.0, 60.0))


def test_slow_stacks_up_to_the_cap() -> None:
    monster = _monster()

    for _ in range(5):
        monster.apply_slow(0.2, 3.0, max_percent=0.8)

    assert monster.slow_percent == pytest.approx(0.8)
    assert monster.slow_timer == pytest.approx(3.0)
    assert monster.effective_speed == pytest.approx(80.0 * 0.2)


def test_slow_reduces_movement_and_expires() -> None:
    monster = _monster(position=(0.0, 200.0))
    monster.apply_slow(0.5, 1.0, max_percent=0.8)
    system = _system([monster])

    system.update(0.5, _train(wagons=[]), train_moving=False)

    assert monster.position == pytest.approx((0.0, 180.0))
    assert monster.slow_timer == pytest.approx(0.5)
    assert monster.is_slowed is True

    system.update(0.6, _train(wagons=[]), train_moving=False)

    assert monster.is_slowed is False
    assert monster.slow_percent == pytest.approx(0.0)
    assert monster.effective_speed == pytest.approx(80.0)


def test_slow_timer_refreshes_on_a_new_hit() -> None:
    monster = _monster()
    monster.apply_slow(0.2, 1.0, max_percent=0.8)
    monster.tick_slow(0.9)

    monster.apply_slow(0.2, 3.0, max_percent=0.8)

    assert monster.slow_timer == pytest.approx(3.0)
    assert monster.slow_percent == pytest.approx(0.4)


def test_slow_effect_is_cleared_after_expiring() -> None:
    monster = _monster()
    monster.apply_slow(0.4, 1.0, max_percent=0.8)

    monster.tick_slow(1.0)

    assert monster.slow_timer == pytest.approx(0.0)
    assert monster.slow_percent == pytest.approx(0.0)
    assert monster.is_slowed is False

    monster.apply_slow(0.2, 3.0, max_percent=0.8)

    assert monster.slow_percent == pytest.approx(0.2)
    assert monster.slow_timer == pytest.approx(3.0)


def test_monster_attacks_on_interval() -> None:
    system = _system([_monster(position=(0.0, 30.0))])

    first = system.update(0.1, _train(wagons=[]), train_moving=False)
    assert first.damage == pytest.approx(5.0)
    assert system.monsters[0].attack_timer == pytest.approx(1.0)

    second = system.update(0.4, _train(wagons=[]), train_moving=False)
    assert second.damage == 0.0
    third = system.update(0.6, _train(wagons=[]), train_moving=False)
    assert third.damage == pytest.approx(5.0)


def test_monster_damages_the_nearest_wagon() -> None:
    train = _train(wagons=["ICE"])
    system = _system([_monster(position=(0.0, 70.0))])

    result = system.update(0.01, train, train_moving=False)

    assert result.damage == 0.0
    assert result.destroyed_wagons == ()
    assert train.wagon_health == pytest.approx([25.0])


def test_monster_damages_the_locomotive_when_it_is_nearest() -> None:
    train = _train(wagons=["ICE"])
    system = _system([_monster(position=(0.0, 10.0))])

    result = system.update(0.01, train, train_moving=False)

    assert result.damage == pytest.approx(5.0)
    assert train.wagon_health == pytest.approx([30.0])


def test_destroyed_wagon_is_removed_and_the_rest_moves_forward() -> None:
    train = _train(
        wagons=["ICE", "MORTAR"],
        wagon_health=[5.0, 30.0],
        wagon_max_health=[30.0, 30.0],
    )
    system = _system([_monster(position=(0.0, 60.0))])

    result = system.update(0.01, train, train_moving=False)

    assert result.destroyed_wagons == (0,)
    assert train.wagons == ["MORTAR"]
    assert train.wagon_health == pytest.approx([30.0])
    assert train.car_samples()[1].sample.position == pytest.approx((0.0, 40.0))


def test_moving_train_crushes_a_monster_for_gold() -> None:
    system = _system([_monster(position=(0.0, 0.0))])

    result = system.update(0.1, _train(), train_moving=True)

    assert result.crushed == 1
    assert result.gold == 1
    assert result.damage == 0.0
    assert system.monsters == []
    assert system.crushed_total == 1


def test_crush_uses_the_collision_radius() -> None:
    system = _system([_monster(position=(0.0, 27.0)), _monster(position=(0.0, 29.0))])

    result = system.update(0.01, _train(wagons=[]), train_moving=True)

    assert result.crushed == 1
    assert len(system.monsters) == 1


def test_stationary_train_does_not_crush() -> None:
    system = _system([_monster(position=(0.0, 0.0))])

    result = system.update(0.1, _train(wagons=[]), train_moving=False)

    assert result.crushed == 0
    assert result.damage == pytest.approx(5.0)
    assert len(system.monsters) == 1


def test_monster_takes_damage_without_going_below_zero() -> None:
    monster = _monster()
    monster.take_damage(4.0)
    assert monster.hp == pytest.approx(6.0)
    monster.take_damage(100.0)
    assert monster.hp == 0.0
    assert not monster.is_alive


def test_dead_monsters_are_removed() -> None:
    monster = _monster()
    monster.take_damage(100.0)
    system = _system([monster])

    system.update(0.1, _train(), train_moving=False)

    assert system.monsters == []
    assert system.update(0.1, _train(), train_moving=False).damage == 0.0


def test_spawn_cap_is_respected() -> None:
    system = MonsterSystem(
        _spawn(cooldown_start=1.0, cooldown_min=0.1),
        _monster_configs(),
        world_size=_WORLD_SIZE,
        train_center=lambda: (100.0, 50.0),
        attack_range=24.0,
        crush_radius=18.0,
        hit_radius=10.0,
        rng=FakeRng(),
        max_monsters=1,
    )

    system.update(10.0, _train(), train_moving=False)

    assert len(system.monsters) == 1

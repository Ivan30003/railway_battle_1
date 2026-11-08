from __future__ import annotations

import pytest

from game.core.path import PathRoute
from game.core.train import LOCOMOTIVE, Train


def _route() -> PathRoute:
    # A 100 x 100 rectangle: each side is 100 px, the full loop is 400 px.
    return PathRoute([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])


def _train(**kwargs: object) -> Train:
    params = {
        "route": _route(),
        "speed": 50.0,
        "wagon_spacing": 40.0,
        "wagons": [],
        "travelled": 0.0,
    }
    params.update(kwargs)
    return Train(**params)  # type: ignore[arg-type]


def test_train_starts_at_route_origin() -> None:
    train = _train()

    assert train.distance == 0.0
    assert train.progress == 0.0
    assert train.completed_laps == 0
    assert train.wagon_count == 0

    locomotive = train.locomotive_sample()
    assert locomotive.position == pytest.approx((0.0, 0.0))
    assert locomotive.direction == pytest.approx((1.0, 0.0))


def test_update_moves_at_constant_speed() -> None:
    train = _train()

    assert train.update(1.0) == 0
    assert train.travelled == pytest.approx(50.0)
    assert train.distance == pytest.approx(50.0)

    assert train.update(0.5) == 0
    assert train.travelled == pytest.approx(75.0)
    assert train.locomotive_sample().position == pytest.approx((75.0, 0.0))


def test_distance_wraps_and_counts_one_lap() -> None:
    train = _train(travelled=350.0)

    assert train.update(1.0) == 1
    assert train.completed_laps == 1
    assert train.travelled == pytest.approx(400.0)
    assert train.distance == pytest.approx(0.0)
    assert train.progress == pytest.approx(0.0)


def test_multiple_laps_are_reported() -> None:
    train = _train(travelled=100.0)

    assert train.advance(900.0) == 2
    assert train.completed_laps == 2
    assert train.distance == pytest.approx(200.0)
    assert train.progress == pytest.approx(0.5)


def test_wagons_follow_the_locomotive_by_arc_length() -> None:
    train = _train(
        speed=10.0,
        wagon_spacing=40.0,
        wagons=["MACHINEGUN", "ICE"],
    )
    train.advance(100.0)

    cars = train.car_samples()
    assert [car.kind for car in cars] == [LOCOMOTIVE, "MACHINEGUN", "ICE"]
    assert cars[0].is_locomotive
    assert not cars[1].is_locomotive
    assert [car.offset for car in cars] == pytest.approx([0.0, 40.0, 80.0])
    expected = [(100.0, 0.0), (60.0, 0.0), (20.0, 0.0)]
    for car, position in zip(cars, expected, strict=True):
        assert car.sample.position == pytest.approx(position)


def test_wagons_wrap_around_the_start() -> None:
    train = _train(wagon_spacing=40.0, wagons=["ICE"], travelled=10.0)

    wagon = train.car_samples()[1]
    assert wagon.sample.position == pytest.approx((0.0, 30.0))


def test_non_positive_dt_and_distance_do_not_move() -> None:
    train = _train(travelled=25.0)

    assert train.update(0.0) == 0
    assert train.update(-1.0) == 0
    assert train.advance(0.0) == 0
    assert train.advance(-5.0) == 0
    assert train.travelled == pytest.approx(25.0)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"speed": 0.0}, "speed"),
        ({"speed": -1.0}, "speed"),
        ({"wagon_spacing": 0.0}, "spacing"),
        ({"wagon_spacing": -1.0}, "spacing"),
        ({"travelled": -1.0}, "Travelled"),
        ({"wagons": [""]}, "Wagon kinds"),
        ({"wagons": [None]}, "Wagon kinds"),
    ],
)
def test_invalid_parameters_raise(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _train(**kwargs)


def test_wagons_list_is_copied() -> None:
    wagons = ["ICE"]
    train = _train(wagons=wagons)
    wagons.append("MORTAR")

    assert train.wagons == ["ICE"]
    assert train.wagon_count == 1

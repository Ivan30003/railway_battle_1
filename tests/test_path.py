from __future__ import annotations

import pytest

from game.core.path import PathRoute


def _square() -> PathRoute:
    return PathRoute(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)))


def test_total_length() -> None:
    assert _square().total_length == pytest.approx(40.0)


def test_sample_at_corners() -> None:
    route = _square()

    first = route.sample(0.0)
    assert first.position == pytest.approx((0.0, 0.0))
    assert first.direction == pytest.approx((1.0, 0.0))
    assert first.segment == 0

    second = route.sample(10.0)
    assert second.position == pytest.approx((10.0, 0.0))
    assert second.direction == pytest.approx((0.0, 1.0))
    assert second.segment == 1


def test_sample_mid_segment() -> None:
    sample = _square().sample(25.0)

    assert sample.position == pytest.approx((5.0, 10.0))
    assert sample.direction == pytest.approx((-1.0, 0.0))
    assert sample.distance == pytest.approx(25.0)
    assert sample.segment == 2


def test_sample_wraps_beyond_total_length() -> None:
    route = _square()

    wrapped = route.sample(45.0)
    assert wrapped.distance == pytest.approx(5.0)
    assert wrapped.position == pytest.approx((5.0, 0.0))
    assert wrapped.direction == pytest.approx((1.0, 0.0))


def test_negative_distance_wraps() -> None:
    sample = _square().sample(-1.0)

    assert sample.distance == pytest.approx(39.0)
    assert sample.position == pytest.approx((0.0, 1.0))
    assert sample.direction == pytest.approx((0.0, -1.0))


def test_duplicate_points_are_removed() -> None:
    route = PathRoute(
        ((0.0, 0.0), (0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 0.0))
    )

    assert route.points == ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))
    assert route.total_length == pytest.approx(20.0 + 2.0 * (50.0**0.5))


def test_too_few_points_raise() -> None:
    with pytest.raises(ValueError, match="two distinct"):
        PathRoute(((0.0, 0.0), (0.0, 0.0)))

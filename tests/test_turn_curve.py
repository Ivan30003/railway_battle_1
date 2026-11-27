from __future__ import annotations

import math

import pytest

from game.core.turn_curve import (
    CIRCULAR_CURVATURE,
    DEFAULT_CURVATURES,
    MAX_POINTS,
    MIN_POINTS,
    sample_turn,
    select_curvature,
)

ENTRY = (16.0, 0.0)
EXIT = (32.0, 16.0)
ENTRY_DIRECTION = (0.0, 1.0)
EXIT_DIRECTION = (1.0, 0.0)


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*vector)
    return vector[0] / length, vector[1] / length


def test_turn_starts_and_ends_at_side_midpoints() -> None:
    points = sample_turn(
        ENTRY,
        EXIT,
        ENTRY_DIRECTION,
        EXIT_DIRECTION,
        half_size=16.0,
        curvature=CIRCULAR_CURVATURE,
    )

    assert points[0] == pytest.approx(ENTRY)
    assert points[-1] == pytest.approx(EXIT)


def test_turn_is_tangent_to_the_adjacent_straights() -> None:
    points = sample_turn(
        ENTRY,
        EXIT,
        ENTRY_DIRECTION,
        EXIT_DIRECTION,
        half_size=16.0,
        curvature=CIRCULAR_CURVATURE,
    )

    first = _unit((points[1][0] - points[0][0], points[1][1] - points[0][1]))
    last = _unit((points[-1][0] - points[-2][0], points[-1][1] - points[-2][1]))

    assert first == pytest.approx(ENTRY_DIRECTION, abs=0.06)
    assert last == pytest.approx(EXIT_DIRECTION, abs=0.06)


def test_turn_stays_inside_the_tile() -> None:
    for curvature in DEFAULT_CURVATURES:
        points = sample_turn(
            ENTRY,
            EXIT,
            ENTRY_DIRECTION,
            EXIT_DIRECTION,
            half_size=16.0,
            curvature=curvature,
        )
        for x, y in points:
            assert 16.0 - 1e-9 <= x <= 32.0 + 1e-9
            assert 0.0 - 1e-9 <= y <= 16.0 + 1e-9


@pytest.mark.parametrize(
    "entry, exit_point, entry_direction, exit_direction",
    [
        ((16.0, 0.0), (32.0, 16.0), (0.0, 1.0), (1.0, 0.0)),
        ((16.0, 0.0), (0.0, 16.0), (0.0, 1.0), (-1.0, 0.0)),
        ((16.0, 32.0), (32.0, 16.0), (0.0, -1.0), (1.0, 0.0)),
        ((16.0, 32.0), (0.0, 16.0), (0.0, -1.0), (-1.0, 0.0)),
    ],
)
def test_every_turn_orientation_stays_inside_the_tile(
    entry: tuple[float, float],
    exit_point: tuple[float, float],
    entry_direction: tuple[float, float],
    exit_direction: tuple[float, float],
) -> None:
    for curvature in DEFAULT_CURVATURES:
        points = sample_turn(
            entry,
            exit_point,
            entry_direction,
            exit_direction,
            half_size=16.0,
            curvature=curvature,
        )

        assert points[0] == pytest.approx(entry)
        assert points[-1] == pytest.approx(exit_point)
        for x, y in points:
            assert -1e-9 <= x <= 32.0 + 1e-9
            assert -1e-9 <= y <= 32.0 + 1e-9


def test_point_count_follows_the_arc_length() -> None:
    counts = []
    for half_size in (8.0, 16.0, 32.0, 64.0):
        points = sample_turn(
            (half_size, 0.0),
            (half_size * 2.0, half_size),
            ENTRY_DIRECTION,
            EXIT_DIRECTION,
            half_size=half_size,
            curvature=CIRCULAR_CURVATURE,
        )
        assert MIN_POINTS <= len(points) <= MAX_POINTS
        counts.append(len(points))

    assert counts[0] == MIN_POINTS
    assert counts[-1] == MAX_POINTS
    assert counts == sorted(counts)


@pytest.mark.parametrize("curvature", DEFAULT_CURVATURES)
def test_more_rounded_turns_are_longer(curvature: float) -> None:
    points = sample_turn(
        ENTRY,
        EXIT,
        ENTRY_DIRECTION,
        EXIT_DIRECTION,
        half_size=16.0,
        curvature=curvature,
    )
    length = sum(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(points, points[1:], strict=False)
    )

    assert 20.0 < length < 32.0


def test_select_curvature_is_stable_and_deterministic() -> None:
    first = select_curvature(3, 7, DEFAULT_CURVATURES)

    assert select_curvature(3, 7, DEFAULT_CURVATURES) == first
    assert first in DEFAULT_CURVATURES

    chosen = {
        select_curvature(x, y, DEFAULT_CURVATURES)
        for x in range(6)
        for y in range(6)
    }
    assert len(chosen) > 1
    assert chosen <= set(DEFAULT_CURVATURES)


def test_single_curvature_is_used_for_every_tile() -> None:
    assert select_curvature(1, 2, (CIRCULAR_CURVATURE,)) == CIRCULAR_CURVATURE


def test_empty_curvature_list_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        select_curvature(0, 0, ())

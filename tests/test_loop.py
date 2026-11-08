from __future__ import annotations

import pytest

from game.app.loop import FixedTimestep


def test_one_frame_is_one_step() -> None:
    timer = FixedTimestep()
    assert timer.advance(1.0 / 60.0) == 1


def test_double_frame_runs_two_steps() -> None:
    timer = FixedTimestep()
    assert timer.advance(1.0 / 30.0) == 2


def test_accumulator_keeps_remainder() -> None:
    timer = FixedTimestep()
    assert timer.advance(0.01) == 0
    assert timer.advance(0.01) == 1
    assert timer.accumulator < timer.step


def test_slow_frame_is_capped() -> None:
    timer = FixedTimestep()
    assert timer.advance(5.0) == timer.max_steps
    assert timer.accumulator <= timer.step


@pytest.mark.parametrize("value", [-1.0, 0.0])
def test_non_positive_frame_time_does_nothing(value: float) -> None:
    timer = FixedTimestep()
    assert timer.advance(value) == 0

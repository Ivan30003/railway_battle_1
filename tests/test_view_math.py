from __future__ import annotations

import pytest

from game.view.camera import compute_letterbox


def test_exact_integer_scale() -> None:
    box = compute_letterbox((1280, 960), (640, 480))
    assert box.scale == pytest.approx(2.0)
    assert box.offset_x == pytest.approx(0.0)
    assert box.offset_y == pytest.approx(0.0)
    assert box.width == pytest.approx(1280.0)
    assert box.height == pytest.approx(960.0)


def test_letterbox_has_side_bars() -> None:
    box = compute_letterbox((1000, 500), (640, 480))
    assert box.scale == pytest.approx(500 / 480)
    assert box.offset_x > 0
    assert box.offset_y == pytest.approx(0.0)
    assert box.offset_x * 2 + box.width == pytest.approx(1000.0)


def test_letterbox_has_top_bottom_bars() -> None:
    box = compute_letterbox((900, 900), (640, 480))
    assert box.scale == pytest.approx(900 / 640)
    assert box.offset_y > 0
    assert box.offset_x == pytest.approx(0.0)


def test_window_smaller_than_virtual_can_scale_down() -> None:
    box = compute_letterbox((320, 240), (640, 480))
    assert box.scale == pytest.approx(0.5)
    assert box.width == pytest.approx(320.0)
    assert box.height == pytest.approx(240.0)

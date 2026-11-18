from __future__ import annotations

import pytest

from game.core.config import WagonConfig
from game.core.shop import Shop


def _wagon() -> WagonConfig:
    return WagonConfig(
        radius=100.0,
        rotation_speed_deg_per_sec=180.0,
        fire_interval=1.0,
        damage=5.0,
        hp=40.0,
        aim_threshold_deg=7.0,
        priority=None,
        reserve="none",
    )


def _shop(**overrides: int) -> Shop:
    params = {"base_cost": 30, "cost_step": 10}
    params.update(overrides)
    return Shop(
        {"MACHINEGUN": _wagon(), "ICE": _wagon(), "MORTAR": _wagon()},
        **params,
    )


def test_price_grows_with_every_purchase() -> None:
    shop = _shop()

    assert shop.price(0) == 30
    assert shop.price(1) == 40
    assert shop.price(4) == 70


def test_can_buy_checks_the_next_price() -> None:
    shop = _shop()

    assert shop.can_buy("ICE", 29, 0) is False
    assert shop.can_buy("ICE", 30, 0) is True
    assert shop.can_buy("ICE", 39, 1) is False
    assert shop.can_buy("ICE", 40, 1) is True


def test_buy_returns_the_purchase_and_remaining_gold() -> None:
    shop = _shop()

    purchase = shop.buy("MORTAR", 100, 0)

    assert purchase is not None
    assert purchase.kind == "MORTAR"
    assert purchase.price == 30
    assert purchase.gold_after == 70
    assert purchase.purchased_after == 1


def test_buy_without_gold_changes_nothing() -> None:
    shop = _shop()

    assert shop.buy("ICE", 0, 0) is None
    assert shop.buy("ICE", 39, 1) is None


def test_shop_rejects_unknown_wagon_types() -> None:
    shop = _shop()

    with pytest.raises(ValueError, match="Unknown wagon type"):
        shop.buy("SNIPER", 100, 0)
    with pytest.raises(ValueError, match="Unknown wagon type"):
        shop.can_buy("SNIPER", 100, 0)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"base_cost": -1}, "base cost"),
        ({"cost_step": -1}, "cost step"),
    ],
)
def test_invalid_shop_options_raise(overrides: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _shop(**overrides)


def test_shop_requires_at_least_one_wagon_type() -> None:
    with pytest.raises(ValueError, match="At least one"):
        Shop({}, base_cost=30, cost_step=10)


def test_negative_purchase_count_raises() -> None:
    shop = _shop()

    with pytest.raises(ValueError, match="Purchased count"):
        shop.price(-1)

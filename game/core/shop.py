"""Wagon shop pricing and purchases.

The shop sells one wagon at a time. Every purchase raises the price of the next
wagon by ``cost_step``, so the player has to keep earning gold:

    price = base_cost + cost_step * purchased

The shop itself stores no gold. ``buy`` receives the current amount, checks the
price and returns an immutable :class:`Purchase` describing the result, which
keeps the economy easy to test without a running game.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from game.core.config import WagonConfig


@dataclass(frozen=True)
class Purchase:
    """A successful wagon purchase."""

    kind: str
    price: int
    gold_after: int
    purchased_after: int


class Shop:
    """Applies the wagon price ladder to a set of available wagon types."""

    def __init__(
        self,
        wagon_configs: Mapping[str, WagonConfig],
        *,
        base_cost: int,
        cost_step: int,
    ) -> None:
        if not wagon_configs:
            raise ValueError("At least one wagon type is required")
        if base_cost < 0:
            raise ValueError("Wagon base cost cannot be negative")
        if cost_step < 0:
            raise ValueError("Wagon cost step cannot be negative")
        self.wagon_configs = dict(wagon_configs)
        self.base_cost = int(base_cost)
        self.cost_step = int(cost_step)

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(self.wagon_configs)

    def price(self, purchased: int) -> int:
        """Return the price of the next wagon after ``purchased`` buys."""
        if purchased < 0:
            raise ValueError("Purchased count cannot be negative")
        return self.base_cost + self.cost_step * purchased

    def can_buy(self, kind: str, gold: int, purchased: int) -> bool:
        self._require_kind(kind)
        return gold >= self.price(purchased)

    def buy(self, kind: str, gold: int, purchased: int) -> Purchase | None:
        """Buy ``kind`` or return ``None`` when there is not enough gold."""
        self._require_kind(kind)
        price = self.price(purchased)
        if gold < price:
            return None
        return Purchase(
            kind=kind,
            price=price,
            gold_after=gold - price,
            purchased_after=purchased + 1,
        )

    def _require_kind(self, kind: str) -> None:
        if kind not in self.wagon_configs:
            raise ValueError(f"Unknown wagon type: {kind}")


__all__ = ["Purchase", "Shop"]

"""Train composition and movement along a closed route.

The train is a locomotive followed by wagons spaced at a fixed arc-length
distance. Movement is stored as total travelled distance, so lap counting is
independent of the route wrapping and of the frame rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from game.core.path import PathRoute, RouteSample

LOCOMOTIVE = "LOCOMOTIVE"

_LAP_EPSILON = 1e-9


@dataclass(frozen=True)
class TrainCar:
    """A rendered car: the locomotive or one wagon."""

    kind: str
    sample: RouteSample
    offset: float
    wagon_index: int | None = None
    hp: float = 0.0
    max_hp: float = 0.0

    @property
    def is_locomotive(self) -> bool:
        return self.kind == LOCOMOTIVE

    @property
    def is_wagon(self) -> bool:
        return self.wagon_index is not None


@dataclass
class Train:
    """Locomotive and wagons moving at a constant speed."""

    route: PathRoute
    speed: float
    wagon_spacing: float
    wagons: list[str] = field(default_factory=list)
    travelled: float = 0.0
    wagon_health: list[float] = field(default_factory=list)
    wagon_max_health: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.speed <= 0.0:
            raise ValueError("Train speed must be positive")
        if self.wagon_spacing <= 0.0:
            raise ValueError("Wagon spacing must be positive")
        if self.travelled < 0.0:
            raise ValueError("Travelled distance cannot be negative")
        self.wagons = list(self.wagons)
        if any(not isinstance(kind, str) or not kind for kind in self.wagons):
            raise ValueError("Wagon kinds must be non-empty strings")

        if not self.wagon_max_health:
            self.wagon_max_health = [30.0] * len(self.wagons)
        else:
            self.wagon_max_health = [float(value) for value in self.wagon_max_health]
        if not self.wagon_health:
            self.wagon_health = list(self.wagon_max_health)
        else:
            self.wagon_health = [float(value) for value in self.wagon_health]
        if len(self.wagon_max_health) != len(self.wagons):
            raise ValueError("Wagon max health must match the wagon count")
        if len(self.wagon_health) != len(self.wagons):
            raise ValueError("Wagon health must match the wagon count")
        if any(value <= 0.0 for value in self.wagon_max_health):
            raise ValueError("Wagon max health must be positive")
        if any(value < 0.0 for value in self.wagon_health):
            raise ValueError("Wagon health cannot be negative")
        self.wagon_health = [
            min(health, maximum)
            for health, maximum in zip(
                self.wagon_health, self.wagon_max_health, strict=True
            )
        ]

    @property
    def distance(self) -> float:
        """Distance from the start along the route, wrapped to one lap."""
        return self.route.wrap(self.travelled)

    @property
    def progress(self) -> float:
        """Lap progress in ``[0, 1)``."""
        return self.distance / self.route.total_length

    @property
    def completed_laps(self) -> int:
        return int((self.travelled + _LAP_EPSILON) // self.route.total_length)

    @property
    def wagon_count(self) -> int:
        return len(self.wagons)

    def locomotive_sample(self) -> RouteSample:
        return self.route.sample(self.travelled)

    def center(self) -> tuple[float, float]:
        """Average position of the locomotive and all wagons."""
        cars = self.car_samples()
        count = len(cars)
        return (
            sum(car.sample.position[0] for car in cars) / count,
            sum(car.sample.position[1] for car in cars) / count,
        )

    def car_samples(self) -> list[TrainCar]:
        """Return the locomotive followed by wagons, front to back."""
        cars = [TrainCar(LOCOMOTIVE, self.route.sample(self.travelled), 0.0)]
        for index, kind in enumerate(self.wagons):
            offset = self.wagon_spacing * (index + 1)
            cars.append(
                TrainCar(
                    kind,
                    self.route.sample(self.travelled - offset),
                    offset,
                    wagon_index=index,
                    hp=self.wagon_health[index],
                    max_hp=self.wagon_max_health[index],
                )
            )
        return cars

    def nearest_car(self, point: tuple[float, float]) -> TrainCar:
        """Return the locomotive or wagon closest to ``point``."""
        return min(
            self.car_samples(),
            key=lambda car: (car.sample.position[0] - point[0]) ** 2
            + (car.sample.position[1] - point[1]) ** 2,
        )

    def add_wagon(self, kind: str, *, max_hp: float = 30.0) -> None:
        """Attach a new wagon to the back of the train."""
        if not isinstance(kind, str) or not kind:
            raise ValueError("Wagon kinds must be non-empty strings")
        if max_hp <= 0.0:
            raise ValueError("Wagon max health must be positive")
        self.wagons.append(kind)
        self.wagon_max_health.append(float(max_hp))
        self.wagon_health.append(float(max_hp))

    def damage_wagon(self, index: int, amount: float) -> bool:
        """Damage a wagon and remove it when its HP reaches zero.

        Returns ``True`` when the wagon was destroyed. Removing a wagon from
        the middle of the list makes every wagon behind it move one slot
        forward, closing the gap.
        """
        index = self._wagon_index(index)
        self.wagon_health[index] = max(
            0.0,
            self.wagon_health[index] - max(0.0, amount),
        )
        if self.wagon_health[index] > 0.0:
            return False
        self.remove_wagon(index)
        return True

    def remove_wagon(self, index: int) -> str:
        """Remove a wagon and return its kind."""
        index = self._wagon_index(index)
        self.wagon_health.pop(index)
        self.wagon_max_health.pop(index)
        return self.wagons.pop(index)

    def _wagon_index(self, index: int) -> int:
        if index < 0:
            index += len(self.wagons)
        if not 0 <= index < len(self.wagons):
            raise IndexError(f"Wagon index out of range: {index}")
        return index

    def advance(self, distance: float) -> int:
        """Move forward and return how many full laps were completed."""
        if distance <= 0.0:
            return 0
        previous_laps = self.completed_laps
        self.travelled += float(distance)
        return self.completed_laps - previous_laps

    def update(self, dt: float) -> int:
        """Advance by ``dt`` seconds and return the number of completed laps."""
        if dt <= 0.0:
            return 0
        return self.advance(self.speed * dt)

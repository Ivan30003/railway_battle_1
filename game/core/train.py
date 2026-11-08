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

    @property
    def is_locomotive(self) -> bool:
        return self.kind == LOCOMOTIVE


@dataclass
class Train:
    """Locomotive and wagons moving at a constant speed."""

    route: PathRoute
    speed: float
    wagon_spacing: float
    wagons: list[str] = field(default_factory=list)
    travelled: float = 0.0

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

    def car_samples(self) -> list[TrainCar]:
        """Return the locomotive followed by wagons, front to back."""
        cars = [TrainCar(LOCOMOTIVE, self.route.sample(self.travelled), 0.0)]
        for index, kind in enumerate(self.wagons, start=1):
            offset = self.wagon_spacing * index
            cars.append(TrainCar(kind, self.route.sample(self.travelled - offset), offset))
        return cars

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

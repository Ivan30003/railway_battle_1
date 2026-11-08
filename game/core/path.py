"""Closed-loop path with arc-length parameterisation.

The route is stored as a closed polyline. ``sample`` converts a travelled
distance into a position and a unit tangent, which is all the train needs to
move at a constant speed regardless of tile size.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

Point = tuple[float, float]

_EPSILON = 1e-9


@dataclass(frozen=True)
class RouteSample:
    """A point on the route at a given travelled distance."""

    distance: float
    position: Point
    direction: Point
    segment: int


@dataclass(frozen=True)
class _Segment:
    start: Point
    end: Point
    length: float
    start_distance: float


class PathRoute:
    """A closed polyline sampled by arc length."""

    def __init__(self, points: Sequence[Point]) -> None:
        cleaned: list[Point] = []
        for point in points:
            current = (float(point[0]), float(point[1]))
            if not cleaned or not _same_point(cleaned[-1], current):
                cleaned.append(current)

        if len(cleaned) > 2 and _same_point(cleaned[0], cleaned[-1]):
            cleaned.pop()
        if len(cleaned) < 2:
            raise ValueError("PathRoute needs at least two distinct points")

        segments: list[_Segment] = []
        total = 0.0
        count = len(cleaned)
        for index in range(count):
            start = cleaned[index]
            end = cleaned[(index + 1) % count]
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            if length <= _EPSILON:
                continue
            segments.append(_Segment(start, end, length, total))
            total += length
        if not segments:
            raise ValueError("PathRoute needs at least one non-zero segment")

        self._points = tuple(cleaned)
        self._segments = tuple(segments)
        self._total_length = total

    @property
    def points(self) -> tuple[Point, ...]:
        return self._points

    @property
    def total_length(self) -> float:
        return self._total_length

    def wrap(self, distance: float) -> float:
        """Wrap a distance into ``[0, total_length)``."""
        return float(distance) % self._total_length

    def sample(self, distance: float) -> RouteSample:
        """Return the position and unit tangent at ``distance``."""
        wrapped = self.wrap(distance)
        segment_index = self._segment_index(wrapped)
        segment = self._segments[segment_index]
        ratio = (wrapped - segment.start_distance) / segment.length
        position = (
            segment.start[0] + (segment.end[0] - segment.start[0]) * ratio,
            segment.start[1] + (segment.end[1] - segment.start[1]) * ratio,
        )
        direction = (
            (segment.end[0] - segment.start[0]) / segment.length,
            (segment.end[1] - segment.start[1]) / segment.length,
        )
        return RouteSample(wrapped, position, direction, segment_index)

    def _segment_index(self, distance: float) -> int:
        # Routes are small (a few hundred tiles), so a linear scan is enough and
        # avoids keeping a second, mutable lookup table.
        for index, segment in enumerate(self._segments):
            if distance < segment.start_distance + segment.length - _EPSILON:
                return index
        return len(self._segments) - 1


def _same_point(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= _EPSILON and abs(a[1] - b[1]) <= _EPSILON

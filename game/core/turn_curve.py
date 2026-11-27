"""Curved track pieces inside turning tiles.

A turn tile connects two perpendicular sides of a square tile. The path enters
at the midpoint of one side and leaves at the midpoint of the other. A circular
quarter arc is the unique curve perpendicular to both sides at those points,
so its curvature cannot vary. To support several visual variants the curve is
modelled as a cubic Bezier: the endpoints are the side midpoints and the
control points lie on the side normals. ``curvature`` controls the handle
length, so it changes how tight or round the bend looks while keeping the ends
tangent to the straight track in neighbouring tiles.

``CIRCULAR_CURVATURE`` reproduces a quarter circle. Smaller values pull the
curve towards the diagonal (a tighter bend), larger values make it rounder.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

Point = tuple[float, float]

MIN_POINTS = 24
MAX_POINTS = 40

# Cubic handle factor that approximates a quarter circle: (4/3) * tan(pi/8).
CIRCULAR_CURVATURE = 4.0 / 3.0 * math.tan(math.pi / 8.0)
DEFAULT_CURVATURES = (0.4, 0.55, 0.75)


def select_curvature(x: int, y: int, curvatures: Sequence[float]) -> float:
    """Pick a curvature for a tile deterministically from its coordinates."""
    if not curvatures:
        raise ValueError("curvatures must not be empty")
    if len(curvatures) == 1:
        return float(curvatures[0])
    index = (int(x) * 31 + int(y) * 17) % len(curvatures)
    return float(curvatures[index])


def sample_turn(
    entry: Point,
    exit: Point,
    entry_direction: Point,
    exit_direction: Point,
    *,
    half_size: float,
    curvature: float,
) -> tuple[Point, ...]:
    """Sample a smooth turn from ``entry`` to ``exit``.

    ``entry_direction`` is the unit direction of travel entering the tile and
    ``exit_direction`` the unit direction leaving it. Both point along the
    straight track in the adjacent tiles, so the sampled curve joins them
    tangentially at both ends.
    """
    if half_size <= 0.0:
        raise ValueError("half_size must be positive")
    if curvature <= 0.0:
        raise ValueError("curvature must be positive")

    handle = curvature * half_size
    control_a = _offset(entry, entry_direction, handle)
    control_b = _offset(exit, exit_direction, -handle)
    length = _bezier_length(entry, control_a, control_b, exit)
    count = min(MAX_POINTS, max(MIN_POINTS, math.ceil(length)))
    return tuple(
        _bezier_point(entry, control_a, control_b, exit, index / (count - 1))
        for index in range(count)
    )


def _offset(point: Point, direction: Point, distance: float) -> Point:
    return (
        point[0] + direction[0] * distance,
        point[1] + direction[1] * distance,
    )


def _bezier_point(
    p0: Point,
    p1: Point,
    p2: Point,
    p3: Point,
    t: float,
) -> Point:
    inverse = 1.0 - t
    a = inverse * inverse * inverse
    b = 3.0 * inverse * inverse * t
    c = 3.0 * inverse * t * t
    d = t * t * t
    return (
        a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
        a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
    )


def _bezier_length(
    p0: Point,
    p1: Point,
    p2: Point,
    p3: Point,
    steps: int = 64,
) -> float:
    total = 0.0
    previous = p0
    for index in range(1, steps + 1):
        point = _bezier_point(p0, p1, p2, p3, index / steps)
        total += math.hypot(point[0] - previous[0], point[1] - previous[1])
        previous = point
    return total


__all__ = [
    "CIRCULAR_CURVATURE",
    "DEFAULT_CURVATURES",
    "MAX_POINTS",
    "MIN_POINTS",
    "sample_turn",
    "select_curvature",
]

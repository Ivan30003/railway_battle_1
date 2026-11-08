"""Shared core exceptions."""

from __future__ import annotations


class MapError(ValueError):
    """Raised when a map file cannot be parsed or does not form a valid loop."""

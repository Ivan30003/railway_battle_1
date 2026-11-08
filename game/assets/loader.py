"""Asset loading with procedural placeholders for missing files."""

from __future__ import annotations

import json
from pathlib import Path

import pygame

from game.assets.procedural import placeholder_image


class AssetLoader:
    """Loads images by logical name and caches fonts.

    ``manifest.json`` maps a logical asset name to a file path relative to the
    assets directory. Missing entries (or missing files) fall back to a
    deterministic procedural placeholder, so the game always runs.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        pygame.font.init()
        self.root = Path(root) if root is not None else Path(__file__).resolve().parent
        self.manifest = self._load_manifest()
        self._images: dict[tuple[str, tuple[int, int] | None], pygame.Surface] = {}
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self._font_path = self._find_font()

    @staticmethod
    def _find_font() -> str | None:
        for name in ("dejavusans", "liberationsans", "notosans", "freesans", "arial"):
            path = pygame.font.match_font(name)
            if path:
                return path
        return None

    def _load_manifest(self) -> dict[str, str]:
        manifest_path = self.root / "manifest.json"
        if not manifest_path.is_file():
            return {}
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def image(
        self,
        name: str,
        size: tuple[int, int] | None = None,
    ) -> pygame.Surface:
        """Return an image by logical name, or a placeholder if unavailable."""
        cache_key = (name, size)
        cached = self._images.get(cache_key)
        if cached is not None:
            return cached

        surface: pygame.Surface | None = None
        relative = self.manifest.get(name)
        if relative is not None:
            path = self.root / relative
            if path.is_file():
                try:
                    surface = pygame.image.load(str(path))
                    surface = self._convert(surface)
                except pygame.error:
                    surface = None

        if surface is None:
            surface = placeholder_image(name, size or (32, 32))
        elif size is not None and surface.get_size() != size:
            surface = pygame.transform.smoothscale(surface, size)

        self._images[cache_key] = surface
        return surface

    @staticmethod
    def _convert(surface: pygame.Surface) -> pygame.Surface:
        try:
            return surface.convert_alpha()
        except pygame.error:
            return surface

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (int(size), bool(bold))
        cached = self._fonts.get(key)
        if cached is not None:
            return cached
        pygame.font.init()
        font = pygame.font.Font(self._font_path, key[0])
        font.set_bold(key[1])
        self._fonts[key] = font
        return font

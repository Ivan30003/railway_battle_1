"""Application entry point and window / loop wiring."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pygame

from game.app.loop import FixedTimestep
from game.app.scene_manager import SceneManager
from game.assets.loader import AssetLoader
from game.core.config import ConfigError, GameConfig
from game.core.errors import MapError
from game.core.map_loader import MapData, load_map
from game.io.actions import Action
from game.io.input import InputState
from game.view.debug_overlay import DebugOverlay
from game.view.renderer import Renderer
from game.view.theme import Theme

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "game.json"

_SCENE_CHOICES = ("menu", "game", "shop", "gameover", "victory")


def _resolve_map_path(config: GameConfig, map_path: str | Path | None) -> Path:
    if map_path is not None:
        path = Path(map_path).expanduser()
        return path if path.is_absolute() else Path.cwd() / path
    spec = Path(config.maps[0]).expanduser()
    return spec if spec.is_absolute() else PROJECT_ROOT / spec


class App:
    def __init__(
        self,
        config: GameConfig,
        *,
        map_path: str | Path | None = None,
        debug: bool = False,
        initial_scene: str = "menu",
        seed: int = 0,
    ) -> None:
        self.config = config
        self.seed = int(seed)
        self.running = True
        self.frame_index = 0
        self.fps = 0.0
        self.frame_ms = 0.0

        self.map_data: MapData = load_map(
            _resolve_map_path(config, map_path),
            tile_size=config.tile_size,
        )

        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption("Паровоз — Milestone 1")
        self._display_flags = pygame.DOUBLEBUF
        if config.window.resizable:
            self._display_flags |= pygame.RESIZABLE
        self._use_vsync = config.window.vsync and os.environ.get("SDL_VIDEODRIVER") != "dummy"
        self.window = self._create_window((config.window.width, config.window.height))

        self.theme = Theme()
        self.assets = AssetLoader(Path(__file__).resolve().parents[1] / "assets")
        self.renderer = Renderer(
            self.window,
            self.map_data.pixel_size,
            self.assets,
            self.theme,
        )
        self.input = InputState()
        self.debug_overlay = DebugOverlay(enabled=debug)
        self.scene_manager = SceneManager(self)
        self.scene_manager.set_initial(initial_scene)
        self.timer = FixedTimestep()
        self.clock = pygame.time.Clock()

    def _create_window(self, size: tuple[int, int]) -> pygame.Surface:
        kwargs = {"vsync": 1} if self._use_vsync else {}
        try:
            return pygame.display.set_mode(size, self._display_flags, **kwargs)
        except (TypeError, pygame.error):
            return pygame.display.set_mode(size, self._display_flags)

    def request_quit(self) -> None:
        self.running = False

    def _resize(self, size: tuple[int, int]) -> None:
        width = max(320, int(size[0]))
        height = max(240, int(size[1]))
        window = self._create_window((width, height))
        self.window = window
        self.renderer.set_window(window)

    def _pump_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self._resize(event.size)
            self.input.process_event(event)

    def _handle_global_actions(self) -> None:
        if self.input.was_action(Action.QUIT):
            self.request_quit()
        if self.input.was_action(Action.TOGGLE_DEBUG):
            self.debug_overlay.toggle()

    def _sync_display_surface(self) -> None:
        surface = pygame.display.get_surface()
        if surface is not None and surface is not self.window:
            self.window = surface
            self.renderer.set_window(surface)

    def run(self, max_frames: int | None = None) -> None:
        try:
            if max_frames is not None and max_frames <= 0:
                return
            while self.running:
                frame_time = min(self.clock.tick(60) / 1000.0, self.timer.max_frame_time)
                if frame_time > 0.0:
                    instant_fps = 1.0 / frame_time
                    if self.fps == 0.0:
                        self.fps = instant_fps
                    else:
                        self.fps = self.fps * 0.9 + instant_fps * 0.1
                    self.frame_ms = frame_time * 1000.0

                self.input.begin_frame()
                self._pump_events()
                if not self.running:
                    break

                self._sync_display_surface()
                self.input.set_virtual_mouse(
                    self.renderer.window_to_virtual(self.input.mouse_window)
                )
                self._handle_global_actions()
                self.scene_manager.handle_actions(self.input)
                self.scene_manager.apply_pending()
                if not self.running:
                    break

                for _ in range(self.timer.advance(frame_time)):
                    self.scene_manager.update(self.timer.step, self.input)

                self.renderer.begin_frame(self.theme.background)
                self.scene_manager.render(self.renderer)
                self.debug_overlay.render(self.renderer, self)
                self.renderer.present()

                self.frame_index += 1
                if max_frames is not None and self.frame_index >= max_frames:
                    break
        finally:
            pygame.quit()


def _non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m game",
        description="Паровоз — milestone 1: map, route and debug marker",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="path to the JSON configuration file",
    )
    parser.add_argument(
        "--map",
        type=Path,
        default=None,
        help="map file to load (default: the first entry in config.maps)",
    )
    parser.add_argument(
        "--scene",
        choices=_SCENE_CHOICES,
        default="menu",
        help="initial scene (default: menu)",
    )
    parser.add_argument("--debug", action="store_true", help="start with the debug overlay")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for future simulation")
    parser.add_argument(
        "--headless-frames",
        type=_non_negative_int,
        default=None,
        metavar="N",
        help="run N frames with dummy SDL drivers and exit (for smoke tests)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.headless_frames is not None:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    try:
        config = GameConfig.load(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    try:
        app = App(
            config,
            map_path=args.map,
            debug=args.debug,
            initial_scene=args.scene,
            seed=args.seed,
        )
    except MapError as exc:
        print(f"Map error: {exc}", file=sys.stderr)
        pygame.quit()
        return 2
    except pygame.error as exc:
        print(f"Failed to start pygame: {exc}", file=sys.stderr)
        pygame.quit()
        return 1

    app.run(max_frames=args.headless_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

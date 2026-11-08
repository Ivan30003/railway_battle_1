"""Debug overlay (F1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.core.game_state import GamePhase
from game.view.renderer import Renderer

if TYPE_CHECKING:
    from game.app.main import App


class DebugOverlay:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def toggle(self) -> None:
        self.enabled = not self.enabled

    def render(self, renderer: Renderer, app: App) -> None:
        if not self.enabled:
            return

        scene = app.scene_manager.current
        scene_name = scene.display_name if scene is not None else "none"
        phase = getattr(getattr(scene, "state", None), "phase", None)
        phase_name = phase.value if isinstance(phase, GamePhase) else "-"
        window_size = renderer.window.get_size()
        mouse_window = app.input.mouse_window
        mouse_virtual = app.input.mouse_virtual
        config_path = app.config.source_path.name if app.config.source_path else "-"
        map_data = app.map_data
        map_name = map_data.source_path.name if map_data.source_path else "-"

        lines = [
            f"FPS {app.fps:5.1f}   frame {app.frame_ms:5.1f} ms   frame #{app.frame_index}",
            f"scene {scene_name}   phase {phase_name}",
            f"window {window_size[0]}x{window_size[1]}   virtual "
            f"{renderer.virtual_size[0]}x{renderer.virtual_size[1]}   "
            f"scale {renderer.letterbox.scale:.3f}",
            f"mouse window ({mouse_window[0]}, {mouse_window[1]})   "
            f"virtual ({mouse_virtual[0]:.1f}, {mouse_virtual[1]:.1f})",
            f"map {map_name}   {map_data.width}x{map_data.height} tiles   "
            f"route {len(map_data.route_tiles)} tiles / {map_data.route_length:.0f} px",
            f"seed {app.seed}   config {config_path}",
            "F1 debug   B shop   Esc pause   M menu",
        ]

        line_height = 14
        panel = (8, 48, 470, line_height * len(lines) + 12)
        renderer.draw_panel(panel, (12, 16, 22), renderer.theme.debug, width=1, radius=4)
        for index, line in enumerate(lines):
            renderer.draw_text(
                line,
                11,
                renderer.theme.debug,
                (16, 54 + index * line_height),
            )

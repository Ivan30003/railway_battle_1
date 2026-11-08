from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("scene", ["menu", "game", "shop", "gameover", "victory"])
def test_scene_starts_and_exits_headless(scene: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "game",
            "--headless-frames",
            "3",
            "--scene",
            scene,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_bad_config_returns_exit_code(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "game",
            "--config",
            str(tmp_path / "missing.json"),
            "--headless-frames",
            "1",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "Config error" in result.stderr

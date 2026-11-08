from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "game", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("scene", ["menu", "game", "shop", "gameover", "victory"])
def test_scene_starts_and_exits_headless(scene: str) -> None:
    result = _run("--headless-frames", "3", "--scene", scene)

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_explicit_map_starts_headless() -> None:
    result = _run("--headless-frames", "3", "--scene", "game", "--map", "maps/map2.txt")

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_bad_config_returns_exit_code(tmp_path: Path) -> None:
    result = _run(
        "--config",
        str(tmp_path / "missing.json"),
        "--headless-frames",
        "1",
    )

    assert result.returncode == 2
    assert "Config error" in result.stderr


def test_bad_map_returns_exit_code(tmp_path: Path) -> None:
    path = tmp_path / "broken.txt"
    path.write_text("START=0,0\nDIR=RIGHT\nSH SH\n", encoding="utf-8")

    result = _run("--map", str(path), "--headless-frames", "1")

    assert result.returncode == 2
    assert "Map error" in result.stderr

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.core.config import ConfigError, GameConfig

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "game.json"


def test_shipped_config_loads() -> None:
    config = GameConfig.load(CONFIG_PATH)

    assert config.window.width == 1280
    assert config.window.height == 960
    assert config.window.resizable is True
    assert config.locomotive_hp == 100.0
    assert config.rounds_per_map == 5
    assert config.start_gold == 0
    assert config.maps == ("maps/map1.txt", "maps/map2.txt")
    assert config.tile_size == 32
    assert set(config.wagon_configs) == {"MACHINEGUN", "ICE", "MORTAR", "SNIPER"}
    assert set(config.monster_configs) == {"FAST_WEAK", "SLOW_TANK"}
    assert config.wagon_configs["SNIPER"].priority == ("SLOW_TANK", "FAST_WEAK")
    assert config.wagon_configs["MORTAR"].reserve == "primary"
    assert config.source_path == CONFIG_PATH


def test_empty_object_uses_defaults() -> None:
    config = GameConfig.from_dict({})

    assert config.window.width == 1280
    assert config.locomotive_hp == 100.0
    assert config.cannon.range == 450.0
    assert len(config.wagon_configs) == 4
    assert len(config.monster_configs) == 2


def test_nested_override_keeps_other_defaults() -> None:
    config = GameConfig.from_dict({"window": {"width": 800}})

    assert config.window.width == 800
    assert config.window.height == 960
    assert config.window.resizable is True


def test_wagon_override_merges_fields() -> None:
    config = GameConfig.from_dict(
        {"wagon_configs": {"MACHINEGUN": {"damage": 9}}}
    )

    machinegun = config.wagon_configs["MACHINEGUN"]
    assert machinegun.damage == 9.0
    assert machinegun.hp == 50.0
    assert machinegun.reserve == "target"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        GameConfig.load(tmp_path / "missing.json")


def test_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        GameConfig.load(path)


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"tile_size": -1}, "tile_size"),
        ({"tile_size": True}, "tile_size"),
        ({"window": {"resizable": "yes"}}, "window.resizable"),
        ({"ice_slow_max": 1.5}, "ice_slow_max"),
        ({"maps": []}, "maps"),
        ({"cannon": {"range": 0}}, "cannon.range"),
        ({"wagon_configs": {"UNKNOWN": {}}}, "Unknown wagon"),
        ({"wagon_configs": {"ICE": {"reserve": "sometimes"}}}, "reserve"),
        (
            {"wagon_configs": {"SNIPER": {"priority": ["UNKNOWN"]}}},
            "unknown monster type",
        ),
    ],
)
def test_invalid_values_raise(raw: dict, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        GameConfig.from_dict(raw)


def test_config_file_can_be_loaded_from_json_text(tmp_path: Path) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["start_gold"] = 77
    path = tmp_path / "custom.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    config = GameConfig.load(path)
    assert config.start_gold == 77

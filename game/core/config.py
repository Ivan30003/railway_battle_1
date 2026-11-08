"""Game configuration loading and validation.

The core layer deliberately has no pygame dependency, so the configuration can be
loaded (and tested) without creating a window or initialising SDL.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the configuration file is missing or invalid."""


@dataclass(frozen=True)
class WindowConfig:
    width: int
    height: int
    resizable: bool
    vsync: bool


@dataclass(frozen=True)
class CannonConfig:
    damage: float
    fire_interval: float
    range: float


@dataclass(frozen=True)
class SpawnConfig:
    initial_interval: float
    min_interval: float
    ramp_seconds: float
    tank_share_start: float
    tank_share_max: float
    spawn_margin: float


@dataclass(frozen=True)
class WagonConfig:
    radius: float
    rotation_speed_deg_per_sec: float
    fire_interval: float
    damage: float
    hp: float
    aim_threshold_deg: float
    priority: tuple[str, ...] | None
    reserve: str
    slow_percent: float | None = None
    aoe_radius: float | None = None


@dataclass(frozen=True)
class MonsterConfig:
    hp: float
    speed: float
    gold: int
    damage: float
    attack_interval: float


@dataclass(frozen=True)
class GameConfig:
    window: WindowConfig
    tile_size: int
    train_speed: float
    wagon_spacing: float
    rounds_per_map: int
    start_wagons: tuple[str, ...]
    start_gold: int
    wagon_base_cost: int
    wagon_cost_step: int
    locomotive_hp: float
    ice_slow_per_wagon: float
    ice_slow_max: float
    ice_slow_duration: float
    mortar_aoe_radius: float
    turret_aim_threshold_deg: float
    train_stop_per_crush_ms: float
    monster_hit_radius: float
    train_crush_radius: float
    monster_attack_range: float
    cannon: CannonConfig
    maps: tuple[str, ...]
    spawn: SpawnConfig
    wagon_configs: dict[str, WagonConfig]
    monster_configs: dict[str, MonsterConfig]
    source_path: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> GameConfig:
        config_path = Path(path)
        if not config_path.is_file():
            raise ConfigError(f"Config file not found: {config_path}")
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigError(f"Cannot read config {config_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"Invalid JSON in {config_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        return cls.from_dict(raw, source_path=config_path)

    @classmethod
    def from_dict(cls, raw: Any, source_path: Path | None = None) -> GameConfig:
        if not isinstance(raw, dict):
            raise ConfigError("Config root must be a JSON object")

        merged = _deep_merge(copy.deepcopy(DEFAULT_CONFIG), raw)

        window = _mapping(merged, "window")
        window_cfg = WindowConfig(
            width=_positive_int(window.get("width"), "window.width"),
            height=_positive_int(window.get("height"), "window.height"),
            resizable=_boolean(window.get("resizable"), "window.resizable"),
            vsync=_boolean(window.get("vsync"), "window.vsync"),
        )

        cannon = _mapping(merged, "cannon")
        cannon_cfg = CannonConfig(
            damage=_positive_number(cannon.get("damage"), "cannon.damage"),
            fire_interval=_positive_number(cannon.get("fire_interval"), "cannon.fire_interval"),
            range=_positive_number(cannon.get("range"), "cannon.range"),
        )

        spawn = _mapping(merged, "spawn")
        spawn_cfg = SpawnConfig(
            initial_interval=_positive_number(
                spawn.get("initial_interval"), "spawn.initial_interval"
            ),
            min_interval=_positive_number(spawn.get("min_interval"), "spawn.min_interval"),
            ramp_seconds=_positive_number(spawn.get("ramp_seconds"), "spawn.ramp_seconds"),
            tank_share_start=_fraction(spawn.get("tank_share_start"), "spawn.tank_share_start"),
            tank_share_max=_fraction(spawn.get("tank_share_max"), "spawn.tank_share_max"),
            spawn_margin=_non_negative_number(spawn.get("spawn_margin"), "spawn.spawn_margin"),
        )

        maps_raw = merged.get("maps")
        if not isinstance(maps_raw, list) or not maps_raw:
            raise ConfigError("maps must be a non-empty list of file paths")
        maps: list[str] = []
        for index, value in enumerate(maps_raw):
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"maps[{index}] must be a non-empty string")
            maps.append(value)

        wagon_configs = _parse_wagon_configs(_mapping(merged, "wagon_configs"), merged)
        monster_configs = _parse_monster_configs(_mapping(merged, "monster_configs"))
        start_wagons = _parse_start_wagons(merged.get("start_wagons"), wagon_configs)

        ice_slow_per_wagon = _fraction(merged.get("ice_slow_per_wagon"), "ice_slow_per_wagon")
        ice_slow_max = _fraction(merged.get("ice_slow_max"), "ice_slow_max")
        if ice_slow_max > 1.0:
            raise ConfigError("ice_slow_max must be between 0 and 1")

        return cls(
            window=window_cfg,
            tile_size=_positive_int(merged.get("tile_size"), "tile_size"),
            train_speed=_positive_number(merged.get("train_speed"), "train_speed"),
            wagon_spacing=_positive_number(merged.get("wagon_spacing"), "wagon_spacing"),
            rounds_per_map=_positive_int(merged.get("rounds_per_map"), "rounds_per_map"),
            start_wagons=start_wagons,
            start_gold=_non_negative_int(merged.get("start_gold"), "start_gold"),
            wagon_base_cost=_non_negative_int(merged.get("wagon_base_cost"), "wagon_base_cost"),
            wagon_cost_step=_non_negative_int(merged.get("wagon_cost_step"), "wagon_cost_step"),
            locomotive_hp=_positive_number(merged.get("locomotive_hp"), "locomotive_hp"),
            ice_slow_per_wagon=ice_slow_per_wagon,
            ice_slow_max=ice_slow_max,
            ice_slow_duration=_positive_number(
                merged.get("ice_slow_duration"), "ice_slow_duration"
            ),
            mortar_aoe_radius=_positive_number(
                merged.get("mortar_aoe_radius"), "mortar_aoe_radius"
            ),
            turret_aim_threshold_deg=_positive_number(
                merged.get("turret_aim_threshold_deg"), "turret_aim_threshold_deg"
            ),
            train_stop_per_crush_ms=_positive_number(
                merged.get("train_stop_per_crush_ms"), "train_stop_per_crush_ms"
            ),
            monster_hit_radius=_positive_number(
                merged.get("monster_hit_radius"), "monster_hit_radius"
            ),
            train_crush_radius=_positive_number(
                merged.get("train_crush_radius"), "train_crush_radius"
            ),
            monster_attack_range=_positive_number(
                merged.get("monster_attack_range"), "monster_attack_range"
            ),
            cannon=cannon_cfg,
            maps=tuple(maps),
            spawn=spawn_cfg,
            wagon_configs=wagon_configs,
            monster_configs=monster_configs,
            source_path=source_path,
        )


def _parse_wagon_configs(raw: dict[str, Any], merged: dict[str, Any]) -> dict[str, WagonConfig]:
    known = set(DEFAULT_CONFIG["wagon_configs"])
    unknown = set(raw) - known
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(f"Unknown wagon type(s): {names}")

    result: dict[str, WagonConfig] = {}
    for wagon_type in sorted(known):
        item = _mapping(raw, wagon_type)
        prefix = f"wagon_configs.{wagon_type}"
        reserve = item.get("reserve")
        if reserve not in {"target", "none", "primary"}:
            raise ConfigError(f"{prefix}.reserve must be one of: target, none, primary")
        priority = _priority(item.get("priority"), f"{prefix}.priority", merged)
        slow_percent = (
            _fraction(item.get("slow_percent"), f"{prefix}.slow_percent")
            if item.get("slow_percent") is not None
            else None
        )
        aoe_radius = (
            _positive_number(item.get("aoe_radius"), f"{prefix}.aoe_radius")
            if item.get("aoe_radius") is not None
            else None
        )
        result[wagon_type] = WagonConfig(
            radius=_positive_number(item.get("radius"), f"{prefix}.radius"),
            rotation_speed_deg_per_sec=_positive_number(
                item.get("rotation_speed_deg_per_sec"),
                f"{prefix}.rotation_speed_deg_per_sec",
            ),
            fire_interval=_positive_number(item.get("fire_interval"), f"{prefix}.fire_interval"),
            damage=_non_negative_number(item.get("damage"), f"{prefix}.damage"),
            hp=_positive_number(item.get("hp"), f"{prefix}.hp"),
            aim_threshold_deg=_non_negative_number(
                item.get("aim_threshold_deg"), f"{prefix}.aim_threshold_deg"
            ),
            priority=priority,
            reserve=reserve,
            slow_percent=slow_percent,
            aoe_radius=aoe_radius,
        )
    return result


def _parse_start_wagons(
    value: Any,
    wagon_configs: dict[str, WagonConfig],
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigError("start_wagons must be a list of wagon type names")
    result: list[str] = []
    for index, kind in enumerate(value):
        if not isinstance(kind, str) or not kind.strip():
            raise ConfigError(f"start_wagons[{index}] must be a non-empty string")
        if kind not in wagon_configs:
            raise ConfigError(
                f"start_wagons[{index}] references unknown wagon type: {kind}"
            )
        result.append(kind)
    return tuple(result)


def _parse_monster_configs(raw: dict[str, Any]) -> dict[str, MonsterConfig]:
    if not isinstance(raw, dict) or not raw:
        raise ConfigError("monster_configs must be a non-empty object")
    result: dict[str, MonsterConfig] = {}
    for monster_type, item in raw.items():
        if not isinstance(monster_type, str) or not monster_type.strip():
            raise ConfigError("monster_configs keys must be non-empty strings")
        if not isinstance(item, dict):
            raise ConfigError(f"monster_configs.{monster_type} must be an object")
        prefix = f"monster_configs.{monster_type}"
        result[monster_type] = MonsterConfig(
            hp=_positive_number(item.get("hp"), f"{prefix}.hp"),
            speed=_positive_number(item.get("speed"), f"{prefix}.speed"),
            gold=_non_negative_int(item.get("gold"), f"{prefix}.gold"),
            damage=_non_negative_number(item.get("damage"), f"{prefix}.damage"),
            attack_interval=_positive_number(
                item.get("attack_interval"), f"{prefix}.attack_interval"
            ),
        )
    for required in ("FAST_WEAK", "SLOW_TANK"):
        if required not in result:
            raise ConfigError(f"monster_configs.{required} is required")
    return result


def _priority(
    value: Any, field: str, merged: dict[str, Any]
) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{field} must be null or a list of monster type names")
    monster_types = set(_mapping(merged, "monster_configs"))
    unknown = set(value) - monster_types
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(f"{field} references unknown monster type(s): {names}")
    return tuple(value)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be an object")
    return value


def _positive_int(value: Any, field: str) -> int:
    number = _int(value, field)
    if number <= 0:
        raise ConfigError(f"{field} must be greater than 0")
    return number


def _non_negative_int(value: Any, field: str) -> int:
    number = _int(value, field)
    if number < 0:
        raise ConfigError(f"{field} must be greater than or equal to 0")
    return number


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{field} must be an integer")
    return value


def _positive_number(value: Any, field: str) -> float:
    number = _number(value, field)
    if number <= 0:
        raise ConfigError(f"{field} must be greater than 0")
    return number


def _non_negative_number(value: Any, field: str) -> float:
    number = _number(value, field)
    if number < 0:
        raise ConfigError(f"{field} must be greater than or equal to 0")
    return number


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{field} must be a number")
    return float(value)


def _fraction(value: Any, field: str) -> float:
    number = _number(value, field)
    if not 0.0 <= number <= 1.0:
        raise ConfigError(f"{field} must be between 0 and 1")
    return number


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{field} must be true or false")
    return value


DEFAULT_CONFIG: dict[str, Any] = {
    "window": {
        "width": 1280,
        "height": 960,
        "resizable": True,
        "vsync": True,
    },
    "tile_size": 32,
    "train_speed": 70,
    "wagon_spacing": 44,
    "rounds_per_map": 5,
    "start_wagons": ["MACHINEGUN", "ICE"],
    "start_gold": 0,
    "wagon_base_cost": 30,
    "wagon_cost_step": 10,
    "locomotive_hp": 100,
    "ice_slow_per_wagon": 0.2,
    "ice_slow_max": 0.8,
    "ice_slow_duration": 3.0,
    "mortar_aoe_radius": 64,
    "turret_aim_threshold_deg": 7,
    "train_stop_per_crush_ms": 500,
    "monster_hit_radius": 10,
    "train_crush_radius": 18,
    "monster_attack_range": 24,
    "cannon": {
        "damage": 30,
        "fire_interval": 0.35,
        "range": 450,
    },
    "maps": ["maps/map1.txt", "maps/map2.txt"],
    "spawn": {
        "initial_interval": 2.0,
        "min_interval": 0.35,
        "ramp_seconds": 600,
        "tank_share_start": 0.1,
        "tank_share_max": 0.5,
        "spawn_margin": 32,
    },
    "wagon_configs": {
        "MACHINEGUN": {
            "radius": 150,
            "rotation_speed_deg_per_sec": 360,
            "fire_interval": 0.2,
            "damage": 5,
            "hp": 50,
            "aim_threshold_deg": 7,
            "priority": None,
            "reserve": "target",
        },
        "ICE": {
            "radius": 120,
            "rotation_speed_deg_per_sec": 180,
            "fire_interval": 1.0,
            "damage": 2,
            "hp": 40,
            "aim_threshold_deg": 7,
            "priority": None,
            "reserve": "none",
            "slow_percent": 0.2,
            "aoe_radius": 48,
        },
        "MORTAR": {
            "radius": 200,
            "rotation_speed_deg_per_sec": 90,
            "fire_interval": 2.0,
            "damage": 20,
            "hp": 40,
            "aim_threshold_deg": 7,
            "priority": None,
            "reserve": "primary",
            "aoe_radius": 64,
        },
        "SNIPER": {
            "radius": 300,
            "rotation_speed_deg_per_sec": 60,
            "fire_interval": 3.0,
            "damage": 50,
            "hp": 30,
            "aim_threshold_deg": 5,
            "priority": ["SLOW_TANK", "FAST_WEAK"],
            "reserve": "target",
        },
    },
    "monster_configs": {
        "FAST_WEAK": {
            "hp": 10,
            "speed": 80,
            "gold": 1,
            "damage": 5,
            "attack_interval": 1.0,
        },
        "SLOW_TANK": {
            "hp": 50,
            "speed": 30,
            "gold": 5,
            "damage": 15,
            "attack_interval": 1.5,
        },
    },
}

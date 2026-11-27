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


INFANTRY_WAGON = "INFANTRY"

_INFANTRY_FIELDS = (
    "drop_interval",
    "soldiers_per_drop",
    "drop_offset",
    "soldier_range",
    "soldier_damage",
    "soldier_fire_interval",
    "soldier_radius",
    "soldier_speed",
)

_LEGACY_SPAWN_KEYS = {
    "initial_interval",
    "min_interval",
    "ramp_seconds",
    "tank_share_start",
    "tank_share_max",
    "spawn_margin",
}


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
    cooldown_start: float
    cooldown_step: float
    cooldown_min: float
    probability_spawn_dist_start: dict[str, float]


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
    # Infantry-only fields. Other wagon types leave them as ``None``.
    drop_interval: float | None = None
    soldiers_per_drop: int | None = None
    drop_offset: float | None = None
    soldier_range: float | None = None
    soldier_damage: float | None = None
    soldier_fire_interval: float | None = None
    soldier_radius: float | None = None
    soldier_speed: float | None = None


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
    curved_turns: bool
    turn_curvatures: tuple[float, ...]
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
    train_stop_per_crush_ms: float
    crush_slow_factor: float
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

        spawn = merged.get("spawn")
        if spawn is not None:
            _reject_legacy_spawn_keys(_mapping(merged, "spawn"))

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
        spawn_cfg = SpawnConfig(
            cooldown_start=_positive_number(
                merged.get("monsters_cooldown_start"),
                "monsters_cooldown_start",
            ),
            cooldown_step=_non_negative_number(
                merged.get("monsters_cooldown_step"),
                "monsters_cooldown_step",
            ),
            cooldown_min=_positive_number(
                merged.get("monsters_cooldown_min"),
                "monsters_cooldown_min",
            ),
            probability_spawn_dist_start=_parse_spawn_distribution(
                merged.get("monsters_probability_spawn_dist_start"),
                monster_configs,
            ),
        )
        if spawn_cfg.cooldown_min > spawn_cfg.cooldown_start:
            raise ConfigError(
                "monsters_cooldown_min must be less than or equal to "
                "monsters_cooldown_start"
            )
        start_wagons = _parse_start_wagons(merged.get("start_wagons"), wagon_configs)

        curved_turns = _boolean(merged.get("curved_turns"), "curved_turns")
        turn_curvatures = _curvature_list(merged.get("turn_curvatures"))

        ice_slow_per_wagon = _fraction(merged.get("ice_slow_per_wagon"), "ice_slow_per_wagon")
        ice_slow_max = _fraction(merged.get("ice_slow_max"), "ice_slow_max")
        if ice_slow_max > 1.0:
            raise ConfigError("ice_slow_max must be between 0 and 1")

        return cls(
            window=window_cfg,
            tile_size=_positive_int(merged.get("tile_size"), "tile_size"),
            curved_turns=curved_turns,
            turn_curvatures=turn_curvatures,
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
            train_stop_per_crush_ms=_positive_number(
                merged.get("train_stop_per_crush_ms"), "train_stop_per_crush_ms"
            ),
            crush_slow_factor=_fraction(
                merged.get("crush_slow_factor"), "crush_slow_factor"
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
        drop_interval = (
            _positive_number(item.get("drop_interval"), f"{prefix}.drop_interval")
            if item.get("drop_interval") is not None
            else None
        )
        soldiers_per_drop = (
            _positive_int(item.get("soldiers_per_drop"), f"{prefix}.soldiers_per_drop")
            if item.get("soldiers_per_drop") is not None
            else None
        )
        drop_offset = (
            _positive_number(item.get("drop_offset"), f"{prefix}.drop_offset")
            if item.get("drop_offset") is not None
            else None
        )
        soldier_range = (
            _positive_number(item.get("soldier_range"), f"{prefix}.soldier_range")
            if item.get("soldier_range") is not None
            else None
        )
        soldier_damage = (
            _non_negative_number(item.get("soldier_damage"), f"{prefix}.soldier_damage")
            if item.get("soldier_damage") is not None
            else None
        )
        soldier_fire_interval = (
            _positive_number(
                item.get("soldier_fire_interval"),
                f"{prefix}.soldier_fire_interval",
            )
            if item.get("soldier_fire_interval") is not None
            else None
        )
        soldier_radius = (
            _positive_number(item.get("soldier_radius"), f"{prefix}.soldier_radius")
            if item.get("soldier_radius") is not None
            else None
        )
        soldier_speed = (
            _positive_number(item.get("soldier_speed"), f"{prefix}.soldier_speed")
            if item.get("soldier_speed") is not None
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
                item.get("aim_threshold_deg"),
                f"{prefix}.aim_threshold_deg",
            ),
            priority=priority,
            reserve=reserve,
            slow_percent=slow_percent,
            aoe_radius=aoe_radius,
            drop_interval=drop_interval,
            soldiers_per_drop=soldiers_per_drop,
            drop_offset=drop_offset,
            soldier_range=soldier_range,
            soldier_damage=soldier_damage,
            soldier_fire_interval=soldier_fire_interval,
            soldier_radius=soldier_radius,
            soldier_speed=soldier_speed,
        )
        if wagon_type == INFANTRY_WAGON:
            missing = [
                field
                for field in _INFANTRY_FIELDS
                if getattr(result[wagon_type], field) is None
            ]
            if missing:
                raise ConfigError(
                    f"{prefix}.{missing[0]} is required for {INFANTRY_WAGON}"
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


def _parse_spawn_distribution(
    value: Any,
    monster_configs: dict[str, MonsterConfig],
) -> dict[str, float]:
    if not isinstance(value, dict) or not value:
        raise ConfigError(
            "monsters_probability_spawn_dist_start must be a non-empty object"
        )
    known = set(monster_configs)
    unknown = set(value) - known
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(
            "monsters_probability_spawn_dist_start references unknown "
            f"monster type(s): {names}"
        )
    missing = known - set(value)
    if missing:
        names = ", ".join(sorted(missing))
        raise ConfigError(
            "monsters_probability_spawn_dist_start is missing monster type(s): "
            f"{names}"
        )

    result: dict[str, float] = {}
    for kind, probability in value.items():
        result[kind] = _fraction(
            probability,
            f"monsters_probability_spawn_dist_start.{kind}",
        )
    total = sum(result.values())
    if abs(total - 1.0) > 1e-6:
        raise ConfigError("monsters_probability_spawn_dist_start must sum to 1.0")
    return result


def _reject_legacy_spawn_keys(spawn: dict[str, Any]) -> None:
    legacy = sorted(_LEGACY_SPAWN_KEYS & set(spawn))
    if not legacy:
        return
    names = ", ".join(f"spawn.{key}" for key in legacy)
    raise ConfigError(
        f"{names} are no longer supported; monsters now spawn on the screen "
        "edge opposite the train"
    )


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


def _curvature_list(value: Any) -> tuple[float, ...]:
    field = "turn_curvatures"
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{field} must be a non-empty list of numbers")
    result: list[float] = []
    for index, item in enumerate(value):
        number = _number(item, f"{field}[{index}]")
        if not 0.0 < number <= 1.0:
            raise ConfigError(f"{field}[{index}] must be greater than 0 and at most 1")
        result.append(number)
    return tuple(result)


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
    "curved_turns": True,
    "turn_curvatures": [0.4, 0.55, 0.75],
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
    "train_stop_per_crush_ms": 500,
    "crush_slow_factor": 0.5,
    "monster_hit_radius": 10,
    "train_crush_radius": 18,
    "monster_attack_range": 24,
    "monsters_cooldown_start": 2.0,
    "monsters_cooldown_step": 0.1,
    "monsters_cooldown_min": 0.35,
    "monsters_probability_spawn_dist_start": {
        "FAST_WEAK": 0.9,
        "SLOW_TANK": 0.1,
    },
    "cannon": {
        "damage": 30,
        "fire_interval": 0.35,
        "range": 450,
    },
    "maps": ["maps/map1.txt", "maps/map2.txt"],
    "wagon_configs": {
        "MACHINEGUN": {
            "radius": 150,
            "rotation_speed_deg_per_sec": 360,
            "fire_interval": 0.2,
            "damage": 5,
            "hp": 30,
            "aim_threshold_deg": 7,
            "priority": None,
            "reserve": "target",
        },
        "ICE": {
            "radius": 120,
            "rotation_speed_deg_per_sec": 180,
            "fire_interval": 1.0,
            "damage": 2,
            "hp": 30,
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
            "hp": 30,
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
        "INFANTRY": {
            "radius": 10,
            "rotation_speed_deg_per_sec": 360,
            "fire_interval": 1.0,
            "damage": 0,
            "hp": 30,
            "aim_threshold_deg": 7,
            "priority": None,
            "reserve": "none",
            "drop_interval": 8.0,
            "soldiers_per_drop": 2,
            "drop_offset": 26,
            "soldier_range": 120,
            "soldier_damage": 4,
            "soldier_fire_interval": 1.2,
            "soldier_radius": 6,
            "soldier_speed": 24,
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

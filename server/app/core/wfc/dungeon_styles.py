"""
dungeon_styles.py — Dungeon style templates for WFC generation.

Port of DUNGEON_TEMPLATES from tools/dungeon-wfc GeneratorPanel.jsx.
Each style modifies module weights by purpose AND overrides decorator
settings to create dramatically different dungeon feels.

Styles are auto-selected based on floor depth + seed, or can be
manually overridden via FloorConfig.dungeon_style.
"""

from __future__ import annotations

from typing import Any


# ─── Style Definitions ─────────────────────────────────────────────────
#
# Each style has:
#   name            — human-readable name
#   description     — short description of the feel
#   weight_overrides — dict mapping module purpose → weight multiplier
#                      (missing keys default to 1.0 — no change)
#   decorator_overrides — dict of decorator setting overrides
#                         (merged on top of floor-scaled defaults)

DUNGEON_STYLES: dict[str, dict[str, Any]] = {
    "balanced": {
        "name": "Balanced",
        "description": "Default balanced dungeon — no weight modifications",
        "weight_overrides": {},
        "decorator_overrides": {},
    },
    "dense_catacomb": {
        "name": "Dense Catacomb",
        "description": "Tight corridors, many enemies, claustrophobic",
        "weight_overrides": {
            "corridor": 2.5,
            "empty": 0.4,
            "enemy": 2.0,
            "boss": 0.3,
            "loot": 0.3,
            "spawn": 1.0,
        },
        "decorator_overrides": {
            "enemyDensity": 0.7,
            "lootDensity": 0.1,
            "emptyRoomChance": 0.1,
            "guaranteeBoss": False,
            "scatterEnemies": True,
            "scatterChests": False,
        },
    },
    "open_ruins": {
        "name": "Open Ruins",
        "description": "Spacious rooms, fewer walls, exploration-focused",
        "weight_overrides": {
            "corridor": 0.6,
            "empty": 2.5,
            "enemy": 0.8,
            "boss": 0.5,
            "loot": 1.5,
            "spawn": 1.0,
        },
        "decorator_overrides": {
            "enemyDensity": 0.25,
            "lootDensity": 0.3,
            "emptyRoomChance": 0.35,
            "guaranteeBoss": True,
            "scatterEnemies": True,
            "scatterChests": True,
        },
    },
    "boss_rush": {
        "name": "Boss Rush",
        "description": "Direct paths to boss, minimal detours, lethal",
        "weight_overrides": {
            "corridor": 1.8,
            "empty": 0.5,
            "enemy": 1.5,
            "boss": 2.0,
            "loot": 0.3,
            "spawn": 1.0,
        },
        "decorator_overrides": {
            "enemyDensity": 0.6,
            "lootDensity": 0.05,
            "emptyRoomChance": 0.1,
            "guaranteeBoss": True,
            "scatterEnemies": True,
            "scatterChests": False,
        },
    },
    "treasure_vault": {
        "name": "Treasure Vault",
        "description": "Loot-heavy, dead-ends with chests, guarded rooms",
        "weight_overrides": {
            "corridor": 1.0,
            "empty": 1.0,
            "enemy": 1.2,
            "boss": 0.2,
            "loot": 3.0,
            "spawn": 1.0,
        },
        "decorator_overrides": {
            "enemyDensity": 0.3,
            "lootDensity": 0.5,
            "emptyRoomChance": 0.1,
            "guaranteeBoss": False,
            "guaranteeSpawn": True,
            "scatterEnemies": True,
            "scatterChests": True,
        },
    },
}

# All valid style keys (for validation)
VALID_STYLES = frozenset(DUNGEON_STYLES.keys())


# ─── Floor-based auto-selection ────────────────────────────────────────
#
# Each floor tier has a weighted pool of styles. The seed determines
# which style is picked, so the same seed+floor always gives the same
# style (deterministic).

_FLOOR_STYLE_POOLS: list[tuple[int, list[tuple[str, float]]]] = [
    (2, [  # Floors 1-2: introductory — favor Balanced and Open Ruins
        ("balanced", 0.45),
        ("open_ruins", 0.35),
        ("treasure_vault", 0.15),
        ("dense_catacomb", 0.05),
    ]),
    (5, [  # Floors 3-5: mix of all styles
        ("balanced", 0.25),
        ("dense_catacomb", 0.20),
        ("open_ruins", 0.20),
        ("boss_rush", 0.15),
        ("treasure_vault", 0.20),
    ]),
    (8, [  # Floors 6-8: favor intense styles
        ("dense_catacomb", 0.30),
        ("boss_rush", 0.30),
        ("balanced", 0.15),
        ("treasure_vault", 0.15),
        ("open_ruins", 0.10),
    ]),
    (99, [  # Floors 9+: heavily dangerous
        ("dense_catacomb", 0.35),
        ("boss_rush", 0.35),
        ("balanced", 0.10),
        ("treasure_vault", 0.15),
        ("open_ruins", 0.05),
    ]),
]


def _mulberry32(seed: int):
    """Minimal mulberry32 PRNG for style selection."""
    s = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((s ^ (s >> 15)) * (1 | s)) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF) ^ t
        t = t & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def select_style_for_floor(floor_number: int, seed: int) -> str:
    """Auto-select a dungeon style based on floor depth and seed.

    Uses a weighted random pick from the floor tier's style pool.
    Deterministic: same seed + floor_number always picks the same style.

    Args:
        floor_number: The dungeon floor (1-based).
        seed: The generation seed.

    Returns:
        A style key from DUNGEON_STYLES (e.g. "balanced", "dense_catacomb").
    """
    # Find the style pool for this floor tier
    pool = _FLOOR_STYLE_POOLS[-1][1]  # default to deepest tier
    for max_floor, tier_pool in _FLOOR_STYLE_POOLS:
        if floor_number <= max_floor:
            pool = tier_pool
            break

    # Use a deterministic RNG based on seed + floor offset
    rng = _mulberry32(seed + floor_number * 31337)
    roll = rng()

    total = sum(w for _, w in pool)
    cumulative = 0.0
    for style_key, weight in pool:
        cumulative += weight / total
        if roll < cumulative:
            return style_key

    # Fallback (float rounding)
    return pool[-1][0]


def get_style(style_key: str) -> dict[str, Any]:
    """Look up a dungeon style by key.

    Args:
        style_key: Key from DUNGEON_STYLES (e.g. "balanced").

    Returns:
        The style dict. Falls back to "balanced" if key is unknown.
    """
    return DUNGEON_STYLES.get(style_key, DUNGEON_STYLES["balanced"])


def apply_weight_overrides(modules: list[dict], style_key: str) -> list[dict]:
    """Apply a style's weight overrides to a list of modules.

    Creates shallow copies of each module dict with the weight field
    multiplied by the style's override for that module's purpose.
    Modules whose purpose has no override are left unchanged.

    Args:
        modules: List of module dicts (from get_preset_modules()).
        style_key: Key from DUNGEON_STYLES.

    Returns:
        New list of module dicts with adjusted weights.
        Original dicts are NOT mutated.
    """
    style = get_style(style_key)
    overrides = style.get("weight_overrides", {})

    if not overrides:
        return modules  # "balanced" — no changes needed

    adjusted = []
    for mod in modules:
        purpose = mod.get("purpose", "empty")
        multiplier = overrides.get(purpose, 1.0)
        if multiplier != 1.0:
            # Shallow copy with adjusted weight
            new_mod = {**mod, "weight": mod.get("weight", 1.0) * multiplier}
            adjusted.append(new_mod)
        else:
            adjusted.append(mod)

    return adjusted


def get_decorator_overrides(style_key: str) -> dict[str, Any]:
    """Get decorator setting overrides for a style.

    Args:
        style_key: Key from DUNGEON_STYLES.

    Returns:
        Dict of decorator overrides to merge into decorator settings.
    """
    style = get_style(style_key)
    return dict(style.get("decorator_overrides", {}))

"""
module_utils.py — Module data structures, socket derivation, rotation expansion.

Port of tools/dungeon-wfc/src/engine/moduleUtils.js to Python.
All modules are MODULE_SIZE x MODULE_SIZE tile grids. Sockets are auto-derived
from edge tiles. Rotation variants are generated for WFC compatibility matching.
"""

from __future__ import annotations

import copy
from typing import Any

MODULE_SIZE = 8

# Tile types considered "open" (passable) for socket pattern derivation
OPEN_TILES = frozenset({"F", "D", "C", "S", "X", "E", "B"})

# Content roles for the room decorator system
CONTENT_ROLES = ("flexible", "fixed", "structural")


def socket_char(tile: str) -> str:
    """Simplify a tile type for socket pattern comparison.
    All open tiles become 'O', walls stay 'W'.
    """
    return "O" if tile in OPEN_TILES else "W"


def derive_socket(tiles: list[list[str]], direction: str) -> str:
    """Derive socket string for a module edge.

    direction: 'north' | 'south' | 'east' | 'west'
    Returns a string like 'WWOOWW' where W=wall, O=open.
    """
    h = len(tiles)
    w = len(tiles[0]) if h > 0 else 0

    if direction == "north":
        edge_tiles = tiles[0]
    elif direction == "south":
        edge_tiles = tiles[h - 1]
    elif direction == "west":
        edge_tiles = [row[0] for row in tiles]
    elif direction == "east":
        edge_tiles = [row[w - 1] for row in tiles]
    else:
        return ""

    return "".join(socket_char(t) for t in edge_tiles)


def derive_sockets(tiles: list[list[str]]) -> dict[str, str]:
    """Get all four sockets for a module."""
    return {
        "north": derive_socket(tiles, "north"),
        "south": derive_socket(tiles, "south"),
        "east": derive_socket(tiles, "east"),
        "west": derive_socket(tiles, "west"),
    }


def rotate_tiles_90cw(tiles: list[list[str]]) -> list[list[str]]:
    """Rotate a tile grid 90° clockwise.
    newTiles[r][c] = oldTiles[N-1-c][r]
    """
    h = len(tiles)
    w = len(tiles[0]) if h > 0 else 0
    rotated = []
    for r in range(w):
        row = []
        for c in range(h):
            row.append(tiles[h - 1 - c][r])
        rotated.append(row)
    return rotated


def _rotate_slot_90cw(slot: dict, size: int) -> dict:
    """Rotate a single spawn slot coordinate 90° CW within a size×size grid.
    (x, y) → (size-1-y, x)
    """
    return {
        "x": size - 1 - slot["y"],
        "y": slot["x"],
        "types": list(slot.get("types", ["enemy", "loot", "spawn", "boss"])),
    }


def generate_rotation_variants(mod: dict) -> list[dict]:
    """Generate all rotation variants for a module (0°, 90°, 180°, 270°).

    Deduplicates if rotations produce identical socket signatures.
    Returns list of variant dicts with tiles, sockets, rotation, and metadata.
    """
    variants = []
    seen: set[str] = set()

    current_tiles = [list(row) for row in mod["tiles"]]
    current_slots = [
        {**s, "types": list(s.get("types", []))}
        for s in (mod.get("spawnSlots") or [])
    ]
    size = len(mod["tiles"])

    for rot in range(4):
        if rot > 0:
            current_tiles = rotate_tiles_90cw(current_tiles)
            current_slots = [_rotate_slot_90cw(s, size) for s in current_slots]

        sockets = derive_sockets(current_tiles)
        key = f"{sockets['north']}|{sockets['south']}|{sockets['east']}|{sockets['west']}"

        if key not in seen:
            seen.add(key)
            variants.append({
                "tiles": [list(row) for row in current_tiles],
                "sockets": dict(sockets),
                "rotation": rot * 90,
                "sourceId": mod.get("id", ""),
                "sourceName": mod.get("name", "Unknown"),
                "purpose": mod.get("purpose", "empty"),
                "weight": mod.get("weight", 1.0),
                # Decorator metadata
                "contentRole": mod.get("contentRole", "structural"),
                "spawnSlots": [
                    {**s, "types": list(s.get("types", []))}
                    for s in current_slots
                ],
                "maxEnemies": mod.get("maxEnemies", 0),
                "maxChests": mod.get("maxChests", 0),
                "canBeBoss": mod.get("canBeBoss", False),
                "canBeSpawn": mod.get("canBeSpawn", False),
            })

    return variants


def expand_modules(modules: list[dict]) -> list[dict]:
    """Expand the full module library into WFC-ready variants.

    Each module with allowRotation gets up to 4 variants.
    Each module without rotation gets 1 variant.
    """
    variants = []
    for mod in modules:
        if mod.get("allowRotation", False):
            variants.extend(generate_rotation_variants(mod))
        else:
            sockets = derive_sockets(mod["tiles"])
            variants.append({
                "tiles": [list(row) for row in mod["tiles"]],
                "sockets": sockets,
                "rotation": 0,
                "sourceId": mod.get("id", ""),
                "sourceName": mod.get("name", "Unknown"),
                "purpose": mod.get("purpose", "empty"),
                "weight": mod.get("weight", 1.0),
                # Decorator metadata
                "contentRole": mod.get("contentRole", "structural"),
                "spawnSlots": mod.get("spawnSlots", []),
                "maxEnemies": mod.get("maxEnemies", 0),
                "maxChests": mod.get("maxChests", 0),
                "canBeBoss": mod.get("canBeBoss", False),
                "canBeSpawn": mod.get("canBeSpawn", False),
            })
    return variants


def derive_spawn_slots(tiles: list[list[str]]) -> list[dict]:
    """Auto-derive spawnSlots from a module's tile grid.

    Returns an array of {x, y, types} for every interior floor tile
    (tiles not on the outer edge that are 'F' type).
    """
    slots = []
    h = len(tiles)
    w = len(tiles[0]) if h > 0 else 0
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if tiles[r][c] == "F":
                slots.append({"x": c, "y": r, "types": ["enemy", "loot", "spawn", "boss"]})
    return slots

"""
presets.py — Module library for WFC dungeon generation.

Loads modules from a canonical JSON library file (``library.json``) when
available, falling back to the hardcoded ``_BUILTIN_MODULES`` below.

The JSON library is the **single source of truth** shared between the
WFC Dungeon Tool (JS) and the game server (Python).  Edit modules
visually in the tool → export → server picks them up automatically.

Port of tools/dungeon-wfc/src/engine/presets.js to Python.
All modules are 8×8 tiles.  Edge patterns determine socket compatibility.

Socket types (8-char patterns derived from edge tiles):
  Wall:     WWWWWWWW  (solid wall — no connection)
  Standard: WWOOOOWW  (centered 4-wide opening — corridors & room entrances)
  Narrow:   WWWOOWWW  (centered 2-wide opening — tight passages & side doors)
  Interior: WOOOOOOW  (6-wide opening — grand multi-module room joins)

Tile types: W=wall, F=floor, D=door, C=corridor, S=spawn, X=chest, E=enemy, B=boss
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── JSON library path ─────────────────────────────────────────────────
# Resolved relative to the server/ directory (two levels up from this file).
_THIS_DIR = Path(__file__).resolve().parent
_SERVER_ROOT = _THIS_DIR.parent.parent.parent          # server/
_LIBRARY_JSON = _SERVER_ROOT / "configs" / "wfc-modules" / "library.json"

# Required fields every module must have
_REQUIRED_MODULE_FIELDS = frozenset([
    "id", "name", "purpose", "contentRole",
    "width", "height", "weight", "allowRotation",
    "spawnSlots", "maxEnemies", "maxChests",
    "canBeBoss", "canBeSpawn", "tiles",
])


W, F, D, C, S, X, E, B = "W", "F", "D", "C", "S", "X", "E", "B"


_BUILTIN_MODULES: list[dict] = [
    # ═══════════════════════════════════════════════════════
    # FILLER
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_solid",
        "name": "Solid Wall",
        "purpose": "empty",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 3.0,
        "allowRotation": False,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # CORRIDORS — standard 4-wide (socket WWOOOOWW)
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_corridor_h",
        "name": "Corridor Straight",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 2.0,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_corridor_l",
        "name": "Corridor L-Turn",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 1.5,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,W,W],
            [F,F,F,F,F,F,W,W],
            [F,F,F,F,F,F,W,W],
            [F,F,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_corridor_t",
        "name": "Corridor T-Junction",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 1.0,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,F,F],
            [W,W,F,F,F,F,F,F],
            [W,W,F,F,F,F,F,F],
            [W,W,F,F,F,F,F,F],
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_corridor_cross",
        "name": "Corridor Crossroads",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.5,
        "allowRotation": False,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # ROOMS — flexible, decorator assigns content
    # Interior floor area: 6×6 = 36 tiles (positions 1-6)
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_room_dead_end",
        "name": "Dead End Room",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 1.0,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 2, "types": ["enemy", "loot", "boss"]},
            {"x": 4, "y": 2, "types": ["enemy", "loot"]},
            {"x": 1, "y": 4, "types": ["enemy", "loot"]},
            {"x": 6, "y": 4, "types": ["enemy", "loot"]},
            {"x": 2, "y": 5, "types": ["enemy", "loot"]},
            {"x": 5, "y": 5, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_straight",
        "name": "Room Passthrough",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 1.2,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 2, "types": ["enemy", "loot"]},
            {"x": 4, "y": 2, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot"]},
            {"x": 6, "y": 5, "types": ["enemy", "loot"]},
            {"x": 3, "y": 6, "types": ["enemy", "loot", "boss"]},
            {"x": 4, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_corner",
        "name": "Room Corner",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 1.0,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot"]},
            {"x": 6, "y": 5, "types": ["enemy", "loot"]},
            {"x": 2, "y": 6, "types": ["enemy", "loot"]},
            {"x": 5, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_three",
        "name": "Room Three-Way",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.8,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot"]},
            {"x": 6, "y": 5, "types": ["enemy", "loot"]},
            {"x": 2, "y": 6, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_hub",
        "name": "Room Hub",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.4,
        "allowRotation": False,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 4, "y": 4, "types": ["enemy", "loot", "boss"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
            {"x": 2, "y": 2, "types": ["enemy", "loot"]},
            {"x": 5, "y": 5, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # SPECIAL PURPOSE ROOMS — fixed content
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_spawn_room",
        "name": "Spawn Room",
        "purpose": "spawn",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 0.3,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,S,S,S,S,S,S,W],
            [W,S,S,S,S,S,S,W],
            [W,S,S,F,F,S,S,W],
            [W,S,F,F,F,F,S,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_enemy_room",
        "name": "Enemy Den",
        "purpose": "enemy",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 1.5,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,E,F,F,F,W],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,E,F,F,F,E,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,E,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_enemy_room_2",
        "name": "Skeleton Hall",
        "purpose": "enemy",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 1.2,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,E,F,F,E,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,E,F,F,E,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_loot_room",
        "name": "Treasury",
        "purpose": "loot",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 0.5,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,X,F,F,X,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [W,F,X,F,F,X,F,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_boss_room",
        "name": "Boss Chamber",
        "purpose": "boss",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 0.2,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,B,B,F,F,W],
            [W,F,F,B,B,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # DOORED CORRIDOR (doors disabled — tiles replaced with C)
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_door_corridor_h",
        "name": "Doored Corridor",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.8,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,C,C,F,F,F],
            [F,F,F,C,C,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # MULTI-MODULE ROOMS — Grand / Large Room Pieces
    # Interior join socket: WOOOOOOW (6-wide opening)
    # ═══════════════════════════════════════════════════════

    # ─── 2-Module Room Pieces ─────────────────────────────
    {
        "id": "preset_grand_hall",
        "name": "Grand Hall",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.5,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 4, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot"]},
            {"x": 4, "y": 6, "types": ["enemy", "loot", "boss"]},
            {"x": 2, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_grand_hall_pillared",
        "name": "Grand Hall Pillared",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.4,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 4, "types": ["enemy", "loot"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,W,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,W,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_grand_end",
        "name": "Grand End",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.4,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 5, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 2, "y": 3, "types": ["enemy", "loot"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 5, "types": ["enemy", "loot"]},
            {"x": 3, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ─── 4-Module Room Corners (2×2 Grand Rooms) ─────────
    {
        "id": "preset_grand_corner_closed",
        "name": "Grand Corner Closed",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.3,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot"]},
            {"x": 5, "y": 5, "types": ["enemy", "loot", "boss"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
        ],
    },
    {
        "id": "preset_grand_corner_open",
        "name": "Grand Corner Open",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.4,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 5, "types": ["enemy", "loot"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
        ],
    },
    {
        "id": "preset_grand_corner_double",
        "name": "Grand Corner Double",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.3,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 5, "types": ["enemy", "loot"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 5, "maxChests": 3,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
        ],
    },
    {
        "id": "preset_grand_corner_pillared",
        "name": "Grand Corner Pillared",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.35,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot", "boss"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,W,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
        ],
    },

    # ─── Special Purpose Grand Rooms — fixed ──────────────
    {
        "id": "preset_grand_enemy_den",
        "name": "Grand Enemy Den",
        "purpose": "enemy",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 0.4,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,E,F,F,F,F,E,F],
            [F,F,F,F,F,F,F,F],
            [F,F,E,F,F,F,F,F],
            [F,F,F,F,F,E,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,E,F,F,F],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_grand_boss_arena",
        "name": "Grand Boss Arena",
        "purpose": "boss",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 0.1,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,B,B,F,F,F],
            [W,F,F,B,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
        ],
    },
    {
        "id": "preset_grand_treasury",
        "name": "Grand Treasury",
        "purpose": "loot",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 0.2,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,X,F,F,X,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,X,F,F,X,F,F,F],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_grand_spawn",
        "name": "Grand Spawn Hall",
        "purpose": "spawn",
        "contentRole": "fixed",
        "width": 8, "height": 8,
        "weight": 0.15,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,S,S,S,S,S,S,F],
            [F,S,S,S,S,S,S,F],
            [F,S,S,F,F,S,S,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ─── 3×3+ Room Interior Pieces — structural ──────────
    {
        "id": "preset_grand_center",
        "name": "Grand Center",
        "purpose": "empty",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.2,
        "allowRotation": False,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
        ],
    },
    {
        "id": "preset_grand_edge",
        "name": "Grand Edge",
        "purpose": "empty",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.25,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # NARROW CORRIDORS — 2-wide passages (socket: WWWOOWWW)
    # Creates tight squeeze corridors, ambush chokepoints,
    # and secret passages.
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_narrow_corridor_h",
        "name": "Narrow Corridor Straight",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 1.2,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_narrow_corridor_l",
        "name": "Narrow Corridor L-Turn",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.9,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,W,W,W],
            [F,F,F,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
        ],
    },
    {
        "id": "preset_narrow_corridor_t",
        "name": "Narrow Corridor T-Junction",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.6,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,F,F,F],
            [W,W,W,F,F,F,F,F],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
        ],
    },
    {
        "id": "preset_narrow_crossroads",
        "name": "Narrow Crossroads",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.3,
        "allowRotation": False,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
        ],
    },
    {
        "id": "preset_narrow_door_corridor",
        "name": "Narrow Doored Corridor",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.5,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,C,C,F,F,F],
            [F,F,F,C,C,F,F,F],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # TRANSITION MODULES — bridge different socket widths
    # Narrow↔Standard and Standard↔Wide (Grand) connectors.
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_narrow_to_standard",
        "name": "Narrow-to-Standard Widener",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 1.0,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [W,W,W,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,W,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_standard_to_wide",
        "name": "Standard-to-Wide Vestibule",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.6,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # ASYMMETRIC / MIXED-SOCKET ROOMS
    # Rooms with different socket types per edge, creating
    # varied spatial rhythm (main entrance vs side passage).
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_room_alcove",
        "name": "Alcove Room",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.8,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot"]},
            {"x": 6, "y": 5, "types": ["enemy", "loot"]},
            {"x": 3, "y": 6, "types": ["enemy", "loot"]},
            {"x": 5, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_side_passage",
        "name": "Side Passage Room",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.7,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot"]},
            {"x": 6, "y": 5, "types": ["enemy", "loot"]},
            {"x": 3, "y": 6, "types": ["enemy", "loot", "boss"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_narrow_dead_end",
        "name": "Narrow Dead End",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.7,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 3, "y": 1, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 4, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot"]},
            {"x": 4, "y": 3, "types": ["enemy", "loot"]},
            {"x": 3, "y": 5, "types": ["enemy", "loot", "boss"]},
            {"x": 4, "y": 5, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 3, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
            [W,W,W,F,F,W,W,W],
        ],
    },
    {
        "id": "preset_room_antechamber",
        "name": "Antechamber",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.5,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 5, "y": 1, "types": ["enemy", "loot"]},
            {"x": 2, "y": 3, "types": ["enemy", "loot"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 3, "y": 5, "types": ["enemy", "loot"]},
            {"x": 6, "y": 5, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_wide_dead_end",
        "name": "Wide Dead End Room",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.4,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 5, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 2, "y": 3, "types": ["enemy", "loot"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot"]},
            {"x": 1, "y": 5, "types": ["enemy", "loot", "boss"]},
            {"x": 5, "y": 5, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,W,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,W],
            [F,F,F,F,F,W,F,W],
            [F,F,F,F,F,F,F,W],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # NEW ROOM SHAPES — interior variety & tactical cover
    # Pillars, ring paths, crypt niches, guard posts, gates.
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_room_pillar",
        "name": "Pillar Room",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.8,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 4, "y": 2, "types": ["enemy", "loot", "boss"]},
            {"x": 1, "y": 4, "types": ["enemy", "loot"]},
            {"x": 6, "y": 5, "types": ["enemy", "loot"]},
            {"x": 3, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,W,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,W,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_ring",
        "name": "Ring Room",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.7,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
            {"x": 2, "y": 3, "types": ["enemy", "loot"]},
            {"x": 5, "y": 4, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": False, "canBeSpawn": True,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,W,W,F,F,W],
            [W,F,F,W,W,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_crypt_niche",
        "name": "Crypt Niche Room",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.6,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 4, "y": 4, "types": ["enemy", "loot"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_room_guard_post",
        "name": "Guard Post",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.6,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot"]},
            {"x": 5, "y": 4, "types": ["enemy", "loot", "boss"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_room_gatehouse",
        "name": "Gatehouse",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.7,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 6, "y": 1, "types": ["enemy", "loot", "spawn"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "boss"]},
            {"x": 4, "y": 4, "types": ["enemy", "loot"]},
            {"x": 1, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy", "loot"]},
        ],
        "maxEnemies": 4, "maxChests": 2,
        "canBeBoss": True, "canBeSpawn": True,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,F,F,F,F,F,F,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,W,W,W,W,W,W,W],
        ],
    },

    # ═══════════════════════════════════════════════════════
    # CORRIDOR VARIANTS — spatial rhythm & chokepoints
    # Zigzags, collapses, and ambush alcoves add texture
    # to corridor-heavy regions of the dungeon.
    # ═══════════════════════════════════════════════════════
    {
        "id": "preset_corridor_ambush",
        "name": "Ambush Corridor",
        "purpose": "empty",
        "contentRole": "flexible",
        "width": 8, "height": 8,
        "weight": 0.8,
        "allowRotation": True,
        "spawnSlots": [
            {"x": 1, "y": 6, "types": ["enemy"]},
            {"x": 3, "y": 6, "types": ["enemy", "loot"]},
            {"x": 4, "y": 6, "types": ["enemy", "loot"]},
            {"x": 6, "y": 6, "types": ["enemy"]},
        ],
        "maxEnemies": 3, "maxChests": 1,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,F,F,F,F,F,F,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
    {
        "id": "preset_corridor_zigzag",
        "name": "Zigzag Corridor",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.7,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
            [W,W,W,F,F,F,W,W],
            [W,W,F,F,F,W,W,W],
            [W,W,W,F,F,F,W,W],
            [W,W,F,F,F,W,W,W],
            [W,W,F,F,F,F,W,W],
            [W,W,F,F,F,F,W,W],
        ],
    },
    {
        "id": "preset_corridor_collapsed",
        "name": "Collapsed Corridor",
        "purpose": "corridor",
        "contentRole": "structural",
        "width": 8, "height": 8,
        "weight": 0.7,
        "allowRotation": True,
        "spawnSlots": [],
        "maxEnemies": 0, "maxChests": 0,
        "canBeBoss": False, "canBeSpawn": False,
        "tiles": [
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
            [F,F,F,F,F,F,F,F],
            [F,F,F,W,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [F,F,F,F,F,F,F,F],
            [W,W,W,W,W,W,W,W],
            [W,W,W,W,W,W,W,W],
        ],
    },
]


# Generation size presets (grid_rows × grid_cols in modules)
_BUILTIN_SIZE_PRESETS = [
    {"name": "Tiny",   "gridRows": 2, "gridCols": 2, "label": "2×2 (16×16 tiles)"},
    {"name": "Small",  "gridRows": 3, "gridCols": 3, "label": "3×3 (24×24 tiles)"},
    {"name": "Medium", "gridRows": 4, "gridCols": 4, "label": "4×4 (32×32 tiles)"},
    {"name": "Large",  "gridRows": 5, "gridCols": 5, "label": "5×5 (40×40 tiles)"},
]


# ─── JSON Library Loading ──────────────────────────────────────────────

def _validate_module(mod: dict) -> bool:
    """Return True if *mod* has all required fields and valid tiles."""
    if not isinstance(mod, dict):
        return False
    missing = _REQUIRED_MODULE_FIELDS - mod.keys()
    if missing:
        logger.warning("Module '%s' missing fields: %s", mod.get("id", "?"), missing)
        return False
    tiles = mod.get("tiles")
    if not isinstance(tiles, list) or len(tiles) == 0:
        return False
    return True


def _load_library_json(path: Path | str | None = None) -> dict | None:
    """Load and validate the canonical JSON module library.

    Args:
        path: Override path for testing.  Defaults to ``_LIBRARY_JSON``.

    Returns:
        The parsed library dict, or ``None`` if the file is missing or invalid.
    """
    p = Path(path) if path else _LIBRARY_JSON
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "modules" not in data:
            logger.warning("library.json missing 'modules' key — ignoring")
            return None
        version = data.get("version", 1)
        if version < 2:
            logger.warning("library.json version %s < 2 — ignoring", version)
            return None
        modules = data["modules"]
        if not isinstance(modules, list) or len(modules) == 0:
            logger.warning("library.json has empty modules list — ignoring")
            return None
        # Validate every module
        valid = [m for m in modules if _validate_module(m)]
        if len(valid) < len(modules):
            logger.warning(
                "library.json: %d/%d modules valid (skipped %d invalid)",
                len(valid), len(modules), len(modules) - len(valid),
            )
        if len(valid) == 0:
            return None
        data["modules"] = valid
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load library.json: %s", exc)
        return None


def _export_library_json(
    modules: list[dict],
    size_presets: list[dict] | None = None,
    path: Path | str | None = None,
) -> Path:
    """Export modules to the canonical JSON library format.

    Args:
        modules: List of module dicts (same shape as ``_BUILTIN_MODULES``).
        size_presets: Optional size presets to include.
        path: Override path for testing.  Defaults to ``_LIBRARY_JSON``.

    Returns:
        The ``Path`` the file was written to.
    """
    p = Path(path) if path else _LIBRARY_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "version": 2,
        "module_size": 8,
        "generated_from": "server/app/core/wfc/presets.py",
        "modules": modules,
    }
    if size_presets is not None:
        data["size_presets"] = size_presets
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Exported %d modules to %s", len(modules), p)
    return p


# ─── Public API ─────────────────────────────────────────────────────────

# Module source tracking — set after first load
_loaded_from_json: bool = False


def get_preset_modules(json_path: Path | str | None = None) -> list[dict]:
    """Return a deep-copy of the module library.

    Loads from ``library.json`` if it exists and is valid, otherwise falls
    back to the hardcoded ``_BUILTIN_MODULES``.

    Args:
        json_path: Override path for testing.  ``None`` uses the default.

    Returns:
        A fresh deep-copy of the module list (safe to mutate).
    """
    global _loaded_from_json
    lib = _load_library_json(json_path)
    if lib is not None:
        _loaded_from_json = True
        logger.debug("Loaded %d modules from library.json", len(lib["modules"]))
        return copy.deepcopy(lib["modules"])
    _loaded_from_json = False
    return copy.deepcopy(_BUILTIN_MODULES)


def get_size_presets(json_path: Path | str | None = None) -> list[dict]:
    """Return size presets from library.json or the builtin defaults."""
    lib = _load_library_json(json_path)
    if lib is not None and "size_presets" in lib:
        return copy.deepcopy(lib["size_presets"])
    return copy.deepcopy(_BUILTIN_SIZE_PRESETS)


def is_loaded_from_json() -> bool:
    """Return True if the last ``get_preset_modules()`` call used library.json."""
    return _loaded_from_json


def export_builtin_to_json(path: Path | str | None = None) -> Path:
    """Export the hardcoded builtin modules to a JSON library file.

    Useful for bootstrapping library.json or re-exporting after editing
    the Python source.
    """
    return _export_library_json(_BUILTIN_MODULES, _BUILTIN_SIZE_PRESETS, path)


# Backwards-compatible aliases
PRESET_MODULES = _BUILTIN_MODULES
SIZE_PRESETS = _BUILTIN_SIZE_PRESETS

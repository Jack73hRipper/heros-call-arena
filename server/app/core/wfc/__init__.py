"""
WFC Dungeon Generation Package

Server-side port of the WFC Dungeon Lab tool for runtime procedural
dungeon generation. Supports multi-floor dungeon runs with scaling
difficulty and deterministic seeded generation.

Modules:
    module_utils  — Module data structures, socket derivation, rotation
    wfc_engine    — Wave Function Collapse core algorithm
    connectivity  — Flood-fill validation, corridor stitching
    room_decorator — Post-generation content assignment
    map_exporter  — Convert WFC output to game-compatible map dict
    dungeon_generator — High-level generation API
    presets       — Built-in 29 preset module library
"""

from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig, validate_enemy_types
from app.core.wfc.wfc_engine import run_wfc
from app.core.wfc.room_decorator import decorate_rooms
from app.core.wfc.map_exporter import export_to_game_map
from app.core.wfc.presets import get_preset_modules

__all__ = [
    "generate_dungeon_floor",
    "FloorConfig",
    "validate_enemy_types",
    "run_wfc",
    "decorate_rooms",
    "export_to_game_map",
    "get_preset_modules",
]

"""
Map Loader — Reads map JSON configs and provides grid data.

Supports both file-based maps (loaded from server/configs/maps/*.json)
and runtime-generated maps (WFC procedural dungeons stored in memory).
"""

from __future__ import annotations

import json
from pathlib import Path


_maps_dir = Path(__file__).resolve().parent.parent.parent / "configs" / "maps"
_loaded_maps: dict[str, dict] = {}

# Runtime-generated maps keyed by match_id or synthetic map_id (e.g. "wfc_<match_id>")
_runtime_maps: dict[str, dict] = {}


def register_runtime_map(map_id: str, map_data: dict) -> None:
    """Register a runtime-generated map (e.g. WFC dungeon) for use by all accessors.

    The map_data dict must follow the same format as static JSON map configs:
    width, height, tiles, tile_legend, spawn_points, rooms, doors, chests, etc.
    """
    _runtime_maps[map_id] = map_data


def unregister_runtime_map(map_id: str) -> None:
    """Remove a runtime-generated map (call on match cleanup)."""
    _runtime_maps.pop(map_id, None)


def load_map(map_id: str) -> dict:
    """Load a map config by ID. Returns grid dimensions, spawn points, obstacles.

    Checks runtime-generated maps first, then static file cache, then disk.
    """
    # Check runtime maps first (WFC procedural dungeons)
    if map_id in _runtime_maps:
        return _runtime_maps[map_id]

    if map_id in _loaded_maps:
        return _loaded_maps[map_id]

    map_file = _maps_dir / f"{map_id}.json"
    if not map_file.exists():
        raise FileNotFoundError(f"Map config not found: {map_file}")

    with open(map_file, "r") as f:
        data = json.load(f)

    _loaded_maps[map_id] = data
    return data


def get_obstacles(map_id: str) -> set[tuple[int, int]]:
    """Return set of impassable (x, y) positions for a map.

    For dungeon maps with a `tiles` grid, obstacles are generated from wall (W)
    and door (D) tiles.  Closed doors block movement until opened (4B-2).
    For arena maps, falls back to the legacy `obstacles` array.
    """
    data = load_map(map_id)

    # Dungeon maps: derive obstacles from tile grid
    tiles = data.get("tiles")
    if tiles:
        legend = data.get("tile_legend", {})
        # Invert legend: tile char -> type name
        wall_chars = {ch for ch, ttype in legend.items() if ttype == "wall"}
        door_chars = {ch for ch, ttype in legend.items() if ttype == "door"}
        blocking = wall_chars | door_chars
        obstacles = set()
        for y, row in enumerate(tiles):
            for x, ch in enumerate(row):
                if ch in blocking:
                    obstacles.add((x, y))
        return obstacles

    # Arena maps: legacy obstacles array
    obstacles = set()
    for obs in data.get("obstacles", []):
        obstacles.add((obs["x"], obs["y"]))
    return obstacles


def get_obstacles_with_door_states(
    map_id: str,
    door_states: dict[str, str] | None = None,
) -> set[tuple[int, int]]:
    """Return obstacles for a map, honouring live door states.

    Open doors are removed from the obstacle set. If *door_states* is None
    (arena maps), delegates to ``get_obstacles()`` directly.
    """
    obstacles = get_obstacles(map_id)
    if door_states is None:
        return obstacles

    # Remove open doors from obstacles
    for key, state in door_states.items():
        if state == "open":
            parts = key.split(",")
            if len(parts) == 2:
                obstacles.discard((int(parts[0]), int(parts[1])))
    return obstacles


def get_spawn_points(map_id: str) -> list[tuple[int, int]]:
    """Return ordered list of spawn point coordinates (legacy).

    Returns an empty list if the map file doesn't exist (e.g. procedural
    dungeons that haven't been generated yet).
    """
    try:
        data = load_map(map_id)
    except FileNotFoundError:
        return []
    return [(sp["x"], sp["y"]) for sp in data.get("spawn_points", [])]


def get_spawn_zones(map_id: str) -> dict[str, dict]:
    """Return team spawn zones from map config.

    Returns dict like {"a": {"x_min": 0, "y_min": 0, "x_max": 3, "y_max": 3}, ...}.
    Returns empty dict if the map has no spawn_zones defined (spawn.py has fallback).
    """
    data = load_map(map_id)
    return data.get("spawn_zones", {})


def get_ffa_points(map_id: str) -> list[tuple[int, int]]:
    """Return FFA spawn point coordinates from map config.

    Falls back to legacy spawn_points if ffa_points is not defined.
    """
    data = load_map(map_id)
    points = data.get("ffa_points", [])
    if not points:
        points = data.get("spawn_points", [])
    return [(p["x"], p["y"]) for p in points]


def get_map_dimensions(map_id: str) -> tuple[int, int]:
    """Return (width, height) for a map."""
    data = load_map(map_id)
    return data.get("width", 15), data.get("height", 15)


# ---------- Dungeon-specific helpers (return empty for arena maps) ----------


def get_doors(map_id: str) -> list[dict]:
    """Return list of door definitions: [{x, y, state}, ...].

    Returns empty list if the map has no doors (arena maps).
    """
    data = load_map(map_id)
    return data.get("doors", [])


def get_chests(map_id: str) -> list[dict]:
    """Return list of chest positions: [{x, y}, ...].

    Returns empty list if the map has no chests (arena maps).
    """
    data = load_map(map_id)
    return data.get("chests", [])


def get_stairs(map_id: str) -> list[dict]:
    """Return list of staircase positions: [{x, y}, ...].

    Returns empty list if the map has no stairs (arena maps, floor 1 with no stairs yet).
    """
    data = load_map(map_id)
    return data.get("stairs", [])


def get_room_definitions(map_id: str) -> list[dict]:
    """Return list of room definitions from a dungeon map.

    Each room has: id, name, purpose, bounds, and optionally enemy_spawns.
    Returns empty list for arena maps.
    """
    data = load_map(map_id)
    return data.get("rooms", [])


def get_tiles(map_id: str) -> list[list[str]] | None:
    """Return the tile grid for a dungeon map, or None for arena maps."""
    data = load_map(map_id)
    return data.get("tiles")


def is_dungeon_map(map_id: str) -> bool:
    """Check if a map is a dungeon-style map (has map_type='dungeon' or 'pvpve').

    Returns False if the map file doesn't exist (e.g. procedural dungeons
    that haven't been generated yet — match_type check is sufficient).
    """
    try:
        data = load_map(map_id)
    except FileNotFoundError:
        return False
    return data.get("map_type") in ("dungeon", "pvpve")


def get_wave_spawner_config(map_id: str) -> dict | None:
    """Return wave_spawner config from a map, or None if the map has no waves.

    Wave spawner config contains:
      - spawner_room_id: str — room where enemies appear
      - spawn_points: [{x, y}, ...] — positions within the spawner room
      - waves: [{wave_number, name, enemies: [{enemy_type, is_boss?}, ...]}, ...]
    """
    data = load_map(map_id)
    return data.get("wave_spawner")

"""
door_placer.py — Post-decoration door insertion pass.

Scans module boundaries in the assembled tile map and inserts door
separators at room entrances.  Each qualifying opening is evaluated
independently — some get a wall separator with a 1-tile door gap
(creating a tactical chokepoint), while others stay wide open.

Runs between ``decorate_rooms()`` and ``export_to_game_map()`` in
the generation pipeline so it can reference decorated room roles
(spawn rooms are never doored, boss rooms have higher door chance).

Design goals:
  - Rooms WITH doors feel like defensible chokepoints
  - Rooms WITHOUT doors feel spacious and open
  - Socket compatibility is not affected (this runs post-WFC)
  - Deterministic via seeded PRNG
  - Per-style tuning via ``doorChance`` in dungeon_styles
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.wfc.module_utils import MODULE_SIZE

logger = logging.getLogger(__name__)

# ─── Default door placement settings ──────────────────────────────────

DEFAULT_DOOR_SETTINGS: dict[str, Any] = {
    "doorChance": 0.45,           # Base probability any entrance gets a door
    "bossRoomDoorChance": 0.70,   # Higher chance for boss room entrances
    "spawnRoomDoorChance": 0.0,   # Never door off spawn — frustrating
    "narrowDoorChance": 0.55,     # Slightly higher for narrow (2-wide) openings
    "interiorDoorChance": 0.0,    # Never door grand interior joins (multi-module rooms)
    "corridorOnlyDoorChance": 0.15,  # Low chance for corridor↔corridor boundaries
    "minOpeningsForDoor": 1,      # Minimum openings a room must have to get any doors
}


def _create_rng(seed: int):
    """Seeded PRNG (mulberry32)."""
    s = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((s ^ (s >> 15)) * (1 | s)) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF) ^ t
        t = t & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


# ─── Boundary scanning ────────────────────────────────────────────────


def _classify_module(variant: dict | None, decoration_lookup: dict[str, str]) -> str:
    """Classify a module cell for door-chance lookup.

    Returns one of: 'spawn', 'boss', 'room', 'corridor', 'structural'.
    """
    if variant is None:
        return "structural"

    purpose = variant.get("purpose", "empty")
    content_role = variant.get("contentRole", "structural")

    # Check decorator assignment (overrides structural purpose)
    # decoration_lookup maps "row,col" → assignedRole
    # We'll check this from the caller side — this function uses variant data only.

    if purpose == "spawn":
        return "spawn"
    if purpose == "boss":
        return "boss"
    if purpose == "corridor":
        return "corridor"
    if content_role in ("flexible", "fixed"):
        return "room"
    return "structural"


def _find_open_runs(edge_tiles: list[str]) -> list[tuple[int, int]]:
    """Find contiguous runs of open tiles in an edge.

    Returns list of (start_index, length) for each run of non-wall tiles.
    """
    runs = []
    i = 0
    n = len(edge_tiles)
    while i < n:
        if edge_tiles[i] != "W":
            start = i
            while i < n and edge_tiles[i] != "W":
                i += 1
            runs.append((start, i - start))
        else:
            i += 1
    return runs


def _scan_boundaries(
    tile_map: list[list[str]],
    grid: list[list[dict]],
    variants: list[dict],
    decoration_lookup: dict[str, str],
) -> list[dict]:
    """Scan all module boundaries and collect door-eligible openings.

    Returns a list of boundary dicts, each containing:
      - direction: 'horizontal' or 'vertical'
      - cell_a: (grid_row, grid_col) of first module
      - cell_b: (grid_row, grid_col) of second module
      - role_a, role_b: classified roles ('room', 'corridor', 'boss', etc.)
      - openings: list of open tile runs [{start, length, tiles: [(x,y)...]}]
      - socket_width: total open tiles at this boundary
    """
    grid_rows = len(grid)
    grid_cols = len(grid[0]) if grid_rows > 0 else 0
    height = len(tile_map)
    width = len(tile_map[0]) if height > 0 else 0

    boundaries = []

    def _get_variant(gr: int, gc: int) -> dict | None:
        cell = grid[gr][gc]
        vi = cell.get("chosenVariant")
        if vi is None:
            return None
        return variants[vi] if vi < len(variants) else None

    def _get_role(gr: int, gc: int, variant: dict | None) -> str:
        key = f"{gr},{gc}"
        dec_role = decoration_lookup.get(key)
        if dec_role == "spawn":
            return "spawn"
        if dec_role == "boss":
            return "boss"
        if variant is None:
            return "structural"
        return _classify_module(variant, decoration_lookup)

    # Horizontal boundaries (between vertically adjacent modules)
    # The boundary is at the bottom edge of cell_a / top edge of cell_b
    for gr in range(grid_rows - 1):
        for gc in range(grid_cols):
            var_a = _get_variant(gr, gc)
            var_b = _get_variant(gr + 1, gc)
            role_a = _get_role(gr, gc, var_a)
            role_b = _get_role(gr + 1, gc, var_b)

            # The boundary tiles: last row of module A, first row of module B
            boundary_y_a = gr * MODULE_SIZE + (MODULE_SIZE - 1)
            boundary_y_b = (gr + 1) * MODULE_SIZE
            start_x = gc * MODULE_SIZE

            if boundary_y_a >= height or boundary_y_b >= height:
                continue

            # Read the edge tiles from module A's south edge
            edge_tiles = []
            for dx in range(MODULE_SIZE):
                tx = start_x + dx
                if tx < width:
                    edge_tiles.append(tile_map[boundary_y_a][tx])
                else:
                    edge_tiles.append("W")

            runs = _find_open_runs(edge_tiles)
            if not runs:
                continue

            openings = []
            for run_start, run_len in runs:
                tiles = []
                for dx in range(run_len):
                    tx = start_x + run_start + dx
                    # Use the row between the two modules — module A's last row
                    tiles.append((tx, boundary_y_a))
                openings.append({
                    "start": run_start,
                    "length": run_len,
                    "tiles": tiles,
                    "row_a": boundary_y_a,
                    "row_b": boundary_y_b,
                })

            socket_width = sum(r[1] for r in runs)
            boundaries.append({
                "direction": "horizontal",
                "cell_a": (gr, gc),
                "cell_b": (gr + 1, gc),
                "role_a": role_a,
                "role_b": role_b,
                "openings": openings,
                "socket_width": socket_width,
            })

    # Vertical boundaries (between horizontally adjacent modules)
    # The boundary is at the right edge of cell_a / left edge of cell_b
    for gr in range(grid_rows):
        for gc in range(grid_cols - 1):
            var_a = _get_variant(gr, gc)
            var_b = _get_variant(gr, gc + 1)
            role_a = _get_role(gr, gc, var_a)
            role_b = _get_role(gr, gc + 1, var_b)

            boundary_x_a = gc * MODULE_SIZE + (MODULE_SIZE - 1)
            boundary_x_b = (gc + 1) * MODULE_SIZE
            start_y = gr * MODULE_SIZE

            if boundary_x_a >= width or boundary_x_b >= width:
                continue

            # Read the edge tiles from module A's east edge
            edge_tiles = []
            for dy in range(MODULE_SIZE):
                ty = start_y + dy
                if ty < height:
                    edge_tiles.append(tile_map[ty][boundary_x_a])
                else:
                    edge_tiles.append("W")

            runs = _find_open_runs(edge_tiles)
            if not runs:
                continue

            openings = []
            for run_start, run_len in runs:
                tiles = []
                for dy in range(run_len):
                    ty = start_y + run_start + dy
                    tiles.append((boundary_x_a, ty))
                openings.append({
                    "start": run_start,
                    "length": run_len,
                    "tiles": tiles,
                    "col_a": boundary_x_a,
                    "col_b": boundary_x_b,
                })

            socket_width = sum(r[1] for r in runs)
            boundaries.append({
                "direction": "vertical",
                "cell_a": (gr, gc),
                "cell_b": (gr, gc + 1),
                "role_a": role_a,
                "role_b": role_b,
                "openings": openings,
                "socket_width": socket_width,
            })

    return boundaries


# ─── Door placement logic ─────────────────────────────────────────────


def _get_door_chance(
    boundary: dict,
    settings: dict[str, Any],
) -> float:
    """Determine the door probability for a boundary based on room roles.

    Rules (checked in priority order):
      1. If either side is a spawn room → spawnRoomDoorChance (default 0)
      2. If it's a grand interior join (6+ wide) → interiorDoorChance (default 0)
      3. If either side is a boss room → bossRoomDoorChance
      4. If both sides are corridors → corridorOnlyDoorChance
      5. If the opening is narrow (2 wide) → narrowDoorChance
      6. Otherwise → doorChance (base)
    """
    role_a = boundary["role_a"]
    role_b = boundary["role_b"]
    sw = boundary["socket_width"]

    # Never door spawn rooms
    if role_a == "spawn" or role_b == "spawn":
        return settings.get("spawnRoomDoorChance", 0.0)

    # Never door structural walls (shouldn't have openings, but safety check)
    if role_a == "structural" or role_b == "structural":
        return 0.0

    # Grand interior joins (6+ tiles open) — these are multi-module rooms
    if sw >= 6:
        return settings.get("interiorDoorChance", 0.0)

    # Boss rooms get higher door chance
    if role_a == "boss" or role_b == "boss":
        return settings.get("bossRoomDoorChance", 0.70)

    # Corridor-to-corridor: low chance
    if role_a == "corridor" and role_b == "corridor":
        return settings.get("corridorOnlyDoorChance", 0.15)

    # Narrow openings (2-wide)
    if sw <= 2:
        return settings.get("narrowDoorChance", 0.55)

    # Default base chance
    return settings.get("doorChance", 0.45)


def _place_door_at_opening(
    tile_map: list[list[str]],
    opening: dict,
    direction: str,
    rng,
) -> dict | None:
    """Place a wall separator + 1-tile door gap at an opening.

    Fills the opening width with walls except for a single tile
    positioned near the center, which becomes 'D' (door).

    Returns a dict describing the placed door, or None if placement
    is not possible (opening too small).
    """
    tiles = opening["tiles"]
    length = opening["length"]

    if length < 1:
        return None

    # For single-tile openings, just make it a door
    if length == 1:
        dx, dy = tiles[0]
        tile_map[dy][dx] = "D"
        return {"x": dx, "y": dy}

    # Pick the door position — center of the opening, with slight random offset
    center = length // 2
    # Allow the door to be placed at center or center-1 for variety
    if length >= 3:
        offset = -1 if rng() < 0.5 else 0
        door_idx = max(0, min(length - 1, center + offset))
    else:
        # Length == 2: pick one of the two spots
        door_idx = 0 if rng() < 0.5 else 1

    # Fill all opening tiles with walls, except the door position
    door_x, door_y = None, None
    for i, (tx, ty) in enumerate(tiles):
        if i == door_idx:
            tile_map[ty][tx] = "D"
            door_x, door_y = tx, ty
        else:
            tile_map[ty][tx] = "W"

    if door_x is None:
        return None

    return {"x": door_x, "y": door_y}


# ─── Main entry point ─────────────────────────────────────────────────


def insert_room_doors(
    tile_map: list[list[str]],
    grid: list[list[dict]],
    variants: list[dict],
    seed: int = 42,
    settings: dict[str, Any] | None = None,
    decoration_result: dict | None = None,
) -> dict:
    """Insert door separators at module boundaries in the tile map.

    This mutates ``tile_map`` in-place, inserting 'W' (wall) and 'D'
    (door) tiles at eligible module boundary openings.

    Args:
        tile_map: The decorated 2D tile map (mutated in-place).
        grid: WFC grid (rows x cols of cells with chosenVariant).
        variants: Expanded variant list from WFC.
        seed: RNG seed for deterministic results.
        settings: Door placement settings (merged with defaults).
        decoration_result: Output from decorate_rooms() — used to look up
            room roles (spawn, boss, etc.) for per-room door chance.

    Returns:
        dict with:
          - doors: list of {"x", "y"} for each placed door
          - stats: {boundaries_scanned, doors_placed, openings_skipped}
    """
    config = {**DEFAULT_DOOR_SETTINGS, **(settings or {})}
    rng = _create_rng(seed + 99991)  # Offset from WFC/decorator seeds

    # Build decoration lookup: "row,col" → assignedRole
    decoration_lookup: dict[str, str] = {}
    if decoration_result:
        for dr in decoration_result.get("decoratedRooms", []):
            key = f"{dr['gridRow']},{dr['gridCol']}"
            decoration_lookup[key] = dr.get("assignedRole", "")
        # Also check fixed rooms from the variant data
        grid_rows_count = len(grid)
        grid_cols_count = len(grid[0]) if grid_rows_count > 0 else 0
        for gr in range(grid_rows_count):
            for gc in range(grid_cols_count):
                key = f"{gr},{gc}"
                if key in decoration_lookup:
                    continue
                cell = grid[gr][gc]
                vi = cell.get("chosenVariant")
                if vi is not None and vi < len(variants):
                    purpose = variants[vi].get("purpose", "empty")
                    if purpose in ("spawn", "boss"):
                        decoration_lookup[key] = purpose

    # Scan all module boundaries for openings
    boundaries = _scan_boundaries(tile_map, grid, variants, decoration_lookup)

    doors_placed = []
    openings_skipped = 0

    for boundary in boundaries:
        chance = _get_door_chance(boundary, config)

        if chance <= 0:
            openings_skipped += len(boundary["openings"])
            continue

        # Roll once per boundary (all openings at this boundary share the same fate)
        if rng() >= chance:
            openings_skipped += len(boundary["openings"])
            continue

        # Place doors at each opening in this boundary
        for opening in boundary["openings"]:
            result = _place_door_at_opening(
                tile_map, opening, boundary["direction"], rng,
            )
            if result:
                doors_placed.append(result)

    stats = {
        "boundaries_scanned": len(boundaries),
        "doors_placed": len(doors_placed),
        "openings_skipped": openings_skipped,
    }

    logger.info(
        "Door placement: %d boundaries scanned, %d doors placed, %d openings skipped",
        stats["boundaries_scanned"],
        stats["doors_placed"],
        stats["openings_skipped"],
    )

    return {"doors": doors_placed, "stats": stats}

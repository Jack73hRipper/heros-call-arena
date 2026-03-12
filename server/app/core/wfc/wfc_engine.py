"""
wfc_engine.py — Wave Function Collapse core algorithm.

Port of tools/dungeon-wfc/src/engine/wfc.js to Python.
Module-level WFC: each cell in a grid holds one module.
Sockets on adjacent edges must match for modules to be neighbors.
Uses entropy-based collapse with weighted random selection.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from app.core.wfc.module_utils import MODULE_SIZE, expand_modules
from app.core.wfc.connectivity import ensure_connectivity, validate_connectivity


# Direction → opposite direction for socket matching
OPPOSITE = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}

# Direction → row/col offset
OFFSETS = {
    "north": (-1, 0),
    "south": (1, 0),
    "east": (0, 1),
    "west": (0, -1),
}

DIRECTIONS = ("north", "south", "east", "west")


def _create_rng(seed: int):
    """Seeded pseudo-random number generator (mulberry32).

    Deterministic results for a given seed. Returns a callable
    that produces floats in [0, 1).
    """
    s = seed & 0xFFFFFFFF  # unsigned 32-bit

    def rng() -> float:
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((s ^ (s >> 15)) * (1 | s)) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF) ^ t
        t = t & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def run_wfc(
    modules: list[dict],
    grid_rows: int,
    grid_cols: int,
    seed: int = 42,
    pinned: dict[str, int] | None = None,
    max_retries: int = 50,
    force_border_walls: bool = True,
    ensure_connected: bool = True,
) -> dict:
    """Run WFC generation.

    Args:
        modules: Raw module library (before expansion).
        grid_rows: Number of module cells vertically.
        grid_cols: Number of module cells horizontally.
        seed: RNG seed for determinism.
        pinned: Map of "row,col" → variant index to pin.
        max_retries: Max restart attempts on contradiction.
        force_border_walls: Force wall sockets on map edges.
        ensure_connected: Carve corridors to connect isolated regions.

    Returns:
        dict with: success, grid, tileMap, steps, retries, variants, connectivity.
    """
    if pinned is None:
        pinned = {}

    variants = expand_modules(modules)

    if not variants:
        return {
            "success": False,
            "grid": None,
            "tileMap": None,
            "steps": [],
            "retries": 0,
            "variants": [],
            "connectivity": None,
            "error": "No modules in library",
        }

    # Precompute adjacency compatibility table
    # compatible[dir][variant_index] = set of compatible neighbor variant indices
    compatible: dict[str, list[set[int]]] = {}
    for dir_ in DIRECTIONS:
        opp = OPPOSITE[dir_]
        dir_compat = []
        for i in range(len(variants)):
            my_socket = variants[i]["sockets"][dir_]
            compat = set()
            for j in range(len(variants)):
                if variants[j]["sockets"][opp] == my_socket:
                    compat.add(j)
            dir_compat.append(compat)
        compatible[dir_] = dir_compat

    # Precompute border-compatible variant sets
    wall_socket = "W" * MODULE_SIZE
    border_variants: dict[str, set[int]] = {}
    for dir_ in DIRECTIONS:
        bv = set()
        for i in range(len(variants)):
            if variants[i]["sockets"][dir_] == wall_socket:
                bv.add(i)
        border_variants[dir_] = bv

    retries = 0

    while retries <= max_retries:
        rng = _create_rng(seed + retries)
        result = _attempt_wfc(
            variants, compatible, grid_rows, grid_cols, rng,
            pinned, force_border_walls, border_variants,
        )

        if result["success"]:
            tile_map = _assemble_to_tile_map(
                result["grid"], variants, grid_rows, grid_cols,
            )

            # Connectivity enforcement
            connectivity = None
            if ensure_connected:
                connectivity = ensure_connectivity(tile_map)
            else:
                validation = validate_connectivity(tile_map)
                connectivity = {
                    "connected": validation["isConnected"],
                    "regionsFound": validation["regionCount"],
                    "corridorsCarved": 0,
                    "regionSizes": validation["regionSizes"],
                }

            return {
                "success": True,
                "grid": result["grid"],
                "tileMap": tile_map,
                "steps": result["steps"],
                "retries": retries,
                "variants": variants,
                "connectivity": connectivity,
            }

        retries += 1

    return {
        "success": False,
        "grid": None,
        "tileMap": None,
        "steps": [],
        "retries": retries,
        "variants": variants,
        "connectivity": None,
        "error": "Max retries exceeded — contradiction",
    }


def _attempt_wfc(
    variants: list[dict],
    compatible: dict[str, list[set[int]]],
    rows: int,
    cols: int,
    rng,
    pinned: dict[str, int],
    force_border_walls: bool,
    border_variants: dict[str, set[int]],
) -> dict:
    """Single WFC attempt. Returns {success, grid, steps} or {success: False}."""
    num_variants = len(variants)
    all_indices = set(range(num_variants))

    # Initialize grid: each cell has a set of possible variant indices
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            row.append({
                "possible": set(all_indices),
                "collapsed": False,
                "chosenVariant": None,
            })
        grid.append(row)

    # Apply border wall constraints
    if force_border_walls:
        for r in range(rows):
            for c in range(cols):
                cell = grid[r][c]
                if r == 0:
                    cell["possible"] &= border_variants["north"]
                if r == rows - 1:
                    cell["possible"] &= border_variants["south"]
                if c == 0:
                    cell["possible"] &= border_variants["west"]
                if c == cols - 1:
                    cell["possible"] &= border_variants["east"]
                if not cell["possible"]:
                    return {"success": False}

    # Apply pinned constraints
    for key, variant_idx in pinned.items():
        parts = key.split(",")
        r, c = int(parts[0]), int(parts[1])
        if 0 <= r < rows and 0 <= c < cols and 0 <= variant_idx < num_variants:
            grid[r][c]["possible"] = {variant_idx}

    # Initial constraint propagation from pinned cells
    for key in pinned:
        parts = key.split(",")
        r, c = int(parts[0]), int(parts[1])
        if not _propagate(grid, r, c, compatible, rows, cols):
            return {"success": False}

    steps = []
    total_cells = rows * cols
    collapsed_count = 0

    # Count already-collapsed cells
    for r in range(rows):
        for c in range(cols):
            cell = grid[r][c]
            if len(cell["possible"]) == 1 and not cell["collapsed"]:
                cell["collapsed"] = True
                cell["chosenVariant"] = next(iter(cell["possible"]))
                collapsed_count += 1

    while collapsed_count < total_cells:
        # Find cell with minimum entropy (fewest possibilities, > 1)
        min_entropy = float("inf")
        candidates = []

        for r in range(rows):
            for c in range(cols):
                cell = grid[r][c]
                if cell["collapsed"]:
                    continue
                entropy = len(cell["possible"])
                if entropy == 0:
                    return {"success": False}  # Contradiction
                if entropy < min_entropy:
                    min_entropy = entropy
                    candidates = [(r, c)]
                elif entropy == min_entropy:
                    candidates.append((r, c))

        if not candidates:
            break

        # Pick random cell among minimum-entropy candidates
        chosen_idx = int(rng() * len(candidates))
        if chosen_idx >= len(candidates):
            chosen_idx = len(candidates) - 1
        chosen_r, chosen_c = candidates[chosen_idx]
        cell = grid[chosen_r][chosen_c]

        # Weighted collapse
        variant_idx = _weighted_pick(list(cell["possible"]), variants, rng)
        cell["possible"] = {variant_idx}
        cell["collapsed"] = True
        cell["chosenVariant"] = variant_idx
        collapsed_count += 1

        steps.append({
            "row": chosen_r,
            "col": chosen_c,
            "variantIdx": variant_idx,
            "name": variants[variant_idx]["sourceName"],
            "rotation": variants[variant_idx]["rotation"],
        })

        # Propagate constraints
        if not _propagate(grid, chosen_r, chosen_c, compatible, rows, cols):
            return {"success": False}

        # Check for newly-determined cells
        for r in range(rows):
            for c in range(cols):
                if not grid[r][c]["collapsed"] and len(grid[r][c]["possible"]) == 1:
                    grid[r][c]["collapsed"] = True
                    grid[r][c]["chosenVariant"] = next(iter(grid[r][c]["possible"]))
                    collapsed_count += 1

    return {"success": True, "grid": grid, "steps": steps}


def _weighted_pick(indices: list[int], variants: list[dict], rng) -> int:
    """Weighted random pick from a set of variant indices."""
    total_weight = sum(variants[idx]["weight"] for idx in indices)
    if total_weight <= 0:
        return indices[-1] if indices else 0

    r = rng() * total_weight
    for idx in indices:
        r -= variants[idx]["weight"]
        if r <= 0:
            return idx
    return indices[-1]


def _propagate(
    grid: list[list[dict]],
    start_r: int,
    start_c: int,
    compatible: dict[str, list[set[int]]],
    rows: int,
    cols: int,
) -> bool:
    """Propagate constraints from a collapsed/changed cell outward (BFS).

    Returns False if a contradiction is found.
    """
    queue = deque([(start_r, start_c)])
    visited = {(start_r, start_c)}

    while queue:
        r, c = queue.popleft()
        cell = grid[r][c]

        for dir_, (dr, dc) in OFFSETS.items():
            nr = r + dr
            nc = c + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue

            neighbor = grid[nr][nc]
            if neighbor["collapsed"]:
                continue

            # Compute the set of variants allowed in the neighbor based on this cell
            allowed_in_neighbor: set[int] = set()
            for my_var in cell["possible"]:
                allowed_in_neighbor |= compatible[dir_][my_var]

            # Intersect with neighbor's current possibilities
            before_size = len(neighbor["possible"])
            neighbor["possible"] &= allowed_in_neighbor

            if not neighbor["possible"]:
                return False  # Contradiction

            # If possibilities were reduced, propagate from this neighbor too
            if len(neighbor["possible"]) < before_size:
                pos = (nr, nc)
                if pos not in visited:
                    visited.add(pos)
                    queue.append(pos)

    return True


def _assemble_to_tile_map(
    grid: list[list[dict]],
    variants: list[dict],
    grid_rows: int,
    grid_cols: int,
) -> list[list[str]]:
    """Assemble the collapsed WFC grid into a full tile map.

    Each module occupies MODULE_SIZE × MODULE_SIZE tiles.
    """
    tile_h = grid_rows * MODULE_SIZE
    tile_w = grid_cols * MODULE_SIZE
    tile_map = [["W"] * tile_w for _ in range(tile_h)]

    for gr in range(grid_rows):
        for gc in range(grid_cols):
            cell = grid[gr][gc]
            if cell["chosenVariant"] is None:
                continue

            variant = variants[cell["chosenVariant"]]
            start_r = gr * MODULE_SIZE
            start_c = gc * MODULE_SIZE

            for lr in range(MODULE_SIZE):
                for lc in range(MODULE_SIZE):
                    tile_map[start_r + lr][start_c + lc] = variant["tiles"][lr][lc]

    return tile_map


def compute_stats(tile_map: list[list[str]] | None) -> dict | None:
    """Compute dungeon statistics from a tile map."""
    if not tile_map:
        return None

    stats = {
        "width": len(tile_map[0]) if tile_map else 0,
        "height": len(tile_map),
        "totalTiles": 0,
        "walls": 0,
        "floors": 0,
        "doors": 0,
        "corridors": 0,
        "spawns": 0,
        "chests": 0,
        "enemySpawns": 0,
        "bossSpawns": 0,
        "floorRatio": 0,
    }

    tile_counts = {
        "W": "walls", "F": "floors", "D": "doors", "C": "corridors",
        "S": "spawns", "X": "chests", "E": "enemySpawns", "B": "bossSpawns",
    }

    for row in tile_map:
        for tile in row:
            stats["totalTiles"] += 1
            key = tile_counts.get(tile)
            if key:
                stats[key] += 1

    open_tiles = (
        stats["floors"] + stats["doors"] + stats["corridors"]
        + stats["spawns"] + stats["chests"] + stats["enemySpawns"]
        + stats["bossSpawns"]
    )
    if stats["totalTiles"] > 0:
        stats["floorRatio"] = round(open_tiles / stats["totalTiles"] * 100, 1)

    return stats

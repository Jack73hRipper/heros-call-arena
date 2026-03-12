"""
room_decorator.py — Post-generation room content decorator.

Port of tools/dungeon-wfc/src/engine/roomDecorator.js to Python.
After WFC assembles the structural dungeon, this pass assigns
gameplay content (enemies, loot, bosses, spawn points) to
"flexible" rooms based on configurable density settings.
"""

from __future__ import annotations

from typing import Any

from app.core.wfc.module_utils import MODULE_SIZE


# Default decorator settings
DEFAULT_DECORATOR_SETTINGS = {
    "enemyDensity": 0.4,
    "lootDensity": 0.25,
    "guaranteeBoss": True,
    "guaranteeSpawn": True,
    "guaranteeStairs": True,
    "emptyRoomChance": 0.2,
    "scatterEnemies": True,
    "scatterChests": True,
}

# PVPVE decorator defaults
_PVPVE_DECORATOR_DEFAULTS = {
    "guaranteeBoss": True,
    "guaranteeSpawn": True,
    "guaranteeStairs": False,
    "enemyDensity": 0.50,
    "lootDensity": 0.50,
    "emptyRoomChance": 0.15,
    "maxEnemies": 4,
    "pvpve_mode": True,
    "pvpve_team_count": 4,
    "pvpve_boss_guards": 3,
    "pvpve_boss_chests": 2,
}

# PVPVE corner mapping: team_key → (target_row_fn, target_col_fn)
# Functions take (max_row, max_col) and return the target grid coordinate
_PVPVE_TEAM_CORNERS = {
    "a": (lambda mr, mc: 0, lambda mr, mc: 0),           # Top-left
    "b": (lambda mr, mc: mr, lambda mr, mc: mc),          # Bottom-right
    "c": (lambda mr, mc: 0, lambda mr, mc: mc),           # Top-right
    "d": (lambda mr, mc: mr, lambda mr, mc: 0),           # Bottom-left
}

# Team activation order based on team count
_PVPVE_TEAM_ORDER = ["a", "b", "c", "d"]

# Difficulty tiers based on Manhattan distance to center
_PVPVE_DIFFICULTY_TIERS = [
    # (max_distance, tier_name, max_enemies, rarity_bias)
    (0, "boss", 5, "super_unique"),
    (1, "elite", 5, "champion"),
    (2, "hard", 4, "rare"),
]
# Anything farther → "normal" tier


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


def _shuffle(arr: list, rng) -> list:
    """Fisher-Yates shuffle in-place using provided RNG."""
    for i in range(len(arr) - 1, 0, -1):
        j = int(rng() * (i + 1))
        if j > i:
            j = i
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def _infer_content_role(variant: dict) -> str:
    """Infer contentRole from a variant if the field is missing."""
    purpose = variant.get("purpose", "empty")

    # Fixed content: baked-in E/X/S/B tiles
    if purpose in ("enemy", "boss", "loot", "spawn"):
        return "fixed"

    # Structural: corridors, solid walls
    if purpose == "corridor":
        return "structural"

    # Check if module has any floor tiles
    tiles = variant.get("tiles", [])
    has_floor = any(t == "F" for row in tiles for t in row)
    if not has_floor:
        return "structural"

    # Grand interior pieces (3+ interior joins)
    sockets = variant.get("sockets", {})
    interior_join = "WOOOOW"
    join_count = sum(1 for d in ("north", "south", "east", "west")
                     if sockets.get(d) == interior_join)
    if join_count >= 3:
        return "structural"

    return "flexible"


def _derive_floor_slots(tiles: list[list[str]]) -> list[dict]:
    """Derive floor slots from a tile grid (fallback when spawnSlots is empty)."""
    slots = []
    if not tiles:
        return slots
    h = len(tiles)
    w = len(tiles[0]) if h > 0 else 0
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if tiles[r][c] == "F":
                slots.append({"x": c, "y": r, "types": ["enemy", "loot", "spawn", "boss"]})
    return slots


def _place_tile(tile_map: list[list[str]], row: int, col: int, tile: str) -> None:
    """Place a tile on the map (only if target is currently floor)."""
    if 0 <= row < len(tile_map) and 0 <= col < len(tile_map[0]):
        if tile_map[row][col] == "F":
            tile_map[row][col] = tile


def _place_emergency_spawns(tile_map: list[list[str]], count: int = 4) -> list[dict]:
    """Place spawn tiles on the first available floor tiles as a last-resort fallback.

    Used when no flexible or fixed spawn rooms exist in the generated dungeon.
    Scans for interior floor tiles (avoiding edges) and converts them to spawn tiles.

    Returns list of placement dicts, or empty list if no floor tiles found.
    """
    placements = []
    height = len(tile_map)
    width = len(tile_map[0]) if height > 0 else 0

    for r in range(1, height - 1):
        for c in range(1, width - 1):
            if tile_map[r][c] == "F":
                tile_map[r][c] = "S"
                placements.append({"x": c, "y": r, "type": "S"})
                if len(placements) >= count:
                    return placements
    return placements


def _place_emergency_stairs(tile_map: list[list[str]]) -> dict | None:
    """Place a staircase tile on a floor tile far from any spawn tiles.

    Last-resort fallback when no flexible room was available for stairs.
    Scans the map for floor tiles, preferring those farthest from spawn tiles.

    Returns a placement dict, or None if no floor tiles found.
    """
    height = len(tile_map)
    width = len(tile_map[0]) if height > 0 else 0

    # Collect spawn positions
    spawn_positions = []
    floor_positions = []
    for r in range(1, height - 1):
        for c in range(1, width - 1):
            if tile_map[r][c] == "S":
                spawn_positions.append((r, c))
            elif tile_map[r][c] == "F":
                floor_positions.append((r, c))

    if not floor_positions:
        return None

    # Pick the floor tile farthest from all spawn tiles
    if spawn_positions:
        best = max(
            floor_positions,
            key=lambda pos: min(
                abs(pos[0] - sr) + abs(pos[1] - sc) for sr, sc in spawn_positions
            ),
        )
    else:
        # No spawns to measure from — use the last floor tile (bottom-right bias)
        best = floor_positions[-1]

    tile_map[best[0]][best[1]] = "T"
    return {"x": best[1], "y": best[0], "type": "T"}


# ─── PVPVE Layout Helpers ─────────────────────────────────────────────


def _get_active_teams(team_count: int) -> list[str]:
    """Return the list of active team keys for the given team count."""
    return _PVPVE_TEAM_ORDER[:max(2, min(4, team_count))]


def _find_nearest_flexible(
    target_row: int,
    target_col: int,
    flexible_rooms: list[dict],
    assigned_keys: set[str],
    max_radius: int = 99,
) -> dict | None:
    """Find the nearest unassigned flexible room to a target grid position.

    Uses Manhattan distance, expanding outward from the target.
    """
    best_room = None
    best_dist = max_radius + 1
    for room in flexible_rooms:
        key = f"{room['gridRow']},{room['gridCol']}"
        if key in assigned_keys:
            continue
        dist = abs(room["gridRow"] - target_row) + abs(room["gridCol"] - target_col)
        if dist < best_dist:
            best_dist = dist
            best_room = room
    return best_room if best_dist <= max_radius else None


def _pvpve_assign_corner_spawns(
    flexible_rooms: list[dict],
    grid_rows: int,
    grid_cols: int,
    team_count: int,
    assignments: dict[str, str],
) -> dict[str, dict]:
    """Assign spawn rooms to grid corners for each active team.

    Returns a mapping of team_key → room dict for spawns placed.
    """
    active_teams = _get_active_teams(team_count)
    max_row = grid_rows - 1
    max_col = grid_cols - 1
    assigned_keys: set[str] = set(assignments.keys())
    spawn_rooms: dict[str, dict] = {}

    for team_key in active_teams:
        row_fn, col_fn = _PVPVE_TEAM_CORNERS[team_key]
        target_r = row_fn(max_row, max_col)
        target_c = col_fn(max_row, max_col)

        room = _find_nearest_flexible(target_r, target_c, flexible_rooms, assigned_keys)
        if room is not None:
            key = f"{room['gridRow']},{room['gridCol']}"
            assignments[key] = f"spawn_{team_key}"
            assigned_keys.add(key)
            spawn_rooms[team_key] = room

    return spawn_rooms


def _pvpve_assign_center_boss(
    flexible_rooms: list[dict],
    grid_rows: int,
    grid_cols: int,
    assignments: dict[str, str],
    config: dict,
) -> dict | None:
    """Assign the boss room to the center of the grid.

    Returns the boss room dict, or None if no suitable room found.
    """
    center_row = grid_rows // 2
    center_col = grid_cols // 2
    assigned_keys: set[str] = set(assignments.keys())

    # Prefer rooms that explicitly support boss, scanning from center outward
    boss_rooms = [r for r in flexible_rooms if r["canBeBoss"]]
    room = _find_nearest_flexible(center_row, center_col, boss_rooms, assigned_keys)

    # Fallback: any flexible room near center
    if room is None:
        room = _find_nearest_flexible(center_row, center_col, flexible_rooms, assigned_keys)

    if room is not None:
        key = f"{room['gridRow']},{room['gridCol']}"
        assignments[key] = "boss"

    return room


def _pvpve_compute_proximity_ramp(
    flexible_rooms: list[dict],
    spawn_rooms: dict[str, dict],
) -> tuple[dict[str, int], dict[str, str]]:
    """Compute multi-spawn proximity ramp for PVPVE.

    For each flexible room, compute the minimum Manhattan distance to any
    spawn room. Rooms close to any spawn are marked safe/softened.

    Returns:
        (room_distances, proximity_overrides) dicts keyed by "row,col".
    """
    room_distances: dict[str, int] = {}
    proximity_overrides: dict[str, str] = {}

    spawn_positions = [(r["gridRow"], r["gridCol"]) for r in spawn_rooms.values()]

    for room in flexible_rooms:
        key = f"{room['gridRow']},{room['gridCol']}"
        if spawn_positions:
            dist = min(
                abs(room["gridRow"] - sr) + abs(room["gridCol"] - sc)
                for sr, sc in spawn_positions
            )
        else:
            dist = 99
        room_distances[key] = dist

        if dist <= 1:
            proximity_overrides[key] = "safe"
        elif dist == 2:
            proximity_overrides[key] = "softened"

    return room_distances, proximity_overrides


def _pvpve_compute_difficulty_tier(
    room: dict,
    grid_rows: int,
    grid_cols: int,
) -> tuple[str, int]:
    """Compute difficulty tier for a PVPVE room based on distance to center.

    Returns:
        (tier_name, manhattan_distance_to_center)
    """
    center_row = grid_rows / 2.0
    center_col = grid_cols / 2.0
    dist = abs(room["gridRow"] - center_row) + abs(room["gridCol"] - center_col)
    # Round to nearest integer for tier lookup
    int_dist = int(round(dist))

    for max_dist, tier_name, _, _ in _PVPVE_DIFFICULTY_TIERS:
        if int_dist <= max_dist:
            return tier_name, int_dist

    return "normal", int_dist


def _pvpve_get_max_enemies_for_tier(tier: str, base_max: int) -> int:
    """Get max enemies for a room based on its difficulty tier."""
    for _, tier_name, max_enemies, _ in _PVPVE_DIFFICULTY_TIERS:
        if tier == tier_name:
            return max_enemies
    # Normal tier: use standard 2-3
    return min(base_max, 3)


def decorate_rooms(
    grid: list[list[dict]],
    variants: list[dict],
    tile_map: list[list[str]],
    seed: int = 42,
    settings: dict | None = None,
) -> dict:
    """Run the room decorator on a completed WFC result.

    Args:
        grid: WFC grid (rows × cols of cells with chosenVariant).
        variants: Expanded variant list from WFC.
        tile_map: 2D tile map (will be deep-copied, not mutated).
        seed: RNG seed for deterministic results.
        settings: Decorator settings (merged with defaults).

    Returns:
        dict with: decoratedRooms, tileMap (decorated copy), stats.
    """
    config = {**DEFAULT_DECORATOR_SETTINGS, **(settings or {})}
    rng = _create_rng(seed + 77777)

    # Deep-clone the tile map
    decorated_map = [list(row) for row in tile_map]

    grid_rows = len(grid)
    grid_cols = len(grid[0]) if grid_rows > 0 else 0

    # ── Phase 1: Collect flexible rooms ──
    flexible_rooms = []
    fixed_rooms = []

    for gr in range(grid_rows):
        for gc in range(grid_cols):
            cell = grid[gr][gc]
            if cell["chosenVariant"] is None:
                continue

            variant = variants[cell["chosenVariant"]]
            role = variant.get("contentRole") or _infer_content_role(variant)

            if role == "flexible":
                slots = variant.get("spawnSlots") or []
                if not slots:
                    slots = _derive_floor_slots(variant.get("tiles", []))

                floor_cap = config.get("maxEnemiesPerRoom", 5)
                max_enemies = variant.get("maxEnemies") or min(floor_cap, len(slots) // 2)
                max_chests = variant.get("maxChests") or min(2, len(slots) // 3)

                flexible_rooms.append({
                    "gridRow": gr,
                    "gridCol": gc,
                    "variant": variant,
                    "slots": slots,
                    "maxEnemies": max_enemies,
                    "maxChests": max_chests,
                    "canBeBoss": variant.get("canBeBoss", False)
                                and any(s.get("types") and "boss" in s["types"] for s in slots),
                    "canBeSpawn": variant.get("canBeSpawn", False)
                                 and any(s.get("types") and "spawn" in s["types"] for s in slots),
                })
            elif role == "fixed":
                fixed_rooms.append({
                    "gridRow": gr,
                    "gridCol": gc,
                    "variant": variant,
                    "purpose": variant.get("purpose", "empty"),
                })

    # ── Phase 2: Check what fixed rooms already provide ──
    has_fixed_boss = any(r["purpose"] == "boss" for r in fixed_rooms)
    has_fixed_spawn = any(r["purpose"] == "spawn" for r in fixed_rooms)

    # ── Phase 3: Assign roles to flexible rooms ──
    _shuffle(flexible_rooms, rng)

    decorated_rooms = []
    assignments: dict[str, str] = {}
    pvpve_spawn_rooms: dict[str, dict] = {}  # team_key → room (PVPVE only)
    pvpve_difficulty_tiers: dict[str, str] = {}  # "row,col" → tier_name (PVPVE only)

    boss_assigned = has_fixed_boss
    spawn_assigned = has_fixed_spawn
    stairs_assigned = False

    pvpve_mode = config.get("pvpve_mode", False)

    if pvpve_mode:
        # ── PVPVE Path: corner spawns, center boss, multi-spawn proximity ──
        team_count = config.get("pvpve_team_count", 2)

        # Pass A-PVPVE: Force corner spawn rooms
        pvpve_spawn_rooms = _pvpve_assign_corner_spawns(
            flexible_rooms, grid_rows, grid_cols, team_count, assignments,
        )
        spawn_assigned = len(pvpve_spawn_rooms) > 0

        # Pass B-PVPVE: Force boss room to center
        if config["guaranteeBoss"] and not boss_assigned:
            boss_room = _pvpve_assign_center_boss(
                flexible_rooms, grid_rows, grid_cols, assignments, config,
            )
            boss_assigned = boss_room is not None

        # No stairs in PVPVE
        stairs_assigned = True  # Prevent stairs placement

        # Pass B3-PVPVE: Multi-spawn proximity ramp
        room_distances, proximity_overrides = _pvpve_compute_proximity_ramp(
            flexible_rooms, pvpve_spawn_rooms,
        )

        # Compute difficulty tier for each flexible room (distance to center)
        for room in flexible_rooms:
            key = f"{room['gridRow']},{room['gridCol']}"
            tier, _ = _pvpve_compute_difficulty_tier(room, grid_rows, grid_cols)
            pvpve_difficulty_tiers[key] = tier

    else:
        # ── Standard Path: single spawn, single boss, stairs ──

        # Pass A: Guarantee boss room
        if config["guaranteeBoss"] and not boss_assigned:
            for room in flexible_rooms:
                if room["canBeBoss"]:
                    key = f"{room['gridRow']},{room['gridCol']}"
                    assignments[key] = "boss"
                    boss_assigned = True
                    break

        # Pass B: Guarantee spawn room
        if config["guaranteeSpawn"] and not spawn_assigned:
            # First try: flexible rooms that explicitly support spawn
            for room in flexible_rooms:
                key = f"{room['gridRow']},{room['gridCol']}"
                if room["canBeSpawn"] and key not in assignments:
                    assignments[key] = "spawn"
                    spawn_assigned = True
                    break

            # Fallback: if no canBeSpawn room found, use any flexible room with floor slots
            if not spawn_assigned:
                for room in flexible_rooms:
                    key = f"{room['gridRow']},{room['gridCol']}"
                    if key not in assignments and room["slots"]:
                        assignments[key] = "spawn"
                        spawn_assigned = True
                        break

        # Pass B2: Guarantee stairs room (placed far from spawn if possible)
        if config.get("guaranteeStairs", True):
            spawn_key = None
            for room in flexible_rooms:
                key = f"{room['gridRow']},{room['gridCol']}"
                if assignments.get(key) == "spawn":
                    spawn_key = key
                    break

            stairs_candidates = []
            for room in flexible_rooms:
                key = f"{room['gridRow']},{room['gridCol']}"
                if key not in assignments and room["slots"]:
                    dist = 0
                    if spawn_key:
                        sr, sc = [int(v) for v in spawn_key.split(",")]
                        dist = abs(room["gridRow"] - sr) + abs(room["gridCol"] - sc)
                    stairs_candidates.append((dist, key, room))

            stairs_candidates.sort(key=lambda t: -t[0])

            for _, key, room in stairs_candidates:
                assignments[key] = "stairs"
                stairs_assigned = True
                break

        # Pass B3: Compute spawn distance for each flexible room (proximity ramp)
        spawn_room = None
        for room in flexible_rooms:
            key = f"{room['gridRow']},{room['gridCol']}"
            if assignments.get(key) == "spawn":
                spawn_room = room
                break

        if spawn_room is None:
            for fr in fixed_rooms:
                if fr["purpose"] == "spawn":
                    spawn_room = fr
                    break

        room_distances: dict[str, int] = {}
        for room in flexible_rooms:
            key = f"{room['gridRow']},{room['gridCol']}"
            if spawn_room:
                dist = abs(room["gridRow"] - spawn_room["gridRow"]) + abs(room["gridCol"] - spawn_room["gridCol"])
            else:
                dist = 99
            room_distances[key] = dist

        proximity_overrides: dict[str, str] = {}
        for room in flexible_rooms:
            key = f"{room['gridRow']},{room['gridCol']}"
            dist = room_distances.get(key, 99)
            if dist <= 1:
                proximity_overrides[key] = "safe"
            elif dist == 2:
                proximity_overrides[key] = "softened"

    # Pass C: Assign remaining flexible rooms (quota-based deck system)
    remaining = [r for r in flexible_rooms
                 if f"{r['gridRow']},{r['gridCol']}" not in assignments]
    n = len(remaining)

    if n > 0:
        # Compute target counts from density settings
        n_enemy = round(n * config["enemyDensity"])
        n_loot = round(n * config["lootDensity"])
        n_empty = max(1, n - n_enemy - n_loot)  # remainder → empty (at least 1)

        # Clamp if oversubscribed
        if n_enemy + n_loot > n:
            total_want = n_enemy + n_loot
            scale = (n - 1) / total_want if total_want > 0 else 0
            n_enemy = max(1, round(n_enemy * scale))
            n_loot = max(0, round(n_loot * scale))
            n_empty = n - n_enemy - n_loot

        # Build a role deck and shuffle it
        deck = (["enemy"] * n_enemy) + (["loot"] * n_loot) + (["empty"] * n_empty)
        # Pad or trim to exactly match room count
        while len(deck) < n:
            deck.append("empty")
        deck = deck[:n]
        _shuffle(deck, rng)

        # Phase 2: Proximity-aware dealing — swap enemy tokens out of safe zones
        # Sort remaining rooms by distance (closest first) for deterministic swap order
        remaining_sorted = sorted(
            enumerate(remaining),
            key=lambda pair: room_distances.get(
                f"{pair[1]['gridRow']},{pair[1]['gridCol']}", 99
            ),
        )

        # Build index mapping: original index → room
        # Identify safe-zone indices that got "enemy" and far-zone indices with non-enemy
        safe_enemy_indices = []   # indices in deck that are "enemy" but in safe zone
        far_non_enemy_indices = []  # indices in deck with loot/empty in far zone (dist >= 3)

        for orig_idx, room in remaining_sorted:
            key = f"{room['gridRow']},{room['gridCol']}"
            override = proximity_overrides.get(key)
            if override == "safe" and deck[orig_idx] == "enemy":
                safe_enemy_indices.append(orig_idx)
            elif override is None and deck[orig_idx] != "enemy":
                # dist >= 3, has a non-enemy token — candidate for swap
                far_non_enemy_indices.append(orig_idx)

        # Swap enemy tokens from safe zones to far zones
        for safe_idx in safe_enemy_indices:
            if not far_non_enemy_indices:
                # No far swaps available — force to loot (safe fallback)
                deck[safe_idx] = "loot"
            else:
                far_idx = far_non_enemy_indices.pop(0)
                deck[safe_idx], deck[far_idx] = deck[far_idx], deck[safe_idx]

        # Deal roles to rooms
        for room, role in zip(remaining, deck):
            key = f"{room['gridRow']},{room['gridCol']}"
            assignments[key] = role

    # ── Pass C2: Cluster smoothing (Phase 4 — Neighbor-Aware) ──
    # Iteratively find clusters of 2+ adjacent enemy rooms and downgrade one per
    # cluster to "loot" until no adjacent enemy pairs remain.
    def _get_adjacent_keys(gr: int, gc: int) -> list[str]:
        return [f"{gr + dr},{gc + dc}" for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]]

    # Build a lookup from key → room for fast adjacency checks
    room_by_key: dict[str, dict] = {}
    for room in flexible_rooms:
        rk = f"{room['gridRow']},{room['gridCol']}"
        room_by_key[rk] = room

    hot_clusters: list[list[dict]] = []
    smoothed_keys: set[str] = set()

    # Iterate until no adjacent enemy pairs remain (handles chains of 3+)
    max_iterations = len(flexible_rooms)  # safety bound
    for _iteration in range(max_iterations):
        # Find clusters of adjacent enemy rooms via BFS
        visited: set[str] = set()
        iteration_clusters: list[list[dict]] = []

        for room in flexible_rooms:
            rk = f"{room['gridRow']},{room['gridCol']}"
            if rk in visited or assignments.get(rk) != "enemy":
                continue
            # BFS to find connected enemy rooms
            cluster: list[dict] = []
            queue = [room]
            while queue:
                current = queue.pop(0)
                ck = f"{current['gridRow']},{current['gridCol']}"
                if ck in visited:
                    continue
                visited.add(ck)
                if assignments.get(ck) == "enemy":
                    cluster.append(current)
                    for adj_key in _get_adjacent_keys(current["gridRow"], current["gridCol"]):
                        if adj_key not in visited and adj_key in room_by_key:
                            queue.append(room_by_key[adj_key])
            if len(cluster) >= 2:
                iteration_clusters.append(cluster)

        if not iteration_clusters:
            break  # No more adjacent enemy pairs — done

        # Downgrade one room per cluster to "loot"
        for cluster in iteration_clusters:
            # Pick the room closest to spawn (easiest to reach = most forgiving)
            cluster.sort(key=lambda r: room_distances.get(f"{r['gridRow']},{r['gridCol']}", 0))
            target = cluster[0]
            target_key = f"{target['gridRow']},{target['gridCol']}"
            assignments[target_key] = "loot"  # Downgrade to loot (scatter may add 1 guard)
            smoothed_keys.add(target_key)

        hot_clusters.extend(iteration_clusters)

    # ── Phase 4: Place content based on assignments ──
    for room in flexible_rooms:
        key = f"{room['gridRow']},{room['gridCol']}"
        role = assignments.get(key, "empty")

        start_r = room["gridRow"] * MODULE_SIZE
        start_c = room["gridCol"] * MODULE_SIZE

        placements = []
        available_slots = _shuffle(list(room["slots"]), rng)

        if role == "boss":
            boss_slots = [s for s in available_slots if s.get("types") and "boss" in s["types"]]
            if boss_slots:
                bs = boss_slots[0]
                _place_tile(decorated_map, start_r + bs["y"], start_c + bs["x"], "B")
                placements.append({"x": start_c + bs["x"], "y": start_r + bs["y"], "type": "B"})
                # Guard enemies — PVPVE gets more guards + chests in boss room
                guard_count = config.get("pvpve_boss_guards", 2) if pvpve_mode else 2
                boss_chests = config.get("pvpve_boss_chests", 0) if pvpve_mode else 0
                guard_slots = [s for s in available_slots
                               if s is not bs and s.get("types") and "enemy" in s["types"]]
                for i in range(min(guard_count, len(guard_slots))):
                    _place_tile(decorated_map, start_r + guard_slots[i]["y"], start_c + guard_slots[i]["x"], "E")
                    placements.append({"x": start_c + guard_slots[i]["x"], "y": start_r + guard_slots[i]["y"], "type": "E"})
                # PVPVE boss room chests
                if boss_chests > 0:
                    placed_positions = {(p["x"], p["y"]) for p in placements}
                    chest_slots = [s for s in available_slots
                                   if s.get("types") and "loot" in s["types"]
                                   and (start_c + s["x"], start_r + s["y"]) not in placed_positions]
                    for i in range(min(boss_chests, len(chest_slots))):
                        _place_tile(decorated_map, start_r + chest_slots[i]["y"], start_c + chest_slots[i]["x"], "X")
                        placements.append({"x": start_c + chest_slots[i]["x"], "y": start_r + chest_slots[i]["y"], "type": "X"})

        elif role == "spawn" or role.startswith("spawn_"):
            # Standard spawn or PVPVE team spawn (spawn_a, spawn_b, etc.)
            spawn_slots = [s for s in available_slots if s.get("types") and "spawn" in s["types"]]
            count = min(4, len(spawn_slots))
            for i in range(count):
                _place_tile(decorated_map, start_r + spawn_slots[i]["y"], start_c + spawn_slots[i]["x"], "S")
                placements.append({"x": start_c + spawn_slots[i]["x"], "y": start_r + spawn_slots[i]["y"], "type": "S"})

        elif role == "stairs":
            # Place a single staircase tile on a floor slot in this room
            stair_slots = [s for s in available_slots if s.get("types")]
            if stair_slots:
                _place_tile(decorated_map, start_r + stair_slots[0]["y"], start_c + stair_slots[0]["x"], "T")
                placements.append({"x": start_c + stair_slots[0]["x"], "y": start_r + stair_slots[0]["y"], "type": "T"})
            # Also scatter a guard enemy near the stairs
            if len(stair_slots) > 1:
                guard = stair_slots[1]
                _place_tile(decorated_map, start_r + guard["y"], start_c + guard["x"], "E")
                placements.append({"x": start_c + guard["x"], "y": start_r + guard["y"], "type": "E"})

        elif role == "enemy":
            # Phase 2: Softened rooms (distance 2 from spawn) get halved max enemies
            effective_max = room["maxEnemies"]
            if proximity_overrides.get(key) == "softened":
                effective_max = max(1, effective_max // 2)

            # PVPVE: Difficulty gradient — rooms closer to center get more enemies
            if pvpve_mode:
                tier = pvpve_difficulty_tiers.get(key, "normal")
                tier_max = _pvpve_get_max_enemies_for_tier(tier, room["maxEnemies"])
                effective_max = min(effective_max, tier_max) if proximity_overrides.get(key) == "softened" else tier_max

            enemy_slots = [s for s in available_slots if s.get("types") and "enemy" in s["types"]]
            count = min(effective_max, len(enemy_slots))
            actual_count = max(1, int(rng() * count) + 1) if count <= 2 else max(2, int(rng() * count) + 1)
            for i in range(min(actual_count, len(enemy_slots))):
                _place_tile(decorated_map, start_r + enemy_slots[i]["y"], start_c + enemy_slots[i]["x"], "E")
                placements.append({"x": start_c + enemy_slots[i]["x"], "y": start_r + enemy_slots[i]["y"], "type": "E"})
            # Scatter bonus chest
            if config["scatterChests"] and rng() < 0.3:
                placed_positions = {(p["x"], p["y"]) for p in placements}
                chest_slots = [s for s in available_slots
                               if s.get("types") and "loot" in s["types"]
                               and (start_c + s["x"], start_r + s["y"]) not in placed_positions]
                if chest_slots:
                    _place_tile(decorated_map, start_r + chest_slots[0]["y"], start_c + chest_slots[0]["x"], "X")
                    placements.append({"x": start_c + chest_slots[0]["x"], "y": start_r + chest_slots[0]["y"], "type": "X"})

        elif role == "loot":
            loot_slots = [s for s in available_slots if s.get("types") and "loot" in s["types"]]
            count = min(room["maxChests"], len(loot_slots))
            actual_count = max(1, int(rng() * count) + 1)
            for i in range(min(actual_count, len(loot_slots))):
                _place_tile(decorated_map, start_r + loot_slots[i]["y"], start_c + loot_slots[i]["x"], "X")
                placements.append({"x": start_c + loot_slots[i]["x"], "y": start_r + loot_slots[i]["y"], "type": "X"})
            # Scatter guard enemy
            if config["scatterEnemies"] and rng() < 0.45:
                placed_positions = {(p["x"], p["y"]) for p in placements}
                enemy_slots = [s for s in available_slots
                               if s.get("types") and "enemy" in s["types"]
                               and (start_c + s["x"], start_r + s["y"]) not in placed_positions]
                if enemy_slots:
                    _place_tile(decorated_map, start_r + enemy_slots[0]["y"], start_c + enemy_slots[0]["x"], "E")
                    placements.append({"x": start_c + enemy_slots[0]["x"], "y": start_r + enemy_slots[0]["y"], "type": "E"})

        else:  # empty
            if config["scatterEnemies"] and rng() < 0.25:
                enemy_slots = [s for s in available_slots if s.get("types") and "enemy" in s["types"]]
                if enemy_slots:
                    _place_tile(decorated_map, start_r + enemy_slots[0]["y"], start_c + enemy_slots[0]["x"], "E")
                    placements.append({"x": start_c + enemy_slots[0]["x"], "y": start_r + enemy_slots[0]["y"], "type": "E"})
            elif config["scatterChests"] and rng() < 0.1:
                loot_slots = [s for s in available_slots if s.get("types") and "loot" in s["types"]]
                if loot_slots:
                    _place_tile(decorated_map, start_r + loot_slots[0]["y"], start_c + loot_slots[0]["x"], "X")
                    placements.append({"x": start_c + loot_slots[0]["x"], "y": start_r + loot_slots[0]["y"], "type": "X"})

        decorated_rooms.append({
            "gridRow": room["gridRow"],
            "gridCol": room["gridCol"],
            "assignedRole": role,
            "placements": placements,
            "spawnDistance": room_distances.get(key, 99),
            "proximityOverride": proximity_overrides.get(key),
            "clusterSmoothed": key in smoothed_keys,
            "difficultyTier": pvpve_difficulty_tiers.get(key) if pvpve_mode else None,
            "sourceName": room["variant"].get("sourceName")
                         or room["variant"].get("name", "Unknown"),
        })

    # ── Phase 4.5: Emergency spawn fallback ──
    # If guaranteeSpawn is on and no spawn was assigned (no flexible rooms, no fixed spawn),
    # place spawn tiles directly on the first available floor tiles in the tile map.
    if config["guaranteeSpawn"] and not spawn_assigned:
        emergency_placements = _place_emergency_spawns(decorated_map)
        if emergency_placements:
            spawn_assigned = True
            decorated_rooms.append({
                "gridRow": -1,
                "gridCol": -1,
                "assignedRole": "spawn",
                "placements": emergency_placements,
                "sourceName": "Emergency Spawn (fallback)",
            })

    # ── Phase 4.6: Emergency stairs fallback ──
    # If guaranteeStairs is on and no stairs were placed, place one on a floor tile
    # far from any spawn tiles.
    if config.get("guaranteeStairs", True) and not stairs_assigned:
        stair_placement = _place_emergency_stairs(decorated_map)
        if stair_placement:
            stairs_assigned = True
            decorated_rooms.append({
                "gridRow": -1,
                "gridCol": -1,
                "assignedRole": "stairs",
                "placements": [stair_placement],
                "sourceName": "Emergency Stairs (fallback)",
            })

    # ── Phase 5: Compute decoration stats ──
    stats = _compute_decoration_stats(decorated_rooms, fixed_rooms, hot_clusters, smoothed_keys)

    result = {
        "decoratedRooms": decorated_rooms,
        "tileMap": decorated_map,
        "stats": stats,
    }

    # PVPVE: include spawn room metadata for the exporter
    if pvpve_mode and pvpve_spawn_rooms:
        result["pvpve_spawn_rooms"] = {
            team_key: {
                "gridRow": room["gridRow"],
                "gridCol": room["gridCol"],
            }
            for team_key, room in pvpve_spawn_rooms.items()
        }
        result["pvpve_difficulty_tiers"] = pvpve_difficulty_tiers

    return result


def _compute_decoration_stats(
    decorated_rooms: list[dict],
    fixed_rooms: list[dict],
    hot_clusters: list[list[dict]] | None = None,
    smoothed_keys: set[str] | None = None,
) -> dict:
    """Compute summary stats about the decoration pass."""
    role_count = {"enemy": 0, "loot": 0, "boss": 0, "spawn": 0, "stairs": 0, "empty": 0}
    total_placements = 0
    enemies_placed = 0
    chests_placed = 0
    bosses_placed = 0
    spawns_placed = 0
    stairs_placed = 0
    cluster_smoothed_count = 0

    for room in decorated_rooms:
        role = room["assignedRole"]
        # Normalize PVPVE team spawns (spawn_a, spawn_b, etc.) to "spawn" for stats
        stat_role = "spawn" if role.startswith("spawn") else role
        role_count[stat_role] = role_count.get(stat_role, 0) + 1
        total_placements += len(room["placements"])
        if room.get("clusterSmoothed"):
            cluster_smoothed_count += 1
        for p in room["placements"]:
            if p["type"] == "E":
                enemies_placed += 1
            elif p["type"] == "X":
                chests_placed += 1
            elif p["type"] == "B":
                bosses_placed += 1
            elif p["type"] == "S":
                spawns_placed += 1
            elif p["type"] == "T":
                stairs_placed += 1

    return {
        "flexibleRooms": len(decorated_rooms),
        "fixedRooms": len(fixed_rooms),
        "roleCount": role_count,
        "totalPlacements": total_placements,
        "enemiesPlaced": enemies_placed,
        "chestsPlaced": chests_placed,
        "bossesPlaced": bosses_placed,
        "spawnsPlaced": spawns_placed,
        "stairsPlaced": stairs_placed,
        "clustersFound": len(hot_clusters) if hot_clusters is not None else 0,
        "clustersSmoothed": cluster_smoothed_count,
    }

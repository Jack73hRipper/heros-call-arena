"""
map_exporter.py — Convert WFC tile map to Arena game map dict.

Port of tools/dungeon-wfc/src/utils/exportMap.js to Python.
Matches the JSON format used by server/configs/maps/.

Phase 18C: Rarity rolling integrated into enemy spawn data — each enemy_spawn
dict now carries monster_rarity, champion_type, affixes, and display_name so
that match_manager can apply them at unit creation time.

Phase 18G: Super unique boss replacement — on eligible floors, a boss room's
normal boss may be replaced by a hand-crafted super unique with fixed stats,
affixes, and a fixed retinue of minions.
"""

from __future__ import annotations

import random as _random
from typing import Any

from app.core.wfc.module_utils import MODULE_SIZE


# Default enemy type mapping for rooms
ENEMY_TYPE_MAP = {
    "E": "demon",
    "B": "undead_knight",
}


def _normalize_tile(tile: str) -> str:
    """Normalize tile types for game export.

    E and B markers become F (floor) in the exported tile grid —
    enemies are placed via the rooms[].enemy_spawns array instead.
    D (door) markers also become F — doors are disabled for now
    while rooms are being resized; the door collection code is kept
    intact so it can be re-enabled later.
    """
    if tile in ("E", "B", "D"):
        return "F"
    return tile


def export_to_game_map(
    tile_map: list[list[str]],
    grid: list[list[dict]] | None = None,
    variants: list[dict] | None = None,
    map_name: str = "WFC Generated Dungeon",
    floor_number: int = 1,
    enemy_types: dict[str, str] | None = None,
    enemy_roster: dict[str, list[tuple[str, float]]] | None = None,
    seed: int | None = None,
    pvpve_mode: bool = False,
    pvpve_team_count: int = 2,
    decoration_result: dict | None = None,
) -> dict:
    """Convert a WFC tile map + grid metadata into a game-compatible map dict.

    Args:
        tile_map: 2D array of tile characters (pre-decoration).
        grid: WFC grid with cell metadata (chosenVariant).
        variants: Expanded variant list from WFC.
        map_name: Name for the exported map.
        floor_number: Current floor number (for naming/scaling).
        enemy_types: Legacy mapping of tile char → enemy type (default: E→demon, B→undead_knight).
        enemy_roster: Weighted enemy pools — {"regular": [(id, weight)...], "boss": [...], "support": [...]}.
                      When provided, each E/B tile draws from the pool for variety.
        seed: RNG seed for deterministic roster picks.  Ignored when enemy_roster is None.
        pvpve_mode: If True, export PVPVE-specific metadata (multi-team spawns, pve tags).
        pvpve_team_count: Number of player teams (2–4) for PVPVE mode.
        decoration_result: The full decoration result dict (used for PVPVE spawn mapping).

    Returns:
        Game-compatible map dict (same format as server/configs/maps/*.json).
    """
    if enemy_types is None:
        enemy_types = dict(ENEMY_TYPE_MAP)

    # Build a seeded RNG for roster-based enemy picks
    _roster_rng = _random.Random(seed if seed is not None else 0)

    # Phase 18C: Import rarity functions and build a separate RNG for rarity rolls
    from app.core.monster_rarity import (
        load_monster_rarity_config,
        roll_monster_rarity,
        roll_champion_type,
        get_champion_type_name,
        roll_affixes,
        generate_rare_name,
        get_spawn_chances,
        get_floor_override,
        roll_super_unique_spawn,
        get_room_budget,
        get_rarity_cost,
    )
    from app.models.player import get_enemy_definition
    _rarity_rng = _random.Random((seed if seed is not None else 0) + 18_000_003)
    _rarity_config = load_monster_rarity_config()

    # Phase 5 (Spawn Distribution Overhaul): Floor-tier-specific rarity overrides
    _floor_override = get_floor_override(floor_number)

    # Phase 18G: Super unique tracking for this dungeon generation
    _su_rng = _random.Random((seed if seed is not None else 0) + 18_000_007)
    _su_spawned_count = 0

    def _resolve_enemy(tile: str, room_enemy_count: int, room_support_assigned: bool) -> tuple[str, bool]:
        """Resolve enemy_id for a tile.  Returns (enemy_id, is_support_swap)."""
        if enemy_roster is not None:
            from app.core.wfc.dungeon_generator import (
                resolve_enemy_for_tile,
                _SUPPORT_SWAP_CHANCE,
            )
            # For rooms with 2+ regular enemies, one may become a support unit
            is_support = (
                tile == "E"
                and not room_support_assigned
                and room_enemy_count >= 2
                and _roster_rng.random() < _SUPPORT_SWAP_CHANCE
            )
            eid = resolve_enemy_for_tile(tile, enemy_roster, _roster_rng.random, is_support_swap=is_support)
            return eid, is_support
        # Legacy fallback: static mapping
        return enemy_types.get(tile, "demon"), False

    # Phase 18C: Per-room enhanced enemy counter
    _spawn_chances = get_spawn_chances()
    # Phase 5: Floor-tier override may lower the enhanced cap on early floors
    _max_enhanced_per_room = _floor_override.get(
        "max_enhanced_per_room",
        _spawn_chances.get("max_enhanced_per_room", 2),
    )

    def _roll_rarity_for_spawn(enemy_id: str, is_boss: bool, room_enhanced_count: int,
                               room_budget_remaining: int | None = None) -> dict:
        """Roll rarity upgrade for a single enemy spawn.

        Returns a dict with rarity metadata keys:
        monster_rarity, champion_type, affixes, display_name.
        Bosses are never upgraded. Enemies with allow_rarity_upgrade=false are skipped.
        Respects max_enhanced_per_room limit AND per-room difficulty budget (Phase 3).
        """
        # Default: normal
        rarity_data = {
            "monster_rarity": "normal",
            "champion_type": None,
            "affixes": [],
            "display_name": None,
        }

        if is_boss:
            return rarity_data

        # Check max enhanced per room limit (backward-compat hard cap)
        if room_enhanced_count >= _max_enhanced_per_room:
            return rarity_data

        enemy_def = get_enemy_definition(enemy_id)
        if not enemy_def or not getattr(enemy_def, "allow_rarity_upgrade", True):
            return rarity_data

        rarity = roll_monster_rarity(floor_number, _rarity_rng)
        if rarity == "normal":
            return rarity_data

        # Phase 3: Budget-aware downgrade — if the rolled rarity costs more
        # than the remaining budget, downgrade to champion or normal.
        if room_budget_remaining is not None:
            cost = get_rarity_cost(rarity)
            if cost > room_budget_remaining:
                # Try downgrade: rare → champion → normal
                if rarity == "rare" and get_rarity_cost("champion") <= room_budget_remaining:
                    rarity = "champion"
                else:
                    rarity = "normal"
            if rarity == "normal":
                return rarity_data

        rarity_data["monster_rarity"] = rarity

        if rarity == "champion":
            champion_type = roll_champion_type(_rarity_rng)
            rarity_data["champion_type"] = champion_type
            ct_name = get_champion_type_name(champion_type)
            rarity_data["display_name"] = f"{ct_name} {enemy_def.name}"
        elif rarity == "rare":
            rare_tier = _rarity_config.get("rarity_tiers", {}).get("rare", {})
            # Phase 5: Floor-tier override may narrow affix count on early floors
            affix_range = _floor_override.get(
                "rare_affix_count",
                rare_tier.get("affix_count", [2, 3]),
            )
            if isinstance(affix_range, list) and len(affix_range) == 2:
                affix_count = _rarity_rng.randint(affix_range[0], affix_range[1])
            else:
                affix_count = 2
            affixes = roll_affixes(enemy_def, affix_count, _rarity_rng)
            rarity_data["affixes"] = affixes
            rarity_data["display_name"] = generate_rare_name(enemy_def.name, affixes, _rarity_rng)

        return rarity_data

    height = len(tile_map)
    width = len(tile_map[0]) if height > 0 else 0

    # Convert tile map to game format (normalize E/B → F)
    tiles = [[_normalize_tile(t) for t in row] for row in tile_map]

    # Collect spawn points from 'S' tiles
    spawn_points = []
    spawn_bounds = {
        "x_min": float("inf"),
        "y_min": float("inf"),
        "x_max": float("-inf"),
        "y_max": float("-inf"),
    }

    # PVPVE: Build per-team spawn point mapping from decorator metadata
    pvpve_spawn_rooms_meta = {}
    if pvpve_mode and decoration_result:
        pvpve_spawn_rooms_meta = decoration_result.get("pvpve_spawn_rooms", {})

    # Build a grid-cell → team lookup for PVPVE spawn attribution
    _cell_to_team: dict[str, str] = {}
    if pvpve_mode:
        for team_key, room_meta in pvpve_spawn_rooms_meta.items():
            cell_key = f"{room_meta['gridRow']},{room_meta['gridCol']}"
            _cell_to_team[cell_key] = team_key

    spawn_points_by_team: dict[str, list[dict]] = {"a": [], "b": [], "c": [], "d": []}

    for y in range(height):
        for x in range(width):
            if tile_map[y][x] == "S":
                point = {"x": x, "y": y}
                spawn_points.append(point)
                spawn_bounds["x_min"] = min(spawn_bounds["x_min"], x)
                spawn_bounds["y_min"] = min(spawn_bounds["y_min"], y)
                spawn_bounds["x_max"] = max(spawn_bounds["x_max"], x)
                spawn_bounds["y_max"] = max(spawn_bounds["y_max"], y)

                # PVPVE: attribute this spawn to a team
                if pvpve_mode and MODULE_SIZE > 0:
                    cell_r = y // MODULE_SIZE
                    cell_c = x // MODULE_SIZE
                    cell_key = f"{cell_r},{cell_c}"
                    team = _cell_to_team.get(cell_key)
                    if team:
                        spawn_points_by_team[team].append(point)

    # Fallback: use first floor tiles if no spawn points
    if not spawn_points:
        for y in range(height):
            for x in range(width):
                if tile_map[y][x] in ("F", "C") and len(spawn_points) < 5:
                    spawn_points.append({"x": x, "y": y})
                    spawn_bounds["x_min"] = min(spawn_bounds["x_min"], x)
                    spawn_bounds["y_min"] = min(spawn_bounds["y_min"], y)
                    spawn_bounds["x_max"] = max(spawn_bounds["x_max"], x)
                    spawn_bounds["y_max"] = max(spawn_bounds["y_max"], y)

    # Collect doors
    doors = []
    for y in range(height):
        for x in range(width):
            if tile_map[y][x] == "D":
                doors.append({"x": x, "y": y, "state": "closed"})

    # Collect chests
    chests = []
    for y in range(height):
        for x in range(width):
            if tile_map[y][x] == "X":
                chests.append({"x": x, "y": y})

    # Collect stairs
    stairs = []
    for y in range(height):
        for x in range(width):
            if tile_map[y][x] == "T":
                stairs.append({"x": x, "y": y})

    # Build rooms from the WFC module grid
    rooms = []
    if grid is not None and variants is not None:
        grid_rows = len(grid)
        grid_cols = len(grid[0]) if grid_rows > 0 else 0

        for gr in range(grid_rows):
            for gc in range(grid_cols):
                cell = grid[gr][gc]
                if cell["chosenVariant"] is None:
                    continue

                variant = variants[cell["chosenVariant"]]
                start_r = gr * MODULE_SIZE
                start_c = gc * MODULE_SIZE

                # Scan the actual tileMap region for content
                enemy_spawns = []
                has_content = False
                detected_purpose = variant.get("purpose", "empty")

                # Pre-count regular enemies in this module for support-swap logic
                regular_count = 0
                for lr in range(MODULE_SIZE):
                    for lc in range(MODULE_SIZE):
                        r2 = start_r + lr
                        c2 = start_c + lc
                        if r2 < height and c2 < width and tile_map[r2][c2] == "E":
                            regular_count += 1

                support_assigned = False

                # Phase 18C: Track enhanced enemies per room
                room_enhanced_count = 0

                # Phase 3 (Spawn Distribution Overhaul): Compute per-room
                # difficulty budget based on floor tier and enemy count.
                room_budget = get_room_budget(floor_number, regular_count)
                room_budget_remaining = room_budget

                for lr in range(MODULE_SIZE):
                    for lc in range(MODULE_SIZE):
                        r = start_r + lr
                        c = start_c + lc
                        if r < height and c < width:
                            tile = tile_map[r][c]
                            if tile == "E":
                                eid, was_support = _resolve_enemy("E", regular_count, support_assigned)
                                if was_support:
                                    support_assigned = True
                                # Phase 18C+Phase 3: Roll rarity with budget awareness
                                rarity_data = _roll_rarity_for_spawn(
                                    eid, False, room_enhanced_count, room_budget_remaining
                                )
                                rarity_cost = get_rarity_cost(rarity_data["monster_rarity"])
                                room_budget_remaining -= rarity_cost
                                if rarity_data["monster_rarity"] != "normal":
                                    room_enhanced_count += 1
                                spawn_entry = {
                                    "x": c,
                                    "y": r,
                                    "enemy_type": eid,
                                    **rarity_data,
                                }
                                if pvpve_mode:
                                    spawn_entry["team"] = "pve"
                                enemy_spawns.append(spawn_entry)
                                has_content = True
                                if detected_purpose == "empty":
                                    detected_purpose = "enemy"
                            elif tile == "B":
                                boss_eid, _ = _resolve_enemy("B", 0, False)
                                # Phase 18G: Check for super unique boss replacement
                                su_result = roll_super_unique_spawn(
                                    floor_number, _su_rng, _su_spawned_count
                                )
                                if su_result is not None:
                                    _su_spawned_count += 1
                                    # Super unique replaces normal boss
                                    su_entry = {
                                        "x": c,
                                        "y": r,
                                        "enemy_type": su_result.get("base_enemy", boss_eid),
                                        "is_boss": True,
                                        "monster_rarity": "super_unique",
                                        "champion_type": None,
                                        "affixes": list(su_result.get("affixes", [])),
                                        "display_name": su_result.get("name"),
                                        "super_unique_id": su_result.get("id"),
                                    }
                                    if pvpve_mode:
                                        su_entry["team"] = "pve"
                                    enemy_spawns.append(su_entry)
                                    # Add retinue entries — they'll be spawned by match_manager
                                    for ret in su_result.get("retinue", []):
                                        ret_type = ret.get("enemy_type", "skeleton")
                                        ret_count = ret.get("count", 1)
                                        for _ri in range(ret_count):
                                            ret_entry = {
                                                "x": c,
                                                "y": r,
                                                "enemy_type": ret_type,
                                                "is_boss": False,
                                                "monster_rarity": "normal",
                                                "champion_type": None,
                                                "affixes": [],
                                                "display_name": None,
                                                "is_retinue": True,
                                            }
                                            if pvpve_mode:
                                                ret_entry["team"] = "pve"
                                            enemy_spawns.append(ret_entry)
                                else:
                                    boss_entry = {
                                        "x": c,
                                        "y": r,
                                        "enemy_type": boss_eid,
                                        "is_boss": True,
                                        "monster_rarity": "normal",
                                        "champion_type": None,
                                        "affixes": [],
                                        "display_name": None,
                                    }
                                    if pvpve_mode:
                                        boss_entry["team"] = "pve"
                                    enemy_spawns.append(boss_entry)
                                has_content = True
                                if detected_purpose == "empty":
                                    detected_purpose = "boss"
                            elif tile == "S":
                                has_content = True
                                if detected_purpose == "empty":
                                    detected_purpose = "spawn"
                            elif tile == "X":
                                has_content = True
                                if detected_purpose == "empty":
                                    detected_purpose = "loot"
                            elif tile == "T":
                                has_content = True
                                if detected_purpose == "empty":
                                    detected_purpose = "stairs"

                # Skip purely structural modules
                if not has_content and variant.get("purpose") in ("empty", "corridor"):
                    continue

                room = {
                    "id": f"room_{gr}_{gc}",
                    "name": variant.get("sourceName", "Room"),
                    "purpose": detected_purpose,
                    "bounds": {
                        "x_min": start_c,
                        "y_min": start_r,
                        "x_max": start_c + MODULE_SIZE - 1,
                        "y_max": start_r + MODULE_SIZE - 1,
                    },
                }

                if enemy_spawns:
                    room["enemy_spawns"] = enemy_spawns

                rooms.append(room)

    # Build spawn zone from spawn bounds
    spawn_zones = {}
    if pvpve_mode:
        # PVPVE: Per-team spawn zones from grouped spawn points
        for team_key, points in spawn_points_by_team.items():
            if points:
                xs = [p["x"] for p in points]
                ys = [p["y"] for p in points]
                spawn_zones[team_key] = {
                    "x_min": max(0, min(xs) - 2),
                    "y_min": max(0, min(ys) - 2),
                    "x_max": min(width - 1, max(xs) + 2),
                    "y_max": min(height - 1, max(ys) + 2),
                }
    elif spawn_points and spawn_bounds["x_min"] != float("inf"):
        spawn_zones["a"] = {
            "x_min": int(spawn_bounds["x_min"]),
            "y_min": int(spawn_bounds["y_min"]),
            "x_max": int(spawn_bounds["x_max"]),
            "y_max": int(spawn_bounds["y_max"]),
        }

    # PVPVE: Identify the boss room for metadata
    boss_room_meta = None
    if pvpve_mode:
        for room in rooms:
            if room.get("purpose") == "boss":
                boss_chests = [c for c in chests
                               if (room["bounds"]["x_min"] <= c["x"] <= room["bounds"]["x_max"]
                                   and room["bounds"]["y_min"] <= c["y"] <= room["bounds"]["y_max"])]
                boss_room_meta = {
                    "id": room["id"],
                    "bounds": room["bounds"],
                    "enemy_spawns": room.get("enemy_spawns", []),
                    "chests": boss_chests,
                }
                break

    map_data = {
        "name": map_name,
        "width": width,
        "height": height,
        "map_type": "pvpve" if pvpve_mode else "dungeon",
        "spawn_points": spawn_points[:8],
        "spawn_zones": spawn_zones,
        "ffa_points": spawn_points[:8],
        "rooms": rooms,
        "doors": doors,
        "chests": chests,
        "stairs": stairs,
        "tiles": tiles,
        "tile_legend": {
            "W": "wall",
            "F": "floor",
            "D": "door",
            "C": "corridor",
            "S": "spawn",
            "X": "chest",
            "T": "stairs",
        },
    }

    # PVPVE-specific top-level fields
    if pvpve_mode:
        map_data["pvpve_team_count"] = pvpve_team_count
        map_data["spawn_points_by_team"] = {
            k: v for k, v in spawn_points_by_team.items() if v
        }
        if boss_room_meta:
            map_data["boss_room"] = boss_room_meta

    return map_data

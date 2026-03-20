"""
Dungeon Manager — Dungeon lifecycle, floor advancement, and enemy spawning.

Extracted from match_manager.py (Phase 7 of the Match Manager Split Plan).
Handles procedural dungeon generation, door/chest/ground-item state,
exploration tracking, floor transitions, and room-based enemy spawning
with monster rarity integration.
"""

from __future__ import annotations

import random
import uuid

from app.models.match import MatchState, MatchType
from app.models.player import PlayerState, Position, apply_enemy_stats, get_enemy_definition
from app.core.map_loader import (
    load_map, get_spawn_points, get_doors, get_chests, get_room_definitions,
    get_stairs, get_map_dimensions, register_runtime_map, unregister_runtime_map,
)
from app.core.ai_behavior import set_room_bounds, clear_room_bounds
from app.core.ai_exploration import build_room_graph, init_room_discovery
from app.core.wfc.dungeon_generator import generate_dungeon_floor
from app.core.fov_manager import _compute_initial_fov

from app.core.match_store import (
    _active_matches, _player_states, _action_queues, _fov_cache,
)


# ---------------------------------------------------------------------------
# Dungeon map detection
# ---------------------------------------------------------------------------

def _is_static_dungeon_map(map_id: str) -> bool:
    """Check if a map_id refers to a pre-existing static dungeon map file.

    Returns True for static files like 'wfc_dungeon_test_12x8' that exist
    on disk (or are already registered as runtime maps).
    Returns False for placeholder/unknown IDs that need procedural generation.
    """
    try:
        data = load_map(map_id)
        return data.get("map_type") == "dungeon"
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Procedural dungeon generation
# ---------------------------------------------------------------------------

def _generate_procedural_dungeon(match: MatchState) -> None:
    """Generate a WFC procedural dungeon and register it as the match's map.

    Called during start_match() for DUNGEON matches that don't have a static map.
    The generated map is registered as a runtime map with a synthetic map_id
    of 'wfc_<match_id>' so all existing map_loader accessors work seamlessly.

    Phase 12 Feature 5: Procedural Dungeon Integration.
    """
    import logging
    import random as _rng
    logger = logging.getLogger(__name__)

    match_id = match.match_id

    # Derive seed from match_id for determinism
    seed = hash(match_id) & 0xFFFFFFFF
    floor_number = match.current_floor  # Phase 12-5: use current floor number

    # Store dungeon seed for multi-floor generation
    match.dungeon_seed = seed

    # --- Assign a visual theme for this dungeon ---
    DUNGEON_THEMES = [
        'bleeding_catacombs', 'ashen_undercroft', 'drowned_sanctum',
        'hollowed_cathedral', 'iron_depths', 'forgotten_cellar',
        'pale_ossuary', 'silent_vault',
        'fungal_grotto', 'frozen_crypt', 'cursed_shrine',
    ]
    if not match.theme_id:
        # Use the dungeon seed for deterministic but per-match theme selection
        theme_rng = _rng.Random(seed)
        match.theme_id = theme_rng.choice(DUNGEON_THEMES)
    logger.info("Dungeon theme for match %s: %s", match_id, match.theme_id)

    logger.info("Generating procedural dungeon for match %s (seed=%d, floor=%d)",
                match_id, seed, floor_number)

    result = generate_dungeon_floor(seed=seed, floor_number=floor_number)

    if not result.success:
        # Fallback: use an existing static dungeon map if available
        logger.warning(
            "Procedural gen failed for match %s: %s — falling back to static map",
            match_id, result.error,
        )
        return

    # Register the generated map as a runtime map
    wfc_map_id = f"wfc_{match_id}"
    register_runtime_map(wfc_map_id, result.game_map)

    # Update the match config to point to the generated map
    match.config.map_id = wfc_map_id

    # Re-resolve spawn positions with the new map's spawn points
    spawn_points = get_spawn_points(wfc_map_id)
    if spawn_points:
        players = _player_states.get(match_id, {})
        for i, (pid, player) in enumerate(players.items()):
            if player.is_alive and i < len(spawn_points):
                player.position.x = spawn_points[i][0]
                player.position.y = spawn_points[i][1]

    logger.info(
        "Procedural dungeon ready for match %s: %s (%d rooms, %d doors)",
        match_id, wfc_map_id,
        len(result.game_map.get("rooms", [])),
        len(result.game_map.get("doors", [])),
    )


# ---------------------------------------------------------------------------
# Dungeon state initialization
# ---------------------------------------------------------------------------

def _init_dungeon_state(match: MatchState) -> None:
    """Populate door_states, chest_states, and ground_items from the dungeon map data.

    Called once when a dungeon match starts.
    Chest states now include tier info: "unopened:wooden", "unopened:iron", etc.
    PVPVE mode uses location-based centrality for tier rolling instead of floor depth.
    """
    import random as _rng
    from app.core.loot import roll_chest_tier, roll_chest_tier_pvpve

    map_id = match.config.map_id
    doors = get_doors(map_id)
    chests = get_chests(map_id)
    rooms = get_room_definitions(map_id)

    match.door_states = {
        f"{d['x']},{d['y']}": d.get("state", "closed")
        for d in doors
    }

    # Build a lookup of which room (purpose) each chest is in
    floor_number = getattr(match, "current_floor", 1) or 1
    chest_rng = _rng.Random(hash(match.match_id) & 0xFFFFFFFF ^ floor_number)

    is_pvpve = match.config.match_type == MatchType.PVPVE

    # For PVPVE centrality: compute map center from dimensions
    map_center_x, map_center_y, max_dist = 0.0, 0.0, 1.0
    if is_pvpve:
        map_w, map_h = get_map_dimensions(map_id)
        map_center_x = map_w / 2.0
        map_center_y = map_h / 2.0
        # Max possible distance is corner to center
        max_dist = max(1.0, (map_center_x**2 + map_center_y**2) ** 0.5)

    chest_states = {}
    for c in chests:
        cx, cy = c["x"], c["y"]
        key = f"{cx},{cy}"

        # Check if this chest is in a boss room
        is_boss = False
        for room in rooms:
            bounds = room.get("bounds", {})
            if (room.get("purpose") == "boss"
                    and bounds.get("x_min", 0) <= cx <= bounds.get("x_max", 0)
                    and bounds.get("y_min", 0) <= cy <= bounds.get("y_max", 0)):
                is_boss = True
                break

        # Use pre-assigned tier from map data, or roll one
        pre_tier = c.get("tier")
        if pre_tier:
            tier = pre_tier
        elif is_pvpve:
            # PVPVE: compute centrality (0 = edge/spawn, 1 = center/boss)
            dist = ((cx - map_center_x)**2 + (cy - map_center_y)**2) ** 0.5
            centrality = 1.0 - (dist / max_dist)
            centrality = max(0.0, min(1.0, centrality))
            tier = roll_chest_tier_pvpve(
                centrality=centrality,
                is_boss_room=is_boss,
                seed=chest_rng.randint(0, 2**31),
            )
        else:
            tier = roll_chest_tier(
                floor_number=floor_number,
                is_boss_room=is_boss,
                seed=chest_rng.randint(0, 2**31),
            )
        chest_states[key] = f"unopened:{tier}"

    match.chest_states = chest_states
    # Initialize empty ground items dict for loot drops (Phase 4D-2)
    match.ground_items = {}

    # Assign a visual theme if one hasn't been set yet (static dungeon maps)
    if not match.theme_id:
        DUNGEON_THEMES = [
            'bleeding_catacombs', 'ashen_undercroft', 'drowned_sanctum',
            'hollowed_cathedral', 'iron_depths', 'forgotten_cellar',
            'pale_ossuary', 'silent_vault',
            'fungal_grotto', 'frozen_crypt', 'cursed_shrine',
        ]
        theme_rng = _rng.Random(hash(match.match_id) & 0xFFFFFFFF)
        match.theme_id = theme_rng.choice(DUNGEON_THEMES)


# ---------------------------------------------------------------------------
# Exploration state
# ---------------------------------------------------------------------------

def _init_exploration_state(match: MatchState) -> None:
    """Build room graph and initialize per-team discovery tracking.

    Called after _init_dungeon_state so door/chest states are already populated.
    Skipped silently for arena maps (no rooms → no exploration).
    """
    match_id = match.match_id
    map_id = match.config.map_id
    rooms = get_room_definitions(map_id)
    if not rooms:
        return  # Arena map or no rooms — nothing to track

    doors = get_doors(map_id)
    chests = get_chests(map_id)
    build_room_graph(match_id, rooms, doors, chests)

    # Determine active teams
    teams: list[str] = []
    for team_letter, team_list in [("a", match.team_a), ("b", match.team_b),
                                   ("c", match.team_c), ("d", match.team_d)]:
        if team_list:
            teams.append(team_letter)
    init_room_discovery(match_id, teams)


# ---------------------------------------------------------------------------
# Dungeon state accessors
# ---------------------------------------------------------------------------

def get_dungeon_state(match_id: str) -> dict | None:
    """Return dungeon-specific state for a match (door/chest/ground_items states).

    Returns None for non-dungeon matches.
    """
    match = _active_matches.get(match_id)
    if not match:
        return None
    if not match.door_states and not match.chest_states and not match.ground_items:
        return None
    return {
        "door_states": match.door_states,
        "chest_states": match.chest_states,
        "ground_items": match.ground_items,
    }


def get_stairs_info(match_id: str) -> dict:
    """Return stairs positions and unlocked status for stairs interaction.

    Stairs unlock when all team_b enemies on the floor are dead.
    Returns {"positions": [(x,y), ...], "unlocked": bool, "current_floor": int}.
    """
    match = _active_matches.get(match_id)
    if not match:
        return {"positions": [], "unlocked": False, "current_floor": 1}

    # Phase 27C: PVPVE has no stairs (single floor)
    if match.config.match_type == MatchType.PVPVE:
        return {"positions": [], "unlocked": False, "current_floor": 1}

    map_id = match.config.map_id
    stairs_data = get_stairs(map_id)
    positions = [(s["x"], s["y"]) for s in stairs_data]

    # Stairs unlock when all team_b enemies are dead
    players = _player_states.get(match_id, {})
    team_b_alive = any(
        p.is_alive for pid, p in players.items()
        if p.team == "b"
    )
    unlocked = not team_b_alive

    # Persist unlocked state on match
    match.stairs_unlocked = unlocked

    return {
        "positions": positions,
        "unlocked": unlocked,
        "current_floor": match.current_floor,
    }


# ---------------------------------------------------------------------------
# Floor advancement
# ---------------------------------------------------------------------------

def advance_floor(match_id: str) -> dict | None:
    """Generate the next dungeon floor and transition the party.

    Called by tick_loop when turn_result.floor_advance is True.
    1. Increment floor number
    2. Clean up old runtime map
    3. Generate new floor via WFC
    4. Re-init dungeon state (doors, chests)
    5. Remove all team_b enemies
    6. Spawn new enemies
    7. Move surviving party to new spawn points
    8. Reset stairs_unlocked
    9. Recompute FOV

    Returns a dict with the new floor data for broadcasting, or None on failure.
    """
    import logging
    logger = logging.getLogger(__name__)

    match = _active_matches.get(match_id)
    if not match:
        return None

    # Phase 27C: PVPVE is single-floor — no floor advancement
    if match.config.match_type == MatchType.PVPVE:
        return None

    players = _player_states.get(match_id, {})
    old_map_id = match.config.map_id

    # 1. Increment floor
    match.current_floor += 1
    new_floor = match.current_floor
    match.stairs_unlocked = False

    logger.info("Advancing match %s to floor %d", match_id, new_floor)

    # 2. Clean up old runtime map
    unregister_runtime_map(old_map_id)

    # 3. Generate new floor
    seed = match.dungeon_seed
    result = generate_dungeon_floor(seed=seed, floor_number=new_floor)

    if not result.success:
        logger.warning("Floor generation failed for match %s floor %d: %s",
                        match_id, new_floor, result.error)
        # Rollback
        match.current_floor -= 1
        return None

    # Register new map
    wfc_map_id = f"wfc_{match_id}"
    register_runtime_map(wfc_map_id, result.game_map)
    match.config.map_id = wfc_map_id

    # 4. Re-init dungeon state
    _init_dungeon_state(match)
    _init_exploration_state(match)

    # 5. Remove all team_b enemies from player state
    enemy_ids_to_remove = [
        pid for pid, p in players.items()
        if p.team == "b"
    ]
    for eid in enemy_ids_to_remove:
        players.pop(eid, None)
        if eid in match.ai_ids:
            match.ai_ids.remove(eid)
        if eid in match.player_ids:
            match.player_ids.remove(eid)
        if eid in match.team_b:
            match.team_b.remove(eid)

    # Clear AI room bounds and patrol state
    clear_room_bounds(match_id)

    # 6. Spawn new enemies for this floor
    _spawn_dungeon_enemies(match_id)

    # 7. Move surviving party to new spawn points (clustered together)
    spawn_points = get_spawn_points(wfc_map_id)
    alive_party = [
        (pid, p) for pid, p in players.items()
        if p.team == "a" and p.is_alive and not p.extracted
    ]

    # Build enough positions for all party members, even if spawn_points is small.
    # For overflow members, find walkable floor tiles adjacent to the first spawn.
    new_map_data_sp = load_map(wfc_map_id)
    sp_tiles = new_map_data_sp.get("tiles", [])
    sp_legend = new_map_data_sp.get("tile_legend", {})
    sp_walkable = {"floor", "spawn", "corridor", "stairs"}

    def _is_walkable(x: int, y: int) -> bool:
        if 0 <= y < len(sp_tiles) and 0 <= x < len(sp_tiles[0]):
            ch = sp_tiles[y][x]
            return sp_legend.get(ch, "wall") in sp_walkable
        return False

    # If we have fewer spawn points than party members, expand with nearby walkable tiles
    if spawn_points and len(spawn_points) < len(alive_party):
        used = set(spawn_points)
        anchor_x, anchor_y = spawn_points[0]
        # BFS outward from anchor to find nearby walkable tiles
        from collections import deque
        queue_bfs = deque([(anchor_x, anchor_y)])
        visited = {(anchor_x, anchor_y)}
        extra_positions = []
        while queue_bfs and len(spawn_points) + len(extra_positions) < len(alive_party):
            cx, cy = queue_bfs.popleft()
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if (nx, ny) not in visited and _is_walkable(nx, ny):
                    visited.add((nx, ny))
                    if (nx, ny) not in used:
                        extra_positions.append((nx, ny))
                        used.add((nx, ny))
                    queue_bfs.append((nx, ny))
        spawn_points = list(spawn_points) + extra_positions
    elif not spawn_points:
        # No spawn points at all — fallback to first walkable tile for everyone
        for y in range(len(sp_tiles)):
            for x in range(len(sp_tiles[0]) if sp_tiles else 0):
                if _is_walkable(x, y):
                    spawn_points = [(x, y)]
                    break
            if spawn_points:
                break

    for i, (pid, player) in enumerate(alive_party):
        if i < len(spawn_points):
            player.position.x = spawn_points[i][0]
            player.position.y = spawn_points[i][1]
        elif spawn_points:
            # Still overflow — stack on last known spawn point
            player.position.x = spawn_points[-1][0]
            player.position.y = spawn_points[-1][1]
        # Clear action queue for this unit
        queue = _action_queues.get(match_id, {})
        queue.pop(pid, None)
        # Clear auto-target
        player.auto_target_id = None
        player.auto_skill_id = None

    # 8. Clear FOV cache (will be recomputed by tick_loop)
    _fov_cache.pop(match_id, None)

    # 9. Recompute initial FOV for all alive units
    _compute_initial_fov(match_id)

    # 10. Reset portal/channeling state
    match.portal = None
    match.channeling = None

    # Build new floor payload
    map_data = load_map(wfc_map_id)
    tiles = map_data.get("tiles", [])
    tile_legend = map_data.get("tile_legend", {})

    # Build obstacles (wall-only, doors excluded for client)
    wall_chars = {ch for ch, ttype in tile_legend.items() if ttype == "wall"}
    new_obstacles = []
    for y, row in enumerate(tiles):
        for x, ch in enumerate(row):
            if ch in wall_chars:
                new_obstacles.append({"x": x, "y": y})

    # Build player snapshot for the new floor
    players_payload = {}
    for pid, p in players.items():
        entry = {
            "username": p.username,
            "position": {"x": p.position.x, "y": p.position.y},
            "hp": p.hp,
            "max_hp": p.max_hp,
            "is_alive": p.is_alive,
            "is_ready": p.is_ready,
            "unit_type": p.unit_type,
            "team": p.team,
            "class_id": p.class_id,
            "attack_damage": p.attack_damage,
            "ranged_damage": p.ranged_damage,
            "armor": p.armor,
            "vision_range": p.vision_range,
            "ranged_range": p.ranged_range,
            "enemy_type": p.enemy_type,
            "ai_behavior": p.ai_behavior,
            "is_boss": p.is_boss,
            "ai_stance": p.ai_stance,
            # Phase 19 fix: Include advanced stats for floor advance
            "crit_chance": p.crit_chance,
            "crit_damage": p.crit_damage,
            "dodge_chance": p.dodge_chance,
            "damage_reduction_pct": p.damage_reduction_pct,
            "hp_regen": p.hp_regen,
            "life_on_hit": p.life_on_hit,
            "cooldown_reduction_pct": p.cooldown_reduction_pct,
            "skill_damage_pct": p.skill_damage_pct,
            "thorns": p.thorns,
            "gold_find_pct": p.gold_find_pct,
            "magic_find_pct": p.magic_find_pct,
            "armor_pen": p.armor_pen,
            "sprite_variant": p.sprite_variant,
        }
        # Phase 18C: Include monster rarity metadata for enhanced enemies
        if p.monster_rarity and p.monster_rarity != "normal":
            entry["monster_rarity"] = p.monster_rarity
            entry["champion_type"] = p.champion_type
            entry["affixes"] = list(p.affixes) if p.affixes else []
            entry["display_name"] = p.display_name
        if p.is_minion:
            entry["is_minion"] = True
            entry["minion_owner_id"] = p.minion_owner_id
        players_payload[pid] = entry

    logger.info(
        "Floor %d ready for match %s: %d rooms, %d doors, %d enemies",
        new_floor, match_id,
        len(result.game_map.get("rooms", [])),
        len(result.game_map.get("doors", [])),
        sum(1 for p in players.values() if p.team == "b"),
    )

    # Phase 21F: Build lightweight room list for client-side room props
    rooms = get_room_definitions(wfc_map_id)
    dungeon_rooms = [
        {"archetype": r.get("archetype", r.get("purpose", "empty")), "bounds": r["bounds"]}
        for r in rooms if "bounds" in r
    ]

    return {
        "floor_number": new_floor,
        "grid_width": map_data.get("width", 15),
        "grid_height": map_data.get("height", 15),
        "tiles": tiles,
        "tile_legend": tile_legend,
        "obstacles": new_obstacles,
        "door_states": dict(match.door_states),
        "chest_states": dict(match.chest_states),
        "players": players_payload,
        "is_dungeon": True,
        "dungeon_rooms": dungeon_rooms,
    }


# ---------------------------------------------------------------------------
# Dungeon enemy spawning
# ---------------------------------------------------------------------------

def _spawn_dungeon_enemies(match_id: str) -> None:
    """Spawn typed enemies in dungeon rooms based on room enemy_spawns data.

    Reads room definitions from the dungeon map, creates enemy units with
    stats from enemies_config.json, and places them at room-specific positions.
    Each enemy is named by type (e.g. 'Demon-1', 'Skeleton-2', 'Undead Knight').
    Enemies are always on team 'b' (opposing the player party on team 'a').

    Phase 4C: Static spawns only — enemies do not respawn.
    Phase 18C: Apply monster rarity upgrades (champion/rare) from spawn data,
    spawn champion packs, and place rare minions on adjacent tiles.
    Phase 28B: Generate and apply equipment loadouts after rarity upgrades.
    """
    from app.core.monster_rarity import (
        apply_rarity_to_player,
        apply_super_unique_stats,
        create_minions,
        get_champion_type_name,
        get_floor_override,
        get_super_unique,
        load_monster_rarity_config,
        roll_champion_type,
    )

    match = _active_matches.get(match_id)
    if not match:
        return

    players = _player_states.get(match_id, {})
    rooms = get_room_definitions(match.config.map_id)

    # Cache room bounds for AI leashing (Phase 4C)
    set_room_bounds(match_id, rooms)

    # Phase 18C: Load rarity config for minion/champion pack counts
    rarity_config = load_monster_rarity_config()

    # Phase 5 (Spawn Distribution Overhaul): Floor-tier-specific rarity overrides
    floor_override = get_floor_override(getattr(match, 'current_floor', 1))

    # Phase 18C: Build set of occupied tiles (player party) to avoid stacking
    occupied: set[tuple[int, int]] = set()
    for p in players.values():
        if p.is_alive:
            occupied.add((p.position.x, p.position.y))

    # Track enemy name counters for naming: "Demon-1", "Demon-2", etc.
    name_counters: dict[str, int] = {}

    # Phase 18C: Load map tiles for finding adjacent open floor tiles
    map_data = load_map(match.config.map_id)
    map_tiles = map_data.get("tiles", [])
    tile_legend = map_data.get("tile_legend", {})
    walkable_types = {"floor", "spawn", "corridor"}

    def _is_walkable(x: int, y: int) -> bool:
        """Check if a tile is walkable (floor/spawn/corridor)."""
        if 0 <= y < len(map_tiles) and 0 <= x < len(map_tiles[0]):
            ch = map_tiles[y][x]
            return tile_legend.get(ch, "wall") in walkable_types
        return False

    def _find_adjacent_open_tiles(cx: int, cy: int, count: int, room_bounds: dict | None = None) -> list[tuple[int, int]]:
        """Find up to `count` open walkable tiles near (cx, cy).

        Uses BFS outward from the center position. Respects room bounds if given.
        Avoids occupied tiles.
        """
        from collections import deque
        result = []
        visited = {(cx, cy)}
        queue = deque([(cx, cy)])
        while queue and len(result) < count:
            px, py = queue.popleft()
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                if len(result) >= count:
                    break
                nx, ny = px + dx, py + dy
                if (nx, ny) in visited:
                    continue
                visited.add((nx, ny))
                if not _is_walkable(nx, ny):
                    continue
                # Respect room bounds if provided
                if room_bounds:
                    if not (room_bounds["x_min"] <= nx <= room_bounds["x_max"] and
                            room_bounds["y_min"] <= ny <= room_bounds["y_max"]):
                        continue
                if (nx, ny) not in occupied:
                    result.append((nx, ny))
                queue.append((nx, ny))
        return result

    def _register_enemy(ai_id: str, unit: PlayerState) -> None:
        """Register an enemy unit with the match."""
        players[ai_id] = unit
        match.ai_ids.append(ai_id)
        match.player_ids.append(ai_id)
        match.team_b.append(ai_id)
        occupied.add((unit.position.x, unit.position.y))

    for room in rooms:
        enemy_spawns = room.get("enemy_spawns", [])
        if not enemy_spawns:
            continue

        room_id = room.get("id", "unknown")
        room_bounds = room.get("bounds")

        for spawn in enemy_spawns:
            enemy_type = spawn.get("enemy_type")
            if not enemy_type:
                continue  # Skip spawns without a type (legacy format)

            enemy_def = get_enemy_definition(enemy_type)
            if not enemy_def:
                continue  # Unknown enemy type — skip

            # Phase 18C: Read rarity metadata from spawn data
            monster_rarity = spawn.get("monster_rarity", "normal")
            champion_type = spawn.get("champion_type")
            affixes = spawn.get("affixes", [])
            rarity_display_name = spawn.get("display_name")

            # Generate unique ID
            ai_id = f"enemy-{str(uuid.uuid4())[:6]}"

            # Generate name: use rarity display name if present, else "Demon-1" / "Undead Knight"
            is_boss = spawn.get("is_boss", enemy_def.is_boss)
            if rarity_display_name:
                display_name = rarity_display_name
            elif is_boss:
                display_name = enemy_def.name
            else:
                name_counters[enemy_type] = name_counters.get(enemy_type, 0) + 1
                display_name = f"{enemy_def.name}-{name_counters[enemy_type]}"

            enemy_unit = PlayerState(
                player_id=ai_id,
                username=display_name,
                position=Position(x=spawn["x"], y=spawn["y"]),
                unit_type="ai",
                team="b",
                is_ready=True,
            )

            # Apply enemy stats from config
            apply_enemy_stats(enemy_unit, enemy_type, room_id=room_id)

            # Override is_boss if spawn-level flag differs from config
            if is_boss:
                enemy_unit.is_boss = True

            # Phase 18C: Apply monster rarity upgrade if present
            # Phase 18G: Super unique boss replacement — apply fixed stats/affixes
            if monster_rarity == "super_unique":
                su_id = spawn.get("super_unique_id")
                su_config = get_super_unique(su_id) if su_id else None
                if su_config:
                    apply_super_unique_stats(enemy_unit, su_config)
                else:
                    # Fallback: apply as generic super_unique without fixed stats
                    apply_rarity_to_player(
                        enemy_unit,
                        rarity=monster_rarity,
                        champion_type=champion_type,
                        affixes=affixes,
                        display_name=display_name,
                    )
            elif monster_rarity and monster_rarity != "normal":
                apply_rarity_to_player(
                    enemy_unit,
                    rarity=monster_rarity,
                    champion_type=champion_type,
                    affixes=affixes,
                    display_name=display_name,
                )

            # Phase 28B: Monster loadout generation DISABLED (Phase 28-FIX).
            # Dungeon monsters should NOT spawn with player-style gear.
            # generate_enemy_loadout() is kept for reuse by Phase 28E (hero party loadouts).

            _register_enemy(ai_id, enemy_unit)

            # Phase 18C: Champion pack spawning — spawn 1–2 additional champions
            if monster_rarity == "champion":
                champ_tier = rarity_config.get("rarity_tiers", {}).get("champion", {})
                pack_range = champ_tier.get("pack_size", [2, 3])
                # pack_size includes the original, so additional = pack_size - 1
                if isinstance(pack_range, list) and len(pack_range) == 2:
                    total_pack = random.randint(pack_range[0], pack_range[1])
                else:
                    total_pack = 2
                additional_count = max(0, total_pack - 1)

                adjacent_tiles = _find_adjacent_open_tiles(
                    spawn["x"], spawn["y"], additional_count, room_bounds
                )

                for tile_pos in adjacent_tiles:
                    pack_id = f"enemy-{str(uuid.uuid4())[:6]}"
                    name_counters[enemy_type] = name_counters.get(enemy_type, 0) + 1
                    ct_name = get_champion_type_name(champion_type)
                    pack_name = f"{ct_name} {enemy_def.name}-{name_counters[enemy_type]}"

                    pack_unit = PlayerState(
                        player_id=pack_id,
                        username=pack_name,
                        position=Position(x=tile_pos[0], y=tile_pos[1]),
                        unit_type="ai",
                        team="b",
                        is_ready=True,
                    )
                    apply_enemy_stats(pack_unit, enemy_type, room_id=room_id)
                    apply_rarity_to_player(
                        pack_unit,
                        rarity="champion",
                        champion_type=champion_type,
                        affixes=[],
                        display_name=pack_name,
                    )
                    _register_enemy(pack_id, pack_unit)

            # Phase 18C: Rare minion spawning — spawn Normal-tier minions near leader
            elif monster_rarity == "rare":
                rare_tier = rarity_config.get("rarity_tiers", {}).get("rare", {})
                minion_range = rare_tier.get("minion_count", [2, 3])
                if isinstance(minion_range, list) and len(minion_range) == 2:
                    minion_count = random.randint(minion_range[0], minion_range[1])
                else:
                    minion_count = 2

                # Phase 5: Floor-tier override may cap minion count on early floors
                floor_max_minions = floor_override.get("max_rare_minions")
                if floor_max_minions is not None:
                    minion_count = min(minion_count, floor_max_minions)

                minion_datas = create_minions(
                    enemy_unit, enemy_def, minion_count, room_id, random.Random()
                )

                adjacent_tiles = _find_adjacent_open_tiles(
                    spawn["x"], spawn["y"], minion_count, room_bounds
                )

                for i, minion_data in enumerate(minion_datas):
                    if i >= len(adjacent_tiles):
                        break  # Not enough space — spawn fewer minions

                    mx, my = adjacent_tiles[i]
                    minion_id = minion_data["player_id"]

                    name_counters[enemy_type] = name_counters.get(enemy_type, 0) + 1
                    minion_name = f"{enemy_def.name}-{name_counters[enemy_type]}"

                    minion_unit = PlayerState(
                        player_id=minion_id,
                        username=minion_name,
                        position=Position(x=mx, y=my),
                        unit_type="ai",
                        team="b",
                        is_ready=True,
                    )
                    apply_enemy_stats(minion_unit, enemy_type, room_id=room_id)

                    # Mark as minion linked to rare leader
                    minion_unit.minion_owner_id = ai_id
                    minion_unit.is_minion = True
                    minion_unit.monster_rarity = "normal"

                    _register_enemy(minion_id, minion_unit)

            # Phase 18G: Super unique retinue spawning — spawn retinue near boss
            # Retinue entries come from map_exporter with is_retinue=True at the boss position
            # We handle them by spawning as normal enemies on adjacent tiles, linked to the boss
            elif spawn.get("is_retinue") and monster_rarity == "normal":
                # Find adjacent open tile for retinue member
                adjacent_tiles = _find_adjacent_open_tiles(
                    spawn["x"], spawn["y"], 1, room_bounds
                )
                if adjacent_tiles:
                    rx, ry = adjacent_tiles[0]
                    enemy_unit.position.x = rx
                    enemy_unit.position.y = ry
                # If no adjacent tiles available, keep original position (stacking)

    _player_states[match_id] = players

"""
PVPVE Manager — PVPVE match flow: team distribution, dungeon generation, PVE enemy spawning.

Extracted from match_manager.py (Phase 8 of the match-manager split plan).
"""

from __future__ import annotations

import random
import uuid

from app.models.match import MatchState, MatchType
from app.models.player import PlayerState, Position, apply_class_stats, get_all_classes, apply_enemy_stats, get_enemy_definition
from app.core.map_loader import load_map, get_room_definitions, register_runtime_map
from app.core.ai_behavior import set_room_bounds
from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig

from app.core.match_store import (
    _active_matches, _player_states, _hero_ally_map,
)
from app.core.loadout_generator import generate_hero_loadout, _apply_loadout_to_unit


# ---------- PVPVE Match Flow (Phase 27C) ----------


# Team assignment order: diagonal opposites first for max separation
_PVPVE_TEAM_KEYS = ["a", "b", "c", "d"]


def _start_pvpve_match(match_id: str) -> None:
    """Full PVPVE match initialization sequence.

    1. Assign player teams (distribute humans + AI across teams)
    2. Generate procedural PVPVE dungeon
    3. Resolve spawns using per-team spawn zones
    4. Apply class stats
    5. Init dungeon state (doors, chests, ground items)
    6. Spawn PVE enemies on the "pve" team
    7. Compute initial FOV
    """
    import logging
    logger = logging.getLogger(__name__)

    # Import cross-module dependencies from match_manager (orchestrator functions)
    from app.core.match_manager import _resolve_smart_spawns, _apply_lobby_class_selections
    from app.core.hero_manager import _load_heroes_at_match_start
    from app.core.dungeon_manager import _init_dungeon_state, _init_exploration_state

    match = _active_matches.get(match_id)
    if not match:
        return

    logger.info("Starting PVPVE match %s (teams=%d)",
                match_id, match.config.pvpve_team_count)

    # 0.5. Spawn AI hero teams for unoccupied team slots
    _spawn_pvpve_ai_teams(match_id)

    # 1. Distribute players across teams
    _assign_pvpve_teams(match_id)

    # 1b. Load persistent heroes (spawned as AI allies during lobby, need team reassignment)
    _load_heroes_at_match_start(match_id)

    # 2. Generate procedural PVPVE dungeon
    _generate_pvpve_dungeon(match)

    # 3. Resolve spawns — teams spawn in their designated corner zones
    _resolve_smart_spawns(match_id)

    # 4. Apply class stats to all players based on lobby selections
    _apply_lobby_class_selections(match_id)

    # 5. Init dungeon state (doors, chests, ground items)
    _init_dungeon_state(match)
    _init_exploration_state(match)

    # 6. Spawn PVE enemies
    _spawn_pvpve_enemies(match_id)

    logger.info("PVPVE match %s ready: %d teams, %d PVE enemies",
                match_id, match.config.pvpve_team_count,
                len(match.team_pve))


def _spawn_pvpve_ai_teams(match_id: str) -> None:
    """Spawn AI hero teams for PVPVE matches.

    Reads pvpve_ai_team_count and pvpve_ai_team_sizes from config.
    Creates AI hero units with random classes and assigns them to the
    team slots not occupied by human players (fills from team B onward).

    Called before _assign_pvpve_teams() so the units exist when team
    distribution runs.
    """
    import logging
    logger = logging.getLogger(__name__)

    match = _active_matches.get(match_id)
    if not match:
        return

    config = match.config
    ai_team_count = config.pvpve_ai_team_count
    if ai_team_count <= 0:
        return

    team_count = max(2, min(4, config.pvpve_team_count))
    active_teams = _PVPVE_TEAM_KEYS[:team_count]

    # Determine which teams humans actually occupy (use their lobby-chosen team,
    # not index-based round-robin — two players can both be on team A).
    players = _player_states.get(match_id, {})
    humans = [pid for pid in match.player_ids
              if not pid.startswith(("ai-", "enemy-", "hero-", "pvpve-ai-"))]
    human_teams: set[str] = set()
    for pid in humans:
        p = players.get(pid)
        if p and p.team in active_teams:
            human_teams.add(p.team)

    # AI hero teams fill the remaining team slots (non-human teams)
    ai_team_keys = [t for t in active_teams if t not in human_teams]
    # If there are more AI teams requested than available slots, cap it
    ai_team_keys = ai_team_keys[:ai_team_count]

    if not ai_team_keys:
        logger.info("PVPVE match %s: no AI team slots available (all teams have humans)", match_id)
        return

    all_classes = get_all_classes()
    all_class_ids = list(all_classes.keys())
    if not all_class_ids:
        logger.warning("PVPVE match %s: no classes available for AI teams", match_id)
        return

    ai_team_sizes = config.pvpve_ai_team_sizes
    class_name_counts: dict[str, int] = {}

    for team_idx, team_key in enumerate(ai_team_keys):
        # Determine team size: use config list if available, else default 3
        if team_idx < len(ai_team_sizes):
            team_size = max(1, min(5, ai_team_sizes[team_idx]))
        else:
            team_size = 3

        team_label = team_key.upper()
        logger.info("PVPVE match %s: spawning AI team %s with %d units",
                    match_id, team_label, team_size)

        # Pre-select unique classes for this PVPVE team (no duplicates within a team)
        team_pool = list(all_class_ids)
        random.shuffle(team_pool)
        team_class_picks = team_pool[:team_size]

        for i in range(team_size):
            ai_id = f"pvpve-ai-{team_key}-{str(uuid.uuid4())[:6]}"

            ai_class = team_class_picks[i] if i < len(team_class_picks) else random.choice(all_class_ids)
            cls_name = all_classes[ai_class].name if ai_class in all_classes else ai_class
            class_name_counts[cls_name] = class_name_counts.get(cls_name, 0) + 1
            if class_name_counts[cls_name] == 1:
                display_name = f"{cls_name}"
            else:
                display_name = f"{cls_name} {class_name_counts[cls_name]}"

            is_leader = (i == 0)  # First unit per team is the leader

            ai_unit = PlayerState(
                player_id=ai_id,
                username=display_name,
                position=Position(x=0, y=0),  # Will be resolved by smart spawns
                unit_type="ai",
                team=team_key,
                armor=2,
                is_ready=True,
                is_team_leader=is_leader,
            )

            # Non-leaders get hero_id + follow stance so they stick with the
            # team leader via the stance system.  The leader keeps hero_id=None
            # so it falls through to aggressive AI (explore, fight, patrol).
            if not is_leader:
                ai_unit.hero_id = f"pvpve-team-{ai_id}"
                ai_unit.ai_stance = "follow"

            apply_class_stats(ai_unit, ai_class)

            # Give PVPVE AI heroes class-appropriate equipment (mirrors _spawn_ai_units)
            eq, inv = generate_hero_loadout(
                class_id=ai_class,
                class_def=all_classes.get(ai_class),
                floor_number=1,
                match_tier="mid",
            )
            if eq or inv:
                _apply_loadout_to_unit(ai_unit, eq, inv)

            players[ai_id] = ai_unit
            match.ai_ids.append(ai_id)
            match.player_ids.append(ai_id)

    logger.info("PVPVE match %s: spawned %d AI hero teams (%s)",
                match_id, len(ai_team_keys),
                ", ".join(k.upper() for k in ai_team_keys))


def _assign_pvpve_teams(match_id: str) -> None:
    """Distribute players across PVPVE teams.

    - Humans keep their lobby-chosen team when it's a valid active team,
      otherwise fall back to round-robin placement.
    - Host is guaranteed team A if they haven't explicitly changed.
    - PVPVE AI team units (pvpve-ai- prefix) placed on their pre-assigned team
    - Hero allies placed with their owner
    - Generic AI allies distributed with the host's team
    """
    match = _active_matches.get(match_id)
    if not match:
        return

    players = _player_states.get(match_id, {})
    team_count = max(2, min(4, match.config.pvpve_team_count))
    active_teams = _PVPVE_TEAM_KEYS[:team_count]

    # Clear existing team lists
    match.team_a.clear()
    match.team_b.clear()
    match.team_c.clear()
    match.team_d.clear()

    # Separate unit categories
    humans = [pid for pid in match.player_ids
              if not pid.startswith(("ai-", "enemy-", "hero-", "pvpve-ai-"))]
    hero_allies = [pid for pid in match.player_ids if pid.startswith("hero-")]
    ai_units = [pid for pid in match.player_ids if pid.startswith("ai-")]
    pvpve_ai_units = [pid for pid in match.player_ids if pid.startswith("pvpve-ai-")]

    # Build hero-ally → owner mapping so hero allies stay with their owner
    ally_map = _hero_ally_map.get(match_id, {})
    # Map owner username → owner player_id for lookup
    username_to_pid = {}
    for pid in humans:
        p = players.get(pid)
        if p:
            username_to_pid[p.username] = pid

    # Move host to front of human list so they get first pick
    host_id = match.host_id
    if host_id in humans:
        humans.remove(host_id)
        humans.insert(0, host_id)

    team_lists = {
        "a": match.team_a,
        "b": match.team_b,
        "c": match.team_c,
        "d": match.team_d,
    }

    # Track which team each player ends up on
    pid_to_team: dict[str, str] = {}

    # Respect lobby team assignments: use each human's current team if it's
    # one of the active PVPVE teams; otherwise fall back to round-robin.
    rr_index = 0  # round-robin counter for players needing reassignment
    for pid in humans:
        player = players.get(pid)
        lobby_team = player.team if player else None
        if lobby_team in active_teams:
            team_key = lobby_team
        else:
            # Team not valid for this match's team count — assign round-robin
            team_key = active_teams[rr_index % team_count]
            rr_index += 1
        team_lists[team_key].append(pid)
        pid_to_team[pid] = team_key
        if player:
            player.team = team_key

    # Place PVPVE AI team units on their pre-assigned team
    for ai_id in pvpve_ai_units:
        player = players.get(ai_id)
        if player and player.team in team_lists:
            team_lists[player.team].append(ai_id)

    # Place hero allies on the same team as their owner
    for hero_id in hero_allies:
        owner_username = ally_map.get(hero_id)
        owner_pid = username_to_pid.get(owner_username) if owner_username else None
        owner_team = pid_to_team.get(owner_pid, "a") if owner_pid else "a"
        team_lists[owner_team].append(hero_id)
        player = players.get(hero_id)
        if player:
            player.team = owner_team

    # Distribute generic AI allies — keep on their owner's team in PVPVE
    # (labeled "Add AI allies to your own team" in UI).
    # These are spawned pre-match as team "a" allies; keep them with humans.
    for ai_id in ai_units:
        player = players.get(ai_id)
        if not player:
            continue
        # Find the human team this ally was spawned for (originally team "a")
        # In PVPVE the "ai_allies" slider adds allies to the host's team.
        owner_team = "a"
        if owner_team in active_teams:
            team_lists[owner_team].append(ai_id)
            player.team = owner_team
        else:
            # Fallback: first active team
            team_lists[active_teams[0]].append(ai_id)
            player.team = active_teams[0]


def _generate_pvpve_dungeon(match: MatchState) -> None:
    """Generate a WFC procedural dungeon for PVPVE and register as the match's map.

    Uses FloorConfig.for_pvpve() to produce a dungeon with:
    - Corner spawn rooms for each team
    - Center boss arena
    - PVE enemies tagged with team="pve"
    """
    import logging
    import random as _rng
    logger = logging.getLogger(__name__)

    match_id = match.match_id
    config = match.config

    # Derive seed from match_id for determinism
    seed = hash(match_id) & 0xFFFFFFFF
    match.dungeon_seed = seed

    # Assign a visual theme
    DUNGEON_THEMES = [
        'bleeding_catacombs', 'ashen_undercroft', 'drowned_sanctum',
        'hollowed_cathedral', 'iron_depths', 'forgotten_cellar',
        'pale_ossuary', 'silent_vault',
        'fungal_grotto', 'frozen_crypt', 'cursed_shrine',
    ]
    if not match.theme_id:
        theme_rng = _rng.Random(seed)
        match.theme_id = theme_rng.choice(DUNGEON_THEMES)
    logger.info("PVPVE dungeon theme for match %s: %s", match_id, match.theme_id)

    pvpve_config = FloorConfig.for_pvpve(
        seed=seed,
        team_count=config.pvpve_team_count,
        grid_size=config.pvpve_grid_size,
        pve_density=config.pvpve_pve_density,
        loot_density=config.pvpve_loot_density,
        boss_enabled=config.pvpve_boss_enabled,
    )

    logger.info("Generating PVPVE dungeon for match %s (seed=%d, grid=%dx%d, teams=%d)",
                match_id, seed, config.pvpve_grid_size, config.pvpve_grid_size,
                config.pvpve_team_count)

    result = generate_dungeon_floor(config=pvpve_config)

    if not result.success:
        logger.warning(
            "PVPVE dungeon gen failed for match %s: %s — falling back to static map",
            match_id, result.error,
        )
        return

    # Register the generated map as a runtime map
    pvpve_map_id = f"pvpve_{match_id}"
    register_runtime_map(pvpve_map_id, result.game_map)
    match.config.map_id = pvpve_map_id

    logger.info(
        "PVPVE dungeon ready for match %s: %s (%d rooms, %d doors)",
        match_id, pvpve_map_id,
        len(result.game_map.get("rooms", [])),
        len(result.game_map.get("doors", [])),
    )


def _spawn_pvpve_enemies(match_id: str) -> None:
    """Spawn PVE enemies in a PVPVE dungeon.

    Similar to _spawn_dungeon_enemies() but:
    - All enemies are placed on team="pve" instead of team="b"
    - Enemy IDs are tracked in match.state.team_pve
    - Reads the "team" field from spawn data (set by map_exporter to "pve")
    - Champion packs and rare minions work identically

    Phase 27C: PVPVE match manager flow.
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

    # Cache room bounds for AI leashing
    set_room_bounds(match_id, rooms)

    rarity_config = load_monster_rarity_config()
    floor_override = get_floor_override(1)  # PVPVE is single-floor

    # Build set of occupied tiles (all player teams) to avoid stacking
    occupied: set[tuple[int, int]] = set()
    for p in players.values():
        if p.is_alive:
            occupied.add((p.position.x, p.position.y))

    name_counters: dict[str, int] = {}

    # Load map tiles for finding adjacent open floor tiles
    map_data = load_map(match.config.map_id)
    map_tiles = map_data.get("tiles", [])
    tile_legend = map_data.get("tile_legend", {})
    walkable_types = {"floor", "spawn", "corridor"}

    def _is_walkable(x: int, y: int) -> bool:
        if 0 <= y < len(map_tiles) and 0 <= x < len(map_tiles[0]):
            ch = map_tiles[y][x]
            return tile_legend.get(ch, "wall") in walkable_types
        return False

    def _find_adjacent_open_tiles(cx: int, cy: int, count: int,
                                  room_bounds: dict | None = None) -> list[tuple[int, int]]:
        from collections import deque
        result = []
        visited = {(cx, cy)}
        queue = deque([(cx, cy)])
        while queue and len(result) < count:
            px, py = queue.popleft()
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                if len(result) >= count:
                    break
                nx, ny = px + dx, py + dy
                if (nx, ny) in visited:
                    continue
                visited.add((nx, ny))
                if not _is_walkable(nx, ny):
                    continue
                if room_bounds:
                    if not (room_bounds["x_min"] <= nx <= room_bounds["x_max"] and
                            room_bounds["y_min"] <= ny <= room_bounds["y_max"]):
                        continue
                if (nx, ny) not in occupied:
                    result.append((nx, ny))
                queue.append((nx, ny))
        return result

    def _register_pve_enemy(ai_id: str, unit: PlayerState) -> None:
        """Register a PVE enemy unit with the match."""
        players[ai_id] = unit
        match.ai_ids.append(ai_id)
        match.player_ids.append(ai_id)
        match.team_pve.append(ai_id)
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
                continue

            enemy_def = get_enemy_definition(enemy_type)
            if not enemy_def:
                continue

            # Read rarity metadata from spawn data
            monster_rarity = spawn.get("monster_rarity", "normal")
            champion_type = spawn.get("champion_type")
            affixes = spawn.get("affixes", [])
            rarity_display_name = spawn.get("display_name")

            ai_id = f"enemy-{str(uuid.uuid4())[:6]}"

            is_boss = spawn.get("is_boss", enemy_def.is_boss)
            if rarity_display_name:
                display_name = rarity_display_name
            elif is_boss:
                display_name = enemy_def.name
            else:
                name_counters[enemy_type] = name_counters.get(enemy_type, 0) + 1
                display_name = f"{enemy_def.name}-{name_counters[enemy_type]}"

            # Use the team from spawn data (should be "pve" for PVPVE maps)
            enemy_team = spawn.get("team", "pve")

            enemy_unit = PlayerState(
                player_id=ai_id,
                username=display_name,
                position=Position(x=spawn["x"], y=spawn["y"]),
                unit_type="ai",
                team=enemy_team,
                is_ready=True,
            )

            apply_enemy_stats(enemy_unit, enemy_type, room_id=room_id)

            if is_boss:
                enemy_unit.is_boss = True

            # Apply monster rarity upgrades
            if monster_rarity == "super_unique":
                su_id = spawn.get("super_unique_id")
                su_config = get_super_unique(su_id) if su_id else None
                if su_config:
                    apply_super_unique_stats(enemy_unit, su_config)
                else:
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

            _register_pve_enemy(ai_id, enemy_unit)

            # Champion pack spawning
            if monster_rarity == "champion":
                champ_tier = rarity_config.get("rarity_tiers", {}).get("champion", {})
                pack_range = champ_tier.get("pack_size", [2, 3])
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
                        team=enemy_team,
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
                    _register_pve_enemy(pack_id, pack_unit)

            # Rare minion spawning
            elif monster_rarity == "rare":
                rare_tier = rarity_config.get("rarity_tiers", {}).get("rare", {})
                minion_range = rare_tier.get("minion_count", [2, 3])
                if isinstance(minion_range, list) and len(minion_range) == 2:
                    minion_count = random.randint(minion_range[0], minion_range[1])
                else:
                    minion_count = 2

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
                        break

                    mx, my = adjacent_tiles[i]
                    minion_id = minion_data["player_id"]

                    name_counters[enemy_type] = name_counters.get(enemy_type, 0) + 1
                    minion_name = f"{enemy_def.name}-{name_counters[enemy_type]}"

                    minion_unit = PlayerState(
                        player_id=minion_id,
                        username=minion_name,
                        position=Position(x=mx, y=my),
                        unit_type="ai",
                        team=enemy_team,
                        is_ready=True,
                    )
                    apply_enemy_stats(minion_unit, enemy_type, room_id=room_id)

                    minion_unit.minion_owner_id = ai_id
                    minion_unit.is_minion = True
                    minion_unit.monster_rarity = "normal"

                    _register_pve_enemy(minion_id, minion_unit)

            # Super unique retinue spawning
            elif spawn.get("is_retinue") and monster_rarity == "normal":
                adjacent_tiles = _find_adjacent_open_tiles(
                    spawn["x"], spawn["y"], 1, room_bounds
                )
                if adjacent_tiles:
                    rx, ry = adjacent_tiles[0]
                    enemy_unit.position.x = rx
                    enemy_unit.position.y = ry

    _player_states[match_id] = players

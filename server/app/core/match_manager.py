"""
Match Manager — Handles match lifecycle (create, join, start, end).

Coordinates between lobby, Redis state, and the turn system.
Supports AI opponents/allies, team assignment, and match type configuration.
"""

from __future__ import annotations

import random
import time
import uuid

from app.config import settings
from app.models.match import MatchState, MatchStatus, MatchConfig, MatchSummary, MatchType
from app.models.player import PlayerState, Position, apply_class_stats, get_all_classes, apply_enemy_stats, get_enemy_definition
from app.core.map_loader import load_map, get_spawn_points, get_doors, get_chests, get_tiles, is_dungeon_map, get_obstacles, get_obstacles_with_door_states, get_room_definitions, get_wave_spawner_config, register_runtime_map, unregister_runtime_map, get_stairs, get_map_dimensions
from app.core.spawn import assign_spawns
from app.core.ai_behavior import set_room_bounds, clear_room_bounds
from app.core.ai_exploration import build_room_graph, init_room_discovery, clear_exploration_state
from app.core.combat import get_combat_config
from app.core.fov import compute_fov
from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig

# ── Shared state dicts — single source of truth in match_store ──────
from app.core.match_store import (  # noqa: F401  (re-exported for backwards compat)
    _active_matches, _player_states, _action_queues, _fov_cache,
    _lobby_chat, _class_selections, _hero_selections, _hero_ally_map,
    _username_map, _kill_tracker, _combat_stats, _match_timeline,
    _controlled_hero_map, _wave_state, _dev_mode_players,
    MAX_QUEUE_SIZE,
)


def create_match(host_username: str, config: MatchConfig | None = None) -> tuple[MatchState, PlayerState]:
    """Create a new match and add the host as the first player."""
    match_id = str(uuid.uuid4())[:8]
    player_id = str(uuid.uuid4())[:8]

    match_config = config or MatchConfig(
        tick_rate=settings.TICK_RATE_SECONDS,
        max_players=settings.MAX_PLAYERS_PER_MATCH,
    )

    # Load spawn points from the selected map
    # For procedural dungeons, get_spawn_points returns [] (map not generated yet),
    # so the fallback positions are used during the lobby phase.
    spawn_points = get_spawn_points(match_config.map_id)
    if not spawn_points:
        # Fallback defaults
        spawn_points = [(1, 1), (13, 1), (1, 13), (13, 13),
                        (7, 1), (7, 13), (1, 7), (13, 7)]

    match = MatchState(
        match_id=match_id,
        status=MatchStatus.WAITING,
        config=match_config,
        host_id=player_id,
        player_ids=[player_id],
        team_a=[player_id],
        created_at=time.time(),
    )

    host_player = PlayerState(
        player_id=player_id,
        username=host_username,
        position=Position(x=spawn_points[0][0], y=spawn_points[0][1]),
        unit_type="human",
        team="a",
    )

    _active_matches[match_id] = match
    _player_states[match_id] = {player_id: host_player}
    _class_selections[match_id] = {}
    _hero_selections[match_id] = {}
    _hero_ally_map[match_id] = {}
    _username_map[match_id] = {host_username: player_id}
    _kill_tracker[match_id] = {}
    _combat_stats[match_id] = {}
    _match_timeline[match_id] = []

    # Spawn AI units immediately so they appear in lobby player list (Bug #5)
    if match_config.ai_opponents > 0 or match_config.ai_allies > 0:
        _spawn_ai_units(match_id)

    return match, host_player


def join_match(match_id: str, username: str) -> tuple[MatchState, PlayerState] | None:
    """Add a player to an existing match. Returns None if match is full or not found."""
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        return None
    if len(match.player_ids) >= match.config.max_players:
        return None

    player_id = str(uuid.uuid4())[:8]

    # Load spawn points from the selected map
    spawn_points = get_spawn_points(match.config.map_id)
    if not spawn_points:
        spawn_points = [(1, 1), (13, 1), (1, 13), (13, 13),
                        (7, 1), (7, 13), (1, 7), (13, 7)]

    spawn_index = len(match.player_ids)
    spawn = spawn_points[spawn_index % len(spawn_points)]

    player = PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=spawn[0], y=spawn[1]),
        unit_type="human",
        team="a",
    )

    match.player_ids.append(player_id)
    match.team_a.append(player_id)
    _player_states[match_id][player_id] = player

    # Track username mapping for persistence
    if match_id not in _username_map:
        _username_map[match_id] = {}
    _username_map[match_id][username] = player_id

    return match, player


def get_match(match_id: str) -> MatchState | None:
    return _active_matches.get(match_id)


def get_match_players(match_id: str) -> dict[str, PlayerState]:
    return _player_states.get(match_id, {})


def list_matches() -> list[MatchSummary]:
    """Return summaries of all joinable matches."""
    summaries = []
    for match in _active_matches.values():
        summaries.append(MatchSummary(
            match_id=match.match_id,
            status=match.status,
            player_count=len(match.player_ids),
            max_players=match.config.max_players,
            map_id=match.config.map_id,
            host_id=match.host_id,
            match_type=match.config.match_type,
            ai_opponents=match.config.ai_opponents,
            ai_allies=match.config.ai_allies,
        ))
    return summaries


def set_player_ready(match_id: str, player_id: str, ready: bool = True) -> bool:
    """Set a player's ready status. Returns True if all human players are now ready."""
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return False
    player.is_ready = ready

    # Check if all HUMAN players are ready and we have minimum humans
    # AI units are always ready and don't count toward min player threshold
    match = _active_matches.get(match_id)
    if not match:
        return False

    human_players = {pid: p for pid, p in players.items() if p.unit_type == "human"}

    min_needed = settings.MIN_PLAYERS_TO_START
    if match.config.match_type != MatchType.PVP:
        min_needed = 1  # Solo PvE and Mixed can start with 1 human

    all_ready = (
        len(human_players) >= min_needed
        and all(p.is_ready for p in human_players.values())
    )
    return all_ready


def start_match(match_id: str) -> bool:
    """Transition match from WAITING to IN_PROGRESS.

    AI units are already spawned during lobby phase (visible in lobby list).
    On start, re-resolves all spawn positions using the smart spawn system
    so teams are properly grouped based on final team assignments.
    """
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        return False

    # AI units are already in _player_states from lobby phase.
    # Ensure they exist (in case config was changed and AI re-spawned).
    _ensure_ai_spawned(match_id)

    # --- Propagate host-selected theme from config to match state ---
    if match.config.theme_id:
        match.theme_id = match.config.theme_id

    # --- Phase 27C: PVPVE match initialization ---
    if match.config.match_type == MatchType.PVPVE:
        _start_pvpve_match(match_id)
    else:
        # --- Procedural dungeon generation (Phase 12 Feature 5) ---
        # Must run BEFORE smart spawns so the generated map is available for load_map()
        if match.config.match_type == MatchType.DUNGEON and not _is_static_dungeon_map(match.config.map_id):
            _generate_procedural_dungeon(match)

        # --- Smart Spawn: re-resolve all positions based on final teams ---
        _resolve_smart_spawns(match_id)

        # --- Apply class stats to all players based on lobby selections ---
        _apply_lobby_class_selections(match_id)

        # --- Load persistent heroes for dungeon matches (4E-2) ---
        _load_heroes_at_match_start(match_id)

        # --- Dungeon state initialization (4B-1) + enemy spawning (4C) ---
        if match.config.match_type == MatchType.DUNGEON or is_dungeon_map(match.config.map_id):
            _init_dungeon_state(match)
            _init_exploration_state(match)
            _spawn_dungeon_enemies(match_id)

    # --- Wave spawner initialization (if map has wave_spawner config) ---
    _init_wave_state(match_id)

    match.status = MatchStatus.IN_PROGRESS
    match.current_turn = 0

    # --- Phase 16B: Clear item/loot config caches so Item Forge changes take effect ---
    from app.core.loot import clear_caches as clear_loot_caches
    from app.core.item_generator import clear_generator_caches
    clear_loot_caches()
    clear_generator_caches()

    # --- Compute initial FOV for all alive units so first frame has fog ---
    _compute_initial_fov(match_id)

    # Clear lobby chat and class selections on match start (hero_selections kept for post-match)
    _lobby_chat.pop(match_id, None)
    _class_selections.pop(match_id, None)

    return True


def _spawn_ai_units(match_id: str) -> None:
    """Spawn AI opponents and allies based on match config.

    Called during lobby phase so AI appear in lobby player list.
    Clears any existing AI first to support config changes.
    """
    match = _active_matches.get(match_id)
    if not match:
        return

    # Remove existing AI units first (supports config changes in lobby)
    _clear_ai_units(match_id)

    config = match.config
    num_opponents = config.ai_opponents
    num_allies = config.ai_allies

    if num_opponents == 0 and num_allies == 0:
        return

    # Load spawn points from map
    spawn_points = get_spawn_points(config.map_id)
    if not spawn_points:
        spawn_points = [(1, 1), (13, 1), (1, 13), (13, 13),
                        (7, 1), (7, 13), (1, 7), (13, 7)]

    # Figure out which spawn points are already taken by humans
    players = _player_states.get(match_id, {})
    human_count = len([pid for pid in match.player_ids if not pid.startswith("ai-")])

    # Get available class IDs for random AI assignment
    all_classes = get_all_classes()
    all_class_ids = list(all_classes.keys())
    # Track how many of each class name are used so duplicates get numbered
    class_name_counts: dict[str, int] = {}

    # Pre-select unique classes for ally slots (no duplicates within the team)
    ally_classes: list[str] = []
    if all_class_ids:
        # Lock in any manually-specified classes first
        specified: list[str] = []
        random_slots: list[int] = []
        for i in range(num_allies):
            if i < len(config.ai_ally_classes) and config.ai_ally_classes[i] and config.ai_ally_classes[i] in all_class_ids:
                specified.append(config.ai_ally_classes[i])
            else:
                specified.append("")
                random_slots.append(i)
        # Build pool excluding already-specified classes
        used = {c for c in specified if c}
        pool = [c for c in all_class_ids if c not in used]
        random.shuffle(pool)
        for idx in random_slots:
            if pool:
                specified[idx] = pool.pop()
            else:
                # More slots than classes — fallback to full pool (shouldn't happen with 11 classes / 5 max)
                specified[idx] = random.choice(all_class_ids)
        ally_classes = specified

    # Spawn AI allies (team A)
    for i in range(num_allies):
        ai_id = f"ai-{str(uuid.uuid4())[:6]}"
        spawn_idx = (human_count + i) % len(spawn_points)

        ai_unit = PlayerState(
            player_id=ai_id,
            username=f"AI Ally {i + 1}",
            position=Position(x=spawn_points[spawn_idx][0], y=spawn_points[spawn_idx][1]),
            unit_type="ai",
            team="a",
            armor=2,
            is_ready=True,  # AI are always ready
        )

        # Enable stance-based follow so generic AI allies stick with the
        # human player instead of using enemy-style patrol AI.
        ai_unit.hero_id = f"generic-{ai_id}"
        ai_unit.ai_stance = "follow"

        # Assign pre-selected unique class
        if ally_classes:
            ai_class = ally_classes[i]
            apply_class_stats(ai_unit, ai_class)
            # Phase 28E: Give AI allies class-appropriate equipment
            eq, inv = generate_hero_loadout(
                class_id=ai_class,
                class_def=all_classes.get(ai_class),
                floor_number=1,
                match_tier="mid",
            )
            if eq or inv:
                _apply_loadout_to_unit(ai_unit, eq, inv)
            # Name AI after its class (e.g. "Crusader", "Mage 2")
            cls_name = all_classes[ai_class].name if ai_class in all_classes else ai_class
            class_name_counts[cls_name] = class_name_counts.get(cls_name, 0) + 1
            if class_name_counts[cls_name] == 1:
                ai_unit.username = cls_name
            else:
                ai_unit.username = f"{cls_name} {class_name_counts[cls_name]}"

        players[ai_id] = ai_unit
        match.ai_ids.append(ai_id)
        match.player_ids.append(ai_id)
        match.team_a.append(ai_id)

    # Pre-select unique classes for opponent slots (no duplicates within the team)
    opponent_classes: list[str] = []
    if all_class_ids:
        specified_opp: list[str] = []
        random_slots_opp: list[int] = []
        for i in range(num_opponents):
            if i < len(config.ai_opponent_classes) and config.ai_opponent_classes[i] and config.ai_opponent_classes[i] in all_class_ids:
                specified_opp.append(config.ai_opponent_classes[i])
            else:
                specified_opp.append("")
                random_slots_opp.append(i)
        used_opp = {c for c in specified_opp if c}
        pool_opp = [c for c in all_class_ids if c not in used_opp]
        random.shuffle(pool_opp)
        for idx in random_slots_opp:
            if pool_opp:
                specified_opp[idx] = pool_opp.pop()
            else:
                specified_opp[idx] = random.choice(all_class_ids)
        opponent_classes = specified_opp

    # Spawn AI opponents (team B)
    offset = human_count + num_allies
    for i in range(num_opponents):
        ai_id = f"ai-{str(uuid.uuid4())[:6]}"
        spawn_idx = (offset + i) % len(spawn_points)

        ai_unit = PlayerState(
            player_id=ai_id,
            username=f"AI Opponent {i + 1}",
            position=Position(x=spawn_points[spawn_idx][0], y=spawn_points[spawn_idx][1]),
            unit_type="ai",
            team="b",
            armor=2,
            is_ready=True,  # AI are always ready
        )

        # Assign pre-selected unique class
        if opponent_classes:
            ai_class = opponent_classes[i]
            apply_class_stats(ai_unit, ai_class)
            # Phase 28E: Give AI opponents class-appropriate equipment
            eq, inv = generate_hero_loadout(
                class_id=ai_class,
                class_def=all_classes.get(ai_class),
                floor_number=1,
                match_tier="mid",
            )
            if eq or inv:
                _apply_loadout_to_unit(ai_unit, eq, inv)
            # Name AI after its class (e.g. "Crusader", "Mage 2")
            cls_name = all_classes[ai_class].name if ai_class in all_classes else ai_class
            class_name_counts[cls_name] = class_name_counts.get(cls_name, 0) + 1
            if class_name_counts[cls_name] == 1:
                ai_unit.username = cls_name
            else:
                ai_unit.username = f"{cls_name} {class_name_counts[cls_name]}"

        players[ai_id] = ai_unit
        match.ai_ids.append(ai_id)
        match.player_ids.append(ai_id)
        match.team_b.append(ai_id)

    _player_states[match_id] = players


def _clear_ai_units(match_id: str) -> None:
    """Remove all AI units from a match. Used before re-spawning on config change."""
    match = _active_matches.get(match_id)
    if not match:
        return
    players = _player_states.get(match_id, {})

    for ai_id in list(match.ai_ids):
        players.pop(ai_id, None)
        if ai_id in match.player_ids:
            match.player_ids.remove(ai_id)
        if ai_id in match.team_a:
            match.team_a.remove(ai_id)
        if ai_id in match.team_b:
            match.team_b.remove(ai_id)
        if ai_id in match.team_c:
            match.team_c.remove(ai_id)
        if ai_id in match.team_d:
            match.team_d.remove(ai_id)

    match.ai_ids.clear()


def _ensure_ai_spawned(match_id: str) -> None:
    """Ensure AI units exist before match start. No-op if already spawned."""
    match = _active_matches.get(match_id)
    if not match:
        return
    config = match.config
    if (config.ai_opponents + config.ai_allies) == 0:
        return
    # If AI are already in player_states, nothing to do
    if match.ai_ids:
        return
    _spawn_ai_units(match_id)


def _apply_lobby_class_selections(match_id: str) -> None:
    """Apply class stats to human players based on their lobby class selections.

    Called at match start. AI units already have classes assigned at spawn time.
    Players without a class selection keep default stats (backward compat).
    """
    selections = _class_selections.get(match_id, {})
    players = _player_states.get(match_id, {})

    for pid, class_id in selections.items():
        player = players.get(pid)
        if player and player.unit_type == "human" and class_id:
            apply_class_stats(player, class_id)


def _resolve_smart_spawns(match_id: str) -> None:
    """Re-calculate all player positions using the smart spawn system.

    Called at match start so team formations reflect final lobby assignments.
    Determines FFA vs. team mode and delegates to assign_spawns().
    """
    match = _active_matches.get(match_id)
    if not match:
        return

    players = _player_states.get(match_id, {})
    if not players:
        return

    # Load full map data for spawn logic
    map_data = load_map(match.config.map_id)

    # Build team rosters from current team assignments
    team_rosters: dict[str, list[str]] = {
        "a": list(match.team_a),
        "b": list(match.team_b),
        "c": list(match.team_c),
        "d": list(match.team_d),
    }

    # Determine FFA vs team mode:
    # FFA only when every occupied team has at most 1 player (true free-for-all).
    # If any team has 2+ members they should spawn together in formation.
    # Exception: Dungeon matches always use team spawning so the party
    # spawns in a compact formation together instead of being scattered.
    max_team_size = max((len(r) for r in team_rosters.values()), default=0)
    is_dungeon = (match.config.match_type in (MatchType.DUNGEON, MatchType.PVPVE)
                  or is_dungeon_map(match.config.map_id))
    is_ffa = max_team_size <= 1 and not is_dungeon

    # Compute new positions
    spawn_map = assign_spawns(team_rosters, map_data, is_ffa=is_ffa)

    # Apply new positions to player states
    for pid, (x, y) in spawn_map.items():
        player = players.get(pid)
        if player:
            player.position = Position(x=x, y=y)


def end_match(match_id: str) -> None:
    """Mark match as finished and persist surviving heroes."""
    match = _active_matches.get(match_id)
    if match:
        # Post-match persistence: save surviving heroes' loot + gold
        _persist_post_match(match_id)
        match.status = MatchStatus.FINISHED


def remove_match(match_id: str) -> None:
    """Clean up match data."""
    _active_matches.pop(match_id, None)
    _player_states.pop(match_id, None)
    _action_queues.pop(match_id, None)
    _fov_cache.pop(match_id, None)
    _lobby_chat.pop(match_id, None)
    _class_selections.pop(match_id, None)
    _hero_selections.pop(match_id, None)
    _hero_ally_map.pop(match_id, None)
    _username_map.pop(match_id, None)
    _kill_tracker.pop(match_id, None)
    _combat_stats.pop(match_id, None)
    _match_timeline.pop(match_id, None)
    _wave_state.pop(match_id, None)
    _dev_mode_players.pop(match_id, None)
    clear_room_bounds(match_id)  # Phase 4C: clean up AI room bounds
    clear_exploration_state(match_id)  # Phase SE-A: clean up exploration state

    # Phase 12-5: clean up runtime-generated dungeon map
    wfc_map_id = f"wfc_{match_id}"
    unregister_runtime_map(wfc_map_id)
    # Phase 27C: clean up PVPVE runtime map
    pvpve_map_id = f"pvpve_{match_id}"
    unregister_runtime_map(pvpve_map_id)


def remove_player(match_id: str, player_id: str) -> str | None:
    """Remove a player from a match (disconnect / leave handling).

    Cleans up player_ids, team lists, action queues, and player state.
    During lobby phase, fully removes the player entry.
    During in-progress phase, marks player as dead (for combat resolution).
    Auto-cleans empty waiting matches.
    Returns the removed player's username (for broadcast), or None.
    """
    match = _active_matches.get(match_id)
    username = None
    if not match:
        return None

    # Check if player is actually in this match
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player and player_id not in match.player_ids:
        return None  # Already removed — prevent double-removal broadcasts

    if player:
        username = player.username

    # Remove from player_ids and team lists
    if player_id in match.player_ids:
        match.player_ids.remove(player_id)
    if player_id in match.team_a:
        match.team_a.remove(player_id)
    if player_id in match.team_b:
        match.team_b.remove(player_id)
    if player_id in match.team_c:
        match.team_c.remove(player_id)
    if player_id in match.team_d:
        match.team_d.remove(player_id)

    if match.status == MatchStatus.WAITING:
        # Lobby phase: fully remove the player entry so they don't ghost
        players.pop(player_id, None)
    else:
        # In-progress: mark dead for combat resolution
        if player:
            player.is_alive = False

    # Clear player's action queue
    queue = _action_queues.get(match_id, {})
    queue.pop(player_id, None)

    # Clean up empty waiting matches so they don't linger in the lobby list
    human_ids = [pid for pid in match.player_ids if not pid.startswith("ai-")]
    if match.status == MatchStatus.WAITING and len(human_ids) == 0:
        remove_match(match_id)

    return username


def change_player_team(match_id: str, player_id: str, new_team: str) -> bool:
    """Move a player to a different team ('a', 'b', 'c', or 'd').

    Only allowed while match is in WAITING status.
    Returns True on success, False on failure.
    """
    if new_team not in ("a", "b", "c", "d"):
        return False
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        return False
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return False

    # Remove from all team lists
    for team_list in (match.team_a, match.team_b, match.team_c, match.team_d):
        if player_id in team_list:
            team_list.remove(player_id)

    # Add to new team
    team_map = {"a": match.team_a, "b": match.team_b, "c": match.team_c, "d": match.team_d}
    team_map[new_team].append(player_id)
    player.team = new_team
    return True


def get_player_username(match_id: str, player_id: str) -> str | None:
    """Get a player's username by ID."""
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    return player.username if player else None


# ---------- Action Queue — extracted to action_queue.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.action_queue import (  # noqa: E402, F401
    queue_action,
    pop_next_actions,
    get_and_clear_actions,
    clear_player_queue,
    remove_last_action,
    get_player_queue,
)


# ---------- Auto-Target (Phase 10A) — extracted to auto_target.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.auto_target import (  # noqa: E402, F401
    set_auto_target,
    clear_auto_target,
    get_auto_target,
    _get_skill_effective_range,
    _is_in_skill_range,
    generate_auto_target_action,
    _generate_move_toward,
)


def increment_turn(match_id: str) -> int:
    """Increment and return the new turn number."""
    match = _active_matches.get(match_id)
    if match:
        match.current_turn += 1
        return match.current_turn
    return 0


# ---------- FOV Cache & Dev Mode — extracted to fov_manager.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.fov_manager import (  # noqa: E402, F401
    _compute_initial_fov,
    set_fov_cache,
    get_fov_cache,
    get_team_fov,
    set_dev_mode,
    is_dev_mode,
)


# ---------- Payload Builders — extracted to match_payloads.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.match_payloads import (  # noqa: E402, F401
    get_match_start_payload,
    get_match_start_payload_for_player,
    get_player_joined_payload,
    get_lobby_players_payload,
    get_players_snapshot,
)


def get_alive_count(match_id: str) -> int:
    """Return the number of alive players in a match."""
    players = _player_states.get(match_id, {})
    return sum(1 for p in players.values() if p.is_alive)


# ---------- FOV cache & dev-mode accessors live in fov_manager.py ----------
# (re-exported above)

def get_match_teams(match_id: str) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (team_a, team_b, team_c, team_d) ID lists for a match."""
    match = _active_matches.get(match_id)
    if not match:
        return [], [], [], []
    return list(match.team_a), list(match.team_b), list(match.team_c), list(match.team_d)


def get_ai_ids(match_id: str) -> list[str]:
    """Return list of AI unit IDs in a match."""
    match = _active_matches.get(match_id)
    if not match:
        return []
    return list(match.ai_ids)


# ---------- Party Control — extracted to party_manager.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.party_manager import (  # noqa: E402, F401
    is_party_member,
    set_party_control,
    release_party_control,
    select_all_party,
    release_all_party,
    queue_group_action,
    queue_group_batch_actions,
    get_controlled_unit_ids,
    set_unit_stance,
    set_all_stances,
    get_party_members,
)


# ---------- Lobby Config — extracted to lobby_config.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.lobby_config import (  # noqa: E402, F401
    select_class,
    get_class_selection,
    add_lobby_message,
    get_lobby_chat,
    update_match_config,
    get_match_config_payload,
    spawn_lobby_ai,
)


# ---------- PVPVE Manager — extracted to pvpve_manager.py (Phase 8) ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.pvpve_manager import (  # noqa: E402, F401
    _start_pvpve_match, _spawn_pvpve_ai_teams, _assign_pvpve_teams,
    _generate_pvpve_dungeon, _spawn_pvpve_enemies, _PVPVE_TEAM_KEYS,
)


# ── Re-exports from dungeon_manager (Phase 7 extraction) ───────────
from app.core.dungeon_manager import (  # noqa: E402, F401
    _is_static_dungeon_map, _generate_procedural_dungeon,
    _init_dungeon_state, _init_exploration_state,
    get_dungeon_state, get_stairs_info, advance_floor,
    _spawn_dungeon_enemies,
)


# ── Re-exports from loadout_generator (Phase 6 extraction) ─────────
from app.core.loadout_generator import (  # noqa: E402, F401
    generate_enemy_loadout, _apply_loadout_to_unit, generate_hero_loadout,
    _RARITY_TIERS, _MONSTER_RARITY_BONUS, _CLASS_ARMOR_POOL, _MATCH_TIER_BONUS,
)


# ---------- Hero Persistence helpers (Phase 4E-2) — extracted to hero_manager.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.hero_manager import (  # noqa: E402, F401
    MAX_PARTY_SIZE,
    MAX_DUNGEON_PARTY,
    MAX_TEAM_SIZE,
    get_team_slots_remaining,
    get_all_team_slots,
    get_dungeon_slots_available,
    select_heroes,
    select_hero,
    select_roster_heroes,
    _spawn_hero_ally,
    _remove_hero_ally,
    get_hero_selection,
    _load_heroes_at_match_start,
    _apply_hero_equipment_bonuses,
    handle_hero_permadeath,
    track_kill,
    get_kill_tracker,
    track_damage_dealt,
    track_damage_taken,
    track_healing_done,
    track_items_looted,
    track_turn_survived,
    get_combat_stats,
    record_turn_events,
    save_match_report,
    _persist_post_match,
    get_match_end_payload,
    validate_dungeon_hero_selections,
)


# ---------- Equipment helpers (Phase 4D-2) — extracted to equipment_manager.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.equipment_manager import (  # noqa: E402, F401
    equip_item,
    unequip_item,
    destroy_item,
    _apply_equipment_stats,
    _remove_equipment_stats,
    transfer_item_in_match,
    get_party_member_inventory,
    dev_get_unit_inventory,
)


# ---------- Wave Spawner System (extracted to wave_spawner.py) ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.wave_spawner import (  # noqa: E402, F401
    _init_wave_state,
    get_wave_state,
    check_wave_clear,
    _spawn_next_wave,
    advance_wave_if_cleared,
    is_wave_map,
    all_waves_complete,
)

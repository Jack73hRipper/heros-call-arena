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
from app.core.map_loader import load_map, get_spawn_points, get_doors, get_chests, get_tiles, is_dungeon_map, get_obstacles, get_obstacles_with_door_states, get_room_definitions, get_wave_spawner_config, register_runtime_map, unregister_runtime_map, get_stairs
from app.core.spawn import assign_spawns
from app.core.ai_behavior import set_room_bounds, clear_room_bounds
from app.core.combat import get_combat_config
from app.core.fov import compute_fov
from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig


# In-memory store for prototype (backed by Redis in service layer)
_active_matches: dict[str, MatchState] = {}
_player_states: dict[str, dict[str, PlayerState]] = {}  # match_id -> {unit_id -> PlayerState}

# Action queue: match_id -> {player_id -> [PlayerAction, ...]} (persistent queue, max 10)
_action_queues: dict[str, dict[str, list]] = {}

# Per-unit FOV cache: match_id -> {unit_id -> set of visible (x,y)}
_fov_cache: dict[str, dict[str, set[tuple[int, int]]]] = {}

# Lobby chat messages: match_id -> [{sender, message, timestamp}, ...]
_lobby_chat: dict[str, list[dict]] = {}

# Class selection per player in lobby: match_id -> {player_id -> class_id}
_class_selections: dict[str, dict[str, str]] = {}

# Hero selection per player in lobby: match_id -> {player_id -> [hero_id, ...]}
# Supports up to 4 heroes per player for dungeon runs
_hero_selections: dict[str, dict[str, list[str]]] = {}

# Hero ally mapping: match_id -> {ai_unit_id -> owner_username}
# Tracks which AI allies are hero-backed so persistence/permadeath works
_hero_ally_map: dict[str, dict[str, str]] = {}

# Username-to-player_id mapping within a match (for persistence lookups)
# match_id -> {username -> player_id}
_username_map: dict[str, dict[str, str]] = {}

# Per-match kill tracker for gold rewards: match_id -> {player_id -> {enemy_kills: int, boss_kills: int}}
_kill_tracker: dict[str, dict[str, dict[str, int]]] = {}

# Per-match combat stats tracker: match_id -> {player_id -> {damage_dealt, damage_taken, healing_done, items_looted, turns_survived}}
_combat_stats: dict[str, dict[str, dict[str, int]]] = {}

# Per-match turn-by-turn timeline for Arena Analyst: match_id -> [turn_entry, ...]
_match_timeline: dict[str, list[dict]] = {}

# Wave spawner state: match_id -> {current_wave, total_waves, wave_config, spawning_active}
_wave_state: dict[str, dict] = {}

MAX_QUEUE_SIZE = 10


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

    print(f"[create_match] OK: match_id={match_id} player_id={player_id} "
          f"username={host_username} active_matches={list(_active_matches.keys())}")

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

        # Use specified class if available, otherwise random
        if all_class_ids:
            if i < len(config.ai_ally_classes) and config.ai_ally_classes[i] and config.ai_ally_classes[i] in all_class_ids:
                ai_class = config.ai_ally_classes[i]
            else:
                ai_class = random.choice(all_class_ids)
            apply_class_stats(ai_unit, ai_class)
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

        # Use specified class if available, otherwise random
        if all_class_ids:
            if i < len(config.ai_opponent_classes) and config.ai_opponent_classes[i] and config.ai_opponent_classes[i] in all_class_ids:
                ai_class = config.ai_opponent_classes[i]
            else:
                ai_class = random.choice(all_class_ids)
            apply_class_stats(ai_unit, ai_class)
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


def select_class(match_id: str, player_id: str, class_id: str) -> bool:
    """Set a player's class selection in lobby. Returns True on success."""
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        print(f"[select_class] FAIL: match not found or not WAITING "
              f"(match_id={match_id}, found={match is not None}, "
              f"status={match.status if match else 'N/A'}, "
              f"active_matches={list(_active_matches.keys())})")
        return False

    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        print(f"[select_class] FAIL: player {player_id} not found in match {match_id}. "
              f"Known player_ids: {list(players.keys())}")
        return False

    # Validate the class_id exists
    all_classes = get_all_classes()
    if class_id not in all_classes:
        return False

    if match_id not in _class_selections:
        _class_selections[match_id] = {}
    _class_selections[match_id][player_id] = class_id

    # Also set class_id on the player model for lobby display
    player.class_id = class_id
    return True


def get_class_selection(match_id: str, player_id: str) -> str | None:
    """Get a player's selected class in lobby."""
    return _class_selections.get(match_id, {}).get(player_id)


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
    # FFA when only one team has players (e.g., PvP with everyone on team A)
    # Exception: Dungeon matches always use team spawning so the party
    # spawns in a compact formation together instead of being scattered.
    active_teams = sum(1 for roster in team_rosters.values() if roster)
    is_dungeon = (match.config.match_type in (MatchType.DUNGEON, MatchType.PVPVE)
                  or is_dungeon_map(match.config.map_id))
    is_ffa = active_teams <= 1 and not is_dungeon

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
    clear_room_bounds(match_id)  # Phase 4C: clean up AI room bounds

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


# ---------- Action Queue ----------

def queue_action(match_id: str, player_id: str, action) -> bool | str:
    """Append an action to a player's persistent queue.

    Returns True on success, or an error string on failure.

    Phase 10B: Queueing a repositioning action (MOVE, INTERACT, LOOT) clears
    auto-target since it signals a new navigational intent.
    Combat actions (SKILL, ATTACK, RANGED_ATTACK, USE_ITEM) preserve
    auto-target so auto-attacks resume automatically after the queued
    action resolves — "skill weaving" without losing pursuit.
    """
    from app.models.actions import ActionType

    if match_id not in _action_queues:
        _action_queues[match_id] = {}
    # Verify player is alive
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player or not player.is_alive:
        return "Cannot queue action — you are dead"

    if player_id not in _action_queues[match_id]:
        _action_queues[match_id][player_id] = []

    if len(_action_queues[match_id][player_id]) >= MAX_QUEUE_SIZE:
        return f"Queue full — maximum {MAX_QUEUE_SIZE} actions"

    # Phase 10B / Balance-pass: Only repositioning actions break auto-target.
    # Combat actions (skills, attacks, items) preserve the pursuit so
    # auto-attacks fill every tick the player isn't actively casting.
    _PRESERVE_AUTO_TARGET = {
        ActionType.SKILL,
        ActionType.ATTACK,
        ActionType.RANGED_ATTACK,
        ActionType.USE_ITEM,
        ActionType.WAIT,
    }
    if player.auto_target_id is not None:
        action_type = getattr(action, 'action_type', None)
        if action_type not in _PRESERVE_AUTO_TARGET:
            player.auto_target_id = None
            player.auto_skill_id = None

    _action_queues[match_id][player_id].append(action)
    return True


def pop_next_actions(match_id: str) -> dict:
    """Pop the first action from each player's queue for this tick.

    Returns {player_id: PlayerAction} for players who have queued actions.
    Remaining actions stay in the queue for future ticks.
    """
    match_queues = _action_queues.get(match_id, {})
    actions = {}
    for pid, queue in list(match_queues.items()):
        if queue:
            actions[pid] = queue.pop(0)
        # Clean up empty queues
        if not queue:
            match_queues.pop(pid, None)
    return actions


def get_and_clear_actions(match_id: str) -> dict:
    """DEPRECATED — kept for backward compatibility.
    Use pop_next_actions() for the persistent queue model.
    """
    return pop_next_actions(match_id)


def clear_player_queue(match_id: str, player_id: str) -> int:
    """Clear all queued actions for a player. Returns number of actions cleared."""
    match_queues = _action_queues.get(match_id, {})
    queue = match_queues.get(player_id, [])
    count = len(queue)
    match_queues.pop(player_id, None)
    return count


def remove_last_action(match_id: str, player_id: str) -> bool:
    """Remove the last queued action for a player. Returns True if an action was removed."""
    match_queues = _action_queues.get(match_id, {})
    queue = match_queues.get(player_id, [])
    if queue:
        queue.pop()
        if not queue:
            match_queues.pop(player_id, None)
        return True
    return False


def get_player_queue(match_id: str, player_id: str) -> list:
    """Get a copy of a player's current action queue."""
    match_queues = _action_queues.get(match_id, {})
    return list(match_queues.get(player_id, []))


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


def _compute_initial_fov(match_id: str) -> None:
    """Compute and cache FOV for all alive units at match start.

    This ensures the first match_start message includes per-player visible_tiles
    so dungeons don't flash the full map on the first frame.
    """
    match = _active_matches.get(match_id)
    if not match:
        return
    players = _player_states.get(match_id, {})
    map_data = load_map(match.config.map_id)
    grid_width = map_data.get("width", settings.GRID_WIDTH)
    grid_height = map_data.get("height", settings.GRID_HEIGHT)

    # Compute obstacles honouring current door states (open doors passable)
    door_states = dict(match.door_states) if match.door_states else None
    obstacles = get_obstacles_with_door_states(match.config.map_id, door_states)

    for uid, unit in players.items():
        if unit.is_alive:
            fov = compute_fov(
                unit.position.x, unit.position.y,
                unit.vision_range,
                grid_width, grid_height,
                obstacles,
            )
            set_fov_cache(match_id, uid, fov)


def get_match_start_payload(match_id: str) -> dict | None:
    """Build the match_start message payload per the WebSocket protocol spec."""
    match = _active_matches.get(match_id)
    if not match:
        return None
    players = _player_states.get(match_id, {})

    # Load map data for obstacles
    map_data = load_map(match.config.map_id)
    # For dungeon maps, derive wall-only obstacles from the tile grid.
    # Door tiles are excluded here because the client manages door blocking
    # dynamically via doorStates (closed doors get added to obstacleSet,
    # open doors are walkable). Sending doors as permanent obstacles would
    # prevent pathing through opened doors.
    if is_dungeon_map(match.config.map_id):
        tiles = map_data.get("tiles", [])
        legend = map_data.get("tile_legend", {})
        wall_chars = {ch for ch, ttype in legend.items() if ttype == "wall"}
        obstacles = []
        for y, row in enumerate(tiles):
            for x, ch in enumerate(row):
                if ch in wall_chars:
                    obstacles.append({"x": x, "y": y})
    else:
        obstacles = [{"x": o["x"], "y": o["y"]} for o in map_data.get("obstacles", [])]

    players_payload = {}
    for pid, p in players.items():
        players_payload[pid] = {
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
            "ai_stance": p.ai_stance,  # Phase 7C: stance for hero allies
            # Phase 19 fix: Include advanced stats at match start
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

    payload = {
        "type": "match_start",
        "match_id": match.match_id,
        "players": players_payload,
        "grid_width": map_data.get("width", settings.GRID_WIDTH),
        "grid_height": map_data.get("height", settings.GRID_HEIGHT),
        "obstacles": obstacles,
        "tick_rate": match.config.tick_rate,
        "match_type": match.config.match_type.value,
        "team_a": list(match.team_a),
        "team_b": list(match.team_b),
        "team_c": list(match.team_c),
        "team_d": list(match.team_d),
        "ai_ids": list(match.ai_ids),
    }

    # Phase 6C: Include class skill definitions for all classes in the match
    from app.core.skills import get_class_skills as _get_class_skills, get_skill as _get_skill
    class_ids_in_match = set()
    for p in players.values():
        if p.class_id:
            class_ids_in_match.add(p.class_id)
    class_skills_payload = {}
    for cid in class_ids_in_match:
        skill_ids = _get_class_skills(cid)
        skill_defs = []
        for sid in skill_ids:
            sdef = _get_skill(sid)
            if sdef:
                skill_defs.append({
                    "skill_id": sdef["skill_id"],
                    "name": sdef["name"],
                    "icon": sdef["icon"],
                    "cooldown_turns": sdef["cooldown_turns"],
                    "targeting": sdef["targeting"],
                    "range": sdef["range"],
                    "description": sdef["description"],
                    "requires_line_of_sight": sdef.get("requires_line_of_sight", False),
                    "is_auto_attack": sdef.get("is_auto_attack", False),
                })
        class_skills_payload[cid] = skill_defs
    if class_skills_payload:
        payload["class_skills"] = class_skills_payload

    # Dungeon-specific data for client rendering
    if is_dungeon_map(match.config.map_id):
        tiles = get_tiles(match.config.map_id)
        tile_legend = map_data.get("tile_legend", {})
        payload["tiles"] = tiles
        payload["tile_legend"] = tile_legend
        payload["door_states"] = dict(match.door_states)
        payload["chest_states"] = dict(match.chest_states)
        payload["is_dungeon"] = True
        payload["current_floor"] = match.current_floor
        payload["stairs_unlocked"] = match.stairs_unlocked
        if match.theme_id:
            payload["theme_id"] = match.theme_id

    return payload


def get_match_start_payload_for_player(match_id: str, player_id: str) -> dict | None:
    """Build a per-player match_start payload that includes FOV-filtered visible_tiles.

    Wraps get_match_start_payload and adds the player's initial FOV so the client
    can render fog from the very first frame (no full-map flash).
    """
    base = get_match_start_payload(match_id)
    if not base:
        return None

    match = _active_matches.get(match_id)
    if not match:
        return base

    # Get team-based FOV for this player
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return base

    player_team = player.team
    team_a, team_b, team_c, team_d = get_match_teams(match_id)
    team_map = {"a": team_a, "b": team_b, "c": team_c, "d": team_d}
    team_members = team_map.get(player_team, [])

    # Use shared team FOV if applicable
    if team_members:
        player_fov = get_team_fov(match_id, team_members)
    else:
        player_fov = get_fov_cache(match_id, player_id)

    # Filter players: only include units visible to this player
    if player_fov:
        filtered_players = {}
        for uid, data in base["players"].items():
            if uid == player_id:
                filtered_players[uid] = data
                continue
            pos = data["position"]
            if (pos["x"], pos["y"]) in player_fov:
                filtered_players[uid] = data
            elif data.get("team") == player_team:
                # Allies always visible
                filtered_players[uid] = data
        base["players"] = filtered_players
        base["visible_tiles"] = list(player_fov)

    return base


def get_player_joined_payload(match_id: str, player_id: str) -> dict | None:
    """Build the player_joined broadcast payload."""
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return None
    return {
        "type": "player_joined",
        "player_id": player_id,
        "username": player.username,
        "position": {"x": player.position.x, "y": player.position.y},
    }


def get_lobby_players_payload(match_id: str) -> dict:
    """Build a dict of all players for lobby state sync.

    Only includes players whose IDs are still in match.player_ids
    to prevent ghost entries from appearing.
    """
    match = _active_matches.get(match_id)
    players = _player_states.get(match_id, {})
    active_ids = set(match.player_ids) if match else set()
    hero_selections = _hero_selections.get(match_id, {})
    result = {}
    for pid, p in players.items():
        if pid not in active_ids:
            continue  # Skip removed/ghost players
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
            "enemy_type": p.enemy_type,
            "is_boss": p.is_boss,
        }
        # Include hero_ids if selected (Phase 4E-2, multi-hero support)
        if pid in hero_selections:
            selection = hero_selections[pid]
            # Support both list (new) and string (legacy) formats
            if isinstance(selection, list):
                entry["hero_ids"] = selection
                entry["hero_id"] = selection[0] if selection else None  # backward compat
            else:
                entry["hero_id"] = selection
                entry["hero_ids"] = [selection]
        result[pid] = entry
    return result


def get_players_snapshot(match_id: str) -> dict:
    """Build a compact snapshot of all unit states for turn_result broadcast."""
    players = _player_states.get(match_id, {})
    result = {}
    for pid, p in players.items():
        entry = {
            "username": p.username,
            "position": {"x": p.position.x, "y": p.position.y},
            "hp": p.hp,
            "max_hp": p.max_hp,
            "is_alive": p.is_alive,
            "unit_type": p.unit_type,
            "team": p.team,
            "cooldowns": dict(p.cooldowns),
            "active_buffs": list(p.active_buffs),  # Phase 6C: include buff state
            "class_id": p.class_id,
            "enemy_type": p.enemy_type,
            "ai_behavior": p.ai_behavior,
            "is_boss": p.is_boss,
            "ai_stance": p.ai_stance,  # Phase 7C: stance for hero allies
            "extracted": p.extracted,  # Phase 12C: portal extraction
            # Phase 19 fix: Core combat stats (were missing, causing 0 display in inventory)
            "attack_damage": p.attack_damage,
            "ranged_damage": p.ranged_damage,
            "armor": p.armor,
            "vision_range": p.vision_range,
            "ranged_range": p.ranged_range,
            # Phase 19 fix: Advanced stats (Phase 16A) for inventory panel
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
        result[pid] = entry
    return result


def get_alive_count(match_id: str) -> int:
    """Return the number of alive players in a match."""
    players = _player_states.get(match_id, {})
    return sum(1 for p in players.values() if p.is_alive)


# ---------- FOV Cache ----------

def set_fov_cache(match_id: str, unit_id: str, visible: set[tuple[int, int]]) -> None:
    """Store computed FOV for a unit."""
    if match_id not in _fov_cache:
        _fov_cache[match_id] = {}
    _fov_cache[match_id][unit_id] = visible


def get_fov_cache(match_id: str, unit_id: str) -> set[tuple[int, int]]:
    """Get cached FOV for a unit. Returns empty set if not cached."""
    return _fov_cache.get(match_id, {}).get(unit_id, set())


def get_team_fov(match_id: str, team_member_ids: list[str]) -> set[tuple[int, int]]:
    """Get combined FOV for an entire team (union of all members' FOV).

    This enables shared team vision — if any teammate can see a tile,
    all teammates can see it.
    """
    match_fov = _fov_cache.get(match_id, {})
    combined: set[tuple[int, int]] = set()
    for member_id in team_member_ids:
        member_fov = match_fov.get(member_id)
        if member_fov:
            combined |= member_fov
    return combined


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


# ---------- Lobby Chat ----------

def add_lobby_message(match_id: str, player_id: str, message: str) -> dict | None:
    """Add a chat message to the lobby. Returns the message dict, or None on failure."""
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        return None

    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return None

    msg = {
        "sender": player.username,
        "sender_id": player_id,
        "message": message[:500],  # Limit message length
        "timestamp": time.time(),
    }

    if match_id not in _lobby_chat:
        _lobby_chat[match_id] = []
    _lobby_chat[match_id].append(msg)

    # Keep last 100 messages
    if len(_lobby_chat[match_id]) > 100:
        _lobby_chat[match_id] = _lobby_chat[match_id][-100:]

    return msg


def get_lobby_chat(match_id: str) -> list[dict]:
    """Get all chat messages for a lobby."""
    return list(_lobby_chat.get(match_id, []))


# ---------- In-Lobby Config Update ----------

def update_match_config(match_id: str, player_id: str, updates: dict) -> dict | None:
    """Update match configuration during lobby phase. Host-only.

    Supported updates: map_id, match_type, ai_opponents, ai_allies.
    Returns updated config dict on success, None on failure.
    Re-spawns AI units if AI counts changed.
    """
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        return None

    # Only host can change config
    if player_id != match.host_id:
        return None

    config = match.config
    ai_changed = False

    if "map_id" in updates:
        # Validate map exists on disk (auto-discovers new maps from configs/maps/)
        from app.core.map_loader import _maps_dir
        map_file = _maps_dir / f"{updates['map_id']}.json"
        if map_file.exists():
            config.map_id = updates["map_id"]

    if "match_type" in updates:
        try:
            config.match_type = MatchType(updates["match_type"])
            # PvP mode: reset AI counts
            if config.match_type == MatchType.PVP:
                if config.ai_opponents > 0 or config.ai_allies > 0:
                    config.ai_opponents = 0
                    config.ai_allies = 0
                    ai_changed = True
        except ValueError:
            pass  # Invalid match type, ignore

    if "ai_opponents" in updates and config.match_type != MatchType.PVP:
        new_val = max(0, min(10, int(updates["ai_opponents"])))
        if new_val != config.ai_opponents:
            config.ai_opponents = new_val
            ai_changed = True

    if "ai_allies" in updates and config.match_type != MatchType.PVP:
        new_val = max(0, min(10, int(updates["ai_allies"])))
        if new_val != config.ai_allies:
            config.ai_allies = new_val
            ai_changed = True

    if "theme_id" in updates:
        valid_themes = [
            'bleeding_catacombs', 'ashen_undercroft', 'drowned_sanctum',
            'hollowed_cathedral', 'iron_depths', 'forgotten_cellar',
            'pale_ossuary', 'silent_vault',
        ]
        new_theme = updates["theme_id"]
        if new_theme is None or new_theme in valid_themes:
            config.theme_id = new_theme  # None = random

    # Handle AI class selections (list of class IDs per slot)
    valid_class_ids = set(get_all_classes().keys())
    if "ai_opponent_classes" in updates and config.match_type != MatchType.PVP:
        raw = updates["ai_opponent_classes"]
        if isinstance(raw, list):
            sanitized = [c if (isinstance(c, str) and c in valid_class_ids) else "" for c in raw]
            config.ai_opponent_classes = sanitized
            ai_changed = True

    if "ai_ally_classes" in updates and config.match_type != MatchType.PVP:
        raw = updates["ai_ally_classes"]
        if isinstance(raw, list):
            sanitized = [c if (isinstance(c, str) and c in valid_class_ids) else "" for c in raw]
            config.ai_ally_classes = sanitized
            ai_changed = True

    # --- PVPVE-specific config fields ---
    if config.match_type == MatchType.PVPVE:
        if "pvpve_team_count" in updates:
            config.pvpve_team_count = max(2, min(4, int(updates["pvpve_team_count"])))
        if "pvpve_pve_density" in updates:
            config.pvpve_pve_density = max(0.0, min(1.0, float(updates["pvpve_pve_density"])))
        if "pvpve_boss_enabled" in updates:
            config.pvpve_boss_enabled = bool(updates["pvpve_boss_enabled"])
        if "pvpve_loot_density" in updates:
            config.pvpve_loot_density = max(0.0, min(1.0, float(updates["pvpve_loot_density"])))
        if "pvpve_grid_size" in updates:
            gs = int(updates["pvpve_grid_size"])
            if gs in (6, 8, 10):
                config.pvpve_grid_size = gs
        if "pvpve_ai_team_count" in updates:
            config.pvpve_ai_team_count = max(0, min(config.pvpve_team_count - 1, int(updates["pvpve_ai_team_count"])))
        if "pvpve_ai_team_sizes" in updates:
            raw_sizes = updates["pvpve_ai_team_sizes"]
            if isinstance(raw_sizes, list):
                config.pvpve_ai_team_sizes = [max(1, min(5, int(s))) for s in raw_sizes]

    # Re-spawn AI if counts or classes changed
    if ai_changed:
        _spawn_ai_units(match_id)

    return {
        "map_id": config.map_id,
        "match_type": config.match_type.value,
        "ai_opponents": config.ai_opponents,
        "ai_allies": config.ai_allies,
        "max_players": config.max_players,
        "host_id": match.host_id,
        "theme_id": config.theme_id,
        "ai_opponent_classes": config.ai_opponent_classes,
        "ai_ally_classes": config.ai_ally_classes,
        "pvpve_team_count": config.pvpve_team_count,
        "pvpve_pve_density": config.pvpve_pve_density,
        "pvpve_boss_enabled": config.pvpve_boss_enabled,
        "pvpve_loot_density": config.pvpve_loot_density,
        "pvpve_grid_size": config.pvpve_grid_size,
        "pvpve_ai_team_count": config.pvpve_ai_team_count,
        "pvpve_ai_team_sizes": config.pvpve_ai_team_sizes,
    }


def spawn_lobby_ai(match_id: str) -> None:
    """Spawn AI units in lobby so they appear in the player list.

    Called after match creation if config has AI units.
    """
    match = _active_matches.get(match_id)
    if not match:
        return
    config = match.config
    if config.ai_opponents == 0 and config.ai_allies == 0:
        return
    _spawn_ai_units(match_id)


def get_match_config_payload(match_id: str) -> dict | None:
    """Get the current match config as a serializable dict."""
    match = _active_matches.get(match_id)
    if not match:
        return None
    return {
        "map_id": match.config.map_id,
        "match_type": match.config.match_type.value,
        "ai_opponents": match.config.ai_opponents,
        "ai_allies": match.config.ai_allies,
        "max_players": match.config.max_players,
        "host_id": match.host_id,
        "theme_id": match.config.theme_id,
        "ai_opponent_classes": match.config.ai_opponent_classes,
        "ai_ally_classes": match.config.ai_ally_classes,
        "pvpve_team_count": match.config.pvpve_team_count,
        "pvpve_pve_density": match.config.pvpve_pve_density,
        "pvpve_boss_enabled": match.config.pvpve_boss_enabled,
        "pvpve_loot_density": match.config.pvpve_loot_density,
        "pvpve_grid_size": match.config.pvpve_grid_size,
        "pvpve_ai_team_count": match.config.pvpve_ai_team_count,
        "pvpve_ai_team_sizes": match.config.pvpve_ai_team_sizes,
    }


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

    # Determine which teams humans occupy.
    # Humans fill from team A round-robin, so figure out teams needing AI fill.
    humans = [pid for pid in match.player_ids
              if not pid.startswith(("ai-", "enemy-", "hero-", "pvpve-ai-"))]
    human_teams: set[str] = set()
    for i in range(len(humans)):
        human_teams.add(active_teams[i % team_count])

    # AI hero teams fill the remaining team slots (non-human teams)
    ai_team_keys = [t for t in active_teams if t not in human_teams]
    # If there are more AI teams requested than available slots, cap it
    ai_team_keys = ai_team_keys[:ai_team_count]

    if not ai_team_keys:
        logger.info("PVPVE match %s: no AI team slots available (all teams have humans)", match_id)
        return

    players = _player_states.get(match_id, {})
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

        for i in range(team_size):
            ai_id = f"pvpve-ai-{team_key}-{str(uuid.uuid4())[:6]}"

            ai_class = random.choice(all_class_ids)
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

            players[ai_id] = ai_unit
            match.ai_ids.append(ai_id)
            match.player_ids.append(ai_id)

    logger.info("PVPVE match %s: spawned %d AI hero teams (%s)",
                match_id, len(ai_team_keys),
                ", ".join(k.upper() for k in ai_team_keys))


def _assign_pvpve_teams(match_id: str) -> None:
    """Distribute players across PVPVE teams.

    - Host goes to team A
    - Other humans distributed round-robin across teams
    - PVPVE AI team units (pvpve-ai- prefix) placed on their pre-assigned team
    - Hero allies placed with their owner
    - Generic AI allies distributed round-robin across teams
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

    # Distribute humans round-robin across teams (host first → team A)
    # Move host to front of human list
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

    for i, pid in enumerate(humans):
        team_key = active_teams[i % team_count]
        team_lists[team_key].append(pid)
        pid_to_team[pid] = team_key
        player = players.get(pid)
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


# ---------- Dungeon helpers (Phase 4B-1) ----------


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


def _init_dungeon_state(match: MatchState) -> None:
    """Populate door_states, chest_states, and ground_items from the dungeon map data.

    Called once when a dungeon match starts.
    """
    import random as _rng

    map_id = match.config.map_id
    doors = get_doors(map_id)
    chests = get_chests(map_id)

    match.door_states = {
        f"{d['x']},{d['y']}": d.get("state", "closed")
        for d in doors
    }
    match.chest_states = {
        f"{c['x']},{c['y']}": "unopened"
        for c in chests
    }
    # Initialize empty ground items dict for loot drops (Phase 4D-2)
    match.ground_items = {}

    # Assign a visual theme if one hasn't been set yet (static dungeon maps)
    if not match.theme_id:
        DUNGEON_THEMES = [
            'bleeding_catacombs', 'ashen_undercroft', 'drowned_sanctum',
            'hollowed_cathedral', 'iron_depths', 'forgotten_cellar',
            'pale_ossuary', 'silent_vault',
        ]
        theme_rng = _rng.Random(hash(match.match_id) & 0xFFFFFFFF)
        match.theme_id = theme_rng.choice(DUNGEON_THEMES)


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
    }


def _spawn_dungeon_enemies(match_id: str) -> None:
    """Spawn typed enemies in dungeon rooms based on room enemy_spawns data.

    Reads room definitions from the dungeon map, creates enemy units with
    stats from enemies_config.json, and places them at room-specific positions.
    Each enemy is named by type (e.g. 'Demon-1', 'Skeleton-2', 'Undead Knight').
    Enemies are always on team 'b' (opposing the player party on team 'a').

    Phase 4C: Static spawns only — enemies do not respawn.
    Phase 18C: Apply monster rarity upgrades (champion/rare) from spawn data,
    spawn champion packs, and place rare minions on adjacent tiles.
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


# ---------- Hero Persistence helpers (Phase 4E-2) — extracted to hero_manager.py ----------
# Re-exported here so existing importers continue to work unchanged.
from app.core.hero_manager import (  # noqa: E402, F401
    MAX_PARTY_SIZE,
    MAX_DUNGEON_PARTY,
    get_dungeon_slots_available,
    select_heroes,
    select_hero,
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

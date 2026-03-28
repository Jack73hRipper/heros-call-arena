"""
AI Behavior Engine — Decision logic for AI combatants.

P1 Refactoring: This file has been decomposed into focused modules:
  - ai_pathfinding.py  — A* pathfinding, occupied-set builder
  - ai_skills.py       — Role-specific skill handlers (support/tank/ranged/scout/hybrid)
  - ai_memory.py       — Enemy memory, target selection, ally reinforcement
  - ai_patrol.py       — Waypoint-based patrol/scouting
  - ai_stances.py      — Stance-based hero ally behavior (follow/aggressive/defensive/hold)

This file retains:
  - decide_ai_action (main dispatch)
  - Enemy AI behaviors (aggressive, ranged, boss)
  - Room bounds cache + leashing
  - run_ai_decisions (tick-level orchestrator)
  - clear_ai_patrol_state

All public names are re-exported here so existing imports continue to work.
"""

from __future__ import annotations

import random

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.models.items import INVENTORY_MAX_CAPACITY
from app.core.fov import compute_fov, has_line_of_sight
from app.core.combat import is_adjacent, is_in_range, get_combat_config

# ---------------------------------------------------------------------------
# Re-exports from extracted modules (backward compatibility)
# ---------------------------------------------------------------------------
from app.core.ai_pathfinding import (  # noqa: F401
    _heuristic,
    _neighbors,
    a_star,
    get_next_step_toward,
    _build_occupied_set,
)
from app.core.ai_exploration import (  # noqa: F401
    get_next_exploration_target,
    get_current_room,
    get_doors_for_room,
    skip_room,
    expire_skipped_rooms,
)
from app.core.ai_skills import (  # noqa: F401
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _HEAL_SELF_THRESHOLD,
    _HEAL_ALLY_THRESHOLD,
    _SHADOW_STEP_ESCAPE_HP_THRESHOLD,
    _SHADOW_STEP_OFFENSIVE_MIN_DISTANCE,
    _SHADOW_STEP_GAPCLOSER_MIN_DISTANCE,
    _support_skill_logic,
    _support_move_preference,
    _tank_skill_logic,
    _ranged_dps_skill_logic,
    _find_shadow_step_gapcloser_tile,
    _hybrid_dps_skill_logic,
    _find_valid_shadow_step_tiles,
    _find_shadow_step_escape_tile,
    _find_shadow_step_offensive_tile,
    _scout_skill_logic,
    _offensive_support_skill_logic,
    _decide_skill_usage,
)
from app.core.ai_memory import (  # noqa: F401
    _enemy_memory,
    _MEMORY_EXPIRY_TURNS,
    _update_enemy_memory,
    _pursue_memory_target,
    _reinforce_ally,
    _pick_best_target,
)
from app.core.ai_patrol import (  # noqa: F401
    _patrol_targets,
    _visited_history,
    _stale_area_counter,
    _MAX_VISIT_HISTORY,
    _patrol_action,
    _pick_patrol_waypoint,
    _random_adjacent_move,
)
from app.core.ai_stances import (  # noqa: F401
    VALID_STANCES,
    _POTION_THRESHOLDS,
    _RETREAT_THRESHOLDS,
    _RETREAT_THRESHOLD_DEFAULT,
    _CHEST_SEEK_MAX_RANGE,
    _find_owner,
    _chebyshev,
    _maybe_interact_door,
    _find_adjacent_door_toward_target,
    _has_heal_potions,
    _should_retreat,
    _find_retreat_destination,
    _should_use_potion,
    _find_nearest_unopened_chest,
    _try_loot_adjacent_chest,
    _decide_stance_action,
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _decide_hold_action,
)


# ---------------------------------------------------------------------------
# Phase 28A: Enemy potion thresholds — per-behavior HP% at or below which
# the enemy AI will drink a health potion (if one is in inventory).
# ---------------------------------------------------------------------------
_ENEMY_POTION_THRESHOLDS: dict[str, float] = {
    "aggressive": 0.30,  # Reckless — fights hard, drinks late
    "ranged":     0.40,  # Fragile — drinks earlier to survive
    "boss":       0.25,  # Tough — high HP pool, only drinks when critical
    "support":    0.50,  # Cautious — drinks early to keep healing allies
}


# ---------------------------------------------------------------------------
# Phase 28C: Loot scavenging — per-behavior max range for seeking ground loot
# when idle (no visible enemies). Bosses never scavenge.
# ---------------------------------------------------------------------------
_SCAVENGE_MAX_RANGE: dict[str, int] = {
    "aggressive": 3,
    "ranged":     4,
    "support":    5,
}


# ---------------------------------------------------------------------------
# Anti-Oscillation: Per-unit recent position history
# ---------------------------------------------------------------------------
# Tracks the last few positions each AI unit occupied across turns.
# Used in run_ai_decisions to detect and suppress A→B→A oscillation
# when there is no nearby enemy forcing the movement.
# {unit_id: [pos_turn_N-11, ..., pos_turn_N-1, pos_turn_N]}
_position_history: dict[str, list[tuple[int, int]]] = {}
_POSITION_HISTORY_LEN = 12
_OSCILLATION_COMBAT_RANGE = 3  # Suppress oscillation only when no enemy within this Chebyshev dist

# Extended oscillation: set of ai_ids whose explore_room should be temporarily
# skipped because the leader has been cycling between explore_room and patrol.
# Cleared when the unit genuinely moves to a new tile (not in recent history).
_explore_suppressed: set[str] = set()

# Turn counter for when each AI was first suppressed.  Suppression cannot be
# lifted until at least _MIN_SUPPRESS_TURNS have elapsed, giving patrol enough
# time to physically exit the room.
_suppress_start_tick: dict[str, int] = {}
_MIN_SUPPRESS_TURNS = 10
_MAX_SUPPRESS_TURNS = 20  # Hard cap: lift suppression unconditionally after this many ticks

# Parallel suppression for chest seeking — prevents aggro_chest_seek from
# fighting patrol_move when the AI can't actually reach the chest.
_chest_seek_suppressed: set[str] = set()

# Root Cause #1 fix: Per-leader consecutive pathfinding failures for explore
# targets.  After _EXPLORE_FAIL_THRESHOLD consecutive failures (A* returns
# None or backtrack detected) the target room is marked as temporarily
# unreachable via skip_room() and the leader moves on to the next candidate.
# {ai_id: {room_id: consecutive_fail_count}}
_explore_fail_count: dict[str, dict[str, int]] = {}
_EXPLORE_FAIL_THRESHOLD = 3

# RC#1 tuning: stagnation guard.  Even when A* succeeds each turn, a leader
# can "treadmill" — moving but never actually reaching the target room due to
# congestion, combat detours, or backtracking.  If a leader targets the same
# room for _EXPLORE_STAGNATION_THRESHOLD consecutive *explore_room* decisions
# it is skipped.  {ai_id: (room_id, consecutive_turn_count)}
_explore_target_turns: dict[str, tuple[str, int]] = {}
_EXPLORE_STAGNATION_THRESHOLD = 25

# RC#3 fix: Total-turn stagnation tracker.  _explore_target_turns only
# increments on turns where the explore_room code path runs, which means a
# leader can target the same unreachable room for 100+ REAL turns while the
# counter barely reaches 10 (due to combat, patrol fallback, scavenging,
# etc. consuming most turns).  This tracker increments EVERY tick for leaders
# and triggers a skip once the total wall-clock turns exceed the threshold.
# {ai_id: (room_id, total_turn_count)}
_explore_total_turns: dict[str, tuple[str, int]] = {}
_EXPLORE_TOTAL_STAGNATION_THRESHOLD = 50

# ---------------------------------------------------------------------------
# Phase 29D: Post-Combat Follow Impulse — prevents hero allies from
# freezing after combat ends.  Records the tick when each hero last saw
# or fought enemies.  For 5 ticks after combat, hero allies trail their
# leader instead of WAITing at step 4c.
# ---------------------------------------------------------------------------
_last_combat_tick: dict[str, int] = {}  # {ai_id: tick_number}
_ai_tick_counter: int = 0
_POST_COMBAT_FOLLOW_GRACE = 5  # ticks of trailing after last combat


def _find_nearest_ground_loot(
    ai: PlayerState,
    ground_items: dict[str, list] | None,
    max_range: int = 5,
) -> tuple[int, int] | None:
    """Find the nearest tile with ground items within max_range (Manhattan).

    Returns (x, y) of the best loot tile, or None if nothing reachable.
    Skips search if the AI's inventory is full.
    """
    if not ground_items:
        return None
    if len(ai.inventory) >= INVENTORY_MAX_CAPACITY:
        return None

    ai_x, ai_y = ai.position.x, ai.position.y
    best: tuple[int, int] | None = None
    best_dist = max_range + 1

    for key, items in ground_items.items():
        if not items:
            continue
        parts = key.split(",")
        if len(parts) != 2:
            continue
        x, y = int(parts[0]), int(parts[1])
        dist = abs(x - ai_x) + abs(y - ai_y)
        if dist < best_dist and dist <= max_range:
            best = (x, y)
            best_dist = dist

    return best


# ---------------------------------------------------------------------------
# Room Bounds Cache — for leashing dungeon enemies (Phase 4C)
# ---------------------------------------------------------------------------
# {match_id: {room_id: {"x_min": int, "y_min": int, "x_max": int, "y_max": int}}}
_room_bounds_cache: dict[str, dict[str, dict]] = {}


def set_room_bounds(match_id: str, rooms: list[dict]) -> None:
    """Cache room bounds for a match so AI can be leashed to rooms."""
    _room_bounds_cache[match_id] = {}
    for room in rooms:
        room_id = room.get("id")
        bounds = room.get("bounds")
        if room_id and bounds:
            _room_bounds_cache[match_id][room_id] = bounds


def clear_room_bounds(match_id: str | None = None) -> None:
    """Clear room bounds cache for a match or all matches."""
    if match_id:
        _room_bounds_cache.pop(match_id, None)
    else:
        _room_bounds_cache.clear()


def _is_in_room(x: int, y: int, room_bounds: dict) -> bool:
    """Check if a position is inside the given room bounds."""
    return (room_bounds["x_min"] <= x <= room_bounds["x_max"] and
            room_bounds["y_min"] <= y <= room_bounds["y_max"])


def _get_room_bounds(match_id: str, room_id: str) -> dict | None:
    """Get cached room bounds for a specific room in a match."""
    return _room_bounds_cache.get(match_id, {}).get(room_id)


# Maximum Manhattan distance an enemy will chase from its room center
# before disengaging and returning home.  Prevents infinite cross-map pulls.
_MAX_LEASH_CHASE_DISTANCE = 12


# ---------------------------------------------------------------------------
# Phase 18D: Teleporter Affix — auto-cast Shadow Step
# ---------------------------------------------------------------------------
_TELEPORTER_MIN_DISTANCE = 4  # Only teleport if target is > 3 tiles away


def _try_teleporter_affix(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
) -> PlayerAction | None:
    """Attempt Teleporter affix auto-cast Shadow Step toward a distant enemy.

    Triggers when the nearest visible enemy is >= _TELEPORTER_MIN_DISTANCE
    tiles away (Chebyshev). Finds a valid Shadow Step destination tile that
    is adjacent (1 tile Chebyshev) to the target enemy.

    Returns a SKILL action for shadow_step, or None if not applicable.
    """
    ai_pos = (ai.position.x, ai.position.y)

    # Compute FOV to find visible enemies
    own_fov = compute_fov(
        ai.position.x, ai.position.y,
        ai.vision_range,
        grid_width, grid_height,
        obstacles,
    )
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov

    # Find visible enemies
    enemies: list[PlayerState] = []
    for unit in all_units.values():
        if (
            unit.is_alive
            and unit.player_id != ai.player_id
            and unit.team != ai.team
            and (unit.position.x, unit.position.y) in visible_tiles
        ):
            enemies.append(unit)

    if not enemies:
        return None

    # Pick the closest enemy
    def _dist(e: PlayerState) -> int:
        return max(abs(ai.position.x - e.position.x), abs(ai.position.y - e.position.y))

    nearest = min(enemies, key=_dist)
    dist = _dist(nearest)

    # Only teleport if target is far enough away
    if dist < _TELEPORTER_MIN_DISTANCE:
        return None

    target_pos = (nearest.position.x, nearest.position.y)

    # Find valid shadow step tiles (uses standard range=3 SS infrastructure)
    valid_tiles = _find_valid_shadow_step_tiles(
        ai, all_units, grid_width, grid_height, obstacles,
    )
    if not valid_tiles:
        return None

    # Filter to tiles adjacent to target (Chebyshev distance <= 1)
    adjacent_tiles = [
        t for t in valid_tiles
        if max(abs(t[0] - target_pos[0]), abs(t[1] - target_pos[1])) <= 1
    ]

    # If no adjacent tiles, find the tile closest to target
    candidates = adjacent_tiles if adjacent_tiles else valid_tiles
    best = min(candidates, key=lambda t: max(abs(t[0] - target_pos[0]), abs(t[1] - target_pos[1])))

    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.SKILL,
        skill_id="shadow_step",
        target_x=best[0],
        target_y=best[1],
        reason="teleporter_affix_shadowstep",
    )


# ---------------------------------------------------------------------------
# AI Decision Logic
# ---------------------------------------------------------------------------

def decide_ai_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    portal: dict | None = None,
    match_state=None,
    ground_items: dict[str, list] | None = None,
    chest_states: dict[str, str] | None = None,
) -> PlayerAction | None:
    """Decide the next action for an AI unit based on its behavior profile.

    Dispatches to behavior-specific logic:
      - 'aggressive' (default): chase → melee → ranged → patrol
      - 'ranged': maintain distance → ranged attack → retreat if close
      - 'boss': guard room → attack intruders → never leave room
      - None/unknown: falls back to aggressive (arena backward compat)

    Args:
        team_fov: Pre-computed shared team FOV.
        match_id: Match ID for room bounds lookup (needed for boss leashing).
        pending_moves: Phase 7A-3 — ``{unit_id: (from_pos, to_pos)}`` for
                       AI units that already decided to MOVE this tick.
                       Vacating positions are excluded from the occupied set
                       and claimed positions are added, preventing sequential
                       AI decisions from blocking each other.
        door_tiles: Phase 7D-1 — set of closed-door positions for door-aware
                    A*.  Only passed to hero ally stance functions; enemy AI
                    does NOT receive door_tiles (enemies cannot open doors).
        portal: Phase 12C — active portal dict or None.
                When active, hero allies pathfind to the portal and extract.

    Returns a PlayerAction, or None if no action needed.
    """
    if not ai.is_alive:
        return None

    # Phase 12C: Extracted units do nothing
    if ai.extracted:
        return None

    # Phase 12: Stunned units cannot take any action — skip their turn entirely
    from app.core.skills import is_stunned
    if is_stunned(ai):
        return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT, reason="stunned")

    # -----------------------------------------------------------------------
    # Phase 18D: Teleporter affix — auto-cast Shadow Step when target is far
    # -----------------------------------------------------------------------
    if (
        getattr(ai, 'affixes', None)
        and "teleporter" in ai.affixes
        and ai.cooldowns.get("teleporter_affix", 0) <= 0
    ):
        teleporter_action = _try_teleporter_affix(
            ai, all_units, grid_width, grid_height, obstacles, team_fov,
        )
        if teleporter_action:
            # Set internal cooldown (will be decremented by normal CD ticking)
            ai.cooldowns["teleporter_affix"] = 3
            return teleporter_action

    # Phase 7C: Hero allies with stances use stance-based behavior instead of
    # the enemy AI behavior profiles (aggressive/ranged/boss).
    # Phase 7D-1: Pass door_tiles so hero allies can path through closed doors.
    if ai.hero_id is not None and ai.ai_stance:
        return _decide_stance_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, portal=portal, match_state=match_state, chest_states=chest_states)

    # ── Cross-room aggro fix: suppress team-shared FOV for leashed enemies ──
    # Enemies inside their assigned room should only detect players via their
    # own vision, not through allies in distant rooms.  Once an enemy leaves
    # its room (leash broken / chasing), it regains access to team FOV.
    if ai.room_id and match_id and team_fov is not None:
        _rb = _get_room_bounds(match_id, ai.room_id)
        if _rb and _is_in_room(ai.position.x, ai.position.y, _rb):
            team_fov = None

    # All AI (enemies + allies) receive door_tiles so they can path through
    # and open closed doors.  A* treats doors as elevated-cost tiles (+3),
    # so open routes are still preferred.  When adjacent to a closed door on
    # the planned path, AI emits INTERACT to open it before moving through.
    behavior = ai.ai_behavior or "aggressive"

    if behavior == "dummy":
        # Training dummy: stand in place, never move, never attack.
        return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT, reason="dummy_wait")
    elif behavior == "ranged":
        return _decide_ranged_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, ground_items=ground_items)
    elif behavior == "boss":
        return _decide_boss_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles)
    elif behavior == "support":
        return _decide_support_behavior(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, ground_items=ground_items)
    else:
        # "aggressive" or any unknown behavior → default aggressive
        return _decide_aggressive_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, ground_items=ground_items, chest_states=chest_states)


# ---------------------------------------------------------------------------
# Support AI Behavior — Healer/Buffer enemies (Dark Priest, Acolyte)
# ---------------------------------------------------------------------------

def _decide_support_behavior(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    ground_items: dict[str, list] | None = None,
) -> PlayerAction | None:
    """Support enemy AI — heal/buff allies first, then ranged attack, stay back.

    Decision loop:
      1. Compute FOV + find visible enemies
      2. No enemies → stay near most injured ally or patrol
      3. Try skill usage (heal, buff, offensive spells via _decide_skill_usage)
      4. If ranged ready + enemy in range + LOS → ranged attack
      5. If adjacent to enemy → retreat away (support doesn't melee by choice)
      6. Move toward most injured ally (stay grouped)
      7. Fallback: wait

    Support enemies are priority targets — designed to be killed first.
    They extend fights by healing allies, creating interesting tactical decisions.
    """
    # Phase 28A: Potion check before any combat decisions — HERO PARTIES ONLY
    if getattr(ai, 'enemy_type', None) is None:
        threshold = _ENEMY_POTION_THRESHOLDS.get("support", 0.50)
        potion_action = _should_use_potion(ai, hp_threshold=threshold)
        if potion_action:
            return potion_action

    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))
    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)
    # Phase 18D: Ghostly champions can phase through occupied tiles
    is_ghostly = getattr(ai, 'champion_type', None) == "ghostly"

    # Compute FOV
    own_fov = compute_fov(
        ai.position.x, ai.position.y,
        ai.vision_range,
        grid_width, grid_height,
        obstacles,
    )
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov

    # Find visible enemies
    enemies: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive or unit.player_id == ai_id or unit.team == ai.team:
            continue
        if (unit.position.x, unit.position.y) in visible_tiles:
            enemies.append(unit)

    _update_enemy_memory(ai_id, enemies, all_units)

    # Room leashing: only apply when idle (no visible enemies).
    # When enemies are visible, the leash is broken so the AI can chase
    # freely — prevents players from exploiting room-edge cheese.
    room_bounds = None
    effective_obstacles = obstacles
    if ai.room_id and match_id:
        room_bounds = _get_room_bounds(match_id, ai.room_id)

    # No visible enemies — move toward most injured ally or return to room
    if not enemies:
        if room_bounds:
            # Path back toward room center if outside
            if not _is_in_room(ai.position.x, ai.position.y, room_bounds):
                center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
                center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
                occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
                next_step = get_next_step_toward(
                    ai_pos, (center_x, center_y),
                    grid_width, grid_height,
                    obstacles, occupied, door_tiles,
                )
                if next_step:
                    door_action = _maybe_interact_door(ai, next_step, door_tiles)
                    if door_action:
                        return door_action
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                        reason="support_leash_return",
                    )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="support_leash_idle")
        # Try to stay near allies — use support move preference
        move_target = _support_move_preference(ai, all_units)
        if move_target:
            occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
            next_step = get_next_step_toward(
                ai_pos, move_target,
                grid_width, grid_height,
                effective_obstacles, occupied, door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                    reason="support_move_to_injured_ally",
                )

        # Phase 28C: Opportunistic loot seeking when idle & no allies to group with — HERO PARTIES ONLY
        if getattr(ai, 'enemy_type', None) is None:
            scavenge_range = _SCAVENGE_MAX_RANGE.get("support", 3)
            loot_target = _find_nearest_ground_loot(ai, ground_items, max_range=scavenge_range)
            if loot_target:
                occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
                next_step = get_next_step_toward(
                    ai_pos, loot_target,
                    grid_width, grid_height, effective_obstacles, occupied, door_tiles,
                )
                if next_step:
                    door_action = _maybe_interact_door(ai, next_step, door_tiles)
                    if door_action:
                        return door_action
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                        reason="support_scavenge_loot",
                    )

        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="support_idle")

    _patrol_targets.pop(ai_id, None)

    # ── Chase distance cap: leashed enemies disengage if too far from home ──
    if ai.room_id and match_id and room_bounds:
        center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
        center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
        chase_dist = abs(ai.position.x - center_x) + abs(ai.position.y - center_y)
        if chase_dist > _MAX_LEASH_CHASE_DISTANCE:
            occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
            next_step = get_next_step_toward(
                ai_pos, (center_x, center_y),
                grid_width, grid_height, obstacles, occupied, door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                    reason="support_leash_exceeded",
                )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="support_leash_return_stuck")

    # Priority 1: Try skill usage (heal, buff, offensive spells)
    if ai.class_id:
        skill_action = _decide_skill_usage(
            ai, enemies, all_units, grid_width, grid_height, obstacles,
        )
        if skill_action:
            return skill_action

    # Phase 7A-3: Use _build_occupied_set with pending_moves prediction
    occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)

    target = _pick_best_target(ai, enemies, all_units)
    target_pos = Position(x=target.position.x, y=target.position.y)

    dist_to_target = max(
        abs(ai.position.x - target.position.x),
        abs(ai.position.y - target.position.y),
    )

    # Priority 2: If adjacent to enemy → retreat away (support doesn't want melee)
    if dist_to_target <= 2:
        retreat_tile = _find_retreat_tile(
            ai_pos,
            (target.position.x, target.position.y),
            grid_width, grid_height,
            effective_obstacles, occupied,
        )
        if retreat_tile:
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=retreat_tile[0],
                target_y=retreat_tile[1],
                reason="support_retreat_from_enemy",
            )

    # Priority 3: Ranged attack if available
    ranged_cd = ai.cooldowns.get("ranged_attack", 0)
    if ranged_cd == 0 and ranged_range > 1 and is_in_range(ai.position, target_pos, ranged_range):
        if has_line_of_sight(
            ai.position.x, ai.position.y,
            target.position.x, target.position.y,
            obstacles,
        ):
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.RANGED_ATTACK,
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
                reason="support_ranged_attack",
            )

    # Priority 4: Move toward most injured ally (stay grouped for healing)
    move_target = _support_move_preference(ai, all_units)
    if move_target:
        next_step = get_next_step_toward(
            ai_pos, move_target,
            grid_width, grid_height,
            effective_obstacles, occupied, door_tiles,
        )
        if next_step:
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=next_step[0],
                target_y=next_step[1],
                reason="support_group_with_ally",
            )

    # Fallback: melee if adjacent (last resort for support)
    if is_adjacent(ai.position, target_pos):
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.ATTACK,
            target_x=target.position.x,
            target_y=target.position.y,
            target_id=target.player_id,
            reason="support_melee_fallback",
        )

    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="support_stuck")


def _decide_aggressive_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    ground_items: dict[str, list] | None = None,
    chest_states: dict[str, str] | None = None,
) -> PlayerAction | None:
    """Aggressive AI behavior — chase → melee → ranged → patrol.

    Decision loop:
      1. Compute FOV (merged with team FOV if available)
      2. Find visible enemies
      3. Update last-known enemy memory
      4. If no visible enemies → check memory → reinforce allies → patrol
      5. Pick best enemy (weighted: low HP, threatening allies, distance)
      6. If adjacent → melee attack
      7. If within 3 tiles → rush to melee (move toward target)
      8. If far away + ranged ready + LOS → ranged attack (harass at distance)
      9. Otherwise → move toward target (A* pathfinding)
     10. Stuck + ranged ready → ranged attack (last resort)

    Room leashing: If the AI has a room_id and no enemies are visible,
    it stays in / returns to its room. When enemies ARE visible, the
    leash is broken and the AI chases freely (prevents room-edge cheese).
    Bosses always stay leashed (handled by _decide_boss_action).

    Phase 18D: Ghostly champions pass through occupied tiles (ghostly=True
    for _build_occupied_set).

    Returns a PlayerAction, or None if no action needed.
    """
    # Phase 28A: Potion check before any combat decisions — HERO PARTIES ONLY
    # (dungeon monsters have enemy_type set; hero party AI has enemy_type=None)
    if getattr(ai, 'enemy_type', None) is None:
        threshold = _ENEMY_POTION_THRESHOLDS.get(ai.ai_behavior or "aggressive", 0.30)
        potion_action = _should_use_potion(ai, hp_threshold=threshold)
        if potion_action:
            return potion_action

    config = get_combat_config()
    # Use per-unit ranged_range from class stats, fallback to global config
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))
    ai_id = ai.player_id
    # Phase 18D: Ghostly champions can phase through occupied tiles
    is_ghostly = getattr(ai, 'champion_type', None) == "ghostly"

    # Phase 27C fix: PVPVE hero team leaders must be able to path through
    # their own followers.  Without this, the leader treats compact-spawned
    # followers as obstacles, causing deadlock in narrow corridors (leader
    # oscillates while followers WAIT because the leader is nearby).
    # Dungeon enemies (enemy_type set) keep the default behavior.
    allow_swap = ai.team if getattr(ai, 'enemy_type', None) is None else None

    # Step 1: Compute own FOV, then merge with team shared FOV
    own_fov = compute_fov(
        ai.position.x, ai.position.y,
        ai.vision_range,
        grid_width, grid_height,
        obstacles,
    )
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov

    # Step 2: Find visible enemies
    enemies: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive:
            continue
        if unit.player_id == ai_id:
            continue
        if unit.team == ai.team:
            continue  # Skip allies
        if (unit.position.x, unit.position.y) in visible_tiles:
            enemies.append(unit)

    # Step 3: Update last-known enemy memory
    _update_enemy_memory(ai_id, enemies, all_units)

    # Phase 29D: Record combat tick for post-combat follow impulse
    if enemies and ai.hero_id is not None:
        _last_combat_tick[ai_id] = _ai_tick_counter

    # Room leashing: only apply when idle (no visible enemies).
    # When enemies are visible, the leash is broken so the AI can chase
    # freely — prevents players from exploiting room-edge cheese.
    # Bosses use _decide_boss_action which always enforces the leash.
    room_bounds = None
    effective_obstacles = obstacles
    if ai.room_id and match_id:
        room_bounds = _get_room_bounds(match_id, ai.room_id)

    # Step 4: No visible enemies — try memory, then reinforce allies, then patrol
    if not enemies:
        # Leashed enemies return to room when idle — apply room boundary
        if room_bounds:
            leashed_obstacles = _add_room_leash_obstacles(
                obstacles, room_bounds, grid_width, grid_height
            )
            # Path back toward room center instead of just waiting
            center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
            center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
            ai_pos = (ai.position.x, ai.position.y)
            if not _is_in_room(ai.position.x, ai.position.y, room_bounds):
                # Outside room — path back home
                occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)
                next_step = get_next_step_toward(
                    ai_pos, (center_x, center_y),
                    grid_width, grid_height,
                    obstacles, occupied, door_tiles,
                )
                if next_step:
                    door_action = _maybe_interact_door(ai, next_step, door_tiles)
                    if door_action:
                        return door_action
                    return PlayerAction(
                        player_id=ai.player_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                        reason="aggro_leash_return",
                    )
            return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT, reason="aggro_leash_idle")

        # 4a: Check last-known enemy positions (pursue memory targets)
        memory_action = _pursue_memory_target(
            ai, all_units, grid_width, grid_height, obstacles, pending_moves, door_tiles,
        )
        if memory_action:
            return memory_action

        # 4b: Check if any ally is fighting — go help them
        reinforce_action = _reinforce_ally(
            ai, all_units, grid_width, grid_height, obstacles, pending_moves, door_tiles,
        )
        if reinforce_action:
            return reinforce_action

        # 4b2: Phase 29B — Chest seeking when idle — HERO PARTIES ONLY
        # PVPVE team leaders (hero_id=None, enemy_type=None) and hero ally
        # followers both benefit.  Dungeon enemies (enemy_type set) skip this.
        if getattr(ai, 'enemy_type', None) is None and chest_states:
            loot_action = _try_loot_adjacent_chest(ai, chest_states)
            if loot_action:
                return loot_action
            if ai_id not in _chest_seek_suppressed:
                seek_range = _CHEST_SEEK_MAX_RANGE.get(ai.ai_stance or "aggressive", 6)
                chest_target = _find_nearest_unopened_chest(ai, chest_states, seek_range)
                if chest_target:
                    occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)
                    next_step = get_next_step_toward(
                        (ai.position.x, ai.position.y), chest_target,
                        grid_width, grid_height, obstacles, occupied, door_tiles,
                    )
                    if next_step:
                        door_action = _maybe_interact_door(ai, next_step, door_tiles)
                        if door_action:
                            return door_action
                        return PlayerAction(
                            player_id=ai.player_id,
                            action_type=ActionType.MOVE,
                            target_x=next_step[0],
                            target_y=next_step[1],
                            reason="aggro_chest_seek",
                        )

        # 4c: Party members (hero allies) trail their leader instead of patrolling.
        # Phase 29D: Hero allies always follow their owner when idle — this
        # prevents the permanent stalling where hero allies with no visible
        # enemies WAIT indefinitely.  Only WAIT when already adjacent (dist 1)
        # to the owner, preserving the original anti-wander intent.
        if ai.hero_id is not None:
            owner = _find_owner(ai, all_units)
            if owner:
                owner_pos = (owner.position.x, owner.position.y)
                ai_pos_here = (ai.position.x, ai.position.y)
                if _chebyshev(ai_pos_here, owner_pos) > 1:
                    occupied_here = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)
                    next_step = get_next_step_toward(
                        ai_pos_here, owner_pos,
                        grid_width, grid_height, obstacles, occupied_here, door_tiles,
                    )
                    if next_step:
                        door_action = _maybe_interact_door(ai, next_step, door_tiles)
                        if door_action:
                            return door_action
                        return PlayerAction(
                            player_id=ai.player_id,
                            action_type=ActionType.MOVE,
                            target_x=next_step[0],
                            target_y=next_step[1],
                            reason="aggro_trail_owner",
                        )
            return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT, reason="aggro_idle_near_owner")

        # 4d: Phase 28C — Opportunistic loot seeking when idle — HERO PARTIES ONLY
        if getattr(ai, 'enemy_type', None) is None:
            scavenge_range = _SCAVENGE_MAX_RANGE.get(ai.ai_behavior or "aggressive", 5)
            loot_target = _find_nearest_ground_loot(ai, ground_items, max_range=scavenge_range)
            if loot_target:
                occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)
                next_step = get_next_step_toward(
                    (ai.position.x, ai.position.y), loot_target,
                    grid_width, grid_height, obstacles, occupied, door_tiles,
                )
                if next_step:
                    door_action = _maybe_interact_door(ai, next_step, door_tiles)
                    if door_action:
                        return door_action
                    return PlayerAction(
                        player_id=ai.player_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                        reason="aggro_scavenge_loot",
                    )

        # 4e: Strategic exploration for team leaders; patrol fallback for enemies
        if getattr(ai, 'is_team_leader', False) and match_id and ai_id not in _explore_suppressed:
            target = get_next_exploration_target(match_id, ai.team, (ai.position.x, ai.position.y))
            if target:
                _target_rid = target["room_id"]

                # --- RC#1 stagnation guard: skip room if targeted too long ---
                _prev = _explore_target_turns.get(ai_id)
                if _prev and _prev[0] == _target_rid:
                    _stag_count = _prev[1] + 1
                else:
                    _stag_count = 1
                _explore_target_turns[ai_id] = (_target_rid, _stag_count)

                if _stag_count >= _EXPLORE_STAGNATION_THRESHOLD:
                    skip_room(match_id, ai.team, _target_rid, _ai_tick_counter)
                    _explore_target_turns.pop(ai_id, None)
                    _explore_fail_count.get(ai_id, {}).pop(_target_rid, None)
                    # Fall through to patrol this tick; next tick picks new target
                else:
                    occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)
                    _leader_pos = (ai.position.x, ai.position.y)
                    _entrance = target["entrance"]

                    # Direct door check: if the entrance is a door tile and
                    # the leader is adjacent, interact immediately.  This
                    # handles the case where A* returns an empty path because
                    # the leader is already "at" the goal (Chebyshev ≤ 1).
                    if (
                        door_tiles
                        and _entrance in door_tiles
                        and max(abs(_leader_pos[0] - _entrance[0]),
                                abs(_leader_pos[1] - _entrance[1])) <= 1
                        and _leader_pos != _entrance
                    ):
                        if ai_id in _explore_fail_count:
                            _explore_fail_count[ai_id].pop(_target_rid, None)
                        return PlayerAction(
                            player_id=ai.player_id,
                            action_type=ActionType.INTERACT,
                            target_x=_entrance[0],
                            target_y=_entrance[1],
                            reason="open_door",
                        )

                    next_step = get_next_step_toward(
                        _leader_pos, _entrance,
                        grid_width, grid_height, obstacles, occupied, door_tiles,
                    )

                    # --- Root Cause #1 fix: track pathfinding failures ---
                    _explore_failed = False

                    if not next_step:
                        # A* found no path to target entrance
                        _explore_failed = True
                    else:
                        # Anti-backtrack: reject explore_room move that returns
                        # the leader to its previous tile (A→B→A).  Fall through
                        # to patrol, which has its own anti-backtrack guard.
                        _leader_hist = _position_history.get(ai_id, [])
                        _is_backtrack = len(_leader_hist) >= 2 and next_step == _leader_hist[-2]
                        if _is_backtrack:
                            _explore_failed = True
                        else:
                            door_action = _maybe_interact_door(ai, next_step, door_tiles)
                            if not door_action:
                                # Root Cause #2 fix: A* may route around a closed
                                # door (3x cost) even though the door is adjacent
                                # and leads toward the target.  Force INTERACT.
                                forced_door = _find_adjacent_door_toward_target(
                                    (ai.position.x, ai.position.y),
                                    target["entrance"],
                                    door_tiles,
                                )
                                if forced_door:
                                    door_action = PlayerAction(
                                        player_id=ai.player_id,
                                        action_type=ActionType.INTERACT,
                                        target_x=forced_door[0],
                                        target_y=forced_door[1],
                                        reason="open_door",
                                    )
                            if door_action:
                                # Success — clear failure counter
                                if ai_id in _explore_fail_count:
                                    _explore_fail_count[ai_id].pop(_target_rid, None)
                                return door_action
                            # Feed this move into patrol's visited history so the
                            # stale-area detector accounts for explore_room moves.
                            if ai_id not in _visited_history:
                                _visited_history[ai_id] = []
                            _visited_history[ai_id].append((ai.position.x, ai.position.y))
                            if len(_visited_history[ai_id]) > _MAX_VISIT_HISTORY:
                                _visited_history[ai_id] = _visited_history[ai_id][-_MAX_VISIT_HISTORY:]
                            # Success — clear failure counter
                            if ai_id in _explore_fail_count:
                                _explore_fail_count[ai_id].pop(_target_rid, None)
                            return PlayerAction(
                                player_id=ai.player_id,
                                action_type=ActionType.MOVE,
                                target_x=next_step[0],
                                target_y=next_step[1],
                                reason="explore_room",
                            )

                    # Handle explore failure: increment counter, skip room if threshold hit
                    if _explore_failed:
                        # RC#3: Door rescue — when pathfinding fails, check if
                        # there's an adjacent closed door the leader should open.
                        # The entrance may be BEYOND the door (room center), so
                        # the direct door check above won't fire.  Any adjacent
                        # closed door is likely the blocker.
                        if door_tiles:
                            _rescue_door = _find_adjacent_door_toward_target(
                                (ai.position.x, ai.position.y),
                                _entrance,
                                door_tiles,
                            )
                            if _rescue_door:
                                # Clear failure counter — door was the problem
                                if ai_id in _explore_fail_count:
                                    _explore_fail_count[ai_id].pop(_target_rid, None)
                                return PlayerAction(
                                    player_id=ai.player_id,
                                    action_type=ActionType.INTERACT,
                                    target_x=_rescue_door[0],
                                    target_y=_rescue_door[1],
                                    reason="open_door",
                                )

                        # RC#4: Door-path rescue — if we can't reach the
                        # entrance, try pathing to the nearest DOOR that
                        # connects to the target room.  The entrance may be
                        # the room center (unreachable), but the corridor
                        # door in front of the room IS reachable.
                        if match_id and door_tiles:
                            _room_doors = get_doors_for_room(match_id, _target_rid)
                            _leader_pos2 = (ai.position.x, ai.position.y)
                            _occ2 = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)
                            _best_door_step = None
                            _best_door_dist = float("inf")
                            _best_door_pos = None
                            for _dp in _room_doors:
                                if _dp not in door_tiles:
                                    continue  # door already open
                                _dp_dist = max(abs(_leader_pos2[0] - _dp[0]), abs(_leader_pos2[1] - _dp[1]))
                                if _dp_dist <= 1:
                                    # Adjacent to this door — interact directly
                                    if ai_id in _explore_fail_count:
                                        _explore_fail_count[ai_id].pop(_target_rid, None)
                                    return PlayerAction(
                                        player_id=ai.player_id,
                                        action_type=ActionType.INTERACT,
                                        target_x=_dp[0],
                                        target_y=_dp[1],
                                        reason="open_door",
                                    )
                                if _dp_dist < _best_door_dist:
                                    _step = get_next_step_toward(
                                        _leader_pos2, _dp,
                                        grid_width, grid_height,
                                        obstacles, _occ2, door_tiles,
                                    )
                                    if _step:
                                        _best_door_step = _step
                                        _best_door_dist = _dp_dist
                                        _best_door_pos = _dp
                            if _best_door_step:
                                if ai_id in _explore_fail_count:
                                    _explore_fail_count[ai_id].pop(_target_rid, None)
                                # Check if stepping onto a door
                                _door_act2 = _maybe_interact_door(ai, _best_door_step, door_tiles)
                                if _door_act2:
                                    return _door_act2
                                return PlayerAction(
                                    player_id=ai.player_id,
                                    action_type=ActionType.MOVE,
                                    target_x=_best_door_step[0],
                                    target_y=_best_door_step[1],
                                    reason="explore_room",
                                )

                        if ai_id not in _explore_fail_count:
                            _explore_fail_count[ai_id] = {}

                        # Only count as a genuine pathfind failure if the room
                        # is structurally unreachable (ignoring other units).
                        # If the path is just blocked by enemies/other teams in
                        # the corridor, don't penalize — wait for them to move.
                        _structural_fail = True
                        _empty_occ: set[tuple[int, int]] = set()
                        _recheck = get_next_step_toward(
                            (ai.position.x, ai.position.y), _entrance,
                            grid_width, grid_height, obstacles, _empty_occ, door_tiles,
                        )
                        if _recheck:
                            _structural_fail = False  # Path exists, just blocked by units

                        if _structural_fail:
                            _explore_fail_count[ai_id][_target_rid] = \
                                _explore_fail_count[ai_id].get(_target_rid, 0) + 1
                            if _explore_fail_count[ai_id][_target_rid] >= _EXPLORE_FAIL_THRESHOLD:
                                skip_room(match_id, ai.team, _target_rid, _ai_tick_counter)
                                _explore_fail_count[ai_id].pop(_target_rid, None)
                                _explore_target_turns.pop(ai_id, None)
        # Build exploration hint for patrol fallback — gives directional
        # preference toward unexplored rooms when patrol has no waypoint.
        _explore_hint: tuple[int, int] | None = None
        if getattr(ai, 'is_team_leader', False) and match_id:
            _hint_target = get_next_exploration_target(match_id, ai.team, (ai.position.x, ai.position.y))
            if _hint_target:
                _explore_hint = _hint_target["entrance"]
        return _patrol_action(ai, grid_width, grid_height, obstacles, all_units, pending_moves, door_tiles, allow_team_swap=allow_swap, exploration_hint=_explore_hint)

    # Enemies found — clear patrol waypoint so AI doesn't resume old patrol
    _patrol_targets.pop(ai_id, None)

    # ── Chase distance cap: leashed enemies disengage if too far from home ──
    if ai.room_id and match_id and room_bounds:
        center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
        center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
        chase_dist = abs(ai.position.x - center_x) + abs(ai.position.y - center_y)
        if chase_dist > _MAX_LEASH_CHASE_DISTANCE:
            occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)
            next_step = get_next_step_toward(
                (ai.position.x, ai.position.y), (center_x, center_y),
                grid_width, grid_height, obstacles, occupied, door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai.player_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                    reason="aggro_leash_exceeded",
                )
            return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT, reason="aggro_leash_return_stuck")

    # Step 5: Pick best enemy using weighted scoring
    target = _pick_best_target(ai, enemies, all_units)

    # Step 5a: Try skill usage before basic attacks (enemy spellcasting)
    if ai.class_id:
        skill_action = _decide_skill_usage(
            ai, enemies, all_units, grid_width, grid_height, obstacles,
        )
        if skill_action:
            return skill_action

    target_pos = Position(x=target.position.x, y=target.position.y)

    # Pre-compute occupied tiles and pathing for movement decisions
    # Phase 7A-3: Use _build_occupied_set with pending_moves prediction
    occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly, allow_team_swap=allow_swap)

    # Chebyshev distance to target (max of dx, dy — matches diagonal movement)
    dist_to_target = max(
        abs(ai.position.x - target.position.x),
        abs(ai.position.y - target.position.y),
    )

    ranged_cd = ai.cooldowns.get("ranged_attack", 0)

    # Phase 17: Ranged/caster/scout role check — these classes should kite, not rush melee
    # Phase 23 fix: controller (Plague Doctor), offensive_support (Bard), totemic_support (Shaman)
    # are also ranged roles — they should never rush melee between skill cooldowns.
    role = _get_role_for_class(ai.class_id) if ai.class_id else None
    is_ranged_role = role in ("ranged_dps", "caster_dps", "scout", "controller", "offensive_support", "totemic_support") if role else False

    # Step 5b: Ranged kiting — ranged/caster roles retreat when enemies get close
    # Controller (Plague Doctor) kites at 3 tiles — squishy support that folds
    # to melee pressure.  Bard uses 2 like other ranged DPS so it stays closer
    # to the fight for Ballad/Cacophony coverage.
    # Shaman only kites when adjacent (dist 1) — needs to stay close to
    # frontline for totem placement.
    _kite_threshold = 3 if role == "controller" else (1 if role == "totemic_support" else 2)
    if is_ranged_role and dist_to_target <= _kite_threshold:
        # Phase 21E: Bard ally-proximity retreat — when kiting, prefer retreat
        # tiles that stay near allies so buff/skill auras maintain coverage.
        ally_positions = None
        if role == "offensive_support":
            ally_positions = [
                (u.position.x, u.position.y)
                for u in all_units.values()
                if u.is_alive and u.team == ai.team and u.player_id != ai.player_id
            ]
        retreat_tile = _find_retreat_tile(
            (ai.position.x, ai.position.y),
            (target.position.x, target.position.y),
            grid_width, grid_height,
            effective_obstacles, occupied,
            ally_positions=ally_positions,
        )
        if retreat_tile:
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.MOVE,
                target_x=retreat_tile[0],
                target_y=retreat_tile[1],
                reason="aggro_kite_retreat",
            )
        # Can't retreat — ranged roles fall through to ranged attack check

    # Step 5c: Adjacent → melee attack (highest priority when next to enemy)
    # Ranged roles skip melee — they prefer ranged attacks even at close range
    if not is_ranged_role and is_adjacent(ai.position, target_pos):
        return PlayerAction(
            player_id=ai.player_id,
            action_type=ActionType.ATTACK,
            target_x=target.position.x,
            target_y=target.position.y,
            target_id=target.player_id,
            reason="aggro_melee_adjacent",
        )

    # Step 6: If close (within 3 tiles), rush to melee range (non-ranged roles only).
    # Ranged roles prefer to stay at distance and use ranged attacks instead.
    if not is_ranged_role and dist_to_target <= 3:
        next_step = get_next_step_toward(
            (ai.position.x, ai.position.y),
            (target.position.x, target.position.y),
            grid_width, grid_height,
            effective_obstacles, occupied, door_tiles,
        )
        if next_step:
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.MOVE,
                target_x=next_step[0],
                target_y=next_step[1],
                reason="aggro_rush_melee",
            )
        # Can't move closer — use ranged as fallback if available
        if ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
            if has_line_of_sight(
                ai.position.x, ai.position.y,
                target.position.x, target.position.y,
                obstacles,
            ):
                return PlayerAction(
                    player_id=ai.player_id,
                    action_type=ActionType.RANGED_ATTACK,
                    target_x=target.position.x,
                    target_y=target.position.y,
                    target_id=target.player_id,
                    reason="aggro_rush_blocked_ranged",
                )

    # Step 7: Far away (>3 tiles) — harass with ranged if available, otherwise close distance
    if ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
        if has_line_of_sight(
            ai.position.x, ai.position.y,
            target.position.x, target.position.y,
            obstacles,
        ):
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.RANGED_ATTACK,
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
                reason="aggro_ranged_harass",
            )

    # Step 8: Move toward target using A*
    # Controller / offensive_support hold-position: when ranged is on CD and
    # enemies are within medium range, hold position instead of advancing into
    # danger.  Prevents squishy ranged supports from creeping into melee.
    if is_ranged_role and role in ("controller", "caster_dps") and ranged_cd > 0 and dist_to_target <= 4:
        return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT, reason="aggro_controller_hold")

    # Phase 21E revised: Bard advance — when ranged is on CD, advance toward
    # the enemy to pre-position for the next skill cast (Dirge/Cacophony) or
    # ranged shot instead of passively drifting to ally centroid.  This keeps
    # the Bard engaged in the fight rather than wasting turns WAITing.
    # (Falls through to the normal A* move-toward-target below.)

    next_step = get_next_step_toward(
        (ai.position.x, ai.position.y),
        (target.position.x, target.position.y),
        grid_width, grid_height,
        effective_obstacles, occupied, door_tiles,
    )

    if next_step:
        door_action = _maybe_interact_door(ai, next_step, door_tiles)
        if door_action:
            return door_action
        return PlayerAction(
            player_id=ai.player_id,
            action_type=ActionType.MOVE,
            target_x=next_step[0],
            target_y=next_step[1],
            reason="aggro_pathfind_toward_target",
        )

    # Fallback: ranged if stuck and cooldown ready (last resort)
    if ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
        if has_line_of_sight(
            ai.position.x, ai.position.y,
            target.position.x, target.position.y,
            obstacles,
        ):
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.RANGED_ATTACK,
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
                reason="aggro_stuck_ranged_fallback",
            )

    # Truly stuck: wait
    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.WAIT,
        reason="aggro_stuck",
    )


# ---------------------------------------------------------------------------
# Room Leash Helper
# ---------------------------------------------------------------------------

def _add_room_leash_obstacles(
    obstacles: set[tuple[int, int]],
    room_bounds: dict,
    grid_width: int,
    grid_height: int,
) -> set[tuple[int, int]]:
    """Create an expanded obstacle set that includes all tiles outside the room.

    This effectively prevents an AI from pathing outside its assigned room.
    The returned set is a new copy (does not modify the original).
    """
    leashed = set(obstacles)
    x_min, y_min = room_bounds["x_min"], room_bounds["y_min"]
    x_max, y_max = room_bounds["x_max"], room_bounds["y_max"]
    for x in range(grid_width):
        for y in range(grid_height):
            if not (x_min <= x <= x_max and y_min <= y <= y_max):
                leashed.add((x, y))
    return leashed


# ---------------------------------------------------------------------------
# Ranged AI Behavior (Phase 4C — Skeleton)
# ---------------------------------------------------------------------------

def _decide_ranged_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    ground_items: dict[str, list] | None = None,
) -> PlayerAction | None:
    """Ranged AI behavior — maintain distance, ranged attack, retreat if close.

    Decision loop:
      1. Compute FOV + find visible enemies
      2. No enemies → wait (leashed) or patrol (unleashed)
      3. Pick best enemy target
      4. If adjacent → retreat away from enemy (move to max-distance tile)
      5. If within 2 tiles → retreat (too close for comfort)
      6. If in ranged range + LOS + cooldown ready → ranged attack
      7. If ranged on cooldown → move to maintain ideal distance (3-4 tiles)
      8. If out of range → move closer (but not too close)

    Room leashing: If the AI has a room_id and no enemies are visible,
    it stays in / returns to its room. When enemies ARE visible, the
    leash is broken and the AI chases freely (prevents room-edge cheese).
    """
    # Phase 28A: Potion check before any combat decisions — HERO PARTIES ONLY
    if getattr(ai, 'enemy_type', None) is None:
        threshold = _ENEMY_POTION_THRESHOLDS.get("ranged", 0.40)
        potion_action = _should_use_potion(ai, hp_threshold=threshold)
        if potion_action:
            return potion_action

    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))
    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)
    # Phase 18D: Ghostly champions can phase through occupied tiles
    is_ghostly = getattr(ai, 'champion_type', None) == "ghostly"

    # Compute FOV
    own_fov = compute_fov(
        ai.position.x, ai.position.y,
        ai.vision_range,
        grid_width, grid_height,
        obstacles,
    )
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov

    # Find visible enemies
    enemies: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive or unit.player_id == ai_id or unit.team == ai.team:
            continue
        if (unit.position.x, unit.position.y) in visible_tiles:
            enemies.append(unit)

    _update_enemy_memory(ai_id, enemies, all_units)

    # Room leashing: only apply when idle (no visible enemies).
    # When enemies are visible, the leash is broken so the AI can chase
    # freely — prevents players from exploiting room-edge cheese.
    room_bounds = None
    effective_obstacles = obstacles
    if ai.room_id and match_id:
        room_bounds = _get_room_bounds(match_id, ai.room_id)

    if not enemies:
        if room_bounds:
            # Path back toward room center if outside
            if not _is_in_room(ai.position.x, ai.position.y, room_bounds):
                center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
                center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
                occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
                next_step = get_next_step_toward(
                    ai_pos, (center_x, center_y),
                    grid_width, grid_height,
                    obstacles, occupied, door_tiles,
                )
                if next_step:
                    door_action = _maybe_interact_door(ai, next_step, door_tiles)
                    if door_action:
                        return door_action
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                        reason="ranged_leash_return",
                    )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="ranged_leash_idle")
        # Party members (hero allies) hold position instead of patrolling
        if ai.hero_id is not None:
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="ranged_hero_hold")

        # Phase 28C: Opportunistic loot seeking when idle — HERO PARTIES ONLY
        if getattr(ai, 'enemy_type', None) is None:
            scavenge_range = _SCAVENGE_MAX_RANGE.get("ranged", 3)
            loot_target = _find_nearest_ground_loot(ai, ground_items, max_range=scavenge_range)
            if loot_target:
                occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
                next_step = get_next_step_toward(
                    ai_pos, loot_target,
                    grid_width, grid_height, obstacles, occupied, door_tiles,
                )
                if next_step:
                    door_action = _maybe_interact_door(ai, next_step, door_tiles)
                    if door_action:
                        return door_action
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                        reason="ranged_scavenge_loot",
                    )

        return _patrol_action(ai, grid_width, grid_height, obstacles, all_units, pending_moves, door_tiles)

    _patrol_targets.pop(ai_id, None)

    # ── Chase distance cap: leashed enemies disengage if too far from home ──
    if ai.room_id and match_id and room_bounds:
        center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
        center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
        chase_dist = abs(ai.position.x - center_x) + abs(ai.position.y - center_y)
        if chase_dist > _MAX_LEASH_CHASE_DISTANCE:
            occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
            next_step = get_next_step_toward(
                ai_pos, (center_x, center_y),
                grid_width, grid_height, obstacles, occupied, door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                    reason="ranged_leash_exceeded",
                )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="ranged_leash_return_stuck")

    target = _pick_best_target(ai, enemies, all_units)
    target_pos = Position(x=target.position.x, y=target.position.y)

    # Try skill usage before basic attacks (enemy spellcasting — e.g. Medusa)
    if ai.class_id:
        skill_action = _decide_skill_usage(
            ai, enemies, all_units, grid_width, grid_height, obstacles,
        )
        if skill_action:
            return skill_action

    # Phase 7A-3: Use _build_occupied_set with pending_moves prediction
    occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)

    dist_to_target = max(
        abs(ai.position.x - target.position.x),
        abs(ai.position.y - target.position.y),
    )
    ranged_cd = ai.cooldowns.get("ranged_attack", 0)

    # Ideal distance for ranged AI: 3-4 tiles away
    IDEAL_MIN = 3
    IDEAL_MAX = ranged_range - 1  # Stay within range but not at edge

    # Too close (adjacent or within 2 tiles) → retreat away from target
    if dist_to_target <= 2:
        retreat_tile = _find_retreat_tile(
            ai_pos,
            (target.position.x, target.position.y),
            grid_width, grid_height,
            effective_obstacles, occupied,
        )
        if retreat_tile:
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=retreat_tile[0],
                target_y=retreat_tile[1],
                reason="ranged_retreat_close",
            )
        # Can't retreat — melee as last resort
        if is_adjacent(ai.position, target_pos):
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.ATTACK,
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
                reason="ranged_melee_fallback",
            )

    # In range + cooldown ready + LOS → ranged attack
    if ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
        if has_line_of_sight(
            ai.position.x, ai.position.y,
            target.position.x, target.position.y,
            obstacles,
        ):
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.RANGED_ATTACK,
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
                reason="ranged_attack",
            )

    # Out of range or no LOS → move closer but maintain ideal distance
    if dist_to_target > ranged_range:
        next_step = get_next_step_toward(
            ai_pos,
            (target.position.x, target.position.y),
            grid_width, grid_height,
            effective_obstacles, occupied, door_tiles,
        )
        if next_step:
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=next_step[0],
                target_y=next_step[1],
                reason="ranged_close_distance",
            )

    # In range but ranged on cooldown → try to maintain ideal distance
    if IDEAL_MIN <= dist_to_target <= IDEAL_MAX:
        # Good position — wait for cooldown
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="ranged_hold_position")

    # Fallback: wait
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="ranged_wait_fallback")


def _find_retreat_tile(
    ai_pos: tuple[int, int],
    threat_pos: tuple[int, int],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    ally_positions: list[tuple[int, int]] | None = None,
) -> tuple[int, int] | None:
    """Find the best adjacent tile to retreat away from a threat.

    Picks the walkable neighbor that maximizes distance from the threat.

    Phase 21E: When ally_positions is provided (Bard), ties are broken by
    preferring tiles closer to the ally centroid so the Bard kites toward
    teammates rather than into a corner alone.
    """
    # Pre-compute ally centroid for tie-breaking
    ally_cx, ally_cy = 0, 0
    if ally_positions:
        ally_cx = sum(p[0] for p in ally_positions) // len(ally_positions)
        ally_cy = sum(p[1] for p in ally_positions) // len(ally_positions)

    best = None
    best_dist = -1
    best_ally_dist = 999  # lower is better (closer to allies)

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = ai_pos[0] + dx, ai_pos[1] + dy
            if not (0 <= nx < grid_width and 0 <= ny < grid_height):
                continue
            if (nx, ny) in obstacles or (nx, ny) in occupied:
                continue
            dist = max(abs(nx - threat_pos[0]), abs(ny - threat_pos[1]))
            if ally_positions:
                ally_dist = max(abs(nx - ally_cx), abs(ny - ally_cy))
                # Primary: maximize distance from threat
                # Secondary: minimize distance to ally centroid
                if dist > best_dist or (dist == best_dist and ally_dist < best_ally_dist):
                    best_dist = dist
                    best_ally_dist = ally_dist
                    best = (nx, ny)
            else:
                if dist > best_dist:
                    best_dist = dist
                    best = (nx, ny)

    return best


# ---------------------------------------------------------------------------
# Boss AI Behavior (Phase 4C — Undead Knight)
# ---------------------------------------------------------------------------

def _decide_boss_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
) -> PlayerAction | None:
    """Boss AI behavior — guard room, attack intruders, never leave room.

    Decision loop:
      1. Compute FOV + find visible enemies
      2. No enemies → wait at guard position (center of room)
      3. If enemy in room → engage (melee priority, then chase within room)
      4. If enemy visible but outside room → wait (guardian doesn't chase)
      5. Never leaves assigned room bounds

    Boss-specific:
      - Higher aggro range within room (engages anything visible in room)
      - Melee-only (ranged_range=1 typically), but will use ranged if configured
      - Won't pursue outside room bounds — returns to center when idle
    """
    # Phase 28A: Potion check before any combat decisions — HERO PARTIES ONLY
    if getattr(ai, 'enemy_type', None) is None:
        threshold = _ENEMY_POTION_THRESHOLDS.get("boss", 0.25)
        potion_action = _should_use_potion(ai, hp_threshold=threshold)
        if potion_action:
            return potion_action

    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)
    # Phase 18D: Ghostly champions can phase through occupied tiles
    is_ghostly = getattr(ai, 'champion_type', None) == "ghostly"

    # Compute FOV
    own_fov = compute_fov(
        ai.position.x, ai.position.y,
        ai.vision_range,
        grid_width, grid_height,
        obstacles,
    )
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov

    # Room leashing — boss MUST have a room
    room_bounds = None
    effective_obstacles = obstacles
    if ai.room_id and match_id:
        room_bounds = _get_room_bounds(match_id, ai.room_id)
        if room_bounds:
            effective_obstacles = _add_room_leash_obstacles(
                obstacles, room_bounds, grid_width, grid_height
            )

    # Find visible enemies that are INSIDE the boss's room (or adjacent to it)
    enemies_in_room: list[PlayerState] = []
    enemies_visible: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive or unit.player_id == ai_id or unit.team == ai.team:
            continue
        if (unit.position.x, unit.position.y) in visible_tiles:
            enemies_visible.append(unit)
            # Check if enemy is in the room (or close enough to engage)
            if room_bounds and _is_in_room(unit.position.x, unit.position.y, room_bounds):
                enemies_in_room.append(unit)
            elif not room_bounds:
                # No room bounds — treat all visible enemies as in-room
                enemies_in_room.append(unit)

    occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)

    # No enemies in room → return to room center or wait
    if not enemies_in_room:
        if room_bounds:
            center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
            center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
            if ai_pos != (center_x, center_y):
                next_step = get_next_step_toward(
                    ai_pos, (center_x, center_y),
                    grid_width, grid_height,
                    effective_obstacles, occupied, door_tiles,
                )
                if next_step:
                    door_action = _maybe_interact_door(ai, next_step, door_tiles)
                    if door_action:
                        return door_action
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                        reason="boss_return_to_center",
                    )
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="boss_idle")

    # Enemy in room — engage aggressively
    target = _pick_best_target(ai, enemies_in_room, all_units)
    target_pos = Position(x=target.position.x, y=target.position.y)

    # Try skill usage before basic attacks (boss spellcasting — e.g. Reaper)
    if ai.class_id:
        skill_action = _decide_skill_usage(
            ai, enemies_in_room, all_units, grid_width, grid_height, obstacles,
        )
        if skill_action:
            return skill_action

    # Adjacent → melee attack
    if is_adjacent(ai.position, target_pos):
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.ATTACK,
            target_x=target.position.x,
            target_y=target.position.y,
            target_id=target.player_id,
            reason="boss_melee_intruder",
        )

    ranged_range = getattr(ai, 'ranged_range', 1)
    ranged_cd = ai.cooldowns.get("ranged_attack", 0)

    # Ranged attack if available
    if ranged_range > 1 and ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
        if has_line_of_sight(
            ai.position.x, ai.position.y,
            target.position.x, target.position.y,
            obstacles,
        ):
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.RANGED_ATTACK,
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
                reason="boss_ranged_intruder",
            )

    # Chase within room using leashed obstacles
    next_step = get_next_step_toward(
        ai_pos,
        (target.position.x, target.position.y),
        grid_width, grid_height,
        effective_obstacles, occupied, door_tiles,
    )
    if next_step:
        door_action = _maybe_interact_door(ai, next_step, door_tiles)
        if door_action:
            return door_action
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.MOVE,
            target_x=next_step[0],
            target_y=next_step[1],
            reason="boss_chase_intruder",
        )

    # Stuck — wait
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT, reason="boss_stuck")


# ---------------------------------------------------------------------------
# AI Tick Runner
# ---------------------------------------------------------------------------

def run_ai_decisions(
    ai_ids: list[str],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov_map: dict[str, set[tuple[int, int]]] | None = None,
    match_id: str | None = None,
    controlled_ids: set[str] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    portal: dict | None = None,
    match_state=None,
    ground_items: dict[str, list] | None = None,
    chest_states: dict[str, str] | None = None,
) -> list[PlayerAction]:
    """Run AI decision logic for all AI units and return their actions.

    This should be called during tick processing, before action resolution.

    Phase 7A-3: Tracks pending MOVE decisions as each AI is processed
    sequentially.  Later AI units see earlier movers' current positions as
    "vacating" and their targets as "claimed", preventing hallway gridlock
    when multiple allies are pathing through the same corridor.

    Args:
        team_fov_map: Optional dict mapping team letter ("a", "b", etc.)
                      to the combined team FOV set. AI will use its team's
                      shared vision to spot enemies.
        match_id: Match ID for room bounds lookup (Phase 4C dungeon leashing).
        controlled_ids: Set of AI unit IDs currently being player-controlled.
                        These units will be skipped (player queued their actions).
        door_tiles: Phase 7D-1 — set of closed-door positions for door-aware
                    A*.  Passed through to ``decide_ai_action()`` so AI can
                    plan paths through closed doors at elevated cost.
        portal: Phase 12C — active portal dict or None. Hero allies will
                pathfind to the portal and extract when it's active.
    """
    actions: list[PlayerAction] = []

    # Phase 29D: Increment global tick counter for post-combat tracking
    global _ai_tick_counter
    _ai_tick_counter += 1

    # Root Cause #1 fix: expire stale room skips each tick
    if match_id:
        expire_skipped_rooms(match_id, _ai_tick_counter)

    # Phase 7A-3: Track pending moves — {unit_id: (from_pos, to_pos)}
    # Each AI decision sees the pending moves of all previously-decided AI units
    # this tick, preventing sequential pathfinding from causing gridlock.
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}

    for ai_id in ai_ids:
        ai = all_units.get(ai_id)
        if not ai or not ai.is_alive:
            # Clean up patrol + memory + position history state for dead AI
            _patrol_targets.pop(ai_id, None)
            _visited_history.pop(ai_id, None)
            _stale_area_counter.pop(ai_id, None)
            _enemy_memory.pop(ai_id, None)
            _position_history.pop(ai_id, None)
            _last_combat_tick.pop(ai_id, None)
            _explore_total_turns.pop(ai_id, None)
            continue

        # Phase 12C: Skip extracted AI units
        if ai.extracted:
            continue

        # Skip AI units that are player-controlled and have queued actions
        if controlled_ids and ai_id in controlled_ids:
            continue

        # Anti-oscillation: record current position in history
        ai_pos = (ai.position.x, ai.position.y)
        if ai_id not in _position_history:
            _position_history[ai_id] = []
        _position_history[ai_id].append(ai_pos)
        if len(_position_history[ai_id]) > _POSITION_HISTORY_LEN:
            _position_history[ai_id] = _position_history[ai_id][-_POSITION_HISTORY_LEN:]

        # RC#3: Total-turn stagnation guard for team leaders.
        # Increments every tick regardless of what action the leader takes.
        # If a leader's best exploration target stays the same room for
        # _EXPLORE_TOTAL_STAGNATION_THRESHOLD ticks it gets skipped.
        if getattr(ai, 'is_team_leader', False) and match_id:
            _tt_target = get_next_exploration_target(match_id, ai.team, ai_pos)
            if _tt_target:
                _tt_rid = _tt_target["room_id"]
                _tt_prev = _explore_total_turns.get(ai_id)
                if _tt_prev and _tt_prev[0] == _tt_rid:
                    _tt_count = _tt_prev[1] + 1
                else:
                    _tt_count = 1
                _explore_total_turns[ai_id] = (_tt_rid, _tt_count)
                if _tt_count >= _EXPLORE_TOTAL_STAGNATION_THRESHOLD:
                    skip_room(match_id, ai.team, _tt_rid, _ai_tick_counter)
                    _explore_total_turns.pop(ai_id, None)
                    _explore_target_turns.pop(ai_id, None)
                    _explore_fail_count.pop(ai_id, None)
            else:
                _explore_total_turns.pop(ai_id, None)

        # Look up this AI's team FOV from the pre-computed map
        ai_team_fov = None
        if team_fov_map:
            ai_team_fov = team_fov_map.get(ai.team)

        action = decide_ai_action(
            ai, all_units, grid_width, grid_height, obstacles,
            team_fov=ai_team_fov,
            match_id=match_id,
            pending_moves=pending_moves if pending_moves else None,
            door_tiles=door_tiles,
            portal=portal,
            match_state=match_state,
            ground_items=ground_items,
            chest_states=chest_states,
        )

        # Anti-oscillation: suppress MOVE if it returns to the immediately
        # previous position (A→B→A pattern) and there is no nearby enemy
        # that would justify the backtrack (kiting, retreating, chasing).
        # Phase 32A: Exempt follow-regroup and follow-trail moves — these are
        # intentional movements toward the party leader that should never be
        # suppressed.  Followers hanging back behind corners is worse than a
        # brief oscillation while navigating a tight corridor.
        _follow_exempt_reasons = (
            "follow_regroup", "follow_trail", "follow_rush_melee",
            "follow_move_to_target", "follow_corridor_push",
            "follow_combat_approach",
        )
        _is_follow_exempt = (
            action
            and action.reason
            and action.reason.startswith(_follow_exempt_reasons)
        )
        if (
            action
            and action.action_type == ActionType.MOVE
            and action.target_x is not None
            and not _is_follow_exempt
        ):
            history = _position_history.get(ai_id, [])
            if len(history) >= 2:
                target = (action.target_x, action.target_y)
                prev_pos = history[-2]  # position one turn ago
                if target == prev_pos:
                    # Check for nearby enemies — allow oscillation in combat
                    has_nearby_enemy = False
                    for u in all_units.values():
                        if (
                            u.is_alive
                            and u.team != ai.team
                            and u.player_id != ai_id
                            and not getattr(u, 'extracted', False)
                        ):
                            dist = max(
                                abs(u.position.x - ai.position.x),
                                abs(u.position.y - ai.position.y),
                            )
                            if dist <= _OSCILLATION_COMBAT_RANGE:
                                has_nearby_enemy = True
                                break
                    if not has_nearby_enemy:
                        # Clear patrol waypoint so patrol picks a fresh
                        # target instead of routing back to the same tile.
                        _patrol_targets.pop(ai_id, None)

                    # Extended oscillation detection fires REGARDLESS of
                    # nearby enemies.  A single A→B→A reversal is allowed
                    # in combat (kiting, repositioning), but if the unit
                    # has been stuck on ≤2 unique tiles for several turns
                    # it's not making meaningful progress and should yield.
                    # Combat context uses a longer window to tolerate brief
                    # repositioning; out-of-combat is stricter.
                    confirmed_oscillation = False
                    _is_leader = getattr(ai, 'is_team_leader', False)

                    if has_nearby_enemy:
                        _osc_window = 6 if not _is_leader else 12
                    else:
                        _osc_window = 4 if not _is_leader else 8

                    if len(history) >= _osc_window and len(set(history[-_osc_window:])) <= 2:
                        _explore_suppressed.add(ai_id)
                        _chest_seek_suppressed.add(ai_id)
                        _suppress_start_tick.setdefault(ai_id, _ai_tick_counter)
                        confirmed_oscillation = True

                    # Broader stall detection: if the entire recent
                    # history fits inside a tiny bounding box (<=2
                    # tiles wide/tall), the unit is shuffling within
                    # one room.  Only suppress non-leaders outside of
                    # combat — combat units naturally stay in small areas,
                    # and leaders need freedom to explore.
                    if not has_nearby_enemy and not _is_leader and len(history) >= 12:
                        xs = [p[0] for p in history[-12:]]
                        ys = [p[1] for p in history[-12:]]
                        if max(xs) - min(xs) <= 2 and max(ys) - min(ys) <= 2:
                            _explore_suppressed.add(ai_id)
                            _chest_seek_suppressed.add(ai_id)
                            _suppress_start_tick.setdefault(ai_id, _ai_tick_counter)
                            confirmed_oscillation = True

                    if confirmed_oscillation:
                        action = PlayerAction(
                            player_id=ai_id,
                            action_type=ActionType.WAIT,
                            reason="oscillation_suppressed",
                        )

        # Phase 30 stall breaker: if a non-leader unit has been at the same
        # position for 3+ consecutive turns and is still trying to MOVE, it
        # is likely deadlocked with another same-team unit over the same
        # target tile.  Force a WAIT on alternating turns (parity based on
        # player_id hash) so that only one of the competing units yields at
        # a time, letting the other pass and breaking the deadlock.
        if (
            action
            and action.action_type == ActionType.MOVE
            and not getattr(ai, 'is_team_leader', False)
        ):
            history = _position_history.get(ai_id, [])
            if len(history) >= 3 and len(set(history[-3:])) == 1:
                # Deterministic parity from player_id (avoids Python hash
                # randomisation so simulations stay reproducible across runs).
                pid_parity = sum(ord(c) for c in ai_id) % 2
                if _ai_tick_counter % 2 == pid_parity:
                    action = PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.WAIT,
                        reason="stall_breaker_yield",
                    )

        if action:
            # Lift explore/chest-seek suppression.
            # Two paths:
            #   A) MOVE that's far enough from the stuck centroid (normal lift)
            #   B) Hard timeout — unconditionally lift after _MAX_SUPPRESS_TURNS
            #      to prevent the deadlock where suppression forces WAIT,
            #      but the lift condition requires MOVE.
            if ai_id in _explore_suppressed:
                suppressed_since = _suppress_start_tick.get(ai_id, 0)
                elapsed = _ai_tick_counter - suppressed_since

                # Path B: Hard timeout — break the deadlock unconditionally
                if elapsed >= _MAX_SUPPRESS_TURNS:
                    _explore_suppressed.discard(ai_id)
                    _chest_seek_suppressed.discard(ai_id)
                    _suppress_start_tick.pop(ai_id, None)
                    # Also clear visited history so patrol gets fresh candidates
                    _visited_history.pop(ai_id, None)
                    _stale_area_counter.pop(ai_id, 0)
                # Path A: Normal lift — MOVE far enough from stuck centroid
                elif (
                    action.action_type == ActionType.MOVE
                    and action.target_x is not None
                    and elapsed >= _MIN_SUPPRESS_TURNS
                ):
                    history = _position_history.get(ai_id, [])
                    if history:
                        avg_x = sum(p[0] for p in history) / len(history)
                        avg_y = sum(p[1] for p in history) / len(history)
                        dist_from_centroid = (
                            abs(action.target_x - avg_x)
                            + abs(action.target_y - avg_y)
                        )
                        if dist_from_centroid >= 3:
                            _explore_suppressed.discard(ai_id)
                            _chest_seek_suppressed.discard(ai_id)
                            _suppress_start_tick.pop(ai_id, None)

            actions.append(action)
            # Phase 7A-3: Record this action if it's a MOVE so later AI
            # units know this tile is being vacated.
            if action.action_type == ActionType.MOVE and action.target_x is not None:
                from_pos = (ai.position.x, ai.position.y)
                to_pos = (action.target_x, action.target_y)
                if from_pos != to_pos:
                    pending_moves[ai_id] = (from_pos, to_pos)

    return actions


def clear_ai_patrol_state(ai_id: str | None = None) -> None:
    """Clear patrol + memory + position history state for a specific AI or all AI units.

    Call this when a match ends to prevent stale state.
    """
    if ai_id:
        _patrol_targets.pop(ai_id, None)
        _visited_history.pop(ai_id, None)
        _stale_area_counter.pop(ai_id, None)
        _enemy_memory.pop(ai_id, None)
        _position_history.pop(ai_id, None)
        _last_combat_tick.pop(ai_id, None)
        _explore_suppressed.discard(ai_id)
        _chest_seek_suppressed.discard(ai_id)
        _suppress_start_tick.pop(ai_id, None)
        _explore_fail_count.pop(ai_id, None)
        _explore_target_turns.pop(ai_id, None)
        _explore_total_turns.pop(ai_id, None)
    else:
        _patrol_targets.clear()
        _visited_history.clear()
        _stale_area_counter.clear()
        _enemy_memory.clear()
        _position_history.clear()
        _last_combat_tick.clear()
        _explore_suppressed.clear()
        _chest_seek_suppressed.clear()
        _suppress_start_tick.clear()
        _explore_fail_count.clear()
        _explore_target_turns.clear()
        _explore_total_turns.clear()

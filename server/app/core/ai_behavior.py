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
    _find_owner,
    _chebyshev,
    _maybe_interact_door,
    _has_heal_potions,
    _should_retreat,
    _find_retreat_destination,
    _should_use_potion,
    _decide_stance_action,
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _decide_hold_action,
)


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
        return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT)

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
        return _decide_stance_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, portal=portal, match_state=match_state)

    # ── Cross-room aggro fix: suppress team-shared FOV for leashed enemies ──
    # Enemies inside their assigned room should only detect players via their
    # own vision, not through allies in distant rooms.  Once an enemy leaves
    # its room (leash broken / chasing), it regains access to team FOV.
    if ai.room_id and match_id and team_fov is not None:
        _rb = _get_room_bounds(match_id, ai.room_id)
        if _rb and _is_in_room(ai.position.x, ai.position.y, _rb):
            team_fov = None

    # Enemy AI does NOT receive door_tiles — enemies cannot open doors.
    behavior = ai.ai_behavior or "aggressive"

    if behavior == "dummy":
        # Training dummy: stand in place, never move, never attack.
        return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT)
    elif behavior == "ranged":
        return _decide_ranged_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves)
    elif behavior == "boss":
        return _decide_boss_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves)
    elif behavior == "support":
        return _decide_support_behavior(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves)
    else:
        # "aggressive" or any unknown behavior → default aggressive
        return _decide_aggressive_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves)


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
                    obstacles, occupied,
                )
                if next_step:
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                    )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)
        # Try to stay near allies — use support move preference
        move_target = _support_move_preference(ai, all_units)
        if move_target:
            occupied = _build_occupied_set(all_units, ai_id, pending_moves, ghostly=is_ghostly)
            next_step = get_next_step_toward(
                ai_pos, move_target,
                grid_width, grid_height,
                effective_obstacles, occupied,
            )
            if next_step:
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                )
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

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
                grid_width, grid_height, obstacles, occupied,
            )
            if next_step:
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

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
            )

    # Priority 4: Move toward most injured ally (stay grouped for healing)
    move_target = _support_move_preference(ai, all_units)
    if move_target:
        next_step = get_next_step_toward(
            ai_pos, move_target,
            grid_width, grid_height,
            effective_obstacles, occupied,
        )
        if next_step:
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=next_step[0],
                target_y=next_step[1],
            )

    # Fallback: melee if adjacent (last resort for support)
    if is_adjacent(ai.position, target_pos):
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.ATTACK,
            target_x=target.position.x,
            target_y=target.position.y,
            target_id=target.player_id,
        )

    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)


def _decide_aggressive_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
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

    config = get_combat_config()
    # Use per-unit ranged_range from class stats, fallback to global config
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))
    ai_id = ai.player_id
    # Phase 18D: Ghostly champions can phase through occupied tiles
    is_ghostly = getattr(ai, 'champion_type', None) == "ghostly"

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
                occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly)
                next_step = get_next_step_toward(
                    ai_pos, (center_x, center_y),
                    grid_width, grid_height,
                    obstacles, occupied,
                )
                if next_step:
                    return PlayerAction(
                        player_id=ai.player_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                    )
            return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT)

        # 4a: Check last-known enemy positions (pursue memory targets)
        memory_action = _pursue_memory_target(
            ai, all_units, grid_width, grid_height, obstacles, pending_moves
        )
        if memory_action:
            return memory_action

        # 4b: Check if any ally is fighting — go help them
        reinforce_action = _reinforce_ally(
            ai, all_units, grid_width, grid_height, obstacles, pending_moves
        )
        if reinforce_action:
            return reinforce_action

        # 4c: Party members (hero allies) hold position instead of patrolling.
        # This prevents aimless wandering that hinders gameplay.
        if ai.hero_id is not None:
            return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT)

        # 4d: Fall back to patrol (enemy AI only)
        return _patrol_action(ai, grid_width, grid_height, obstacles, all_units, pending_moves)

    # Enemies found — clear patrol waypoint so AI doesn't resume old patrol
    _patrol_targets.pop(ai_id, None)

    # ── Chase distance cap: leashed enemies disengage if too far from home ──
    if ai.room_id and match_id and room_bounds:
        center_x = (room_bounds["x_min"] + room_bounds["x_max"]) // 2
        center_y = (room_bounds["y_min"] + room_bounds["y_max"]) // 2
        chase_dist = abs(ai.position.x - center_x) + abs(ai.position.y - center_y)
        if chase_dist > _MAX_LEASH_CHASE_DISTANCE:
            occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly)
            next_step = get_next_step_toward(
                (ai.position.x, ai.position.y), (center_x, center_y),
                grid_width, grid_height, obstacles, occupied,
            )
            if next_step:
                return PlayerAction(
                    player_id=ai.player_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                )
            return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT)

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
    occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, ghostly=is_ghostly)

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
        )

    # Step 6: If close (within 3 tiles), rush to melee range (non-ranged roles only).
    # Ranged roles prefer to stay at distance and use ranged attacks instead.
    if not is_ranged_role and dist_to_target <= 3:
        next_step = get_next_step_toward(
            (ai.position.x, ai.position.y),
            (target.position.x, target.position.y),
            grid_width, grid_height,
            effective_obstacles, occupied,
        )
        if next_step:
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.MOVE,
                target_x=next_step[0],
                target_y=next_step[1],
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
            )

    # Step 8: Move toward target using A*
    # Controller / offensive_support hold-position: when ranged is on CD and
    # enemies are within medium range, hold position instead of advancing into
    # danger.  Prevents squishy ranged supports from creeping into melee.
    if is_ranged_role and role in ("controller", "caster_dps") and ranged_cd > 0 and dist_to_target <= 4:
        return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT)

    # Phase 21E revised: Bard advance — when ranged is on CD, advance toward
    # the enemy to pre-position for the next skill cast (Dirge/Cacophony) or
    # ranged shot instead of passively drifting to ally centroid.  This keeps
    # the Bard engaged in the fight rather than wasting turns WAITing.
    # (Falls through to the normal A* move-toward-target below.)

    next_step = get_next_step_toward(
        (ai.position.x, ai.position.y),
        (target.position.x, target.position.y),
        grid_width, grid_height,
        effective_obstacles, occupied,
    )

    if next_step:
        return PlayerAction(
            player_id=ai.player_id,
            action_type=ActionType.MOVE,
            target_x=next_step[0],
            target_y=next_step[1],
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
            )

    # Truly stuck: wait
    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.WAIT,
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
                    obstacles, occupied,
                )
                if next_step:
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                    )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)
        # Party members (hero allies) hold position instead of patrolling
        if ai.hero_id is not None:
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)
        return _patrol_action(ai, grid_width, grid_height, obstacles, all_units, pending_moves)

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
                grid_width, grid_height, obstacles, occupied,
            )
            if next_step:
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                )
            return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

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
            )
        # Can't retreat — melee as last resort
        if is_adjacent(ai.position, target_pos):
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.ATTACK,
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
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
            )

    # Out of range or no LOS → move closer but maintain ideal distance
    if dist_to_target > ranged_range:
        next_step = get_next_step_toward(
            ai_pos,
            (target.position.x, target.position.y),
            grid_width, grid_height,
            effective_obstacles, occupied,
        )
        if next_step:
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=next_step[0],
                target_y=next_step[1],
            )

    # In range but ranged on cooldown → try to maintain ideal distance
    if IDEAL_MIN <= dist_to_target <= IDEAL_MAX:
        # Good position — wait for cooldown
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

    # Fallback: wait
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)


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
                    effective_obstacles, occupied,
                )
                if next_step:
                    return PlayerAction(
                        player_id=ai_id,
                        action_type=ActionType.MOVE,
                        target_x=next_step[0],
                        target_y=next_step[1],
                    )
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

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
            )

    # Chase within room using leashed obstacles
    next_step = get_next_step_toward(
        ai_pos,
        (target.position.x, target.position.y),
        grid_width, grid_height,
        effective_obstacles, occupied,
    )
    if next_step:
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.MOVE,
            target_x=next_step[0],
            target_y=next_step[1],
        )

    # Stuck — wait
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)


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

    # Phase 7A-3: Track pending moves — {unit_id: (from_pos, to_pos)}
    # Each AI decision sees the pending moves of all previously-decided AI units
    # this tick, preventing sequential pathfinding from causing gridlock.
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}

    for ai_id in ai_ids:
        ai = all_units.get(ai_id)
        if not ai or not ai.is_alive:
            # Clean up patrol + memory state for dead AI
            _patrol_targets.pop(ai_id, None)
            _visited_history.pop(ai_id, None)
            _enemy_memory.pop(ai_id, None)
            continue

        # Phase 12C: Skip extracted AI units
        if ai.extracted:
            continue

        # Skip AI units that are player-controlled and have queued actions
        if controlled_ids and ai_id in controlled_ids:
            continue

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
        )
        if action:
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
    """Clear patrol + memory state for a specific AI or all AI units.

    Call this when a match ends to prevent stale state.
    """
    if ai_id:
        _patrol_targets.pop(ai_id, None)
        _visited_history.pop(ai_id, None)
        _enemy_memory.pop(ai_id, None)
    else:
        _patrol_targets.clear()
        _visited_history.clear()
        _enemy_memory.clear()

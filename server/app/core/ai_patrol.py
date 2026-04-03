"""
AI Patrol & Scouting — Waypoint-based map exploration for idle AI.

Extracted from ai_behavior.py (P1 refactoring — pure mechanical move).

Implements:
  - Active scouting with waypoint-based patrol movement
  - Center-biased waypoint selection for exploration
  - Random adjacent move fallback
  - Patrol state management (_patrol_targets, _visited_history)
"""

from __future__ import annotations

import random

from app.models.player import PlayerState
from app.models.actions import PlayerAction, ActionType
from app.core.ai_pathfinding import (
    a_star,
    get_next_step_toward,
    _build_occupied_set,
)


# ---------------------------------------------------------------------------
# Patrol Waypoint Memory (module-level, keyed by AI player_id)
# ---------------------------------------------------------------------------

# Stores the current patrol target for each AI unit
_patrol_targets: dict[str, tuple[int, int]] = {}

# Tracks tiles each AI has recently visited to avoid revisiting
_visited_history: dict[str, list[tuple[int, int]]] = {}

# Max history length before oldest entries are dropped
_MAX_VISIT_HISTORY = 30

# Stale-position detector: if the AI stays within a 3×3 area for this many
# consecutive patrol turns, force a distant waypoint (Option C).
_STALE_AREA_THRESHOLD = 10
_STALE_FORCE_MIN_DIST = 15  # minimum Manhattan distance for the forced waypoint
_stale_area_counter: dict[str, int] = {}  # {ai_id: consecutive turns in same area}


# ---------------------------------------------------------------------------
# Patrol / Scouting
# ---------------------------------------------------------------------------

def _patrol_action(
    ai: PlayerState,
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    all_units: dict[str, PlayerState],
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    allow_team_swap: str | None = None,
    exploration_hint: tuple[int, int] | None = None,
) -> PlayerAction:
    """Generate a scouting/patrol movement for an idle AI.

    Strategy:
      1. If AI has a patrol waypoint and hasn't reached it, continue toward it
         via A*.
      2. If AI has reached its waypoint (or has none), pick a new one:
         - Prefer tiles near the map center and away from AI's current area
         - Penalize recently visited tiles
         - Use A* to ensure the waypoint is reachable
      3. If completely stuck, fall back to a random adjacent move.

    This creates purposeful exploration where AI units sweep toward the
    center and contested areas instead of wandering near their spawn.
    """
    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)

    # Track that we visited this tile
    if ai_id not in _visited_history:
        _visited_history[ai_id] = []
    _visited_history[ai_id].append(ai_pos)
    if len(_visited_history[ai_id]) > _MAX_VISIT_HISTORY:
        _visited_history[ai_id] = _visited_history[ai_id][-_MAX_VISIT_HISTORY:]

    # --- Option C: Stale-position detector ---
    # If the AI has stayed within a 3×3 area for _STALE_AREA_THRESHOLD
    # consecutive patrol turns, force a distant waypoint to break out.
    force_distant = False
    history = _visited_history.get(ai_id, [])
    if len(history) >= _STALE_AREA_THRESHOLD:
        recent = history[-_STALE_AREA_THRESHOLD:]
        xs = [p[0] for p in recent]
        ys = [p[1] for p in recent]
        area_width = max(xs) - min(xs)
        area_height = max(ys) - min(ys)
        if area_width <= 2 and area_height <= 2:
            # Stuck in a tiny area — force distant waypoint
            force_distant = True
            _stale_area_counter[ai_id] = _stale_area_counter.get(ai_id, 0) + 1
        else:
            _stale_area_counter[ai_id] = 0
    # ------------------------------------------------

    occupied = _build_occupied_set(all_units, ai_id, pending_moves, allow_team_swap=allow_team_swap)

    # Check if we have an existing waypoint and whether we've reached it
    current_target = _patrol_targets.get(ai_id)
    need_new_target = False

    if force_distant:
        # Stale-position detector triggered — must pick a far-away waypoint
        need_new_target = True
    elif current_target is None:
        need_new_target = True
    elif ai_pos == current_target:
        need_new_target = True
    elif current_target in obstacles:
        need_new_target = True
    else:
        # Check if our existing target is still reachable
        path = a_star(ai_pos, current_target, grid_width, grid_height, obstacles, occupied, door_tiles)
        if path is None:
            need_new_target = True

    if need_new_target:
        new_target = _pick_patrol_waypoint(
            ai_id, ai_pos, grid_width, grid_height, obstacles, occupied,
            min_distance=_STALE_FORCE_MIN_DIST if force_distant else None,
        )
        if new_target:
            _patrol_targets[ai_id] = new_target
            current_target = new_target
        else:
            # No valid waypoint found — fallback to directed/random adjacent move
            return _random_adjacent_move(ai, grid_width, grid_height, obstacles, occupied, exploration_hint)

    # Move toward the waypoint using A*
    next_step = get_next_step_toward(
        ai_pos, current_target,
        grid_width, grid_height,
        obstacles, occupied, door_tiles,
    )

    # --- Phase 33: Unified oscillation check ---
    # Instead of doing our own history[-2] comparison, delegate to the
    # unified check_oscillation() which can REDIRECT to an alternative
    # tile instead of always discarding the waypoint.
    if next_step:
        from app.core.ai_behavior import check_oscillation
        _osc_disp, _osc_redir = check_oscillation(
            ai_id=ai_id,
            target=next_step,
            ai_pos=ai_pos,
            grid_width=grid_width,
            grid_height=grid_height,
            obstacles=obstacles,
            occupied=occupied,
            all_units=None,  # patrol has no combat context
            is_leader=False,
            move_goal=current_target,
        )
        if _osc_disp == "redirect":
            _patrol_targets.pop(ai_id, None)
            from app.core.ai_stances import _maybe_interact_door
            door_action = _maybe_interact_door(ai, _osc_redir, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=_osc_redir[0],
                target_y=_osc_redir[1],
                reason="patrol_redirect",
            )
        elif _osc_disp == "wait":
            # No redirect tile available — pick a completely new waypoint
            _patrol_targets.pop(ai_id, None)
            new_target = _pick_patrol_waypoint(
                ai_id, ai_pos, grid_width, grid_height, obstacles, occupied,
                min_distance=_STALE_FORCE_MIN_DIST if force_distant else 5,
            )
            if new_target:
                _patrol_targets[ai_id] = new_target
                next_step = get_next_step_toward(
                    ai_pos, new_target,
                    grid_width, grid_height,
                    obstacles, occupied, door_tiles,
                )
                if not next_step:
                    return _random_adjacent_move(ai, grid_width, grid_height, obstacles, occupied, exploration_hint)
            else:
                return _random_adjacent_move(ai, grid_width, grid_height, obstacles, occupied, exploration_hint)
    # ---------------------------------------------------

    if next_step:
        from app.core.ai_stances import _maybe_interact_door
        door_action = _maybe_interact_door(ai, next_step, door_tiles)
        if door_action:
            return door_action
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.MOVE,
            target_x=next_step[0],
            target_y=next_step[1],
            reason="patrol_move",
        )

    # A* couldn't find a path — pick a new target next tick, directed/random move now
    _patrol_targets.pop(ai_id, None)
    return _random_adjacent_move(ai, grid_width, grid_height, obstacles, occupied, exploration_hint)


def _pick_patrol_waypoint(
    ai_id: str,
    ai_pos: tuple[int, int],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    min_distance: int | None = None,
) -> tuple[int, int] | None:
    """Pick a patrol waypoint that encourages map exploration.

    Prefers tiles that:
      - Are near the map center (pushes AI toward contested areas)
      - Are far from the AI's current position (avoid local shuffle)
      - Have not been recently visited
      - Are walkable (not obstacles or occupied)

    If *min_distance* is set, only consider candidates at least that many
    Manhattan tiles away from the AI's current position (used by the
    stale-position detector to force a breakout move).

    Falls back to closer tiles if no distant ones are available.
    """
    visited_set = set(_visited_history.get(ai_id, []))
    center_x = grid_width / 2.0
    center_y = grid_height / 2.0

    # Generate candidate waypoints spread across the map
    candidates: list[tuple[int, int]] = []
    for x in range(grid_width):
        for y in range(grid_height):
            if (x, y) in obstacles or (x, y) in occupied:
                continue
            if (x, y) == ai_pos:
                continue
            # Enforce minimum distance when breaking out of stale area
            if min_distance is not None:
                if abs(x - ai_pos[0]) + abs(y - ai_pos[1]) < min_distance:
                    continue
            candidates.append((x, y))

    if not candidates:
        # If min_distance filtered everything out, retry without it
        if min_distance is not None:
            return _pick_patrol_waypoint(
                ai_id, ai_pos, grid_width, grid_height, obstacles, occupied,
                min_distance=None,
            )
        return None

    # Score candidates: prefer center-biased + far from self + unvisited
    # If ALL candidates have been visited, the penalty serves no purpose
    # and would block all movement.  Disable it in that case.
    all_visited = all(tile in visited_set for tile in candidates)

    def score(tile: tuple[int, int]) -> float:
        # Distance from AI — want to move away from current spot
        dist_from_self = abs(tile[0] - ai_pos[0]) + abs(tile[1] - ai_pos[1])
        # Closeness to map center — want to patrol toward center/contested areas
        dist_to_center = abs(tile[0] - center_x) + abs(tile[1] - center_y)
        center_bonus = max(0, (grid_width - dist_to_center))  # Higher when closer to center
        # Visited penalty — strong enough to overcome center-bonus (Bug 2 fix)
        # Disabled when every candidate is visited (prevents total patrol lockout).
        visited_penalty = -15.0 if (tile in visited_set and not all_visited) else 0.0
        return dist_from_self + center_bonus * 0.5 + visited_penalty

    # Sort by score descending, then pick from the top candidates with some
    # randomness to avoid all AI converging on the same tile
    candidates.sort(key=score, reverse=True)
    top_n = min(8, len(candidates))
    return random.choice(candidates[:top_n])


def _random_adjacent_move(
    ai: PlayerState,
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    exploration_hint: tuple[int, int] | None = None,
) -> PlayerAction:
    """Fallback: pick a walkable adjacent tile.

    If *exploration_hint* is provided (e.g. an unexplored room entrance),
    prefer the adjacent tile that minimises Manhattan distance to that target
    instead of choosing randomly.  Falls back to random order when no hint
    is given or when the hint doesn't help.
    """
    directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    # Collect all valid adjacent tiles
    valid: list[tuple[int, int]] = []
    for dx, dy in directions:
        nx, ny = ai.position.x + dx, ai.position.y + dy
        if 0 <= nx < grid_width and 0 <= ny < grid_height:
            if (nx, ny) not in obstacles and (nx, ny) not in occupied:
                valid.append((nx, ny))

    if not valid:
        return PlayerAction(
            player_id=ai.player_id,
            action_type=ActionType.WAIT,
            reason="patrol_surrounded",
        )

    if exploration_hint:
        # Sort by Manhattan distance to the exploration target (closest first)
        valid.sort(key=lambda t: abs(t[0] - exploration_hint[0]) + abs(t[1] - exploration_hint[1]))
        chosen = valid[0]
        reason = "directed_adjacent_move"
    else:
        random.shuffle(valid)
        chosen = valid[0]
        reason = "random_adjacent_move"

    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.MOVE,
        target_x=chosen[0],
        target_y=chosen[1],
        reason=reason,
    )

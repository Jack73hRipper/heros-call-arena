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
_MAX_VISIT_HISTORY = 15


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

    occupied = _build_occupied_set(all_units, ai_id, pending_moves)

    # Check if we have an existing waypoint and whether we've reached it
    current_target = _patrol_targets.get(ai_id)
    need_new_target = False

    if current_target is None:
        need_new_target = True
    elif ai_pos == current_target:
        need_new_target = True
    elif current_target in obstacles:
        need_new_target = True
    else:
        # Check if our existing target is still reachable
        path = a_star(ai_pos, current_target, grid_width, grid_height, obstacles, occupied)
        if path is None:
            need_new_target = True

    if need_new_target:
        new_target = _pick_patrol_waypoint(
            ai_id, ai_pos, grid_width, grid_height, obstacles, occupied
        )
        if new_target:
            _patrol_targets[ai_id] = new_target
            current_target = new_target
        else:
            # No valid waypoint found — fallback to random adjacent move
            return _random_adjacent_move(ai, grid_width, grid_height, obstacles, occupied)

    # Move toward the waypoint using A*
    next_step = get_next_step_toward(
        ai_pos, current_target,
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

    # A* couldn't find a path — pick a new target next tick, random move now
    _patrol_targets.pop(ai_id, None)
    return _random_adjacent_move(ai, grid_width, grid_height, obstacles, occupied)


def _pick_patrol_waypoint(
    ai_id: str,
    ai_pos: tuple[int, int],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """Pick a patrol waypoint that encourages map exploration.

    Prefers tiles that:
      - Are near the map center (pushes AI toward contested areas)
      - Are far from the AI's current position (avoid local shuffle)
      - Have not been recently visited
      - Are walkable (not obstacles or occupied)

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
            candidates.append((x, y))

    if not candidates:
        return None

    # Score candidates: prefer center-biased + far from self + unvisited
    def score(tile: tuple[int, int]) -> float:
        # Distance from AI — want to move away from current spot
        dist_from_self = abs(tile[0] - ai_pos[0]) + abs(tile[1] - ai_pos[1])
        # Closeness to map center — want to patrol toward center/contested areas
        dist_to_center = abs(tile[0] - center_x) + abs(tile[1] - center_y)
        center_bonus = max(0, (grid_width - dist_to_center))  # Higher when closer to center
        # Visited penalty
        visited_penalty = -5.0 if tile in visited_set else 0.0
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
) -> PlayerAction:
    """Fallback: pick a random walkable adjacent tile."""
    directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    random.shuffle(directions)

    for dx, dy in directions:
        nx, ny = ai.position.x + dx, ai.position.y + dy
        if 0 <= nx < grid_width and 0 <= ny < grid_height:
            if (nx, ny) not in obstacles and (nx, ny) not in occupied:
                return PlayerAction(
                    player_id=ai.player_id,
                    action_type=ActionType.MOVE,
                    target_x=nx,
                    target_y=ny,
                )

    # Completely surrounded — wait
    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.WAIT,
    )

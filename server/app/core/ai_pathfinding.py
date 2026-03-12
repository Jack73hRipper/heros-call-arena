"""
AI Pathfinding — A* pathfinding and occupied-tile management.

Extracted from ai_behavior.py (P1 refactoring — pure mechanical move).

Implements:
  - A* pathfinding (obstacle-aware, occupied-tile-aware, door-aware)
  - Chebyshev heuristic for 8-directional movement
  - Occupied-set builder with movement prediction (Phase 7A-3)
"""

from __future__ import annotations

import heapq

from app.models.player import PlayerState
from app.core.skills import is_stunned, is_slowed


# ---------------------------------------------------------------------------
# Occupied-Set Builder (Phase 7A-3: Movement Prediction)
# ---------------------------------------------------------------------------

def _build_occupied_set(
    all_units: dict[str, PlayerState],
    exclude_id: str,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    ghostly: bool = False,
    allow_team_swap: str | None = None,
) -> set[tuple[int, int]]:
    """Build the set of tiles occupied by other alive units.

    Phase 7A-3: If *pending_moves* is provided, units that have already
    been assigned a MOVE action this tick are treated predictively:
      - Their **current** position is excluded (they will vacate it).

    Phase 18D: If *ghostly* is True, returns an empty set because Ghostly
    champions can phase through occupied tiles.

    Phase 2 (Friendly Swap): If *allow_team_swap* is set (e.g. ``"a"``),
    same-team allies are excluded from the occupied set so A* can plan
    paths through them.  The swap injection (Phase 1B) handles the
    actual collision at resolution time.  Hold-stance, stunned, and
    slowed allies remain in the occupied set because they cannot be
    swapped.

    This prevents sequential AI decisions from blocking each other
    when multiple allies are moving through the same corridor.
    The batch resolver (Phase 7A-1) handles any conflicts at resolution
    time, so we do NOT add claimed target positions here — that would
    break A* pathfinding in narrow hallways.

    Args:
        all_units:       Full dict of player_id -> PlayerState.
        exclude_id:      The AI unit computing its own action (skip itself).
        pending_moves:   ``{unit_id: (from_pos, to_pos)}`` for units that
                         already have a MOVE intent this tick.  ``None``
                         disables prediction (backward compat).
        ghostly:         If True, return empty set (Phase 18D: ghostly phase-through).
        allow_team_swap: Team letter (e.g. ``"a"``) whose allies should be
                         excluded from the occupied set.  ``None`` disables
                         (backward compat).
    """
    # Phase 18D: Ghostly champions can move through occupied tiles
    if ghostly:
        return set()

    pending_unit_ids: set[str] = set()
    vacating: set[tuple[int, int]] = set()
    if pending_moves:
        for pid, (from_pos, _to_pos) in pending_moves.items():
            pending_unit_ids.add(pid)
            vacating.add(from_pos)

    occupied: set[tuple[int, int]] = set()
    for u in all_units.values():
        if not u.is_alive or u.player_id == exclude_id:
            continue
        # Phase 12C: Extracted heroes have left the dungeon — don't block tiles
        if getattr(u, 'extracted', False):
            continue
        pos = (u.position.x, u.position.y)
        # Skip positions being vacated by units with pending moves
        if pos in vacating and u.player_id in pending_unit_ids:
            continue
        # Phase 2 (Friendly Swap): Exclude same-team allies so A* can path
        # through them — swap injection handles the collision at resolution.
        # Hold-stance, stunned, and slowed allies stay blocked (immovable).
        if allow_team_swap and u.team == allow_team_swap:
            if getattr(u, 'ai_stance', None) == 'hold':
                occupied.add(pos)
                continue
            if is_stunned(u) or is_slowed(u):
                occupied.add(pos)
                continue
            continue  # Skip — A* can path through this ally
        occupied.add(pos)

    return occupied


# ---------------------------------------------------------------------------
# A* Pathfinding
# ---------------------------------------------------------------------------

def _heuristic(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Chebyshev distance (allows diagonal movement)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _neighbors(x: int, y: int, grid_w: int, grid_h: int) -> list[tuple[int, int]]:
    """Return all 8-directional neighbors within bounds."""
    result = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < grid_w and 0 <= ny < grid_h:
                result.append((nx, ny))
    return result


def a_star(
    start: tuple[int, int],
    goal: tuple[int, int],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    door_tiles: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None:
    """A* pathfinding from start to goal.

    Returns the full path (list of (x, y) positions excluding start),
    or None if no path exists.

    Args:
        start: Starting (x, y).
        goal: Target (x, y).
        grid_width: Map width.
        grid_height: Map height.
        obstacles: Impassable tiles.
        occupied: Tiles occupied by other units (treated as impassable
                  except for the goal tile itself, which the AI wants
                  to approach but not step on).
        door_tiles: Optional set of closed-door positions. These tiles are
                    excluded from the blocked set so A* can path *through*
                    them, but at an elevated traversal cost (+3 instead of
                    +1).  This makes A* prefer open routes but still plan
                    paths through doors when necessary (Phase 7D-1).
    """
    if start == goal:
        return []

    # If the goal tile is occupied by another unit (e.g. an enemy we want
    # to approach), we cannot step onto it.  Instead, A* terminates when
    # it reaches any tile *adjacent* to the goal — that's close enough
    # for melee range.
    goal_is_occupied = goal in occupied

    # Phase 7D-1: Remove closed-door tiles from the blocked set so A* can
    # traverse them (with elevated cost computed below).
    blocked = obstacles | (occupied - {goal})
    if door_tiles:
        blocked = blocked - door_tiles

    open_set: list[tuple[int, tuple[int, int]]] = []
    heapq.heappush(open_set, (0, start))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        # --- Termination conditions ---
        # 1. Reached the goal tile itself (goal is walkable)
        # 2. Reached a tile adjacent to an occupied goal (close enough)
        reached = (
            current == goal
            or (goal_is_occupied and _heuristic(current, goal) == 1)
        )
        if reached:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path

        for nb in _neighbors(current[0], current[1], grid_width, grid_height):
            if nb in blocked:
                continue
            # Don't allow stepping onto goal if it's occupied (we want to
            # stop adjacent to it)
            if nb == goal and goal_is_occupied:
                continue

            # Phase 7D-1: Elevated cost for stepping through a closed door.
            # Normal step = 1. Door step = 3 (makes A* prefer open routes).
            step_cost = 3 if (door_tiles and nb in door_tiles) else 1
            tentative_g = g_score[current] + step_cost
            if tentative_g < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative_g
                f_score = tentative_g + _heuristic(nb, goal)
                heapq.heappush(open_set, (f_score, nb))

    return None  # No path found


def get_next_step_toward(
    start: tuple[int, int],
    goal: tuple[int, int],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    door_tiles: set[tuple[int, int]] | None = None,
) -> tuple[int, int] | None:
    """Return the next single tile to move to when pathing toward goal.

    Returns None if already at goal or no path exists.
    """
    path = a_star(start, goal, grid_width, grid_height, obstacles, occupied, door_tiles)
    if path:
        return path[0]
    return None

"""
FOV Manager — FOV cache accessors and dev mode toggles.

Extracted from match_manager.py as Phase 3 of the match-manager-split.
Pure cache operations with no coupling to game logic.
"""

from __future__ import annotations

from app.config import settings
from app.core.match_store import (
    _active_matches, _player_states,
    _fov_cache, _dev_mode_players,
)
from app.core.map_loader import load_map, get_obstacles_with_door_states
from app.core.fov import compute_fov


# ---------- Initial FOV Computation ----------

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


# ---------- Dev Mode ----------

def set_dev_mode(match_id: str, player_id: str, enabled: bool) -> None:
    """Enable or disable dev mode for a player (skips FOV filtering)."""
    if enabled:
        if match_id not in _dev_mode_players:
            _dev_mode_players[match_id] = set()
        _dev_mode_players[match_id].add(player_id)
    else:
        if match_id in _dev_mode_players:
            _dev_mode_players[match_id].discard(player_id)


def is_dev_mode(match_id: str, player_id: str) -> bool:
    """Check if a player has dev mode enabled."""
    return player_id in _dev_mode_players.get(match_id, set())

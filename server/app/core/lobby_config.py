"""
Lobby Config — Lobby chat, match config updates, and class selection.

Extracted from match_manager.py (Phase 5 of match-manager-split-plan).
All functions operate on shared state from match_store.
"""

from __future__ import annotations

import time

from app.models.match import MatchStatus, MatchType
from app.models.player import get_all_classes
from app.core.match_store import (
    _active_matches, _player_states, _lobby_chat, _class_selections,
)


def select_class(match_id: str, player_id: str, class_id: str) -> bool:
    """Set a player's class selection in lobby. Returns True on success."""
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        return False

    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
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

    # Phase L4: Allowed maps per mode for validation
    _mode_allowed_maps = {
        MatchType.PVP: {'arena_classic'},
        MatchType.SOLO_PVE: {'wave_arena', 'training_room', 'procedural'},
        MatchType.DUNGEON: {'procedural', 'wave_arena', 'training_room'},
        MatchType.PVPVE: {'procedural'},
        MatchType.MIXED: None,  # No restriction for legacy mixed mode
    }

    if "map_id" in updates:
        # Validate map exists on disk (auto-discovers new maps from configs/maps/)
        from app.core.map_loader import _maps_dir
        new_map_id = updates['map_id']
        # 'procedural' is a virtual map ID that doesn't have a file
        map_valid = new_map_id == 'procedural' or (_maps_dir / f"{new_map_id}.json").exists()
        if map_valid:
            # Phase L4: Also validate map is allowed for current mode
            current_type = MatchType(updates.get('match_type', config.match_type.value))
            allowed = _mode_allowed_maps.get(current_type)
            if allowed is None or new_map_id in allowed:
                config.map_id = new_map_id

    if "match_type" in updates:
        try:
            new_type = MatchType(updates["match_type"])
            old_type = config.match_type
            config.match_type = new_type

            # Phase L4: Mode-switch reset — clear irrelevant config when switching modes
            if new_type != old_type:
                # All non-PVP→PVP transitions: clear AI counts
                if new_type == MatchType.PVP:
                    if config.ai_opponents > 0 or config.ai_allies > 0:
                        config.ai_opponents = 0
                        config.ai_allies = 0
                        ai_changed = True
                    config.theme_id = None
                    # Reset PvPvE fields
                    config.pvpve_team_count = 2
                    config.pvpve_pve_density = 0.5
                    config.pvpve_boss_enabled = True
                    config.pvpve_grid_size = 8
                    config.pvpve_ai_team_count = 0
                    config.pvpve_ai_team_sizes = []
                elif new_type in (MatchType.SOLO_PVE, MatchType.DUNGEON):
                    # PvE modes: reset PvPvE-specific fields
                    config.pvpve_team_count = 2
                    config.pvpve_pve_density = 0.5
                    config.pvpve_boss_enabled = True
                    config.pvpve_grid_size = 8
                    config.pvpve_ai_team_count = 0
                    config.pvpve_ai_team_sizes = []
                elif new_type == MatchType.PVPVE:
                    # Entering PvPvE: set defaults
                    config.pvpve_team_count = 2
                    config.pvpve_pve_density = 0.5
                    config.pvpve_boss_enabled = True
                    config.pvpve_grid_size = 8
                    config.pvpve_ai_team_count = 0
                    config.pvpve_ai_team_sizes = []
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
            'fungal_grotto', 'frozen_crypt', 'cursed_shrine',
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
        # Late import to avoid circular dependency — _spawn_ai_units lives in match_manager
        from app.core.match_manager import _spawn_ai_units
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
    # Late import to avoid circular dependency — _spawn_ai_units lives in match_manager
    from app.core.match_manager import _spawn_ai_units
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

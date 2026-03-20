"""
Match Store — Single source of truth for all shared match state dicts.

Extracted from match_manager.py as Phase 1 of the match-manager-split.
All modules that need match state import from here instead of match_manager,
breaking circular-dependency chains and enabling further extraction.
"""

from __future__ import annotations

from app.models.match import MatchState
from app.models.player import PlayerState


# ── In-memory store (backed by Redis in service layer) ──────────────

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

# Phase L2: Controlled hero mapping — match_id -> {player_id -> hero_id}
# Tracks which hero each human player has designated as their controlled unit
_controlled_hero_map: dict[str, dict[str, str]] = {}

# Wave spawner state: match_id -> {current_wave, total_waves, wave_config, spawning_active}
_wave_state: dict[str, dict] = {}

# Dev mode: match_id -> set of player_ids with dev mode enabled (skips FOV filtering)
_dev_mode_players: dict[str, set[str]] = {}

# ── Constants ───────────────────────────────────────────────────────

MAX_QUEUE_SIZE = 10

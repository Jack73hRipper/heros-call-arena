"""
Pydantic models for match state.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    WAITING = "waiting"      # In lobby, waiting for players
    STARTING = "starting"    # Countdown before match begins
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class MatchType(str, Enum):
    PVP = "pvp"            # Humans only
    SOLO_PVE = "solo_pve"  # 1 human vs AI
    MIXED = "mixed"        # Any combo of humans + AI
    DUNGEON = "dungeon"    # Phase 4B: co-op dungeon crawl
    PVPVE = "pvpve"        # Phase 27: competitive dungeon with PVE enemies


class MatchConfig(BaseModel):
    """Settings chosen when creating a match."""
    map_id: str = "arena_classic"
    max_players: int = 8
    tick_rate: float = 1.0
    match_type: MatchType = MatchType.PVP
    ai_opponents: int = 0
    ai_allies: int = 0
    theme_id: str | None = None  # Dungeon visual theme (None = random)
    ai_opponent_classes: list[str] = Field(default_factory=list)  # Per-slot class IDs for AI opponents (empty = random)
    ai_ally_classes: list[str] = Field(default_factory=list)       # Per-slot class IDs for AI allies (empty = random)
    # Phase 27: PVPVE settings
    pvpve_team_count: int = 2          # 2–4 player teams
    pvpve_pve_density: float = 0.5     # PVE enemy density multiplier (0.0–1.0)
    pvpve_boss_enabled: bool = True    # Spawn center boss
    pvpve_loot_density: float = 0.5    # Chest/loot density multiplier
    pvpve_grid_size: int = 8           # WFC grid size (default 8×8)
    pvpve_ai_team_count: int = 0       # Number of AI-controlled hero teams (0 = none)
    pvpve_ai_team_sizes: list[int] = Field(default_factory=list)  # Units per AI team


class MatchState(BaseModel):
    """Full state of an active match, stored in Redis."""
    match_id: str
    status: MatchStatus = MatchStatus.WAITING
    config: MatchConfig = Field(default_factory=MatchConfig)
    host_id: str = ""
    player_ids: list[str] = Field(default_factory=list)
    ai_ids: list[str] = Field(default_factory=list)  # All AI unit IDs
    team_a: list[str] = Field(default_factory=list)   # Humans + AI allies
    team_b: list[str] = Field(default_factory=list)   # AI opponents
    team_c: list[str] = Field(default_factory=list)   # Additional team
    team_d: list[str] = Field(default_factory=list)   # Additional team
    current_turn: int = 0
    created_at: float = 0.0
    # Phase 4B: dungeon state — keyed by "x,y" string for JSON compat
    door_states: dict[str, str] = Field(default_factory=dict)   # {"6,3": "closed", ...}
    chest_states: dict[str, str] = Field(default_factory=dict)  # {"2,12": "unopened", ...}
    # Phase 4D-2: ground items — keyed by "x,y" string, value is list of serialized Item dicts
    ground_items: dict[str, list] = Field(default_factory=dict)  # {"5,3": [{item_id, name, ...}, ...]}
    # Phase 12C: Portal scroll extraction mechanic
    # Channeling state — a player channeling a portal scroll
    channeling: dict | None = None  # {"player_id": str, "action": "portal", "turns_remaining": int, "tile_x": int, "tile_y": int}
    # Active portal entity on the ground
    portal: dict | None = None  # {"active": True, "x": int, "y": int, "turns_remaining": int, "owner_id": str}
    # Phase 12-5: Multi-floor dungeon state
    current_floor: int = 1                  # Current floor number (1-based)
    dungeon_seed: int = 0                   # Base seed for deterministic floor generation
    stairs_unlocked: bool = False           # True when all enemies on floor are dead
    theme_id: str | None = None             # Visual dungeon theme ID (e.g. 'bleeding_catacombs')
    # Phase 26: Shaman totem entities — persistent destructible ground objects
    totems: list = Field(default_factory=list)  # List of totem dicts (healing/searing totems)
    # Phase 27: PVPVE mode — PVE enemy tracking
    team_pve: list[str] = Field(default_factory=list)  # PVE enemy IDs (PVPVE mode)


class MatchSummary(BaseModel):
    """Lightweight view for lobby listing."""
    match_id: str
    status: MatchStatus
    player_count: int
    max_players: int
    map_id: str
    host_id: str
    match_type: MatchType = MatchType.PVP
    ai_opponents: int = 0
    ai_allies: int = 0

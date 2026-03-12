"""
Pydantic models for player actions and turn results.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    MOVE = "move"
    ATTACK = "attack"
    RANGED_ATTACK = "ranged_attack"
    WAIT = "wait"
    INTERACT = "interact"  # Phase 4B: open door, activate object
    LOOT = "loot"          # Phase 4D: pick up item from ground/chest
    USE_ITEM = "use_item"  # Phase 4D: consume potion/scroll from inventory
    SKILL = "skill"        # Phase 6A: use a skill/spell


class PlayerAction(BaseModel):
    """A single action submitted by a player during a turn."""
    player_id: str
    action_type: ActionType
    target_x: int | None = None
    target_y: int | None = None
    target_id: str | None = None   # Entity targeting: player_id of the intended target
    skill_id: str | None = None    # Phase 6A: which skill to use (only for action_type == SKILL)


class ActionResult(BaseModel):
    """Result of a single resolved action, broadcast to clients."""
    player_id: str
    username: str
    action_type: ActionType
    success: bool = True
    message: str = ""
    # Movement
    from_x: int | None = None
    from_y: int | None = None
    to_x: int | None = None
    to_y: int | None = None
    # Combat
    target_id: str | None = None
    target_username: str | None = None
    damage_dealt: int | None = None
    target_hp_remaining: int | None = None
    killed: bool = False
    # Phase 6A: Skill result fields
    skill_id: str | None = None
    buff_applied: dict | None = None   # {stat, magnitude, duration}
    heal_amount: int | None = None
    # Phase 14C: Distinguish DoT/HoT tick results from direct skill casts
    is_tick: bool = False
    # Phase 16A: Critical hit indicator
    is_crit: bool = False


class TurnResult(BaseModel):
    """Complete result of a turn tick, broadcast to all clients."""
    match_id: str
    turn_number: int
    actions: list[ActionResult] = Field(default_factory=list)
    deaths: list[str] = Field(default_factory=list)  # player_ids who died
    winner: str | None = None  # player_id of winner, if match ended
    door_changes: list[dict] = Field(default_factory=list)  # [{x, y, state}, ...]
    # Phase 4D-2: Loot & inventory events
    loot_drops: list[dict] = Field(default_factory=list)       # [{x, y, items: [...]}, ...]
    chest_opened: list[dict] = Field(default_factory=list)     # [{x, y, items: [...], player_id}, ...]
    items_picked_up: list[dict] = Field(default_factory=list)  # [{player_id, items: [...]}, ...]
    items_used: list[dict] = Field(default_factory=list)       # [{player_id, item_id, effect}, ...]
    # Phase 4E-2: Permadeath tracking
    hero_deaths: list[dict] = Field(default_factory=list)      # [{hero_id, hero_name, class_id, lost_items: [...]}, ...]
    # Phase 6A: Buff state changes
    buff_changes: list[dict] = Field(default_factory=list)      # [{player_id, buffs: [...]}, ...]
    # Portal scroll activation — triggers dungeon extract instead of normal victory
    portal_activated: bool = False
    portal_user_id: str | None = None  # who used the scroll
    # Phase 12C: Portal scroll channeling & extraction events
    channeling_started: dict | None = None  # {"player_id", "turns_remaining", "tile_x", "tile_y"}
    channeling_tick: dict | None = None     # {"player_id", "turns_remaining"} — ongoing channel progress
    portal_spawned: dict | None = None      # {"x", "y", "turns_remaining", "owner_id"} — portal entity appeared
    portal_tick: dict | None = None         # {"x", "y", "turns_remaining"} — portal turn countdown
    portal_expired: bool = False            # True if the portal ran out of turns this tick
    extractions: list[dict] = Field(default_factory=list)  # [{"player_id", "username", "hero_id"}]
    # Phase 12-5: Floor transition via stairs
    floor_advance: bool = False             # True if party descended to next floor this tick
    new_floor_number: int | None = None     # The floor number they descended to
    # Phase 18F: Elite kill notifications
    elite_kills: list[dict] = Field(default_factory=list)  # [{type, monster_rarity, display_name, killer_id, loot_items}, ...]

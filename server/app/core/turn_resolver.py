"""
Turn Resolver -- Thin orchestrator for the turn resolution pipeline.

Delegates all phase logic to sub-modules in server/app/core/turn_phases/.
This file contains:
  - resolve_turn() -- the public API entry point
  - Backward-compatible re-exports of all symbols imported by tests/production code

Resolution order:
  0.   Item-use phase (consume potions/scrolls -- portal scrolls start channeling)
  0.25 Channeling phase (tick channeling timers, spawn portal when done)
  0.5  Tick cooldowns for all units
  0.75 Tick active buffs (decrement turns, remove expired)    -- Phase 6B
  0.8  Portal tick (decrement portal timer, expire portal)     -- Phase 12C
  0.85 Extraction phase (heroes on portal tile via INTERACT)   -- Phase 12C
  0.9  Stairs transition (floor advance via stairs)            -- Phase 12-5
  1.   Movement actions
  1.5  Interaction actions (open doors -- Phase 4B-2)
  1.75 Loot actions (chest interaction + ground pickup -- Phase 4D-2)
  1.9  Skill resolution (heal, multi-hit, ranged, buff, teleport) -- Phase 6B
  2.   Ranged attack actions
  3.   Melee attack actions
  3.5  Loot drops from deaths
  3.75 Kill tracking + permadeath
  4.   Victory check

All actions submitted during a turn are resolved simultaneously within each phase.
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import PlayerAction, ActionType, ActionResult, TurnResult
from app.core.combat import get_combat_config

# ---------------------------------------------------------------------------
# Phase sub-module imports -- each resolves one phase of the turn pipeline.
# ---------------------------------------------------------------------------
from app.core.turn_phases.items_phase import _resolve_items
from app.core.turn_phases.portal_phase import (
    _resolve_channeling,
    _resolve_portal_tick,
    _resolve_extractions,
    _resolve_stairs,
)
from app.core.turn_phases.buffs_phase import _resolve_cooldowns_and_buffs
from app.core.turn_phases.auras_phase import _resolve_auras
from app.core.turn_phases.movement_phase import _resolve_movement
from app.core.turn_phases.interaction_phase import _resolve_doors, _resolve_loot
from app.core.turn_phases.skills_phase import _resolve_skills
from app.core.turn_phases.combat_phase import _resolve_ranged, _resolve_melee
from app.core.turn_phases.deaths_phase import _resolve_deaths, _resolve_victory

# ---------------------------------------------------------------------------
# Backward-compatible re-exports -- preserve all import paths used by
# production code and tests (31 import sites).
#
# These symbols are not used by resolve_turn() directly but are imported
# by test files via `from app.core.turn_resolver import <symbol>`.
# ---------------------------------------------------------------------------
from app.core.turn_phases.helpers import (  # noqa: F401
    _is_cardinal_adjacent,
    _is_chebyshev_adjacent,
)
from app.core.turn_phases.portal_phase import (  # noqa: F401
    PORTAL_CHANNEL_TURNS,
    PORTAL_DURATION_TURNS,
    _is_channeling,
)
from app.core.turn_phases.combat_phase import _resolve_entity_target  # noqa: F401


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def resolve_turn(
    match_id: str,
    turn_number: int,
    players: dict[str, PlayerState],
    actions: list[PlayerAction],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_a: list[str] | None = None,
    team_b: list[str] | None = None,
    team_c: list[str] | None = None,
    team_d: list[str] | None = None,
    door_states: dict[str, str] | None = None,
    chest_states: dict[str, str] | None = None,
    ground_items: dict[str, list] | None = None,
    is_dungeon: bool = False,
    match_channeling: dict | None = None,
    match_portal: dict | None = None,
    stairs_positions: list[tuple[int, int]] | None = None,
    stairs_unlocked: bool = False,
    floor_number: int = 1,
    match_state=None,  # Phase 26B: MatchState for totem entity access
) -> TurnResult:
    """Resolve all queued actions for a single turn tick.

    Delegates to named phase helpers in resolution order:
      0          _resolve_items (portal scrolls start channeling)
      0.25       _resolve_channeling (tick channel timers, spawn portal)
      0.5/0.75   _resolve_cooldowns_and_buffs
      0.8        _resolve_portal_tick (decrement portal timer)
      0.85       _resolve_extractions (heroes entering portal)
      0.9        _resolve_stairs (floor transition -- Phase 12-5)
      1          _resolve_movement
      1.5        _resolve_doors
      1.75       _resolve_loot
      1.9        _resolve_skills
      2          _resolve_ranged
      3          _resolve_melee
      3.5/3.75   _resolve_deaths
      4          _resolve_victory
    """
    config = get_combat_config()

    results: list[ActionResult] = []
    deaths: list[str] = []
    door_changes: list[dict] = []
    loot_drops: list[dict] = []
    chest_opened: list[dict] = []
    items_picked_up: list[dict] = []
    items_used: list[dict] = []
    elite_kills: list[dict] = []  # Phase 18F: elite kill notifications
    portal_context: dict = {
        "activated": False,
        "user_id": None,
        "extractions": [],
        "channeling_active": False,
    }
    stairs_context: dict = {
        "floor_advance": False,
        "triggered_by": None,
    }

    # Separate action types
    move_actions = [a for a in actions if a.action_type == ActionType.MOVE]
    melee_actions = [a for a in actions if a.action_type == ActionType.ATTACK]
    ranged_actions = [a for a in actions if a.action_type == ActionType.RANGED_ATTACK]
    interact_actions = [a for a in actions if a.action_type == ActionType.INTERACT]
    loot_actions = [a for a in actions if a.action_type == ActionType.LOOT]
    use_item_actions = [a for a in actions if a.action_type == ActionType.USE_ITEM]
    skill_actions = [a for a in actions if a.action_type == ActionType.SKILL]

    # Phase 0: Use Items (portal scrolls start channeling via portal_context)
    _resolve_items(use_item_actions, players, results, items_used, portal_context)

    # Phase 0.25: Channeling (tick channel timers, spawn portal when complete)
    updated_channeling, updated_portal = _resolve_channeling(
        players, results, portal_context, match_channeling, match_portal,
    )

    # Phase 0.5 + 0.75: Cooldowns & Buffs (Phase 11: DoT/HoT ticks + deaths)
    buff_changes = _resolve_cooldowns_and_buffs(players, results, deaths,
                                                 match_state=match_state)

    # Phase 18D: Resolve auras (Might Aura, Conviction Aura, Berserker enrage)
    _resolve_auras(players, results)

    # Phase 0.8: Portal Tick (decrement portal turn counter)
    updated_portal = _resolve_portal_tick(updated_portal, portal_context, results)

    # Phase 0.85: Extractions (heroes on portal tile via INTERACT enter_portal)
    _resolve_extractions(
        interact_actions, players, updated_portal, team_a, results, portal_context,
    )

    # Phase 0.9: Stairs (floor transition -- Phase 12-5)
    stairs_interact_actions = [a for a in interact_actions if a.target_id == "enter_stairs"]
    _resolve_stairs(
        stairs_interact_actions, players,
        stairs_positions or [], stairs_unlocked,
        team_a, results, stairs_context,
    )

    # Phase 1: Movement (returns pre-move snapshot for melee tracking)
    pre_move_occupants = _resolve_movement(
        move_actions, players, grid_width, grid_height, obstacles, results,
        portal_context=portal_context,
        current_turn=turn_number,
    )

    # Phase 1.5: Door Interactions (filter out enter_portal and enter_stairs actions)
    door_interact_actions = [a for a in interact_actions if a.target_id not in ("enter_portal", "enter_stairs")]
    _resolve_doors(
        door_interact_actions, players, obstacles, door_states, results, door_changes,
    )

    # Phase 1.75: Loot (chests + ground pickup)
    _resolve_loot(
        loot_actions, players, chest_states, ground_items,
        results, chest_opened, items_picked_up,
        floor_number=floor_number,
    )

    # Phase 1.9: Skills
    _resolve_skills(
        skill_actions, players, obstacles, grid_width, grid_height,
        results, deaths, buff_changes, portal_context=portal_context,
        match_state=match_state,
    )

    # Phase 2: Ranged Attacks
    _resolve_ranged(
        ranged_actions, players, obstacles, config, results, deaths,
        portal_context=portal_context,
        match_state=match_state,
    )

    # Phase 3: Melee Attacks
    _resolve_melee(
        melee_actions, players, pre_move_occupants, results, deaths,
        portal_context=portal_context,
        match_state=match_state,
    )

    # Phase 3.5 + 3.75: Death Loot + Kill Tracking + Permadeath
    hero_deaths = _resolve_deaths(
        match_id, deaths, players, ground_items, results, loot_drops,
        floor_number=floor_number,
        elite_kills=elite_kills,
    )

    # Phase 4: Victory Check
    # In dungeon mode, suppress normal team victory (killing all enemies).
    # Dungeon matches end via:
    #   - "all_extracted": all team_a heroes are extracted or dead (at least one extracted)
    #   - "party_wipe": all team_a heroes dead (none extracted)
    winner = None
    if is_dungeon:
        team_a_ids = set(team_a or [])
        team_a_alive = [p for p in players.values() if p.player_id in team_a_ids and p.is_alive and not p.extracted]
        team_a_extracted = [p for p in players.values() if p.player_id in team_a_ids and p.extracted]
        team_a_dead = [p for p in players.values() if p.player_id in team_a_ids and not p.is_alive and not p.extracted]

        if len(team_a_alive) == 0:
            # No one left in play -- match over
            if len(team_a_extracted) > 0:
                winner = "dungeon_extract"
            else:
                winner = "party_wipe"
    else:
        # Phase 27D: derive match_type from match_state for PVPVE exclusion
        _match_type = None
        if match_state and hasattr(match_state, 'config'):
            _match_type = getattr(match_state.config, 'match_type', None)
        winner = _resolve_victory(
            players, team_a, team_b, team_c, team_d,
            match_type=_match_type,
        )

    return TurnResult(
        match_id=match_id,
        turn_number=turn_number,
        actions=results,
        deaths=deaths,
        winner=winner,
        door_changes=door_changes,
        loot_drops=loot_drops,
        chest_opened=chest_opened,
        items_picked_up=items_picked_up,
        items_used=items_used,
        hero_deaths=hero_deaths,
        buff_changes=buff_changes,
        elite_kills=elite_kills,  # Phase 18F
        portal_activated=portal_context.get("activated", False),
        portal_user_id=portal_context.get("user_id"),
        channeling_started=portal_context.get("channeling_started"),
        channeling_tick=portal_context.get("channeling_tick"),
        portal_spawned=portal_context.get("portal_spawned"),
        portal_tick=portal_context.get("portal_tick"),
        portal_expired=portal_context.get("portal_expired", False),
        extractions=portal_context.get("extractions", []),
        floor_advance=stairs_context.get("floor_advance", False),
        new_floor_number=None,  # Set by match_manager after generation
    )
